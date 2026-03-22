from __future__ import annotations

from dataclasses import dataclass

from crawler.settings import (
    DEFAULT_DELAY_SECONDS,
    DEFAULT_MAX_PAGES,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_PER_PAGE,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
)


@dataclass(slots=True)
class CrawlConfig:
    site: str
    keyword: str
    max_pages: int = DEFAULT_MAX_PAGES
    per_page: int = DEFAULT_PER_PAGE
    delay_seconds: float = DEFAULT_DELAY_SECONDS
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    output_path: str = DEFAULT_OUTPUT_PATH
    user_agent: str = DEFAULT_USER_AGENT
    search_url_template: str | None = None
