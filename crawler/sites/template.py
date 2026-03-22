from __future__ import annotations

from urllib.parse import quote_plus

from crawler.parser import parse_html_document
from crawler.sites.base import ParsedPage, SiteAdapter


class TemplateSiteAdapter(SiteAdapter):
    name = "replace-me"

    def build_start_urls(self, keyword: str) -> list[str]:
        encoded_keyword = quote_plus(keyword)
        return [f"https://example.com/search?q={encoded_keyword}"]

    def get_allowed_domains(self) -> set[str]:
        return {"example.com"}

    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        document = parse_html_document(url, html)

        # Replace this generic behavior with selectors that match the real site.
        return ParsedPage(
            title=document.title,
            meta_description=document.meta_description,
            links=document.links,
            matches=[],
        )

    def should_visit(self, url: str) -> bool:
        return "/search" in url or "/article/" in url
