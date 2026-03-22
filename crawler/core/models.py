from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CrawlConfig:
    site: str
    keyword: str
    max_pages: int = 20
    delay_seconds: float = 0.5
    timeout_seconds: float = 10.0
    output_path: str = "data/results.jsonl"
    user_agent: str = "search-crawler/0.1"
    search_url_template: str | None = None

