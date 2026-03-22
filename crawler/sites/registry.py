from __future__ import annotations

from typing import Callable

from crawler.core.models import CrawlConfig
from crawler.sites.cake import CakeItJobsAdapter
from crawler.sites.base import SiteAdapter
from crawler.sites.generic import build_generic_adapter

AdapterFactory = Callable[[CrawlConfig], SiteAdapter]


def _build_generic_from_config(config: CrawlConfig) -> SiteAdapter:
    return build_generic_adapter(config.search_url_template)


REGISTRY: dict[str, AdapterFactory] = {
    "cake": lambda config: CakeItJobsAdapter(config.keyword),
    "generic": _build_generic_from_config,
}


def build_site_adapter(config: CrawlConfig) -> SiteAdapter:
    try:
        factory = REGISTRY[config.site]
    except KeyError as exc:
        available = ", ".join(sorted(REGISTRY))
        raise ValueError(
            f"Unknown site '{config.site}'. Available sites: {available}"
        ) from exc
    return factory(config)


def list_sites() -> list[str]:
    return sorted(REGISTRY)
