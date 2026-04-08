import argparse
import os
import unittest
from unittest.mock import patch

from crawler.cli import (
    ALL_SITES_TOKEN,
    SiteRunFailed,
    SiteRunSummary,
    _default_google_sheet_name,
    _execute_requested_sites,
    _extract_crawl_issues,
    _list_cli_sites,
    _raise_for_failed_sites,
    _resolve_google_sheet_name,
    _resolve_output_path,
    _resolve_requested_sites,
    _validate_runtime_args,
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

    def test_list_cli_sites_includes_all_mode(self) -> None:
        self.assertEqual(_list_cli_sites()[0], ALL_SITES_TOKEN)

    def test_resolve_requested_sites_expands_all_mode(self) -> None:
        self.assertEqual(_resolve_requested_sites("all"), ["cake", "104", "yourator"])

    def test_resolve_output_path_adds_site_suffix_for_multi_site(self) -> None:
        self.assertEqual(
            _resolve_output_path("data/results.jsonl", "cake", multi_site=True),
            "data/results-cake.jsonl",
        )

    def test_resolve_output_path_keeps_single_site_path(self) -> None:
        self.assertEqual(
            _resolve_output_path("data/results.jsonl", "cake", multi_site=False),
            "data/results.jsonl",
        )

    def test_validate_runtime_args_rejects_shared_sheet_in_all_mode(self) -> None:
        args = argparse.Namespace(
            sync_google_sheet=True,
            google_sheet_id="sheet123",
            send_email_notification=False,
            send_machine_email_notification=False,
            google_sheet_name="shared_jobs",
        )

        with self.assertRaisesRegex(
            SystemExit,
            "does not support a shared worksheet name",
        ):
            _validate_runtime_args(args, multi_site=True)

    def test_validate_runtime_args_rejects_custom_env_sheet_in_all_mode(self) -> None:
        args = argparse.Namespace(
            sync_google_sheet=True,
            google_sheet_id="sheet123",
            send_email_notification=False,
            send_machine_email_notification=False,
            google_sheet_name=None,
        )

        with patch.dict(os.environ, {"GOOGLE_SHEET_NAME": "shared_jobs"}, clear=False):
            with self.assertRaisesRegex(
                SystemExit,
                "does not support a shared worksheet name",
            ):
                _validate_runtime_args(args, multi_site=True)

    def test_validate_runtime_args_all_mode_allows_custom_env_when_not_syncing(self) -> None:
        args = argparse.Namespace(
            sync_google_sheet=False,
            google_sheet_id=None,
            send_email_notification=False,
            send_machine_email_notification=False,
            google_sheet_name=None,
        )

        with patch.dict(os.environ, {"GOOGLE_SHEET_NAME": "shared_jobs"}, clear=False):
            _validate_runtime_args(args, multi_site=True)

    def test_execute_requested_sites_continues_after_one_provider_failure(self) -> None:
        args = argparse.Namespace(output="data/results.jsonl")

        with patch(
            "crawler.cli._run_site",
            side_effect=[
                SiteRunFailed(
                    SiteRunSummary(
                        site="cake",
                        output_path="data/results-cake.jsonl",
                        crawled_pages=4,
                        records_found=10,
                        appended_count=3,
                        skipped_count=7,
                        sheet_name="cake_jobs",
                    ),
                    "cake failed",
                ),
                SiteRunSummary(
                    site="104",
                    output_path="data/results-104.jsonl",
                    crawled_pages=3,
                    records_found=8,
                ),
            ],
        ):
            summaries = _execute_requested_sites(args, ["cake", "104"])

        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].site, "cake")
        self.assertEqual(summaries[0].error, "cake failed")
        self.assertEqual(summaries[0].output_path, "data/results-cake.jsonl")
        self.assertEqual(summaries[0].appended_count, 3)
        self.assertEqual(summaries[0].sheet_name, "cake_jobs")
        self.assertEqual(summaries[1].site, "104")
        self.assertEqual(summaries[1].records_found, 8)

    def test_raise_for_failed_sites_raises_non_zero_exit(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            _raise_for_failed_sites(
                [
                    SiteRunSummary(
                        site="cake",
                        output_path="data/results-cake.jsonl",
                        crawled_pages=3,
                        records_found=8,
                    ),
                    SiteRunSummary(
                        site="104",
                        output_path="data/results-104.jsonl",
                        crawled_pages=3,
                        records_found=8,
                        error="104 failed",
                    ),
                ]
            )

        self.assertEqual(exc.exception.code, 1)

    def test_raise_for_failed_sites_allows_successful_multi_site_run(self) -> None:
        _raise_for_failed_sites(
            [
                SiteRunSummary(
                    site="cake",
                    output_path="data/results-cake.jsonl",
                    crawled_pages=3,
                    records_found=8,
                ),
                SiteRunSummary(
                    site="104",
                    output_path="data/results-104.jsonl",
                    crawled_pages=3,
                    records_found=8,
                ),
            ]
        )


if __name__ == "__main__":
    unittest.main()
