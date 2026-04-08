from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from crawler.parser import parse_html_document
from crawler.settings import DEFAULT_PER_PAGE
from crawler.sites.base import ParsedPage, SiteAdapter
from crawler.url_utils import normalize_url

YOURATOR_BASE_URL = "https://www.yourator.co"
YOURATOR_JOBS_URL = f"{YOURATOR_BASE_URL}/jobs"
YOURATOR_JOBS_API_URL = f"{YOURATOR_BASE_URL}/api/v4/jobs"
YOURATOR_SEARCH_API_URL = f"{YOURATOR_BASE_URL}/api/v3/search"
YOURATOR_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)
KEYWORD_GROUPS = [
    (
        "後端",
        [
            "後端",
            "backend",
            "back-end",
            "back end",
            "backend engineer",
            "backend developer",
            "back end engineer",
            "back end developer",
            "後端工程師",
            "後端開發",
            "後端開發工程師",
        ],
    ),
    (
        "前端",
        [
            "前端",
            "frontend",
            "front-end",
            "front end",
            "frontend engineer",
            "frontend developer",
            "front end engineer",
            "front end developer",
            "前端工程師",
            "前端開發",
            "前端開發工程師",
        ],
    ),
    (
        "全端",
        [
            "全端",
            "fullstack",
            "full-stack",
            "full stack",
            "fullstack engineer",
            "full stack engineer",
            "全端工程師",
            "全端開發",
        ],
    ),
    (
        "devops",
        [
            "devops",
            "sre",
            "site reliability engineer",
            "platform engineer",
        ],
    ),
    (
        "ai",
        [
            "ai",
            "ml",
            "machine learning",
            "llm",
            "data engineer",
            "資料工程",
            "資料分析",
            "機器學習",
            "人工智慧",
            "資料科學",
            "數據",
        ],
    ),
]
DETAIL_UPDATED_AT_PATTERN = re.compile(r"最近更新於\s*(\d{4}-\d{2}-\d{2})")
TAG_PATTERN = re.compile(r"<[^>]+>")
SALARY_NUMBER_PATTERN = re.compile(r"\d[\d,]*")


@dataclass(slots=True)
class _DetailMetadata:
    summary: str = ""
    content_updated_at: str = ""


class YouratorJobsAdapter(SiteAdapter):
    name = "yourator"

    def __init__(self, keyword: str = "", per_page: int = DEFAULT_PER_PAGE) -> None:
        self.keyword = keyword.strip()
        self.per_page = per_page

    def build_start_urls(self, keyword: str) -> list[str]:
        return [YOURATOR_JOBS_URL]

    def get_allowed_domains(self) -> set[str]:
        return {"www.yourator.co", "yourator.co"}

    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        document = parse_html_document(url, html)
        current_page = _extract_page_number(url)
        search_terms = _expand_search_terms(keyword)
        api_payload = _fetch_jobs_api_page(current_page)
        matches = _parse_jobs_api_matches(api_payload, search_terms, keyword)

        if current_page == 1 and keyword.strip():
            search_matches = _parse_search_api_matches(
                _fetch_search_api_page(keyword),
                search_terms,
                keyword,
            )
            matches = _merge_matches(matches, search_matches)

        links = list(document.links)
        links.extend(_build_pagination_links(current_page, api_payload))

        return ParsedPage(
            title=document.title,
            meta_description=document.meta_description,
            links=_dedupe_preserve_order(links),
            matches=matches,
        )

    def should_visit(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("yourator.co"):
            return False
        if parsed.path.rstrip("/") != "/jobs":
            return False

        query = parse_qs(parsed.query)
        return set(query).issubset({"page"}) and (
            "page" not in query
            or (len(query["page"]) == 1 and query["page"][0].isdigit())
        )


def _parse_jobs_api_matches(
    payload: dict,
    search_terms: list[str],
    keyword: str,
) -> list[dict]:
    matches: list[dict] = []
    for job in payload.get("jobs", []):
        if search_terms and not _job_card_matches_keyword(job, search_terms):
            continue
        matches.append(_job_card_to_match(job, search_terms, keyword))
    return matches


def _parse_search_api_matches(
    response: dict,
    search_terms: list[str],
    keyword: str,
) -> list[dict]:
    matches: list[dict] = []
    for entity in response.get("jobs", []):
        if search_terms and not _search_entity_matches_keyword(entity, search_terms):
            continue
        matches.append(_search_entity_to_match(entity, search_terms, keyword))
    return matches


def _job_card_matches_keyword(job: dict, search_terms: list[str]) -> bool:
    if not search_terms:
        return True

    title = str(job.get("name", "")).strip()
    company_name = str(job.get("company", {}).get("brand", "")).strip()
    tags_text = ", ".join(_collect_job_tags(job))
    return bool(
        _find_matching_terms(title, search_terms)
        or _find_matching_terms(company_name, search_terms)
        or _find_matching_terms(tags_text, search_terms)
    )


def _search_entity_matches_keyword(entity: dict, search_terms: list[str]) -> bool:
    title = str(entity.get("name", "")).strip()
    company_name = str(entity.get("company", {}).get("brand", "")).strip()
    tags_text = ", ".join(_collect_search_tags(entity))
    summary = _html_to_text(str(entity.get("content", "")).strip())
    category_name = str(entity.get("category", {}).get("name", "")).strip()
    return bool(
        _find_matching_terms(title, search_terms)
        or _find_matching_terms(company_name, search_terms)
        or _find_matching_terms(tags_text, search_terms)
        or _find_matching_terms(summary, search_terms)
        or _find_matching_terms(category_name, search_terms)
    )


def _job_card_to_match(job: dict, search_terms: list[str], keyword: str) -> dict:
    title = str(job.get("name", "")).strip()
    company = job.get("company", {}) if isinstance(job.get("company"), dict) else {}
    company_name = str(company.get("brand", "")).strip()
    tags = _collect_job_tags(job)
    tags_text = ", ".join(tags)
    detail = _fetch_job_detail(_build_job_url(job))
    summary = detail.summary
    title_hit_terms = _find_matching_terms(title, search_terms)
    company_hit_terms = _find_matching_terms(company_name, search_terms)
    tag_hit_terms = _find_matching_terms(tags_text, search_terms)
    summary_hit_terms = _find_matching_terms(summary, search_terms)
    matched_fields: list[str] = []
    matched_terms: list[str] = []

    if title_hit_terms:
        matched_fields.append("title")
        matched_terms.extend(title_hit_terms)
    if company_hit_terms:
        matched_fields.append("company_name")
        matched_terms.extend(company_hit_terms)
    if tag_hit_terms:
        matched_fields.append("tags")
        matched_terms.extend(tag_hit_terms)
    if summary_hit_terms:
        matched_fields.append("summary")
        matched_terms.extend(summary_hit_terms)

    salary_min, salary_max, salary_currency, salary_type = _normalize_salary(
        str(job.get("salary", "")).strip()
    )

    return {
        "type": "job_card",
        "title": title,
        "company_name": company_name,
        "job_url": _build_job_url(job),
        "company_url": _build_company_url(company),
        "summary": summary[:400],
        "matched_fields": matched_fields,
        "matched_terms": _dedupe_preserve_order(matched_terms),
        "location": str(job.get("location", "")).strip(),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "salary_type": salary_type,
        "salary_display": str(job.get("salary", "")).strip(),
        "openings_count": "",
        "employment_type": "",
        "seniority_level": "",
        "experience_required_years": "",
        "management_responsibility": "",
        "tags": tags_text,
        "content_updated_at": detail.content_updated_at or str(job.get("lastActiveAt", "")).strip(),
    }


def _search_entity_to_match(entity: dict, search_terms: list[str], keyword: str) -> dict:
    title = str(entity.get("name", "")).strip()
    company = entity.get("company", {}) if isinstance(entity.get("company"), dict) else {}
    company_name = str(company.get("brand", "")).strip()
    summary = _html_to_text(str(entity.get("content", "")).strip())
    tags = _collect_search_tags(entity)
    tags_text = ", ".join(tags)
    category_name = str(entity.get("category", {}).get("name", "")).strip()
    title_hit_terms = _find_matching_terms(title, search_terms)
    company_hit_terms = _find_matching_terms(company_name, search_terms)
    summary_hit_terms = _find_matching_terms(summary, search_terms)
    tag_hit_terms = _find_matching_terms(tags_text, search_terms)
    category_hit_terms = _find_matching_terms(category_name, search_terms)
    matched_fields: list[str] = []
    matched_terms: list[str] = []

    if title_hit_terms:
        matched_fields.append("title")
        matched_terms.extend(title_hit_terms)
    if company_hit_terms:
        matched_fields.append("company_name")
        matched_terms.extend(company_hit_terms)
    if summary_hit_terms:
        matched_fields.append("summary")
        matched_terms.extend(summary_hit_terms)
    if tag_hit_terms:
        matched_fields.append("tags")
        matched_terms.extend(tag_hit_terms)
    if category_hit_terms:
        matched_fields.append("category")
        matched_terms.extend(category_hit_terms)

    salary_min, salary_max, salary_currency, salary_type = _normalize_salary(
        str(entity.get("salary", "")).strip()
    )

    return {
        "type": "job_card",
        "title": title,
        "company_name": company_name,
        "job_url": _build_search_entity_job_url(entity),
        "company_url": _build_company_url(company),
        "summary": summary[:400],
        "matched_fields": matched_fields,
        "matched_terms": _dedupe_preserve_order(matched_terms),
        "location": _format_search_location(entity),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "salary_type": salary_type,
        "salary_display": str(entity.get("salary", "")).strip(),
        "openings_count": "",
        "employment_type": "",
        "seniority_level": "",
        "experience_required_years": "",
        "management_responsibility": "",
        "tags": tags_text,
        "content_updated_at": "",
    }


def _merge_matches(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {match.get("job_url", ""): dict(match) for match in primary}

    for incoming in secondary:
        job_url = incoming.get("job_url", "")
        if not job_url:
            continue

        existing = merged.get(job_url)
        if not existing:
            merged[job_url] = dict(incoming)
            continue

        existing["matched_fields"] = _dedupe_preserve_order(
            list(existing.get("matched_fields", [])) + list(incoming.get("matched_fields", []))
        )
        existing["matched_terms"] = _dedupe_preserve_order(
            list(existing.get("matched_terms", [])) + list(incoming.get("matched_terms", []))
        )

        if len(str(incoming.get("summary", ""))) > len(str(existing.get("summary", ""))):
            existing["summary"] = incoming.get("summary", "")

        for field in [
            "location",
            "salary_min",
            "salary_max",
            "salary_currency",
            "salary_type",
            "salary_display",
            "tags",
            "content_updated_at",
            "company_url",
        ]:
            if not existing.get(field) and incoming.get(field):
                existing[field] = incoming[field]

    return list(merged.values())


def _build_pagination_links(current_page: int, payload: dict) -> list[str]:
    if not payload.get("hasMore") or not payload.get("nextPage"):
        return []
    query = urlencode({"page": payload["nextPage"]})
    return [f"{YOURATOR_JOBS_URL}?{query}"]


def _build_job_url(job: dict) -> str:
    path = str(job.get("path", "")).strip()
    if path:
        return normalize_url(path, base_url=YOURATOR_BASE_URL) or ""

    company = job.get("company", {}) if isinstance(job.get("company"), dict) else {}
    company_path = str(company.get("path", "")).strip()
    job_id = str(job.get("id", "")).strip()
    if company_path and job_id:
        return normalize_url(f"{company_path}/jobs/{job_id}", base_url=YOURATOR_BASE_URL) or ""
    return ""


def _build_search_entity_job_url(entity: dict) -> str:
    company = entity.get("company", {}) if isinstance(entity.get("company"), dict) else {}
    en_name = str(company.get("enName", "")).strip()
    job_id = str(entity.get("id", "")).strip()
    if not en_name or not job_id:
        return ""
    return f"{YOURATOR_BASE_URL}/companies/{en_name}/jobs/{job_id}"


def _build_company_url(company: dict) -> str:
    path = str(company.get("path", "")).strip()
    if path:
        return normalize_url(path, base_url=YOURATOR_BASE_URL) or ""

    en_name = str(company.get("enName", "")).strip()
    if en_name:
        return f"{YOURATOR_BASE_URL}/companies/{en_name}"
    return ""


def _collect_job_tags(job: dict) -> list[str]:
    raw_tags = job.get("tags", [])
    if not isinstance(raw_tags, list):
        return []
    return _dedupe_preserve_order([str(tag).strip() for tag in raw_tags if str(tag).strip()])


def _collect_search_tags(entity: dict) -> list[str]:
    values: list[str] = []
    for tag in entity.get("tags", []):
        if not isinstance(tag, dict):
            continue
        name = str(tag.get("name", "")).strip()
        if name:
            values.append(name)
    return _dedupe_preserve_order(values)


def _format_search_location(entity: dict) -> str:
    country = str(entity.get("country", {}).get("name", "")).strip()
    city = str(entity.get("city", {}).get("name", "")).strip()
    return " ".join(part for part in [country, city] if part)


def _fetch_jobs_api_page(page: int) -> dict:
    url = f"{YOURATOR_JOBS_API_URL}?{urlencode({'page': page})}"
    return _fetch_json(url).get("payload", {})


def _fetch_search_api_page(keyword: str) -> dict:
    url = f"{YOURATOR_SEARCH_API_URL}?{urlencode({'s': keyword.strip()})}"
    return _fetch_json(url)


def _fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": YOURATOR_BROWSER_USER_AGENT})
    with urlopen(request, timeout=10.0) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def _fetch_job_detail(job_url: str) -> _DetailMetadata:
    if not job_url:
        return _DetailMetadata()

    request = Request(job_url, headers={"User-Agent": YOURATOR_BROWSER_USER_AGENT})
    with urlopen(request, timeout=10.0) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")

    document = parse_html_document(job_url, html)
    updated_match = DETAIL_UPDATED_AT_PATTERN.search(html)
    return _DetailMetadata(
        summary=document.meta_description.strip(),
        content_updated_at=updated_match.group(1) if updated_match else "",
    )


def _normalize_salary(raw_salary: str) -> tuple[str, str, str, str]:
    salary_text = raw_salary.strip()
    if not salary_text:
        return "", "", "", ""

    currency = "TWD" if "NT$" in salary_text else ""
    salary_type = "unknown"
    if "月薪" in salary_text:
        salary_type = "per_month"
    elif "年薪" in salary_text:
        salary_type = "per_year"
    elif "時薪" in salary_text:
        salary_type = "per_hour"
    elif "論件計酬" in salary_text:
        salary_type = "per_project"
    elif "面議" in salary_text:
        salary_type = "negotiable"

    values = [number.replace(",", "") for number in SALARY_NUMBER_PATTERN.findall(salary_text)]
    if not values:
        return "", "", currency, salary_type

    if len(values) == 1:
        return values[0], "", currency, salary_type
    return values[0], values[1], currency, salary_type


def _extract_page_number(url: str) -> int:
    query = parse_qs(urlparse(url).query)
    raw_page = query.get("page", ["1"])[0].strip()
    return int(raw_page) if raw_page.isdigit() and int(raw_page) > 0 else 1


def _expand_search_terms(keyword: str) -> list[str]:
    normalized_keyword = keyword.strip()
    if not normalized_keyword:
        return []

    lowered_keyword = normalized_keyword.casefold()
    for _, variants in KEYWORD_GROUPS:
        variant_cases = {variant.casefold() for variant in variants}
        if lowered_keyword in variant_cases:
            return _dedupe_preserve_order(variants)
    return [normalized_keyword]


def _find_matching_terms(text: str, search_terms: list[str]) -> list[str]:
    lowered_text = text.casefold()
    return [
        term
        for term in search_terms
        if term and term.casefold() in lowered_text
    ]


def _html_to_text(html: str) -> str:
    return " ".join(unescape(TAG_PATTERN.sub(" ", html)).split())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
