from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


SHEET_COLUMNS = [
    "job_url",
    "title",
    "company_name",
    "company_url",
    "keyword",
    "location",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_type",
    "salary_display",
    "openings_count",
    "employment_type",
    "seniority_level",
    "experience_required_years",
    "management_responsibility",
    "tags",
    "matched_fields",
    "matched_terms",
    "summary",
    "source_site",
    "search_page_url",
    "content_updated_at",
    "discovered_at",
]


WWR_SHEET_COLUMNS = [
    "job_url",
    "title",
    "company_name",
    "company_url",
    "wwr_region",
    "wwr_category",
    "feed_url",
    "published_at",
    "headquarters",
    "remote_scope",
    "country_eligibility",
    "timezone_fit",
    "employment_type",
    "salary_display",
    "tags",
    "matched_fields",
    "matched_terms",
    "summary",
    "description_text",
    "logo_url",
    "source_site",
    "discovered_at",
]


@dataclass(slots=True)
class JobRecord:
    job_url: str
    title: str
    company_name: str
    company_url: str
    keyword: str
    location: str
    salary_min: str
    salary_max: str
    salary_currency: str
    salary_type: str
    salary_display: str
    openings_count: str
    employment_type: str
    seniority_level: str
    experience_required_years: str
    management_responsibility: str
    tags: str
    matched_fields: list[str]
    matched_terms: list[str]
    summary: str
    source_site: str
    search_page_url: str
    content_updated_at: str
    discovered_at: str
    wwr_region: str = ""
    wwr_category: str = ""
    feed_url: str = ""
    published_at: str = ""
    headquarters: str = ""
    remote_scope: str = ""
    country_eligibility: str = ""
    timezone_fit: str = ""
    description_text: str = ""
    logo_url: str = ""

    def to_sheet_row(self, columns: list[str] | None = None) -> list[str]:
        return [
            _format_sheet_value(getattr(self, column, ""))
            for column in (columns or SHEET_COLUMNS)
        ]


def flatten_job_records(
    crawl_results: list[dict],
    discovered_at: str | None = None,
) -> list[JobRecord]:
    discovered_value = discovered_at or _utc_now_iso()
    deduped: dict[str, JobRecord] = {}

    for page in crawl_results:
        site = page.get("site", "")
        keyword = page.get("keyword", "")
        search_page_url = page.get("url", "")
        for match in page.get("matches", []):
            job_url = match.get("job_url", "")
            if not job_url:
                continue

            existing = deduped.get(job_url)
            if existing:
                existing.matched_fields = _merge_unique(
                    existing.matched_fields,
                    match.get("matched_fields", []),
                )
                existing.matched_terms = _merge_unique(
                    existing.matched_terms,
                    match.get("matched_terms", []),
                )
                if len(match.get("summary", "")) > len(existing.summary):
                    existing.summary = match.get("summary", "")
                continue

            deduped[job_url] = JobRecord(
                job_url=job_url,
                title=match.get("title", ""),
                company_name=match.get("company_name", ""),
                company_url=match.get("company_url", ""),
                keyword=keyword,
                location=match.get("location", ""),
                salary_min=match.get("salary_min", ""),
                salary_max=match.get("salary_max", ""),
                salary_currency=match.get("salary_currency", ""),
                salary_type=match.get("salary_type", ""),
                salary_display=match.get("salary_display", ""),
                openings_count=match.get("openings_count", ""),
                employment_type=match.get("employment_type", ""),
                seniority_level=match.get("seniority_level", ""),
                experience_required_years=match.get("experience_required_years", ""),
                management_responsibility=match.get("management_responsibility", ""),
                tags=match.get("tags", ""),
                matched_fields=list(match.get("matched_fields", [])),
                matched_terms=list(match.get("matched_terms", [])),
                summary=match.get("summary", ""),
                source_site=site,
                search_page_url=search_page_url,
                content_updated_at=match.get("content_updated_at", ""),
                discovered_at=discovered_value,
                wwr_region=match.get("wwr_region", ""),
                wwr_category=match.get("wwr_category", ""),
                feed_url=match.get("feed_url", ""),
                published_at=match.get("published_at", ""),
                headquarters=match.get("headquarters", ""),
                remote_scope=match.get("remote_scope", ""),
                country_eligibility=match.get("country_eligibility", ""),
                timezone_fit=match.get("timezone_fit", ""),
                description_text=match.get("description_text", ""),
                logo_url=match.get("logo_url", ""),
            )

    return list(deduped.values())


def _merge_unique(current: list[str], incoming: list[str]) -> list[str]:
    return list(dict.fromkeys([*current, *incoming]))


def _format_sheet_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
