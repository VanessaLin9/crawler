import unittest

from crawler.cli import (
    _default_google_sheet_name,
    _extract_crawl_issues,
    _resolve_google_sheet_name,
)


class CliTests(unittest.TestCase):
    def test_default_google_sheet_name_uses_site(self) -> None:
        self.assertEqual(_default_google_sheet_name("cake"), "cake_jobs")
        self.assertEqual(_default_google_sheet_name("104"), "104_jobs")

    def test_resolve_google_sheet_name_prefers_explicit_flag(self) -> None:
        self.assertEqual(
            _resolve_google_sheet_name(
                site="104",
                explicit_name="custom_jobs",
                env_name="cake_jobs",
            ),
            "custom_jobs",
        )

    def test_resolve_google_sheet_name_uses_custom_env_value(self) -> None:
        self.assertEqual(
            _resolve_google_sheet_name(
                site="104",
                explicit_name=None,
                env_name="shared_jobs",
            ),
            "shared_jobs",
        )

    def test_resolve_google_sheet_name_uses_site_default_for_legacy_env(self) -> None:
        self.assertEqual(
            _resolve_google_sheet_name(
                site="104",
                explicit_name=None,
                env_name="cake_jobs",
            ),
            "104_jobs",
        )

    def test_extract_crawl_issues_includes_page_url(self) -> None:
        self.assertEqual(
            _extract_crawl_issues(
                [
                    {
                        "url": "https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF",
                        "error": "104 search API request failed after establishing an anonymous session. Cookie/session behavior may have changed.",
                    }
                ]
            ),
            [
                "104 search API request failed after establishing an anonymous session. Cookie/session behavior may have changed. (page: https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF)"
            ],
        )


if __name__ == "__main__":
    unittest.main()
