# Search Crawler

中文版本: [README.md](/Users/vanessa/develop/search/README.md)

A Python job-search crawler focused on Taiwanese job platforms. The project currently supports three providers: `Cake`, `104`, and `Yourator`.

It can:

- search jobs by keyword
- crawl multiple pages
- extract structured job fields
- sync results to Google Sheets
- deduplicate by `job_url`
- send a human-readable summary email
- optionally send a machine-readable JSON email

## Quick Start

### 1. Install

```bash
git clone https://github.com/VanessaLin9/crawler.git
cd crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Create local config

```bash
cp .env.sample .env
```

At minimum, fill in:

- `GOOGLE_SHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_TO_EMAIL`

If you also want a JSON notification email for another system, add:

- `MACHINE_EMAIL_ENABLED=true`
- `MACHINE_EMAIL_TO=machine-consumer@example.com`

If you do not need email yet, you can leave `SMTP_*` empty and skip the email flags.

### 3. Prepare Google Sheets

You need to:

1. Create a Google Sheet.
2. Create a Google service account JSON credential.
3. Share the sheet with the service account email as `Editor`.
4. Store the JSON file locally, for example:
   `secrets/google-service-account.json`

Example `.env` values:

```env
GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_SERVICE_ACCOUNT_JSON=secrets/google-service-account.json
```

If you do not specify a worksheet name, the crawler routes each provider to its own worksheet:

- `cake` -> `cake_jobs`
- `104` -> `104_jobs`
- `yourator` -> `yourator_jobs`

## Common Commands

Assume you already ran:

```bash
cd /Users/vanessa/develop/search
source .venv/bin/activate
```

### List available sites

```bash
crawl-site --list-sites
```

### Crawl only, without Sheets sync or email

```bash
crawl-site cake "後端"
crawl-site 104 "後端"
crawl-site yourator "後端"
```

### Crawl and sync to Google Sheets

```bash
crawl-site cake "後端" --sync-google-sheet
crawl-site 104 "後端" --sync-google-sheet
crawl-site yourator "後端" --sync-google-sheet
```

### Crawl, sync, and send summary email

```bash
crawl-site cake "後端" --sync-google-sheet --send-email-notification
crawl-site 104 "後端" --sync-google-sheet --send-email-notification
crawl-site yourator "後端" --sync-google-sheet --send-email-notification
```

### Run all supported providers

```bash
crawl-site all "後端" --sync-google-sheet --send-email-notification --send-machine-email-notification
```

This runs:

- `cake`
- `104`
- `yourator`

And writes to:

- `cake_jobs`
- `104_jobs`
- `yourator_jobs`

## Default Settings

Current defaults are defined in [crawler/settings.py](/Users/vanessa/develop/search/crawler/settings.py):

- `max_pages = 9`
- `per_page = 20`
- `delay_seconds = 0.5`
- `timeout_seconds = 10.0`

You can override them, for example:

```bash
crawl-site cake "後端" --max-pages 5 --per-page 30
```

## Email Behavior

When `--send-email-notification` is enabled:

- the crawler syncs to Google Sheets first
- only newly added jobs are included
- no email is sent if there are no new jobs

There are two notification formats:

- human-readable summary email
- machine-readable JSON email

The JSON email is optional and disabled by default.

## GitHub Actions

The repo includes a workflow for running the crawler from GitHub Actions:

- [.github/workflows/crawl-jobs.yml](/Users/vanessa/develop/search/.github/workflows/crawl-jobs.yml)

It currently uses `workflow_dispatch` first, so you can validate connectivity and output quality before relying on a schedule.

## Supported Sites

### 104

`104` uses the search page plus the underlying API, with an anonymous session bootstrap.

Notes:

- structured fields are more limited than Cake in some cases
- salary handling stays conservative and avoids guessing units when unclear

### Cake

`cake` crawls the IT jobs search flow and can extract richer structured fields from its data payloads.

### Yourator

`yourator` currently uses:

- list source: `https://www.yourator.co/api/v4/jobs?page={page}`
- detail source: `https://www.yourator.co/companies/{company}/jobs/{job_id}`

Notes:

- V1 uses a conservative local keyword match strategy on top of the public jobs list
- `content_updated_at` is normalized to `YYYY-MM-DD`
- `面議（經常性薪資達X萬元）` keeps `salary_type=negotiable` while normalizing the salary floor into `salary_min`

### Generic

`generic` is a fast template for experimenting with new sites:

```bash
crawl-site generic "openai" \
  --search-url-template "https://example.com/search?q={keyword}" \
  --max-pages 10 \
  --output data/example.jsonl
```

## Output

Raw crawler output is written as `.jsonl`, one line per crawled search page.

Main page-level fields include:

- `url`
- `status_code`
- `title`
- `meta_description`
- `matches`
- `links`

When syncing to Google Sheets, the data is flattened to one row per job.

## Project Structure

- `crawler/core/`: shared crawl flow and output logic
- `crawler/sites/`: site adapters
- `crawler/sites/template.py`: starter template for a new site
- `crawler/google_sheets.py`: Google Sheets sync
- `crawler/emailer.py`: email notifications
- `crawler/settings.py`: default settings

## Extending the Project

To add a new site:

1. Start from [template.py](/Users/vanessa/develop/search/crawler/sites/template.py).
2. Implement `build_start_urls()`.
3. Implement `parse_page()`.
4. Adjust `should_visit()` if needed.
5. Register the site in [registry.py](/Users/vanessa/develop/search/crawler/sites/registry.py).

## Notes

- `.env` is not committed
- `secrets/` is not committed
- `.env.sample` is only an example
- each user should use their own Google Sheet and service account
