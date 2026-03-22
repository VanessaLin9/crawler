from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import parse_qs, quote, urlparse

from crawler.parser import parse_html_document
from crawler.settings import DEFAULT_PER_PAGE
from crawler.sites.base import ParsedPage, SiteAdapter
from crawler.url_utils import normalize_url

CAKE_IT_JOBS_URL = "https://www.cake.me/jobs/for-it?ref=navs_job_search_it"
CAKE_IT_JOBS_SEARCH_URL_TEMPLATE = "https://www.cake.me/jobs/{keyword}/for-it"
CAKE_CLIENT_SEARCH_API_URL = "https://api.cake.me/api/client/v1/jobs/search"
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


@dataclass(slots=True)
class _CakeJobCard:
    title: str
    job_url: str
    company_name: str = ""
    company_url: str = ""
    content_chunks: list[str] | None = None

    def __post_init__(self) -> None:
        if self.content_chunks is None:
            self.content_chunks = []

    @property
    def summary(self) -> str:
        return " ".join(self.content_chunks or []).strip()


class _CakeJobCardParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.in_body = False
        self.ignore_depth = 0
        self.current_heading_tag: str | None = None
        self.current_anchor_href: str | None = None
        self.current_anchor_text: list[str] = []
        self.heading_job_link: tuple[str, str] | None = None
        self.current_job: _CakeJobCard | None = None
        self.jobs: list[_CakeJobCard] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignore_depth += 1
            return

        if self.ignore_depth:
            return

        if tag == "body":
            self.in_body = True
            return

        if not self.in_body:
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.current_heading_tag = tag
            self.heading_job_link = None
            return

        if tag == "a":
            attributes = dict(attrs)
            self.current_anchor_href = normalize_url(
                attributes.get("href") or "",
                base_url=self.base_url,
            )
            self.current_anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.ignore_depth:
            self.ignore_depth -= 1
            return

        if self.ignore_depth:
            return

        if tag == "body":
            self.in_body = False
            return

        if not self.in_body:
            return

        if tag == "a":
            self._close_anchor()
            return

        if self.current_heading_tag == tag:
            if self.heading_job_link:
                self._start_new_job(*self.heading_job_link)
            self.current_heading_tag = None
            self.heading_job_link = None

    def handle_data(self, data: str) -> None:
        if self.ignore_depth or not self.in_body:
            return

        stripped = " ".join(data.split())
        if not stripped:
            return

        if self.current_anchor_href:
            self.current_anchor_text.append(stripped)

        if self.current_job and not self.current_heading_tag:
            self.current_job.content_chunks.append(stripped)

    def close(self) -> None:
        super().close()
        self._finish_current_job()

    def _close_anchor(self) -> None:
        anchor_href = self.current_anchor_href
        anchor_text = " ".join(self.current_anchor_text).strip()
        self.current_anchor_href = None
        self.current_anchor_text = []

        if not anchor_href or not anchor_text:
            return

        if self.current_heading_tag and _is_cake_job_url(anchor_href):
            self.heading_job_link = (anchor_text, anchor_href)
            return

        if not self.current_job:
            return

        if (
            not self.current_job.company_name
            and _is_cake_company_url(anchor_href)
            and _same_company(anchor_href, self.current_job.job_url)
        ):
            self.current_job.company_name = anchor_text
            self.current_job.company_url = anchor_href

    def _start_new_job(self, title: str, job_url: str) -> None:
        self._finish_current_job()
        self.current_job = _CakeJobCard(title=title, job_url=job_url)

    def _finish_current_job(self) -> None:
        if not self.current_job:
            return
        self.jobs.append(self.current_job)
        self.current_job = None


def _is_cake_job_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("cake.me") and "/companies/" in parsed.path and "/jobs/" in parsed.path


def _is_cake_company_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("cake.me") and "/companies/" in parsed.path and "/jobs/" not in parsed.path


def _same_company(company_url: str, job_url: str) -> bool:
    company_prefix = job_url.split("/jobs/", maxsplit=1)[0]
    return company_url.startswith(company_prefix)


class CakeItJobsAdapter(SiteAdapter):
    name = "cake"

    def __init__(
        self,
        keyword: str = "",
        per_page: int = DEFAULT_PER_PAGE,
        use_search_api: bool = False,
    ) -> None:
        encoded_keyword = quote(keyword.strip(), safe="")
        self.keyword = keyword.strip()
        self.per_page = per_page
        self.use_search_api = use_search_api
        self.search_path = (
            f"/jobs/{encoded_keyword}/for-it" if encoded_keyword else "/jobs/for-it"
        )

    def build_start_urls(self, keyword: str) -> list[str]:
        encoded_keyword = quote(keyword.strip(), safe="")
        if not encoded_keyword:
            return [CAKE_IT_JOBS_URL]
        return [CAKE_IT_JOBS_SEARCH_URL_TEMPLATE.format(keyword=encoded_keyword)]

    def get_allowed_domains(self) -> set[str]:
        return {"www.cake.me", "cake.me"}

    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        document = parse_html_document(url, html)
        search_terms = _expand_search_terms(keyword)
        current_page = _extract_page_number(url)
        api_response = (
            _fetch_search_api_page(keyword, current_page, self.per_page)
            if self.use_search_api
            else None
        )
        links = list(document.links)

        if api_response:
            matches = _parse_api_job_matches(api_response, search_terms)
            links.extend(
                _build_pagination_links(
                    keyword,
                    current_page,
                    api_response,
                )
            )
        else:
            matches = _parse_structured_job_matches(url, html, search_terms)

        if not matches:
            parser = _CakeJobCardParser(base_url=url)
            parser.feed(html)
            parser.close()
            matches = [
                _job_to_match(job, keyword, search_terms)
                for job in parser.jobs
                if _job_matches_keyword(job, search_terms)
            ]

        return ParsedPage(
            title=document.title,
            meta_description=document.meta_description,
            links=_dedupe_preserve_order(links),
            matches=matches,
        )

    def should_visit(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.netloc.endswith("cake.me") or parsed.path != self.search_path:
            return False

        query = parse_qs(parsed.query)
        if not query:
            return True

        if set(query) != {"page"}:
            return False

        page_values = query.get("page", [])
        return len(page_values) == 1 and page_values[0].isdigit()


def _job_matches_keyword(job: _CakeJobCard, search_terms: list[str]) -> bool:
    return any(_collect_field_hits(job, search_terms))


def _job_to_match(job: _CakeJobCard, keyword: str, search_terms: list[str]) -> dict:
    title_hit_terms = _find_matching_terms(job.title, search_terms)
    company_hit_terms = _find_matching_terms(job.company_name, search_terms)
    summary_hit_terms = _find_matching_terms(job.summary, search_terms)
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

    return {
        "type": "job_card",
        "title": job.title,
        "company_name": job.company_name,
        "job_url": job.job_url,
        "company_url": job.company_url,
        "summary": job.summary[:400],
        "matched_fields": matched_fields,
        "matched_terms": _dedupe_preserve_order(matched_terms),
        "location": "",
        "salary_min": "",
        "salary_max": "",
        "salary_currency": "",
        "salary_type": "",
        "salary_display": "",
        "openings_count": "",
        "employment_type": "",
        "seniority_level": "",
        "experience_required_years": "",
        "management_responsibility": "",
        "tags": "",
        "content_updated_at": "",
    }


def _expand_search_terms(keyword: str) -> list[str]:
    normalized_keyword = keyword.casefold().strip()
    for canonical, terms in KEYWORD_GROUPS:
        normalized_terms = {term.casefold() for term in terms}
        if normalized_keyword == canonical.casefold() or normalized_keyword in normalized_terms:
            return _dedupe_preserve_order([keyword, canonical, *terms])
    return [keyword]


def _collect_field_hits(job: _CakeJobCard, search_terms: list[str]) -> list[str]:
    return _dedupe_preserve_order(
        [
            *_find_matching_terms(job.title, search_terms),
            *_find_matching_terms(job.company_name, search_terms),
            *_find_matching_terms(job.summary, search_terms),
        ]
    )


def _find_matching_terms(text: str, search_terms: list[str]) -> list[str]:
    haystack = text.casefold()
    return [term for term in search_terms if term.casefold() in haystack]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _parse_structured_job_matches(
    url: str,
    html: str,
    search_terms: list[str],
) -> list[dict]:
    next_data = _extract_next_data(html)
    if not next_data:
        return []

    job_search = (
        next_data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("jobSearch", {})
    )
    if not job_search:
        return []

    active_filter_key = job_search.get("activeFilterKey")
    view = job_search.get("viewsByFilterKey", {}).get(active_filter_key, {})
    page_map = view.get("pageMap", {})
    entity_by_path_id = job_search.get("entityByPathId", {})
    current_page = _extract_page_number(url)
    page_entities = page_map.get(str(current_page), [])

    matches: list[dict] = []
    for path_id in page_entities:
        entity = entity_by_path_id.get(path_id)
        if not entity:
            continue
        if not _structured_entity_matches(entity, search_terms):
            continue
        matches.append(_structured_entity_to_match(entity, search_terms))
    return matches


def _parse_api_job_matches(
    response: dict,
    search_terms: list[str],
) -> list[dict]:
    matches: list[dict] = []
    for entity in response.get("data", []):
        if not _structured_entity_matches(entity, search_terms):
            continue
        matches.append(_structured_entity_to_match(entity, search_terms))
    return matches


def _extract_next_data(html: str) -> dict | None:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _extract_page_number(url: str) -> int:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    page_values = query.get("page", [])
    if page_values and page_values[0].isdigit():
        return int(page_values[0])
    return 1


def _structured_entity_matches(entity: dict, search_terms: list[str]) -> bool:
    texts = [
        _get_entity_value(entity, "title"),
        _get_entity_value(entity.get("page", {}), "name"),
        _get_entity_value(entity, "description"),
        " ".join(_get_entity_list(entity, "tags")),
    ]
    haystack = " ".join(texts)
    return bool(_find_matching_terms(haystack, search_terms))


def _structured_entity_to_match(entity: dict, search_terms: list[str]) -> dict:
    title = _get_entity_value(entity, "title")
    page = entity.get("page", {}) or {}
    company_name = _get_entity_value(page, "name")
    company_path = _get_entity_value(page, "path")
    job_path = _get_entity_value(entity, "path")
    description = _get_entity_value(entity, "description").strip()
    tags = _get_entity_list(entity, "tags")
    locations = _get_entity_list(entity, "locations")
    salary = entity.get("salary", {}) or {}

    title_hit_terms = _find_matching_terms(title, search_terms)
    company_hit_terms = _find_matching_terms(company_name, search_terms)
    description_hit_terms = _find_matching_terms(description, search_terms)
    tag_hit_terms = _find_matching_terms(" ".join(tags), search_terms)
    matched_fields: list[str] = []
    matched_terms: list[str] = []

    if title_hit_terms:
        matched_fields.append("title")
        matched_terms.extend(title_hit_terms)
    if company_hit_terms:
        matched_fields.append("company_name")
        matched_terms.extend(company_hit_terms)
    if description_hit_terms:
        matched_fields.append("summary")
        matched_terms.extend(description_hit_terms)
    if tag_hit_terms:
        matched_fields.append("tags")
        matched_terms.extend(tag_hit_terms)

    salary_min = _stringify_optional(_get_entity_value(salary, "min"))
    salary_max = _stringify_optional(_get_entity_value(salary, "max"))
    salary_currency = _stringify_optional(_get_entity_value(salary, "currency"))
    salary_type = _stringify_optional(_get_entity_value(salary, "type"))

    return {
        "type": "job_card",
        "title": title,
        "company_name": company_name,
        "job_url": _build_cake_job_url(company_path, job_path),
        "company_url": _build_cake_company_url(company_path),
        "summary": description,
        "matched_fields": matched_fields,
        "matched_terms": _dedupe_preserve_order(matched_terms),
        "location": locations[0] if locations else "",
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": salary_currency,
        "salary_type": salary_type,
        "salary_display": _format_salary_display(
            salary_min,
            salary_max,
            salary_currency,
            salary_type,
        ),
        "openings_count": _stringify_optional(
            _get_entity_value(entity, "numberOfOpenings", "number_of_openings")
        ),
        "employment_type": _normalize_enum_label(
            _get_entity_value(entity, "jobType", "job_type")
        ),
        "seniority_level": _normalize_enum_label(
            _get_entity_value(entity, "seniorityLevel", "seniority_level")
        ),
        "experience_required_years": _stringify_optional(
            _get_entity_value(entity, "minWorkExpYear", "min_work_exp_year")
        ),
        "management_responsibility": _normalize_enum_label(
            _get_entity_value(entity, "numberOfManagement", "number_of_management")
        ),
        "tags": ", ".join(tags),
        "content_updated_at": _get_entity_value(
            entity,
            "contentUpdatedAt",
            "content_updated_at",
        ),
    }


def _build_cake_job_url(company_path: str, job_path: str) -> str:
    return f"https://www.cake.me/companies/{company_path}/jobs/{job_path}"


def _build_cake_company_url(company_path: str) -> str:
    return f"https://www.cake.me/companies/{company_path}"


def _stringify_optional(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _get_entity_value(entity: dict, *keys: str) -> str:
    for key in keys:
        value = entity.get(key)
        if value is None:
            continue
        return str(value)
    return ""


def _get_entity_list(entity: dict, *keys: str) -> list[str]:
    for key in keys:
        value = entity.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]
    return []


def _normalize_enum_label(value: str | None) -> str:
    if not value:
        return ""
    mapping = {
        "full_time": "full_time",
        "part_time": "part_time",
        "contract": "contract",
        "internship": "internship",
        "temporary": "temporary",
        "entry_level": "entry_level",
        "mid_senior_level": "mid_senior_level",
        "associate": "associate",
        "director": "director",
        "internship_level": "internship_level",
        "none": "none",
    }
    return mapping.get(value, value)


def _format_salary_display(
    salary_min: str,
    salary_max: str,
    salary_currency: str,
    salary_type: str,
) -> str:
    if not (salary_min or salary_max):
        return ""

    range_display = salary_min
    if salary_max:
        range_display = f"{salary_min} - {salary_max}" if salary_min else salary_max

    parts = [range_display]
    if salary_currency:
        parts.append(salary_currency)
    if salary_type:
        parts.append(salary_type)
    return " ".join(part for part in parts if part)


def _fetch_search_api_page(
    keyword: str,
    page_number: int,
    per_page: int,
) -> dict | None:
    request_body = json.dumps(
        {
            "query": keyword.strip(),
            "filters": {"professions": ["it"]},
            "sort_by": "popularity",
            "page": page_number,
            "per_page": per_page,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        CAKE_CLIENT_SEARCH_API_URL,
        data=request_body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://www.cake.me",
            "Referer": _build_search_page_url(keyword, page_number),
            "User-Agent": "search-crawler/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read().decode(charset, errors="replace")
    except Exception:
        return None

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _build_pagination_links(keyword: str, current_page: int, response: dict) -> list[str]:
    total_pages = response.get("total_pages")
    if not isinstance(total_pages, int):
        return []
    if current_page >= total_pages:
        return []
    return [_build_search_page_url(keyword, current_page + 1)]


def _build_search_page_url(keyword: str, page_number: int) -> str:
    encoded_keyword = quote(keyword.strip(), safe="")
    if encoded_keyword:
        base_url = CAKE_IT_JOBS_SEARCH_URL_TEMPLATE.format(keyword=encoded_keyword)
    else:
        base_url = "https://www.cake.me/jobs/for-it"

    if page_number <= 1:
        return base_url
    return f"{base_url}?page={page_number}"
