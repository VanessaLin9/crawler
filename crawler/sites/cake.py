from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, urlparse

from crawler.parser import parse_html_document
from crawler.sites.base import ParsedPage, SiteAdapter
from crawler.url_utils import normalize_url

CAKE_IT_JOBS_URL = "https://www.cake.me/jobs/for-it?ref=navs_job_search_it"
CAKE_IT_JOBS_SEARCH_URL_TEMPLATE = "https://www.cake.me/jobs/{keyword}/for-it"
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

    def __init__(self, keyword: str = "") -> None:
        encoded_keyword = quote(keyword.strip(), safe="")
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
        parser = _CakeJobCardParser(base_url=url)
        parser.feed(html)
        parser.close()
        search_terms = _expand_search_terms(keyword)

        matches = [
            _job_to_match(job, keyword, search_terms)
            for job in parser.jobs
            if _job_matches_keyword(job, search_terms)
        ]

        return ParsedPage(
            title=document.title,
            meta_description=document.meta_description,
            links=document.links,
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
