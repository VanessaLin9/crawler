import unittest

from crawler.cli import _default_google_sheet_name, _resolve_google_sheet_name


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


if __name__ == "__main__":
    unittest.main()
