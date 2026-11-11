#!/usr/bin/env python3
"""Public ATS job monitor. No LinkedIn scraping; no credentials required to read feeds.

Persisted state is committed by GitHub Actions so new postings are detected across runs.
First successful baseline does not email pre-existing jobs.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config' / 'companies.json'
STATE = ROOT / 'state.json'
SITE_DATA = ROOT / 'docs' / 'data.json'
OUTBOX = ROOT / '_outbox.json'
USER_AGENT = 'FinanceJobRadar/1.0 (public ATS job postings; hourly; respectful requests)'

GROUPS = [
 ('EN · General Accounting', ['accountant', 'accounting specialist', 'accounting clerk', 'finance and accounting', 'finance & accounting', 'accounting officer', 'accounting analyst', 'finance specialist', 'finance assistant', 'finance administrator', 'finance operations specialist']),
 ('EN · GL / AP / AR', ['general ledger', 'gl accountant', 'accounts payable', 'accounts receivable', 'ap accountant', 'ar accountant', 'billing specialist', 'revenue accountant', 'statutory accounting', 'financial reporting', 'consolidation analyst']),
 ('EN · Controlling & Cost', ['controller', 'controlling', 'cost control', 'cost accountant', 'cost analyst', 'management accountant', 'fp&a', 'financial planning', 'finance business partner', 'finance analyst', 'commercial finance', 'budget analyst', 'project controller', 'business control']),
 ('IT · Contabilità Generale', ['contabile', 'contabilità generale', 'contabilita generale', 'addetto contabilità', 'addetta contabilità', 'specialista contabile', 'impiegato amministrativo contabile', 'responsabile contabilità']),
 ('IT · Ciclo Attivo / Passivo', ['ciclo attivo', 'ciclo passivo', 'contabilità fornitori', 'contabilita fornitori', 'contabilità clienti', 'contabilita clienti', 'bilancio', 'fatturazione', 'amministrazione e finanza']),
 ('IT · Controllo di Gestione', ['controllo di gestione', 'controllo costi', 'contabilità analitica', 'contabilita analitica', 'contabilità industriale', 'contabilita industriale', 'analista finanziario', 'pianificazione e controllo']),
]
SKILLS = ['sap', 'month-end', 'month end', 'closing', 'reconciliation', 'intercompany',
          'financial reporting', 'budgeting', 'forecasting', 'cost accounting', 'ifrs',
          'financial statements', 'accounts payable', 'accounts receivable', 'excel',
          'bilancio', 'riconciliaz', 'controllo di gestione', 'contabilità generale']
# No implicit "Italy" classification for unlocated global/remote jobs.
LOMBARDY_PLACES = [
 'lombardia', 'lombardy', 'milano', 'milan', 'bergamo', 'brescia', 'monza', 'brianza',
 'como', 'lecco', 'varese', 'pavia', 'cremona', 'mantova', 'mantua', 'lodi', 'sondrio',
 'biassono', 'vimercate', 'assago', 'segrate', 'sesto san giovanni', 'rho',
 'cologno monzese', 'legnano', 'gallarate', 'busto arsizio', 'cinisello balsamo',
 'treviglio', 'seriate', 'desio', 'carugate', 'bresso', 'bormio'
]
REST_PLACES = [
 'roma', 'rome', 'lazio', 'torino', 'turin', 'piemonte', 'piedmont', 'novara',
 'bologna', 'parma', 'modena', 'reggio emilia', 'emilia romagna', 'emilia-romagna',
 'venezia', 'venice', 'veneto', 'verona', 'padova', 'padua', 'treviso', 'vicenza',
 'firenze', 'florence', 'toscana', 'tuscany', 'pisa', 'lucca', 'livorno',
 'napoli', 'naples', 'campania', 'bari', 'puglia', 'apulia', 'lecce',
 'genova', 'genoa', 'liguria', 'trieste', 'friuli', 'udine', 'trento', 'trentino',
 'bolzano', 'bozen', 'alto adige', 'south tyrol', 'ancona', 'marche',
 'perugia', 'umbria', 'palermo', 'sicilia', 'sicily', 'catania', 'cagliari',
 'sardegna', 'sardinia', 'abruzzo', 'pescara', 'molise', 'potenza', 'basilicata',
 'calabria', 'catanzaro', 'reggio calabria', "valle d'aosta", 'aosta'
]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def parse_time(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        value = value / 1000 if value > 10**11 else value
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        except ValueError:
            return None
    return None


def text_only(s):
    s = re.sub(r'<[^>]*>', ' ', str(s or ''))
    return ' '.join(html.unescape(s).split())


def fetch_json(url, timeout=14):
    parsed = urlparse(url)
    allowed = {'api.ashbyhq.com', 'api.lever.co', 'api.eu.lever.co',
               'boards-api.greenhouse.io', 'api.smartrecruiters.com'}
    if parsed.scheme != 'https' or parsed.hostname not in allowed:
        raise ValueError('Unapproved API hostname')
    req = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as res:
            if int(res.headers.get('Content-Length', '0') or '0') > 12_000_000:
                raise ValueError('Response too large')
            raw = res.read(12_000_001)
            if len(raw) > 12_000_000:
                raise ValueError('Response too large')
            return json.loads(raw)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as err:
        raise RuntimeError(f'API unavailable: {type(err).__name__}') from err


def source_jobs(company, fetcher=fetch_json):
    p, token = company['provider'], company['token']
    token = quote(token, safe='-')
    if p == 'ashby':
        data = fetcher(f'https://api.ashbyhq.com/posting-api/job-board/{token}')
        if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
            raise ValueError('Unexpected Ashby response')
        for j in data['jobs']:
            if j.get('isListed') is False:
                continue
            address = (j.get('address') or {}).get('postalAddress') or {}
            others = j.get('secondaryLocations') or []
            locs = [j.get('location'), address.get('addressLocality'), address.get('addressRegion')]
            for v in others:
                locs.append(v.get('location'))
            url = j.get('jobUrl') or j.get('applyUrl')
            if url:
                yield {'id': str(url), 'title': j.get('title'), 'location': ' / '.join(dict.fromkeys(x for x in locs if x)),
                       'country': address.get('addressCountry'),
                       'url': j.get('applyUrl') or url, 'published_at': parse_time(j.get('publishedAt')),
                       'description': j.get('descriptionPlain') or text_only(j.get('descriptionHtml')),
                       'department': j.get('department') or '', 'workplace': j.get('workplaceType') or ''}
    elif p == 'lever':
        # Lever EU and global use different hosts; if company changes host, adjust provider/instance.
        data = fetcher(f'https://api.lever.co/v0/postings/{token}?mode=json&limit=1000')
        if not isinstance(data, list):
            raise ValueError('Unexpected Lever response')
        for j in data:
            cats = j.get('categories') or {}
            url = j.get('hostedUrl') or j.get('applyUrl')
            if url:
                yield {'id': str(j.get('id') or url), 'title': j.get('text'), 'location': cats.get('location') or '',
                       'country': None, 'url': url, 'published_at': None,
                       'description': j.get('descriptionPlain') or text_only(j.get('description')),
                       'department': cats.get('team') or '', 'workplace': j.get('workplaceType') or ''}
    elif p == 'greenhouse':
        data = fetcher(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true')
        if not isinstance(data, dict) or not isinstance(data.get('jobs'), list):
            raise ValueError('Unexpected Greenhouse response')
        for j in data['jobs']:
            url = j.get('absolute_url')
            if url:
                yield {'id': str(j.get('id') or url), 'title': j.get('title'),
                       'location': (j.get('location') or {}).get('name') or '',
                       'country': None, 'url': url, 'published_at': None,  # updated_at != published_at
                       'description': text_only(j.get('content')),
                       'department': ', '.join(d.get('name', '') for d in j.get('departments', []) if isinstance(d, dict)),
                       'workplace': ''}
    elif p == 'smartrecruiters':
        offset, page_size = 0, 100
        for _ in range(30):
            data = fetcher(f'https://api.smartrecruiters.com/v1/companies/{token}/postings?limit={page_size}&offset={offset}&country=it')
            if not isinstance(data, dict) or not isinstance(data.get('content'), list):
                raise ValueError('Unexpected SmartRecruiters response')
            items = data['content']
            for j in items:
                place = j.get('location') or {}
                ref = j.get('ref') or ''
                url = f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}" if j.get('id') else ref
                if url:
                    yield {'id': str(j.get('id') or url), 'title': j.get('name'),
                           'location': ' / '.join(x for x in [place.get('city'), place.get('region'), place.get('country')] if x),
                           'country': place.get('country'), 'url': url,
                           'published_at': parse_time(j.get('releasedDate')),
                           'description': '', 'department': (j.get('department') or {}).get('label') or '', 'workplace': ''}
            offset += len(items)
            if len(items) < page_size or offset >= int(data.get('totalFound', 0)):
                break
    else:
        raise ValueError(f'Unsupported provider {p}')


def is_phrase(haystack, needle):
    # Word boundary avoids "accountant" matching "accountantsomething".
    return bool(re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', haystack, re.I))


def match_title(title, description='', department=''):
    title = ' '.join((title or '').lower().split())
    if not title or is_phrase(title, 'account manager') or is_phrase(title, 'account executive'):
        return None
    matches = [(group, sum(is_phrase(title, term) for term in terms)) for group, terms in GROUPS]
    matches = [x for x in matches if x[1]]
    if not matches:
        return None
    group = max(matches, key=lambda x: x[1])[0]
    blob = (description or '').lower()[:12000]
    skill_hits = [s for s in SKILLS if is_phrase(blob, s)]
    score = min(100, 69 + min(len(skill_hits), 5) * 5)
    if re.search(r'\b(internship|intern|stage|stagista|tirocinio)\b', title):
        score -= 35
    if re.search(r'\b(director|vp|head of|chief|cfo)\b', title):
        score -= 25
    if re.search(r'\b(manager|responsabile)\b', title):
        score -= 8
    if 'l.68/99' in title or 'categorie protette' in title:
        score -= 12
    return {'group': group, 'score': max(0, score), 'skill_hits': skill_hits[:5]}


def geography(location, country=None):
    """Return an explicit array; unknown goes to 'verify', never silently assigned to Italy."""
    s = ' '.join(str(location or '').lower().split())
    explicit_country = str(country or '').strip().lower()
    if explicit_country and explicit_country not in ('it', 'ita', 'italy', 'italia'):
        # Multiple-country ATS jobs may have secondary Italian cities despite a primary foreign office.
        if not any(is_phrase(s, city) for city in LOMBARDY_PLACES + REST_PLACES):
            return []
    lomb = any(is_phrase(s, x) for x in LOMBARDY_PLACES)
    rest = any(is_phrase(s, x) for x in REST_PLACES)
    if lomb or rest:
        return (["lombardy"] if lomb else []) + (["rest"] if rest else [])
    if explicit_country in ('it', 'ita', 'italy', 'italia') or is_phrase(s, 'italy') or is_phrase(s, 'italia') or is_phrase(s, 'italian remote'):
        return ['verify']
    return []


def job_from_raw(company, raw):
    title = text_only(raw.get('title'))
    mt = match_title(title, raw.get('description'), raw.get('department'))
    if not mt:
        return None
    places = geography(raw.get('location'), raw.get('country'))
    if not places:
        return None
    url = raw.get('url') or ''
    if urlparse(url).scheme != 'https':
        return None
    if re.search(r'relocation\s+to\s+(luxembourg|spain|germany|france|portugal|netherlands)', title.lower()):
        return None
    return {'id': f"{company['id']}:{hashlib.sha256(str(raw.get('id') or url).encode()).hexdigest()[:22]}",
            'company_id': company['id'], 'company': company['name'], 'industry': company['industry'],
            'title': title, 'location': raw.get('location') or 'Location not provided',
            'geographies': places, 'url': url, 'source': company['provider'],
            'group': mt['group'], 'score': mt['score'], 'skill_hits': mt['skill_hits'],
            'published_at': raw.get('published_at'), 'workplace': raw.get('workplace') or ''}


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temp.replace(path)


def load_json(path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding='utf-8'))


def monitor(fetcher=fetch_json, timestamp=None, email_enabled=False):
    timestamp = timestamp or now_iso()
    config = load_json(CONFIG, {})
    company_list = config['companies']
    state = load_json(STATE, {'initialized': False, 'seen': {}, 'sources': {}, 'digest_day': None})
    state.setdefault('seen', {})
    state.setdefault('sources', {})
    successful_sources = set()
    newly_found = []
    processed = 0
    for company in company_list:
        if company['mode'] != 'api':
            continue
        cid = company['id']
        try:
            rows = list(source_jobs(company, fetcher=fetcher))
            processed += len(rows)
            matched = {}
            for r in rows:
                item = job_from_raw(company, r)
                if item:
                    matched[item['id']] = item
            successful_sources.add(cid)
            previous_status = state['sources'].get(cid) or {}
            state['sources'][cid] = {'status': 'ok', 'last_checked': timestamp, 'last_success': timestamp,
                                     'matched_jobs': len(matched), 'error': None}
            for jid, job in matched.items():
                old = state['seen'].get(jid)
                job['first_seen_at'] = old.get('first_seen_at', timestamp) if old else timestamp
                job['last_seen_at'] = timestamp
                job['active'] = True
                job['stale'] = False
                state['seen'][jid] = job
                if not old and state.get('initialized'):
                    newly_found.append(job)
            # Remove only after a *successful* fetch. Failures preserve cache, marked stale.
            for jid, job in state['seen'].items():
                if job.get('company_id') == cid and jid not in matched:
                    job['active'] = False
            print(f"{company['name']}: {len(rows)} postings, {len(matched)} Italy finance matches")
        except Exception as err:
            last = state['sources'].get(cid) or {}
            state['sources'][cid] = {'status': 'error', 'last_checked': timestamp,
                                     'last_success': last.get('last_success'),
                                     'matched_jobs': last.get('matched_jobs', 0),
                                     'error': str(err)[:130]}
            for j in state['seen'].values():
                if j.get('company_id') == cid and j.get('active'):
                    j['stale'] = True
            print(f"WARNING {company['name']}: {err}", file=sys.stderr)
        time.sleep(0.13)

    # Do not mark a failed initial scan as baseline: first successful scan should still be quiet.
    if successful_sources:
        state['initialized'] = True
    state['last_scan'] = timestamp
    state['schema_version'] = 1
    active_jobs = [dict(v) for v in state['seen'].values() if v.get('active')]
    active_jobs.sort(key=lambda j: (j.get('score', 0), j.get('first_seen_at', '')), reverse=True)
    # Keep recently closed entries for dedupe purposes; avoid limitless growth.
    cutoff = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) - timedelta(days=90)
    state['seen'] = {jid: v for jid, v in state['seen'].items()
                     if v.get('active') or (parse_time(v.get('last_seen_at')) and
                      datetime.fromisoformat(parse_time(v['last_seen_at']).replace('Z', '+00:00')) >= cutoff)}
    sites = []
    for company in company_list:
        record = {'id':company['id'],'name':company['name'],'industry':company['industry'],
                  'mode':company['mode'],'careers_url':company.get('careers_url'),
                  'provider':company.get('provider')}
        record.update(state['sources'].get(company['id']) or {'status':'directory_only', 'last_checked':None,
                                                               'last_success':None, 'matched_jobs':None,'error':None})
        sites.append(record)
    doc = {'schema_version':1,'updated_at':timestamp, 'baseline_ready':bool(successful_sources),
           'jobs':active_jobs, 'companies':sites,
           'stats':{'tracked_companies':len(company_list), 'configured_feeds':sum(c['mode']=='api' for c in company_list),
                    'healthy_feeds':len(successful_sources), 'directory_only':sum(c['mode']=='directory' for c in company_list),
                    'active_matches':len(active_jobs), 'new_this_scan':len(newly_found),
                    'stale_matches':sum(j.get('stale',False) for j in active_jobs)}}
    # Avoid notifying about pre-existing positions on initial scan; only newly detected later.
    priority = [j for j in newly_found if j['score'] >= 69 and not j.get('stale')]
    payload = {'generated_at':timestamp, 'priority':priority, 'digest':[], 'send_daily_digest':False}
    local = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Rome'))
    if email_enabled and local.hour == 8 and state.get('digest_day') != local.date().isoformat():
        day_ago = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) - timedelta(hours=24)
        payload['digest'] = [j for j in active_jobs if not j.get('stale') and
                             datetime.fromisoformat(j['first_seen_at'].replace('Z', '+00:00')) >= day_ago]
        payload['send_daily_digest'] = bool(payload['digest'])
        state['digest_day'] = local.date().isoformat()
    atomic_json(STATE, state)
    atomic_json(SITE_DATA, doc)
    atomic_json(OUTBOX, payload)
    print(f"Done: {len(successful_sources)} sources OK; {len(active_jobs)} active matches; {len(newly_found)} newly detected; {len(priority)} priority alerts")
    # Exit zero on partial failures to keep healthy sources available; source status is displayed.
    return doc, payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scan public employer job feeds')
    parser.add_argument('--no-network', action='store_true', help='Produce empty initial dashboard without HTTP calls')
    args = parser.parse_args()
    if args.no_network:
        # Only for development preview, not for cloud workflow.
        def offline_fetch(_url):
            raise RuntimeError('Offline preview')
        monitor(fetcher=offline_fetch, email_enabled=False)
    else:
        monitor(email_enabled=bool(os.getenv('SMTP_USER') and os.getenv('SMTP_APP_PASSWORD') and os.getenv('ALERT_TO')))
