#!/usr/bin/env python3
"""Send detected matching jobs using Gmail SMTP; all credentials from GitHub Secrets.
The scanner is safe to run without credentials; this sender simply skips email.
"""
import json
import os
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from html import escape

ROOT = Path(__file__).resolve().parents[1]


def render_items(items):
    rows = []
    for j in items[:30]:
        url = j['url']
        if not url.startswith('https://'):
            continue
        rows.append('<div style="padding:14px 0;border-bottom:1px solid #e6e9ee">'
                    f'<b>{escape(j["title"])}</b> · {escape(j["company"])}<br>'
                    f'<small>{escape(j["location"])} · {escape(j["group"])} · match score: {j["score"]}/100</small><br>'
                    f'<a href="{escape(url,quote=True)}">Review role / Apply</a></div>')
    return ''.join(rows)


def send_email(subject, items, sender, recipient, password):
    if not items:
        return
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content('\n\n'.join(f'{j["title"]} — {j["company"]} — {j["location"]}\n{j["url"]}' for j in items[:30]))
    msg.add_alternative('<!doctype html><html><body style="font-family:Arial,sans-serif;color:#1d293b">'
                        '<h2>Accounting &amp; Finance Job Radar</h2>'
                        '<p>New jobs first detected by your scanner. Not necessarily posted in the last hour.</p>'
                        + render_items(items) + '<p><small>You control this monitor in GitHub Actions.</small></p>'
                        '</body></html>', subtype='html')
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30, context=ssl.create_default_context()) as server:
        server.login(sender, password)
        server.send_message(msg)


def main():
    sender = os.getenv('SMTP_USER', '').strip()
    recipient = os.getenv('ALERT_TO', '').strip()
    pw = os.getenv('SMTP_APP_PASSWORD', '').replace(' ', '')
    if not all([sender, recipient, pw]):
        print('Email not configured; skipping notifications.')
        return
    if not all('@' in a and parseaddr(a)[1] == a for a in (sender, recipient)):
        raise ValueError('Invalid SMTP_USER / ALERT_TO email address')
    file = ROOT / '_outbox.json'
    if not file.exists():
        print('No new scan output found.')
        return
    batch = json.loads(file.read_text(encoding='utf-8'))
    priority = batch.get('priority') or []
    digest = batch.get('digest') or []
    if priority:
        send_email(f'Job Radar: {len(priority)} newly detected relevant role(s)', priority, sender, recipient, pw)
        print(f'Priority email sent with {len(priority)} roles.')
    else:
        print('No new priority matches to email.')
    if batch.get('send_daily_digest') and digest:
        send_email(f'Job Radar daily digest: {len(digest)} roles detected in 24h', digest, sender, recipient, pw)
        print(f'Daily digest sent with {len(digest)} roles.')


if __name__ == '__main__':
    main()
