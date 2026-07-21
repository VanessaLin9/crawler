from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from crawler.core.fetcher import FetchResponse, FetchSession, fetch_html


@dataclass(slots=True)
class ParsedPage:
    title: str = ""
    meta_description: str = ""
    links: list[str] = field(default_factory=list)
    matches: list[dict] = field(default_factory=list)


class SiteAdapter(ABC):
    name: str

    @abstractmethod
    def build_start_urls(self, keyword: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_allowed_domains(self) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        raise NotImplementedError

    def fetch_page(
        self,
        session: FetchSession,
        url: str,
        timeout: float,
    ) -> FetchResponse:
        """Fetch one logical page. Default: HTML GET. Override for API-only sites."""
        return fetch_html(session, url, timeout=timeout)

    def should_visit(self, url: str) -> bool:
        return True

