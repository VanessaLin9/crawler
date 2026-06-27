from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser

from crawler.sites.base import ParsedPage, SiteAdapter

WWR_DOMAIN = "weworkremotely.com"
WWR_BACKEND_FEED = (
    "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss"
)
WWR_FULL_STACK_FEED = (
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"
)
WWR_FRONT_END_FEED = (
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss"
)

CATEGORY_KEYWORD_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "後端",
        WWR_BACKEND_FEED,
        ("後端", "backend", "back-end", "back end"),
    ),
    (
        "全端",
        WWR_FULL_STACK_FEED,
        ("全端", "fullstack", "full-stack", "full stack"),
    ),
    (
        "前端",
        WWR_FRONT_END_FEED,
        ("前端", "frontend", "front-end", "front end"),
    ),
)

AI_KEYWORDS: tuple[str, ...] = (
    "AI",
    "人工智慧",
    "生成式 AI",
    "Artificial Intelligence",
    "Generative AI",
    "GenAI",
    "LLM",
    "RAG",
    "AI Agent",
    "Agentic",
    "MCP",
    "Tool Calling",
    "Prompt Engineering",
)

AI_DESCRIPTION_HIGH_SIGNAL_TERMS: tuple[str, ...] = (
    "Generative AI",
    "GenAI",
    "LLM",
    "Large Language Models",
    "Large Language Model",
    "RAG",
    "Retrieval Augmented Generation",
    "AI Agents",
    "AI Agent",
    "Agentic",
    "MCP",
    "Model Context Protocol",
    "Tool Calling",
    "Function Calling",
    "Prompt Engineering",
)

SUPPORTED_KEYWORD_GROUP_LABELS: tuple[str, ...] = (
    "後端 (backend)",
    "全端 (fullstack)",
    "前端 (frontend)",
    "AI (AI, LLM, RAG, GenAI, ...)",
)

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_keyword_alias(keyword: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", keyword.strip()).casefold()


def resolve_keyword_group(keyword: str) -> str:
    normalized_keyword = _normalize_keyword_alias(keyword)
    if not normalized_keyword:
        raise unsupported_keyword_error(keyword)

    for group_name, _, aliases in CATEGORY_KEYWORD_GROUPS:
        normalized_aliases = {_normalize_keyword_alias(alias) for alias in aliases}
        if normalized_keyword in normalized_aliases:
            return group_name

    normalized_ai_keywords = {_normalize_keyword_alias(alias) for alias in AI_KEYWORDS}
    if normalized_keyword in normalized_ai_keywords:
        return "ai"

    raise unsupported_keyword_error(keyword)


def resolve_feed_urls(keyword: str) -> list[str]:
    group = resolve_keyword_group(keyword)
    if group == "ai":
        return [WWR_BACKEND_FEED, WWR_FULL_STACK_FEED]

    for group_name, feed_url, _ in CATEGORY_KEYWORD_GROUPS:
        if group_name == group:
            return [feed_url]

    raise AssertionError(f"Unhandled WWR keyword group: {group}")


def unsupported_keyword_error(keyword: str) -> ValueError:
    supported_groups = ", ".join(SUPPORTED_KEYWORD_GROUP_LABELS)
    return ValueError(
        f"Unsupported WWR keyword '{keyword}'. "
        f"Supported keyword groups: {supported_groups}"
    )


class WwrJobsAdapter(SiteAdapter):
    name = "wwr"

    def __init__(self, keyword: str = "") -> None:
        self.keyword = keyword.strip()

    def build_start_urls(self, keyword: str) -> list[str]:
        return resolve_feed_urls(keyword)

    def get_allowed_domains(self) -> set[str]:
        return {WWR_DOMAIN, f"www.{WWR_DOMAIN}"}

    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        matches = parse_rss_feed(html, keyword)
        return ParsedPage(matches=matches)

    def should_visit(self, url: str) -> bool:
        return False


class _PlainTextHTMLParser(HTMLParser):
    _BLOCK_TAGS = {"p", "br", "li", "div", "h1", "h2", "h3", "ul", "ol", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._ignore_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._ignore_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._ignore_depth = max(0, self._ignore_depth - 1)
            return
        if tag in {"p", "li", "div", "h1", "h2", "h3", "tr"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignore_depth:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        joined = " ".join(self._chunks)
        return _WHITESPACE_PATTERN.sub(" ", joined).strip()


class _CompanyURLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.company_url = ""
        self._await_company_anchor = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a" or not self._await_company_anchor or self.company_url:
            return
        href = dict(attrs).get("href", "").strip()
        if href and "weworkremotely.com" not in href.casefold():
            self.company_url = href
            self._await_company_anchor = False

    def handle_data(self, data: str) -> None:
        if data.strip().startswith("URL:"):
            self._await_company_anchor = True


def parse_rss_feed(xml_text: str, keyword: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    keyword_group = resolve_keyword_group(keyword)
    matches: list[dict] = []

    for item in root.findall("./channel/item"):
        match = _parse_rss_item(item, keyword_group=keyword_group)
        if match is not None:
            matches.append(match)

    return matches


def _parse_rss_item(item: ET.Element, *, keyword_group: str) -> dict | None:
    job_url = _resolve_job_url(item)
    if not job_url:
        return None

    raw_title = _child_text(item, "title")
    title, company_name = _split_title_company(raw_title)
    description_html = _child_text(item, "description")
    category = _child_text(item, "category")
    skills = _child_text(item, "skills")
    summary = _html_to_plain_text(description_html)

    matched_fields: list[str] = []
    matched_terms: list[str] = []
    if keyword_group == "ai":
        ai_match = _match_ai_item(title, skills, summary)
        if ai_match is None:
            return None
        matched_fields, matched_terms = ai_match
    elif category:
        matched_fields = ["category"]
        matched_terms = [category]

    return {
        "type": "job_card",
        "job_url": job_url,
        "title": title,
        "company_name": company_name,
        "company_url": _extract_company_url(description_html),
        "location": _build_location(
            _child_text(item, "region"),
            _child_text(item, "state"),
            _child_text(item, "country"),
        ),
        "employment_type": _child_text(item, "type"),
        "tags": _build_tags(category, skills),
        "summary": summary,
        "content_updated_at": _parse_pub_date(_child_text(item, "pubDate")),
        "matched_fields": matched_fields,
        "matched_terms": matched_terms,
        "salary_min": "",
        "salary_max": "",
        "salary_currency": "",
        "salary_type": "",
        "salary_display": "",
        "openings_count": "",
        "seniority_level": "",
        "experience_required_years": "",
        "management_responsibility": "",
    }


def _child_text(item: ET.Element, tag: str) -> str:
    child = item.find(tag)
    if child is None:
        return ""
    return (child.text or "").strip()


def _resolve_job_url(item: ET.Element) -> str:
    link = _child_text(item, "link")
    if link:
        return link
    return _child_text(item, "guid")


def _split_title_company(raw_title: str) -> tuple[str, str]:
    if ":" not in raw_title:
        return raw_title.strip(), ""
    company_name, title = raw_title.split(":", 1)
    return title.strip(), company_name.strip()


def _build_location(region: str, state: str, country: str) -> str:
    parts: list[str] = []
    for value in (region, state, country):
        normalized = value.strip()
        if normalized and normalized not in parts:
            parts.append(normalized)
    return " | ".join(parts)


def _build_tags(category: str, skills: str) -> str:
    tags: list[str] = []
    for value in (category, skills):
        normalized = value.strip()
        if normalized and normalized not in tags:
            tags.append(normalized)
    return ", ".join(tags)


def _html_to_plain_text(description_html: str) -> str:
    if not description_html.strip():
        return ""
    parser = _PlainTextHTMLParser()
    parser.feed(unescape(description_html))
    parser.close()
    return parser.get_text()


def _extract_company_url(description_html: str) -> str:
    if not description_html.strip():
        return ""
    parser = _CompanyURLParser()
    parser.feed(unescape(description_html))
    parser.close()
    return parser.company_url


def _parse_pub_date(raw_value: str) -> str:
    raw_value = raw_value.strip()
    if not raw_value:
        return ""
    try:
        return parsedate_to_datetime(raw_value).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _match_ai_item(
    title: str,
    skills: str,
    summary: str,
) -> tuple[list[str], list[str]] | None:
    title_hits = _find_matching_terms(title, AI_KEYWORDS)
    skills_hits = _find_matching_terms(skills, AI_KEYWORDS)
    description_hits = _find_matching_terms(summary, AI_DESCRIPTION_HIGH_SIGNAL_TERMS)

    if not title_hits and not skills_hits and not description_hits:
        return None

    matched_fields: list[str] = []
    matched_terms: list[str] = []
    if title_hits:
        matched_fields.append("title")
        matched_terms.extend(title_hits)
    if skills_hits:
        matched_fields.append("skills")
        matched_terms.extend(skills_hits)
    if description_hits:
        matched_fields.append("description")
        matched_terms.extend(description_hits)

    return matched_fields, _dedupe_preserve_order(matched_terms)


def _find_matching_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    if not text.strip():
        return []

    hits: list[str] = []
    for term in terms:
        if _compile_term_pattern(term).search(text):
            hits.append(term)
    return hits


def _compile_term_pattern(term: str) -> re.Pattern[str]:
    stripped = term.strip()
    if not stripped:
        return re.compile(r"a^")
    if stripped.isascii():
        escaped = re.escape(stripped)
        return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.IGNORECASE)
    return re.compile(re.escape(stripped), re.IGNORECASE)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
