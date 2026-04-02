from __future__ import annotations

import json
from http.cookiejar import CookieJar
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener

from crawler.parser import parse_html_document
from crawler.sites.base import ParsedPage, SiteAdapter

JOB104_SEARCH_URL = "https://www.104.com.tw/jobs/search/"
JOB104_SEARCH_API_URL = "https://www.104.com.tw/jobs/search/api/jobs"
JOB104_BROWSER_USER_AGENT = (
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
]


class OneOhFourJobsAdapter(SiteAdapter):
    name = "104"

    def __init__(self, keyword: str = "", per_page: int = 20) -> None:
        self.keyword = keyword.strip()
        self.per_page = per_page

    def build_start_urls(self, keyword: str) -> list[str]:
        return [_build_search_page_url(keyword, 1)]

    def get_allowed_domains(self) -> set[str]:
        return {"www.104.com.tw", "104.com.tw"}

    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        document = parse_html_document(url, html)
        current_page = _extract_page_number(url)
        search_terms = _expand_search_terms(keyword)
        api_response = _fetch_search_api_page(keyword, current_page, self.per_page)
        matches = _parse_api_job_matches(api_response, search_terms) if api_response else []
        links = list(document.links)
        if api_response:
            links.extend(_build_pagination_links(keyword, current_page, api_response))

        return ParsedPage(
            title=document.title,
            meta_description=document.meta_description,
            links=_dedupe_preserve_order(links),
            matches=matches,
        )

    def should_visit(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("104.com.tw"):
            return False
        if parsed.path.rstrip("/") != "/jobs/search":
            return False

        query = parse_qs(parsed.query)
        if set(query) - {"keyword", "page"}:
            return False

        expected_keyword = self.keyword.strip()
        keyword_values = query.get("keyword", [])
        if expected_keyword:
            if len(keyword_values) != 1 or keyword_values[0].strip() != expected_keyword:
                return False
        elif keyword_values:
            return False

        page_values = query.get("page", [])
        return not page_values or (len(page_values) == 1 and page_values[0].isdigit())


def _parse_api_job_matches(response: dict, search_terms: list[str]) -> list[dict]:
    matches: list[dict] = []
    for entity in response.get("data", []):
        if search_terms and not _entity_matches_keyword(entity, search_terms):
            continue
        matches.append(_entity_to_match(entity, search_terms))
    return matches


def _entity_matches_keyword(entity: dict, search_terms: list[str]) -> bool:
    title = _get_string(entity, "jobName", "jobNameSnippet")
    tags_text = " ".join(_collect_tags(entity))
    return bool(
        _find_matching_terms(title, search_terms)
        or _find_matching_terms(tags_text, search_terms)
    )


def _entity_to_match(entity: dict, search_terms: list[str]) -> dict:
    title = _get_string(entity, "jobName", "jobNameSnippet")
    company_name = _get_string(entity, "custName")
    summary = _clean_snippet_markup(_get_string(entity, "descSnippet", "description")).strip()
    tags = _collect_tags(entity)
    tags_text = ", ".join(tags)

    title_hit_terms = _find_matching_terms(title, search_terms)
    company_hit_terms = _find_matching_terms(company_name, search_terms)
    summary_hit_terms = _find_matching_terms(summary, search_terms)
    tag_hit_terms = _find_matching_terms(tags_text, search_terms)
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

    salary_min = _stringify_salary(entity.get("salaryLow"))
    salary_max = _stringify_salary(entity.get("salaryHigh"))
    salary_currency = "TWD" if salary_min or salary_max else ""

    return {
        "type": "job_card",
        "title": title,
        "company_name": company_name,
        "job_url": _get_link(entity, "job"),
        "company_url": _get_link(entity, "cust"),
        "summary": summary[:400],
        "matched_fields": matched_fields,
        "matched_terms": _dedupe_preserve_order(matched_terms),
        "location": _format_location(
            _get_string(entity, "jobAddrNoDesc"),
            _get_string(entity, "jobAddress"),
            _get_string(entity, "mrtDesc"),
        ),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "salary_type": "",
        "salary_display": _format_salary_display(salary_min, salary_max, salary_currency),
        "openings_count": "",
        "employment_type": "",
        "seniority_level": "",
        "experience_required_years": "",
        "management_responsibility": "",
        "tags": tags_text,
        "content_updated_at": _format_appear_date(_get_string(entity, "appearDate")),
    }


def _collect_tags(entity: dict) -> list[str]:
    values: list[str] = []

    for skill in entity.get("pcSkills", []):
        description = ""
        if isinstance(skill, dict):
            description = str(skill.get("description", "")).strip()
        if description:
            values.append(description)

    raw_tags = entity.get("tags", {})
    if isinstance(raw_tags, dict):
        for tag in raw_tags.values():
            if not isinstance(tag, dict):
                continue
            description = str(tag.get("desc", "")).strip()
            if description:
                values.append(description)

    return _dedupe_preserve_order(values)


def _clean_snippet_markup(text: str) -> str:
    return text.replace("[[[", "").replace("]]]", "")


def _format_location(region: str, address: str, mrt_desc: str) -> str:
    parts = [part for part in [region.strip(), address.strip(), mrt_desc.strip()] if part]
    return " ".join(_dedupe_preserve_order(parts))


def _format_salary_display(
    salary_min: str,
    salary_max: str,
    salary_currency: str,
) -> str:
    if not (salary_min or salary_max):
        return ""

    range_display = salary_min
    if salary_max:
        range_display = f"{salary_min} - {salary_max}" if salary_min else salary_max

    parts = [range_display]
    if salary_currency:
        parts.append(salary_currency)
    return " ".join(parts)


def _format_appear_date(value: str) -> str:
    if len(value) != 8 or not value.isdigit():
        return value
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def _stringify_salary(value: object) -> str:
    if value in (None, 0, "0"):
        return ""
    return str(value)


def _get_link(entity: dict, key: str) -> str:
    link = entity.get("link", {}) or {}
    value = link.get(key, "")
    return str(value) if value else ""


def _get_string(entity: dict, *keys: str) -> str:
    for key in keys:
        value = entity.get(key)
        if value is None:
            continue
        return str(value)
    return ""


def _expand_search_terms(keyword: str) -> list[str]:
    normalized_keyword = keyword.casefold().strip()
    for canonical, terms in KEYWORD_GROUPS:
        normalized_terms = {term.casefold() for term in terms}
        if normalized_keyword == canonical.casefold() or normalized_keyword in normalized_terms:
            return _dedupe_preserve_order([keyword, canonical, *terms])
    return [keyword]


def _find_matching_terms(text: str, search_terms: list[str]) -> list[str]:
    haystack = text.casefold()
    return [term for term in search_terms if term and term.casefold() in haystack]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _extract_page_number(url: str) -> int:
    query = parse_qs(urlparse(url).query)
    page_values = query.get("page", [])
    if page_values and page_values[0].isdigit():
        return int(page_values[0])
    return 1


def _build_pagination_links(keyword: str, current_page: int, response: dict) -> list[str]:
    pagination = response.get("metadata", {}).get("pagination", {})
    last_page = pagination.get("lastPage")
    if not isinstance(last_page, int) or current_page >= last_page:
        return []
    return [_build_search_page_url(keyword, current_page + 1)]


def _build_search_page_url(keyword: str, page_number: int) -> str:
    query: dict[str, str | int] = {}
    stripped_keyword = keyword.strip()
    if stripped_keyword:
        query["keyword"] = stripped_keyword
    if page_number > 1:
        query["page"] = page_number
    if not query:
        return JOB104_SEARCH_URL
    return f"{JOB104_SEARCH_URL}?{urlencode(query)}"


def _fetch_search_api_page(
    keyword: str,
    page_number: int,
    per_page: int,
) -> dict | None:
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    search_url = _build_search_page_url(keyword, 1)

    try:
        with opener.open(
            Request(
                search_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "User-Agent": JOB104_BROWSER_USER_AGENT,
                },
                method="GET",
            ),
            timeout=15,
        ) as response:
            response.read()
    except Exception:
        return None

    params = {"page": page_number, "pagesize": per_page}
    stripped_keyword = keyword.strip()
    if stripped_keyword:
        params["keyword"] = stripped_keyword

    api_request = Request(
        f"{JOB104_SEARCH_API_URL}?{urlencode(params)}",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": search_url,
            "User-Agent": JOB104_BROWSER_USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        },
        method="GET",
    )

    try:
        with opener.open(api_request, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset, errors="replace")
    except Exception:
        return None

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
