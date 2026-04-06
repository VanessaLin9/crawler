from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

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

ALL_SITES_TOKEN = "all"
MULTI_SITE_ORDER = ["cake", "104"]


@dataclass(slots=True)
class SiteRunSummary:
    site: str
    output_path: str
    crawled_pages: int
    records_found: int
    crawl_issues: list[str] = field(default_factory=list)
    appended_count: int = 0
    skipped_count: int = 0
    sheet_name: str = ""
    sent_email: bool = False
    sent_machine_email: bool = False
    error: str = ""


class SiteRunFailed(RuntimeError):
    def __init__(self, summary: SiteRunSummary, message: str) -> None:
        super().__init__(message)
        summary.error = message
        self.summary = summary


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
        for site in _list_cli_sites():
            print(site)
        return

    if not args.site or not args.keyword:
        raise SystemExit("site and keyword are required unless --list-sites is used")

    sites = _resolve_requested_sites(args.site)
    _validate_runtime_args(args, multi_site=len(sites) > 1)

    summaries = _execute_requested_sites(args, sites)
    multi_site = len(sites) > 1
    for summary in summaries:
        _print_site_run_summary(
            summary,
            sync_google_sheet=args.sync_google_sheet,
            send_email_notification=args.send_email_notification,
            multi_site=multi_site,
        )

    if multi_site:
        _print_multi_site_summary(summaries, sync_google_sheet=args.sync_google_sheet)
        _raise_for_failed_sites(summaries)


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


def _extract_crawl_issues(results: list[dict]) -> list[str]:
    issues: list[str] = []
    for result in results:
        error = str(result.get("error", "")).strip()
        if not error:
            continue
        url = str(result.get("url", "")).strip()
        issues.append(f"{error} (page: {url})" if url else error)
    return issues


def _list_cli_sites() -> list[str]:
    return [ALL_SITES_TOKEN, *list_sites()]


def _resolve_requested_sites(site: str) -> list[str]:
    normalized_site = site.strip().casefold()
    if normalized_site == ALL_SITES_TOKEN:
        return list(MULTI_SITE_ORDER)
    return [site]


def _validate_runtime_args(args: argparse.Namespace, multi_site: bool) -> None:
    if args.send_email_notification and not args.sync_google_sheet:
        raise SystemExit("--send-email-notification requires --sync-google-sheet")

    if args.sync_google_sheet and not args.google_sheet_id:
        raise SystemExit(
            "--google-sheet-id or GOOGLE_SHEET_ID is required when "
            "--sync-google-sheet is used"
        )

    if args.send_email_notification:
        _validate_email_args(args)
        if args.send_machine_email_notification:
            _validate_machine_email_args(args)

    if args.sync_google_sheet and multi_site and _has_custom_google_sheet_target(
        explicit_name=args.google_sheet_name,
        env_name=os.getenv("GOOGLE_SHEET_NAME"),
    ):
        raise SystemExit(
            f"{ALL_SITES_TOKEN} mode does not support a shared worksheet name. "
            "Remove --google-sheet-name and GOOGLE_SHEET_NAME to use per-site defaults."
        )


def _has_custom_google_sheet_target(
    explicit_name: str | None,
    env_name: str | None,
) -> bool:
    explicit_value = (explicit_name or "").strip()
    if explicit_value:
        return True

    env_value = (env_name or "").strip()
    return bool(env_value and env_value != "cake_jobs")


def _resolve_output_path(base_output: str, site: str, multi_site: bool) -> str:
    if not multi_site:
        return base_output

    path = Path(base_output)
    suffix = "".join(path.suffixes)
    stem = path.name[: -len(suffix)] if suffix else path.name
    file_name = f"{stem}-{site}{suffix}"
    return str(path.with_name(file_name))


def _build_crawl_config(
    args: argparse.Namespace,
    site: str,
    output_path: str,
) -> CrawlConfig:
    return CrawlConfig(
        site=site,
        keyword=args.keyword,
        max_pages=args.max_pages,
        per_page=args.per_page,
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
        output_path=output_path,
        user_agent=args.user_agent,
        search_url_template=args.search_url_template,
    )


def _build_smtp_config(args: argparse.Namespace) -> SmtpConfig:
    return SmtpConfig(
        host=args.smtp_host,
        port=args.smtp_port,
        username=args.smtp_username,
        password=args.smtp_password,
        from_email=args.smtp_from_email,
        to_email=args.smtp_to_email,
        use_tls=not args.smtp_no_tls,
    )


def _run_site(args: argparse.Namespace, site: str, multi_site: bool) -> SiteRunSummary:
    output_path = _resolve_output_path(args.output, site, multi_site)
    summary = SiteRunSummary(
        site=site,
        output_path=output_path,
        crawled_pages=0,
        records_found=0,
    )

    try:
        config = _build_crawl_config(args, site, output_path)
        results = crawl(config)
        records = flatten_job_records(results)
        crawl_issues = _extract_crawl_issues(results)
        summary.crawled_pages = len(results)
        summary.records_found = len(records)
        summary.crawl_issues = crawl_issues

        if not args.sync_google_sheet:
            return summary

        sheet_name = _resolve_google_sheet_name(
            site=site,
            explicit_name=args.google_sheet_name,
            env_name=os.getenv("GOOGLE_SHEET_NAME"),
        )
        sync_result = sync_job_records(
            records=records,
            spreadsheet_id=args.google_sheet_id,
            sheet_name=sheet_name,
            service_account_path=args.google_service_account,
            reset_sheet=args.reset_google_sheet,
        )
        summary.appended_count = sync_result.appended_count
        summary.skipped_count = sync_result.skipped_count
        summary.sheet_name = sync_result.sheet_name

        if not args.send_email_notification:
            return summary

        if sync_result.appended_records or crawl_issues:
            base_smtp_config = _build_smtp_config(args)
            if args.send_machine_email_notification and sync_result.appended_records:
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
                    site=site,
                    keyword=args.keyword,
                    records=sync_result.appended_records,
                    sheet_name=sync_result.sheet_name,
                    spreadsheet_id=sync_result.spreadsheet_id,
                )
                summary.sent_machine_email = True

            send_new_jobs_email(
                smtp_config=base_smtp_config,
                site=site,
                keyword=args.keyword,
                records=sync_result.appended_records,
                sheet_name=sync_result.sheet_name,
                spreadsheet_id=sync_result.spreadsheet_id,
                crawl_issues=crawl_issues,
            )
            summary.sent_email = True

        return summary
    except Exception as exc:
        raise SiteRunFailed(summary, str(exc)) from exc


def _execute_requested_sites(
    args: argparse.Namespace,
    sites: list[str],
) -> list[SiteRunSummary]:
    multi_site = len(sites) > 1
    summaries: list[SiteRunSummary] = []

    for site in sites:
        try:
            summaries.append(_run_site(args, site, multi_site=multi_site))
        except SiteRunFailed as exc:
            if not multi_site:
                raise
            summaries.append(exc.summary)
        except Exception as exc:
            if not multi_site:
                raise
            summaries.append(
                SiteRunSummary(
                    site=site,
                    output_path=_resolve_output_path(args.output, site, multi_site=True),
                    crawled_pages=0,
                    records_found=0,
                    error=str(exc),
                )
            )

    return summaries


def _print_site_run_summary(
    summary: SiteRunSummary,
    *,
    sync_google_sheet: bool,
    send_email_notification: bool,
    multi_site: bool,
) -> None:
    prefix = f"{summary.site}: " if multi_site else ""

    if summary.error:
        print(f"{prefix}failed: {summary.error}")
        return

    if sync_google_sheet:
        print(
            f"{prefix}synced {summary.appended_count} new rows to "
            f"{summary.sheet_name}; skipped {summary.skipped_count} duplicates."
        )
        if send_email_notification:
            if summary.sent_machine_email:
                print(
                    f"{prefix}sent machine-readable email notification for "
                    f"{summary.appended_count} new jobs."
                )
            if summary.sent_email:
                if summary.crawl_issues:
                    print(
                        f"{prefix}sent email notification with crawl issues for "
                        f"{summary.appended_count} new jobs."
                    )
                else:
                    print(
                        f"{prefix}sent email notification for "
                        f"{summary.appended_count} new jobs."
                    )
            else:
                print(f"{prefix}no new jobs found; skipped email notification.")
        return

    print(
        f"{prefix}crawled {summary.crawled_pages} pages and found "
        f"{summary.records_found} jobs."
    )


def _print_multi_site_summary(
    summaries: list[SiteRunSummary],
    *,
    sync_google_sheet: bool,
) -> None:
    if sync_google_sheet:
        print(f"Total new jobs: {sum(summary.appended_count for summary in summaries)}")
    else:
        print(f"Total jobs found: {sum(summary.records_found for summary in summaries)}")

    print(f"Providers run: {', '.join(summary.site for summary in summaries)}")

    failed_sites = [summary.site for summary in summaries if summary.error]
    if failed_sites:
        print(f"Providers failed: {', '.join(failed_sites)}")


def _raise_for_failed_sites(summaries: list[SiteRunSummary]) -> None:
    failed_sites = [summary.site for summary in summaries if summary.error]
    if failed_sites:
        raise SystemExit(1)


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
