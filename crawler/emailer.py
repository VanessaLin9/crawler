from __future__ import annotations

import smtplib
from dataclasses import dataclass
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
) -> None:
    if not records:
        return

    message = EmailMessage()
    message["Subject"] = _build_subject(site, keyword, len(records))
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
        )
    )

    with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=30) as server:
        if smtp_config.use_tls:
            server.starttls()
        if smtp_config.username:
            server.login(smtp_config.username, smtp_config.password)
        server.send_message(message)


def _build_subject(site: str, keyword: str, count: int) -> str:
    return f"[Crawler] {site} {keyword} new jobs: {count}"


def _build_plain_text_body(
    site: str,
    keyword: str,
    records: list[JobRecord],
    sheet_name: str,
    spreadsheet_id: str,
) -> str:
    lines = [
        f"Site: {site}",
        f"Keyword: {keyword}",
        f"New jobs: {len(records)}",
        f"Sheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
        f"Worksheet: {sheet_name}",
        "",
    ]

    for index, record in enumerate(records, start=1):
        lines.extend(
            [
                f"{index}. {record.title}",
                f"Company: {record.company_name}",
                f"Location: {record.location or 'N/A'}",
                f"Salary: {record.salary_display or 'N/A'}",
                f"Type: {record.employment_type or 'N/A'}",
                f"Seniority: {record.seniority_level or 'N/A'}",
                f"Experience: {record.experience_required_years or 'N/A'}",
                f"URL: {record.job_url}",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"
