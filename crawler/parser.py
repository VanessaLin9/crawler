from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from crawler.url_utils import normalize_url


@dataclass(slots=True)
class HtmlDocument:
    title: str
    meta_description: str
    links: list[str]
    text: str


class _DocumentParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.in_title = False
        self.in_body = False
        self.title_chunks: list[str] = []
        self.body_chunks: list[str] = []
        self.links: list[str] = []
        self.meta_description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "body":
            self.in_body = True
        elif tag == "meta":
            if attributes.get("name", "").casefold() == "description":
                self.meta_description = (attributes.get("content") or "").strip()
        elif tag == "a":
            href = attributes.get("href")
            normalized = normalize_url(href or "", base_url=self.base_url)
            if normalized:
                self.links.append(normalized)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "body":
            self.in_body = False

    def handle_data(self, data: str) -> None:
        stripped = data.strip()
        if not stripped:
            return
        if self.in_title:
            self.title_chunks.append(stripped)
        if self.in_body:
            self.body_chunks.append(stripped)


def parse_html_document(url: str, html: str) -> HtmlDocument:
    parser = _DocumentParser(base_url=url)
    parser.feed(html)

    return HtmlDocument(
        title=" ".join(parser.title_chunks).strip(),
        meta_description=parser.meta_description,
        links=list(dict.fromkeys(parser.links)),
        text=" ".join(parser.body_chunks).strip(),
    )
