from __future__ import annotations

from urllib.parse import quote_plus, urlparse

from crawler.parser import parse_html_document
from crawler.sites.base import ParsedPage, SiteAdapter


class GenericSearchAdapter(SiteAdapter):
    name = "generic"

    def __init__(self, search_url_template: str) -> None:
        if "{keyword}" not in search_url_template:
            raise ValueError(
                "The search URL template must include a {keyword} placeholder."
            )

        self.search_url_template = search_url_template
        example_url = search_url_template.format(keyword="example")
        hostname = urlparse(example_url).hostname
        if not hostname:
            raise ValueError(f"Invalid search URL template: {search_url_template}")
        self.allowed_domains = {hostname.lower()}

    def build_start_urls(self, keyword: str) -> list[str]:
        return [self.search_url_template.format(keyword=quote_plus(keyword))]

    def get_allowed_domains(self) -> set[str]:
        return self.allowed_domains

    def parse_page(self, url: str, html: str, keyword: str) -> ParsedPage:
        document = parse_html_document(url, html)
        lower_keyword = keyword.casefold()
        keyword_hits = document.text.casefold().count(lower_keyword)
        matches: list[dict] = []

        if keyword_hits > 0:
            matches.append(
                {
                    "type": "keyword_hit",
                    "keyword": keyword,
                    "count": keyword_hits,
                    "title": document.title,
                }
            )

        return ParsedPage(
            title=document.title,
            meta_description=document.meta_description,
            links=document.links,
            matches=matches,
        )


def build_generic_adapter(search_url_template: str | None) -> GenericSearchAdapter:
    if not search_url_template:
        raise ValueError(
            "The generic adapter requires --search-url-template, for example "
            "https://example.com/search?q={keyword}"
        )
    return GenericSearchAdapter(search_url_template=search_url_template)

