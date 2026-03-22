import unittest

from crawler.url_utils import normalize_url, same_domain


class UrlUtilsTests(unittest.TestCase):
    def test_normalize_url_joins_relative_urls(self) -> None:
        self.assertEqual(
            normalize_url("/docs", base_url="https://example.com/start"),
            "https://example.com/docs",
        )

    def test_normalize_url_removes_fragments(self) -> None:
        self.assertEqual(
            normalize_url("https://example.com/path#section"),
            "https://example.com/path",
        )

    def test_normalize_url_rejects_non_http_urls(self) -> None:
        self.assertIsNone(normalize_url("mailto:test@example.com"))

    def test_same_domain_matches_allowed_host(self) -> None:
        self.assertTrue(
            same_domain("https://example.com/about", {"example.com"}),
        )

    def test_same_domain_rejects_other_hosts(self) -> None:
        self.assertFalse(
            same_domain("https://other.example.com/about", {"example.com"}),
        )


if __name__ == "__main__":
    unittest.main()
