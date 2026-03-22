from __future__ import annotations

import time
from collections import deque

from crawler.core.fetcher import build_session, fetch_html
from crawler.core.models import CrawlConfig
from crawler.core.output import write_results
from crawler.sites.registry import build_site_adapter
from crawler.url_utils import normalize_url, same_domain


def crawl(config: CrawlConfig) -> list[dict]:
    adapter = build_site_adapter(config)
    pending = deque(_normalize_start_urls(adapter.build_start_urls(config.keyword)))
    allowed_domains = adapter.get_allowed_domains()
    visited: set[str] = set()
    results: list[dict] = []
    session = build_session(config.user_agent)

    while pending and len(results) < config.max_pages:
        url = pending.popleft()
        if url in visited:
            continue

        visited.add(url)

        try:
            response = fetch_html(session, url, timeout=config.timeout_seconds)
            parsed = adapter.parse_page(url, response.text, config.keyword)
            record = {
                "site": config.site,
                "keyword": config.keyword,
                "url": url,
                "status_code": response.status_code,
                "title": parsed.title,
                "meta_description": parsed.meta_description,
                "matches": parsed.matches,
                "links": parsed.links,
            }
            results.append(record)
        except Exception as exc:
            results.append(
                {
                    "site": config.site,
                    "keyword": config.keyword,
                    "url": url,
                    "error": str(exc),
                }
            )
            time.sleep(config.delay_seconds)
            continue

        for link in parsed.links:
            if (
                link not in visited
                and same_domain(link, allowed_domains)
                and adapter.should_visit(link)
            ):
                pending.append(link)

        time.sleep(config.delay_seconds)

    write_results(results, config.output_path)
    return results


def _normalize_start_urls(urls: list[str]) -> list[str]:
    normalized_urls: list[str] = []
    for url in urls:
        normalized = normalize_url(url)
        if not normalized:
            raise ValueError(f"Invalid start URL: {url}")
        normalized_urls.append(normalized)
    return normalized_urls
