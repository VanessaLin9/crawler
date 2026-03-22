from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


SHEET_COLUMNS = [
    "job_url",
    "title",
    "company_name",
    "company_url",
    "keyword",
    "matched_fields",
    "matched_terms",
    "summary",
    "source_site",
    "search_page_url",
    "discovered_at",
]


@dataclass(slots=True)
class JobRecord:
    job_url: str
    title: str
    company_name: str
    company_url: str
    keyword: str
    matched_fields: list[str]
    matched_terms: list[str]
    summary: str
    source_site: str
    search_page_url: str
    discovered_at: str

    def to_sheet_row(self) -> list[str]:
        return [
            self.job_url,
            self.title,
            self.company_name,
            self.company_url,
            self.keyword,
            ", ".join(self.matched_fields),
            ", ".join(self.matched_terms),
            self.summary,
            self.source_site,
            self.search_page_url,
            self.discovered_at,
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
                matched_fields=list(match.get("matched_fields", [])),
                matched_terms=list(match.get("matched_terms", [])),
                summary=match.get("summary", ""),
                source_site=site,
                search_page_url=search_page_url,
                discovered_at=discovered_value,
            )

    return list(deduped.values())


def _merge_unique(current: list[str], incoming: list[str]) -> list[str]:
    return list(dict.fromkeys([*current, *incoming]))


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
