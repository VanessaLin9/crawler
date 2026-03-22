from __future__ import annotations

import argparse

from crawler.core.models import CrawlConfig
from crawler.core.spider import crawl
from crawler.sites.registry import list_sites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyword-based website crawler")
    parser.add_argument("site", nargs="?")
    parser.add_argument("keyword", nargs="?")
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output", default="data/results.jsonl")
    parser.add_argument("--user-agent", default="search-crawler/0.1")
    parser.add_argument("--search-url-template")
    parser.add_argument("--list-sites", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.list_sites:
        for site in list_sites():
            print(site)
        return

    if not args.site or not args.keyword:
        raise SystemExit("site and keyword are required unless --list-sites is used")

    config = CrawlConfig(
        site=args.site,
        keyword=args.keyword,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
        timeout_seconds=args.timeout,
        output_path=args.output,
        user_agent=args.user_agent,
        search_url_template=args.search_url_template,
    )
    crawl(config)


if __name__ == "__main__":
    main()
