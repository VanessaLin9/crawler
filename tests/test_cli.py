import argparse
import os
import unittest
from unittest.mock import patch

from crawler.cli import (
    ALL_SITES_TOKEN,
    ENABLED_SITES_ENV_VAR,
    SiteRunFailed,
    SiteRunSummary,
    _default_google_sheet_name,
    _execute_requested_runs,
    _extract_crawl_issues,
    _format_run_summary_prefix,
    _list_cli_sites,
    _parse_keywords_arg,
    _raise_for_failed_runs,
    _resolve_google_sheet_name,
    _resolve_output_path,
    _keyword_output_slug,
    _resolve_requested_keywords,
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

    def test_resolve_requested_sites_uses_enabled_sites_subset_for_all_mode(self) -> None:
        self.assertEqual(
            _resolve_requested_sites("all", enabled_sites_env="yourator, cake"),
            ["cake", "yourator"],
        )

    def test_resolve_requested_sites_rejects_unknown_enabled_site(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "contains unsupported providers",
        ):
            _resolve_requested_sites("all", enabled_sites_env="cake,linkedin")

    def test_resolve_requested_sites_rejects_empty_enabled_sites_for_all_mode(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "did not enable any supported providers",
        ):
            _resolve_requested_sites("all", enabled_sites_env="  ,  ")

    def test_resolve_requested_sites_allows_single_site_when_not_enabled(self) -> None:
        self.assertEqual(
            _resolve_requested_sites("104", enabled_sites_env="cake,yourator"),
            ["104"],
        )

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

    def test_resolve_output_path_adds_keyword_suffix_for_multi_keyword_all_mode(
        self,
    ) -> None:
        self.assertEqual(
            _resolve_output_path(
                "data/results.jsonl",
                "cake",
                multi_site=True,
                keyword="後端",
                multi_keyword=True,
            ),
            "data/results-cake-後端.jsonl",
        )

    def test_resolve_output_path_slugifies_unsafe_keyword_characters(self) -> None:
        self.assertEqual(_keyword_output_slug("AI Agent"), "AI-Agent")
        self.assertEqual(_keyword_output_slug("foo/bar"), "foo-bar")
        self.assertEqual(
            _resolve_output_path(
                "data/results.jsonl",
                "cake",
                multi_site=True,
                keyword="AI Agent",
                multi_keyword=True,
            ),
            "data/results-cake-AI-Agent.jsonl",
        )

    def test_resolve_output_path_adds_site_and_keyword_for_single_site_multi_keyword(
        self,
    ) -> None:
        self.assertEqual(
            _resolve_output_path(
                "data/results.jsonl",
                "cake",
                multi_site=False,
                keyword="後端",
                multi_keyword=True,
            ),
            "data/results-cake-後端.jsonl",
        )

    def test_keyword_output_slug_rejects_empty_slug(self) -> None:
        with self.assertRaisesRegex(SystemExit, "empty output path suffix"):
            _keyword_output_slug("   ")

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

    def test_resolve_requested_sites_reads_enabled_sites_from_env_by_default(self) -> None:
        with patch.dict(os.environ, {ENABLED_SITES_ENV_VAR: "104"}, clear=False):
            self.assertEqual(_resolve_requested_sites("all"), ["104"])

    def test_execute_requested_runs_continues_after_one_provider_failure(self) -> None:
        args = argparse.Namespace(keyword="後端", output="data/results.jsonl")

        with patch(
            "crawler.cli._run_site",
            side_effect=[
                SiteRunFailed(
                    SiteRunSummary(
                        site="cake",
                        keyword="後端",
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
                    keyword="後端",
                    output_path="data/results-104.jsonl",
                    crawled_pages=3,
                    records_found=8,
                ),
            ],
        ) as run_site:
            summaries = _execute_requested_runs(args, ["cake", "104"], ["後端"])

        self.assertEqual(run_site.call_count, 2)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].site, "cake")
        self.assertEqual(summaries[0].keyword, "後端")
        self.assertEqual(summaries[0].error, "cake failed")
        self.assertEqual(summaries[0].output_path, "data/results-cake.jsonl")
        self.assertEqual(summaries[0].appended_count, 3)
        self.assertEqual(summaries[0].sheet_name, "cake_jobs")
        self.assertEqual(summaries[1].site, "104")
        self.assertEqual(summaries[1].records_found, 8)

    def test_execute_requested_runs_uses_keyword_outer_site_inner_order(self) -> None:
        args = argparse.Namespace(keyword="", output="data/results.jsonl")
        calls: list[tuple[str, str]] = []

        def record_run(
            run_args: argparse.Namespace,
            site: str,
            *,
            multi_site: bool,
            multi_keyword: bool,
        ) -> SiteRunSummary:
            calls.append((run_args.keyword, site))
            return SiteRunSummary(
                site=site,
                keyword=run_args.keyword,
                output_path=f"data/results-{site}-{run_args.keyword}.jsonl",
                crawled_pages=1,
                records_found=1,
            )

        with patch("crawler.cli._run_site", side_effect=record_run):
            summaries = _execute_requested_runs(
                args,
                ["cake", "104"],
                ["後端", "全端"],
            )

        self.assertEqual(
            calls,
            [
                ("後端", "cake"),
                ("後端", "104"),
                ("全端", "cake"),
                ("全端", "104"),
            ],
        )
        self.assertEqual(len(summaries), 4)
        self.assertEqual(summaries[2].keyword, "全端")
        self.assertEqual(summaries[2].site, "cake")

    def test_execute_requested_runs_continues_after_keyword_run_failure(self) -> None:
        args = argparse.Namespace(keyword="", output="data/results.jsonl")

        with patch(
            "crawler.cli._run_site",
            side_effect=[
                SiteRunFailed(
                    SiteRunSummary(
                        site="cake",
                        keyword="後端",
                        output_path="data/results-cake-後端.jsonl",
                        crawled_pages=0,
                        records_found=0,
                    ),
                    "cake failed",
                ),
                SiteRunSummary(
                    site="cake",
                    keyword="全端",
                    output_path="data/results-cake-全端.jsonl",
                    crawled_pages=2,
                    records_found=4,
                ),
            ],
        ):
            summaries = _execute_requested_runs(args, ["cake"], ["後端", "全端"])

        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].error, "cake failed")
        self.assertEqual(summaries[1].records_found, 4)

    def test_raise_for_failed_runs_raises_non_zero_exit(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            _raise_for_failed_runs(
                [
                    SiteRunSummary(
                        site="cake",
                        output_path="data/results-cake.jsonl",
                        crawled_pages=3,
                        records_found=8,
                    ),
                    SiteRunSummary(
                        site="104",
                        keyword="後端",
                        output_path="data/results-104.jsonl",
                        crawled_pages=3,
                        records_found=8,
                        error="104 failed",
                    ),
                ]
            )

        self.assertEqual(exc.exception.code, 1)

    def test_raise_for_failed_runs_allows_successful_multi_site_run(self) -> None:
        _raise_for_failed_runs(
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

    def test_format_run_summary_prefix_for_multi_keyword(self) -> None:
        summary = SiteRunSummary(
            site="cake",
            keyword="全端",
            output_path="data/results-cake-全端.jsonl",
            crawled_pages=1,
            records_found=1,
        )
        self.assertEqual(
            _format_run_summary_prefix(summary, show_run_prefix=True, multi_keyword=True),
            "全端 / cake: ",
        )

    def test_resolve_requested_keywords_uses_positional_keyword(self) -> None:
        self.assertEqual(_resolve_requested_keywords("後端", None), ["後端"])

    def test_resolve_requested_keywords_parses_comma_separated_keywords(self) -> None:
        self.assertEqual(
            _resolve_requested_keywords(None, "後端,全端,AI"),
            ["後端", "全端", "AI"],
        )

    def test_resolve_requested_keywords_trims_whitespace(self) -> None:
        self.assertEqual(
            _resolve_requested_keywords(None, "後端, 全端, AI"),
            ["後端", "全端", "AI"],
        )

    def test_resolve_requested_keywords_rejects_empty_keywords_arg(self) -> None:
        with self.assertRaisesRegex(SystemExit, "did not resolve to any keywords"):
            _resolve_requested_keywords(None, ",, ")

    def test_resolve_requested_keywords_rejects_positional_and_flag_together(self) -> None:
        with self.assertRaisesRegex(SystemExit, "not both"):
            _resolve_requested_keywords("後端", "全端,AI")

    def test_resolve_requested_keywords_rejects_positional_and_empty_keywords_flag(
        self,
    ) -> None:
        with self.assertRaisesRegex(SystemExit, "not both"):
            _resolve_requested_keywords("後端", ",,")

    def test_resolve_requested_keywords_requires_keyword_source(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "site and keyword are required unless --list-sites is used",
        ):
            _resolve_requested_keywords(None, None)

    def test_parse_keywords_arg_returns_empty_list_for_none(self) -> None:
        self.assertEqual(_parse_keywords_arg(None), [])


if __name__ == "__main__":
    unittest.main()
