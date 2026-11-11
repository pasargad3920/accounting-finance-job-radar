# Accounting & Finance Job Radar — Italy

**An English-language, self-hosted dashboard for accounting and controlling vacancies in Lombardy and elsewhere in Italy.**

This is a **50-company pilot**, not a claim of monitoring 200 companies:
- **12 identified public ATS boards** are configured for automatic checks, subject to first-run verification.
- **38 additional target companies** appear in the career-directory section but **are not monitored automatically**.
- Supports public Ashby, Lever, Greenhouse, and SmartRecruiters Job Posting APIs. No LinkedIn scraping.
- Six LinkedIn searches (3 English and 3 Italian), linked to 1-hour, 3-hour, and 24-hour windows. 1h/3h URL parameters are unsupported by LinkedIn and may not work.
- Cloud scheduling via GitHub Actions (best-effort hourly, at minute 17 UTC).
- Static public dashboard on GitHub Pages.
- Optional Gmail SMTP notifications using repository Secrets (never hardcode credentials).
- No third-party paid subscriptions are needed for the pilot if free-tier allowances suffice.

**Important:** The code and offline tests have been executed locally. **Live ATS connectivity, GitHub Actions deployment, and email delivery must be verified in your own GitHub repository**. A configured source is **not** a confirmed working source until a scan succeeds.

## Quick setup

A detailed step-by-step Persian deployment guide is in [`DEPLOY_FA.md`](DEPLOY_FA.md).

1. Install [GitHub Desktop](https://desktop.github.com/) or use git on your machine.
2. Extract the ZIP. Publish the extracted project as a **public repository** named `accounting-finance-job-radar` (or your preferred name) with `main` as the default branch.
3. In the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Under **Settings → Secrets and variables → Actions**, create three repository secrets:
   - `SMTP_USER`: the Gmail account that **sends** the alerts.
   - `SMTP_APP_PASSWORD`: that account's Google App Password (requires 2-step verification; if your account offers it).
   - `ALERT_TO`: email address that **receives** the alerts.
5. **Actions → Accounting & Finance Job Radar → Run workflow**. Review logs for successful/failed feeds.
6. Visit **Settings → Pages** for the published dashboard URL. After the baseline scan, later newly detected matching jobs trigger email.

> The initial successful run creates a **silent baseline**: existing postings appear in the dashboard but are not emailed as "new". Future detections will generate alerts.

## Scan schedule and alerts

`17 * * * *` runs around minute 17 of every UTC hour; GitHub may delay or drop scheduled runs. Daily digest is emitted at **08:17 Italy local time** on the first successful scan during the 08:00 hour, *if email secrets are configured* and relevant jobs were first detected within 24 hours. Priority email sends on any scan with newly detected matching jobs with score >=69.

Alerts reflect **first detection by the scanner**, not necessarily the time the company published the job. Ashby's `publishedAt` and SmartRecruiters' `releasedDate` are used when present; Lever and Greenhouse timestamps are not presented as verified posting dates.

**Delivery is best-effort:** email sending may fail, and an alert lost after a successful state commit will not be replayed. Check dashboard for the authoritative active-job list. Secrets are never included in static files.

## Start locally (optional)

Python 3.12+, no third-party packages:

```bash
python -m unittest discover -s tests -v
python scripts/scanner.py
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000`. The scanner connects to employer public APIs. `scripts/send_email.py` sends alert batches only when all three environment variables are configured.

## Project structure

```text
accounting-finance-job-radar/
├── .github/workflows/radar.yml   # schedule, tests, state commit, email, Pages deploy
├── config/companies.json         # 50 pilot target companies; 12 ATS boards configured
├── docs/index.html               # English dashboard UI
├── docs/data.json                # public active-job dataset + source health
├── scripts/scanner.py            # ATS adapters, matching, geography, state handling
├── scripts/send_email.py         # SMTP notifications
├── tests/test_scanner.py         # local regression tests
├── state.json                    # public source & job detection metadata
├── DEPLOY_FA.md                  # detailed Persian instructions
└── README.md
```

## Expand the source list

In `config/companies.json`, an auto-monitored entry needs fields like:

```json
{
  "id": "example-company",
  "name": "Example Company",
  "industry": "Technology",
  "mode": "api",
  "provider": "ashby",
  "token": "actual-public-ashby-board-slug",
  "careers_url": "https://jobs.ashbyhq.com/actual-public-ashby-board-slug"
}
```

**Only use a token verified on that specific employer's actual public career board.** Do not invent URLs or mark a company monitored just because it uses an ATS brand. For Workday and proprietary corporate sites, the currently included monitor does **not** claim automatic coverage; add a documented permitted integration first.

## Geography and search limitations

The scanner matches country/city strings from job posts against known Italian regions/cities. Only explicitly identified Italian locations are included. Italy-only remote jobs with no city appear under **Italy — location to verify**. Both Lombardy and another Italian area can be associated with a multi-location role. The keyword and location lists are editable in `scripts/scanner.py`.

The **LinkedIn** `Rest of Italy` button opens an Italy-wide search and therefore cannot guarantee exclusion of Lombardy. This limitation is disclosed in the interface. On the *corporate feed*, the `Rest of Italy` filter uses parsed posting locations.

The provider matching prioritizes job **titles** rather than indiscriminately searching all job descriptions, to reduce irrelevant results. Titles can still be missed: edit the six-group matching rules as needed.

## Privacy and risk

A one-repository public-site design minimizes setup: source code, source-health data, and the public job cache are visible to everyone. **Never save email addresses, passwords, resumes, or other personal data in the repository.** Keep credentials in GitHub Actions Secrets. GitHub Pages sites are publicly accessible. Employment URLs are external sites; confirm job legitimacy before submitting sensitive information.

## Documentation sources

- [Ashby public posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board)
- [Lever public postings API](https://github.com/lever/postings-api/blob/master/README.md)
- [SmartRecruiters public posting endpoints](https://developers.smartrecruiters.com/docs/endpoints)
- [GitHub Pages custom workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [Google App Passwords](https://support.google.com/mail/answer/185833?hl=en)
