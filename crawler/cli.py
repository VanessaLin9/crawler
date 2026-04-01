from __future__ import annotations

import argparse
import os

from crawler.core.models import CrawlConfig
from crawler.core.spider import crawl
from crawler.emailer import (
    DEFAULT_SMTP_PORT,
    SmtpConfig,
    send_new_jobs_email,
    send_new_jobs_json_email,
)
from crawler.env import load_dotenv
from crawler.google_sheets import (
    DEFAULT_GOOGLE_SERVICE_ACCOUNT,
    sync_job_records,
)
from crawler.records import flatten_job_records
from crawler.settings import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_MAX_PAGES,
    DEFAULT_MACHINE_EMAIL_ENABLED,
    DEFAULT_MACHINE_EMAIL_TO,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_PER_PAGE,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
)
from crawler.sites.registry import list_sites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyword-based website crawler")
    parser.add_argument("site", nargs="?")
    parser.add_argument("keyword", nargs="?")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--per-page", type=int, default=DEFAULT_PER_PAGE)
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--search-url-template")
    parser.add_argument("--list-sites", action="store_true")
    parser.add_argument("--sync-google-sheet", action="store_true")
    parser.add_argument("--google-sheet-id", default=os.getenv("GOOGLE_SHEET_ID"))
    parser.add_argument("--google-sheet-name")
    parser.add_argument(
        "--google-service-account",
        default=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            DEFAULT_GOOGLE_SERVICE_ACCOUNT,
        ),
    )
    parser.add_argument("--reset-google-sheet", action="store_true")
    parser.add_argument("--send-email-notification", action="store_true")
    parser.add_argument("--smtp-host", default=os.getenv("SMTP_HOST"))
    parser.add_argument(
        "--smtp-port",
        type=int,
        default=int(os.getenv("SMTP_PORT", DEFAULT_SMTP_PORT)),
    )
    parser.add_argument("--smtp-username", default=os.getenv("SMTP_USERNAME", ""))
    parser.add_argument("--smtp-password", default=os.getenv("SMTP_PASSWORD", ""))
    parser.add_argument("--smtp-from-email", default=os.getenv("SMTP_FROM_EMAIL"))
    parser.add_argument("--smtp-to-email", default=os.getenv("SMTP_TO_EMAIL"))
    parser.add_argument(
        "--send-machine-email-notification",
        action="store_true",
        default=_env_flag(
            "MACHINE_EMAIL_ENABLED",
            DEFAULT_MACHINE_EMAIL_ENABLED,
        ),
    )
    parser.add_argument(
        "--machine-email-to",
        default=os.getenv("MACHINE_EMAIL_TO", DEFAULT_MACHINE_EMAIL_TO),
    )
    parser.add_argument(
        "--smtp-no-tls",
        action="store_true",
        help="Disable STARTTLS for SMTP connections",
    )
    return parser


def main() -> None:
    load_dotenv()
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
        per_page=args.per_page,
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

        sheet_name = _resolve_google_sheet_name(
            site=args.site,
            explicit_name=args.google_sheet_name,
            env_name=os.getenv("GOOGLE_SHEET_NAME"),
        )
        records = flatten_job_records(results)
        sync_result = sync_job_records(
            records=records,
            spreadsheet_id=args.google_sheet_id,
            sheet_name=sheet_name,
            service_account_path=args.google_service_account,
            reset_sheet=args.reset_google_sheet,
        )
        print(
            f"Synced {sync_result.appended_count} new rows to "
            f"{sync_result.sheet_name}; skipped {sync_result.skipped_count} duplicates."
        )

        if args.send_email_notification:
            _validate_email_args(args)
            if sync_result.appended_records:
                base_smtp_config = SmtpConfig(
                    host=args.smtp_host,
                    port=args.smtp_port,
                    username=args.smtp_username,
                    password=args.smtp_password,
                    from_email=args.smtp_from_email,
                    to_email=args.smtp_to_email,
                    use_tls=not args.smtp_no_tls,
                )
                if args.send_machine_email_notification:
                    _validate_machine_email_args(args)
                    send_new_jobs_json_email(
                        smtp_config=SmtpConfig(
                            host=base_smtp_config.host,
                            port=base_smtp_config.port,
                            username=base_smtp_config.username,
                            password=base_smtp_config.password,
                            from_email=base_smtp_config.from_email,
                            to_email=args.machine_email_to,
                            use_tls=base_smtp_config.use_tls,
                        ),
                        site=args.site,
                        keyword=args.keyword,
                        records=sync_result.appended_records,
                        sheet_name=sync_result.sheet_name,
                        spreadsheet_id=sync_result.spreadsheet_id,
                    )
                    print(
                        "Sent machine-readable email notification for "
                        f"{len(sync_result.appended_records)} new jobs."
                    )
                send_new_jobs_email(
                    smtp_config=base_smtp_config,
                    site=args.site,
                    keyword=args.keyword,
                    records=sync_result.appended_records,
                    sheet_name=sync_result.sheet_name,
                    spreadsheet_id=sync_result.spreadsheet_id,
                )
                print(
                    f"Sent email notification for {len(sync_result.appended_records)} new jobs."
                )
            else:
                print("No new jobs found; skipped email notification.")
    elif args.send_email_notification:
        raise SystemExit("--send-email-notification requires --sync-google-sheet")


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _resolve_google_sheet_name(
    site: str,
    explicit_name: str | None,
    env_name: str | None,
) -> str:
    explicit_value = (explicit_name or "").strip()
    if explicit_value:
        return explicit_value

    env_value = (env_name or "").strip()
    # Preserve intentionally customized env values, but do not force the old
    # single-sheet default onto every provider.
    if env_value and env_value != "cake_jobs":
        return env_value

    return _default_google_sheet_name(site)


def _default_google_sheet_name(site: str) -> str:
    normalized_site = site.strip().casefold()
    return f"{normalized_site}_jobs"


def _validate_email_args(args: argparse.Namespace) -> None:
    required = {
        "--smtp-host / SMTP_HOST": args.smtp_host,
        "--smtp-from-email / SMTP_FROM_EMAIL": args.smtp_from_email,
        "--smtp-to-email / SMTP_TO_EMAIL": args.smtp_to_email,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(
            "Missing SMTP configuration: " + ", ".join(missing)
        )


def _validate_machine_email_args(args: argparse.Namespace) -> None:
    if args.machine_email_to:
        return
    raise SystemExit(
        "Missing machine email configuration: "
        "--machine-email-to / MACHINE_EMAIL_TO"
    )


if __name__ == "__main__":
    main()
