from __future__ import annotations

import re

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
        return ParsedPage()

    def should_visit(self, url: str) -> bool:
        return False
