import unittest

from crawler.core.models import CrawlConfig
from crawler.sites.registry import build_site_adapter, list_sites


class SiteRegistryTests(unittest.TestCase):
    def test_list_sites_returns_registered_sites(self) -> None:
        self.assertEqual(list_sites(), ["cake", "generic"])

    def test_build_site_adapter_returns_generic_adapter(self) -> None:
        config = CrawlConfig(
            site="generic",
            keyword="test",
            search_url_template="https://example.com/search?q={keyword}",
        )
        adapter = build_site_adapter(config)
        self.assertEqual(adapter.name, "generic")

    def test_build_site_adapter_returns_cake_adapter(self) -> None:
        config = CrawlConfig(site="cake", keyword="python")
        adapter = build_site_adapter(config)
        self.assertEqual(adapter.name, "cake")


if __name__ == "__main__":
    unittest.main()
