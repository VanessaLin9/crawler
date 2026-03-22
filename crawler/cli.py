from __future__ import annotations

import argparse
import os

from crawler.core.models import CrawlConfig
from crawler.core.spider import crawl
from crawler.google_sheets import (
    DEFAULT_GOOGLE_SERVICE_ACCOUNT,
    DEFAULT_GOOGLE_SHEET_NAME,
    sync_job_records,
)
from crawler.records import flatten_job_records
from crawler.sites.registry import list_sites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyword-based website crawler")
    parser.add_argument("site", nargs="?")
    parser.add_argument("keyword", nargs="?")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", default="data/results.jsonl")
    parser.add_argument("--user-agent", default="search-crawler/0.1")
    parser.add_argument("--search-url-template")
    parser.add_argument("--list-sites", action="store_true")
    parser.add_argument("--sync-google-sheet", action="store_true")
    parser.add_argument("--google-sheet-id", default=os.getenv("GOOGLE_SHEET_ID"))
    parser.add_argument(
        "--google-sheet-name",
        default=os.getenv("GOOGLE_SHEET_NAME", DEFAULT_GOOGLE_SHEET_NAME),
    )
    parser.add_argument(
        "--google-service-account",
        default=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            DEFAULT_GOOGLE_SERVICE_ACCOUNT,
        ),
    )
    parser.add_argument("--reset-google-sheet", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.list_sites:
        for site in list_sites():
            print(site)
        return

    if not args.site or not args.keyword:
        raise SystemExit("site and keyword are required unless --list-sites is used")

    config = CrawlConfig(
        site=args.site,
        keyword=args.keyword,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
        output_path=args.output,
        user_agent=args.user_agent,
        search_url_template=args.search_url_template,
    )
    results = crawl(config)

    if args.sync_google_sheet:
        if not args.google_sheet_id:
            raise SystemExit(
                "--google-sheet-id or GOOGLE_SHEET_ID is required when "
                "--sync-google-sheet is used"
            )

        records = flatten_job_records(results)
        sync_result = sync_job_records(
            records=records,
            spreadsheet_id=args.google_sheet_id,
            sheet_name=args.google_sheet_name,
            service_account_path=args.google_service_account,
            reset_sheet=args.reset_google_sheet,
        )
        print(
            f"Synced {sync_result.appended_count} new rows to "
            f"{sync_result.sheet_name}; skipped {sync_result.skipped_count} duplicates."
        )


if __name__ == "__main__":
    main()
