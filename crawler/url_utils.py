from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse


def normalize_url(url: str, base_url: str | None = None) -> str | None:
    if not url:
        return None

    absolute = urljoin(base_url, url) if base_url else url
    parsed = urlparse(absolute)

    if parsed.scheme not in {"http", "https"}:
        return None

    clean_path = parsed.path or "/"
    clean_fragment = ""
    clean_query = parsed.query

    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            clean_query,
            clean_fragment,
        )
    )


def same_domain(url: str, allowed_domains: set[str]) -> bool:
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    return hostname.lower() in {domain.lower() for domain in allowed_domains}

