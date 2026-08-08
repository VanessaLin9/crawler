from __future__ import annotations

import json
import smtplib
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from email.utils import formatdate

from crawler.records import JobRecord


DEFAULT_SMTP_PORT = 587


@dataclass(slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    to_email: str
    use_tls: bool = True


def send_new_jobs_email(
    smtp_config: SmtpConfig,
    site: str,
    keyword: str,
    records: list[JobRecord],
    sheet_name: str,
    spreadsheet_id: str,
    crawl_issues: list[str] | None = None,
) -> None:
    if not records and not crawl_issues:
        return

    message = EmailMessage()
    message["Subject"] = _build_subject(site, keyword, len(records), crawl_issues or [])
    message["From"] = smtp_config.from_email
    message["To"] = smtp_config.to_email
    message["Date"] = formatdate(localtime=True)
    message.set_content(
        _build_plain_text_body(
            site=site,
            keyword=keyword,
            records=records,
            sheet_name=sheet_name,
            spreadsheet_id=spreadsheet_id,
            crawl_issues=crawl_issues or [],
        )
    )
    _send_message(smtp_config, message)


def send_new_jobs_json_email(
    smtp_config: SmtpConfig,
    site: str,
    keyword: str,
    records: list[JobRecord],
    sheet_name: str,
    spreadsheet_id: str,
) -> None:
    if not records:
        return

    message = EmailMessage()
    message["Subject"] = _build_json_subject(site, keyword, len(records))
    message["From"] = smtp_config.from_email
    message["To"] = smtp_config.to_email
    message["Date"] = formatdate(localtime=True)
    message.set_content(
        _build_json_body(
            site=site,
            keyword=keyword,
            records=records,
            sheet_name=sheet_name,
            spreadsheet_id=spreadsheet_id,
        ),
        subtype="json",
        charset="utf-8",
    )
    _send_message(smtp_config, message)


def _build_subject(site: str, keyword: str, count: int, crawl_issues: list[str] | None = None) -> str:
    if crawl_issues:
        return f"[Crawler Alert] {site} {keyword} issues detected"
    return f"[Crawler] {site} {keyword} new jobs: {count}"


def _build_json_subject(site: str, keyword: str, count: int) -> str:
    return f"[Crawler JSON] {site} {keyword} new jobs: {count}"


def _build_plain_text_body(
    site: str,
    keyword: str,
    records: list[JobRecord],
    sheet_name: str,
    spreadsheet_id: str,
    crawl_issues: list[str] | None = None,
) -> str:
    issues = crawl_issues or []
    lines = [
        f"Site: {site}",
        f"Keyword: {keyword}",
        f"New jobs: {len(records)}",
        f"Sheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        f"Worksheet: {sheet_name}",
        "",
    ]

    if issues:
        lines.extend(
            [
                "Crawl issues detected:",
                *[f"- {issue}" for issue in issues],
                "",
            ]
        )

    for index, record in enumerate(records, start=1):
        # 人讀信先完整露出 JobRecord 既有欄位，方便用實際測試信再收斂；
        # Summary 放最後，多行時仍靠尾端空行維持職缺邊界。
        lines.extend(
            [
                f"{index}. {record.title}",
                f"Company: {record.company_name}",
                f"Company URL: {_format_optional_text(record.company_url)}",
                f"Location: {_format_optional_text(record.location)}",
                f"Salary: {_format_optional_text(record.salary_display)}",
                f"Salary min: {_format_optional_text(record.salary_min)}",
                f"Salary max: {_format_optional_text(record.salary_max)}",
                f"Salary currency: {_format_optional_text(record.salary_currency)}",
                f"Salary type: {_format_optional_text(record.salary_type)}",
                f"Openings: {_format_optional_text(record.openings_count)}",
                f"Type: {_format_optional_text(record.employment_type)}",
                f"Seniority: {_format_optional_text(record.seniority_level)}",
                f"Experience: {_format_optional_text(record.experience_required_years)}",
                f"Management responsibility: {_format_optional_text(record.management_responsibility)}",
                f"Tags: {_format_optional_text(record.tags)}",
                f"Matched fields: {_format_optional_list(record.matched_fields)}",
                f"Matched terms: {_format_optional_list(record.matched_terms)}",
                # 共用人讀摘要也露出日期欄（WWR 等站需要；無值則 N/A）。PR #11
                f"Posted on: {_format_optional_text(record.content_updated_at)}",
                f"Apply before: {_format_optional_text(record.application_deadline)}",
                f"Source site: {_format_optional_text(record.source_site)}",
                f"Search page URL: {_format_optional_text(record.search_page_url)}",
                f"Discovered at: {_format_optional_text(record.discovered_at)}",
                f"URL: {record.job_url}",
                f"Summary: {_format_optional_text(record.summary)}",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def _format_optional_text(value: str) -> str:
    return value or "N/A"


def _format_optional_list(values: list[str]) -> str:
    if not values:
        return "N/A"
    return ", ".join(values)


def _build_json_body(
    site: str,
    keyword: str,
    records: list[JobRecord],
    sheet_name: str,
    spreadsheet_id: str,
) -> str:
    payload = {
        "site": site,
        "keyword": keyword,
        "new_jobs_count": len(records),
        "sheet_name": sheet_name,
        "spreadsheet_id": spreadsheet_id,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        "jobs": [asdict(record) for record in records],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _send_message(smtp_config: SmtpConfig, message: EmailMessage) -> None:
    with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as server:
        if smtp_config.use_tls:
            server.starttls()
        if smtp_config.username:
            server.login(smtp_config.username, smtp_config.password)
        server.send_message(message)
