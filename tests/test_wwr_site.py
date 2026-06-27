import argparse
import unittest
from pathlib import Path
from unittest.mock import patch

import xml.etree.ElementTree as ET

from crawler.cli import (
    MULTI_SITE_EXCLUDED_SITES,
    _default_google_sheet_name,
    _execute_requested_runs,
    _list_cli_sites,
    _resolve_output_path,
    _resolve_requested_sites,
)
from crawler.core.fetcher import FetchResponse
from crawler.core.models import CrawlConfig
from crawler.core.spider import crawl
from crawler.records import flatten_job_records
from crawler.sites.registry import build_site_adapter, list_sites
from crawler.sites.wwr import (
    AI_KEYWORDS,
    WWR_BACKEND_FEED,
    WWR_FRONT_END_FEED,
    WWR_FULL_STACK_FEED,
    WwrJobsAdapter,
    _find_matching_terms,
    parse_rss_feed,
    resolve_feed_urls,
    resolve_keyword_group,
    unsupported_keyword_error,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "wwr"
BACKEND_SAMPLE_RSS = (FIXTURES_DIR / "backend_sample.rss").read_text(encoding="utf-8")
AI_FILTER_SAMPLE_RSS = (FIXTURES_DIR / "ai_filter_sample.rss").read_text(encoding="utf-8")
AI_DUPLICATE_FULLSTACK_RSS = (
    FIXTURES_DIR / "ai_duplicate_fullstack.rss"
).read_text(encoding="utf-8")


class WwrFeedSelectionTests(unittest.TestCase):
    def test_backend_aliases_resolve_to_backend_feed(self) -> None:
        aliases = ["後端", "backend", "back-end", "back end", "  BACK   END  "]
        for alias in aliases:
            with self.subTest(alias=alias):
                self.assertEqual(resolve_feed_urls(alias), [WWR_BACKEND_FEED])
                self.assertEqual(resolve_keyword_group(alias), "後端")

    def test_full_stack_aliases_resolve_to_full_stack_feed(self) -> None:
        aliases = ["全端", "fullstack", "full-stack", "full stack", "Full   Stack"]
        for alias in aliases:
            with self.subTest(alias=alias):
                self.assertEqual(resolve_feed_urls(alias), [WWR_FULL_STACK_FEED])
                self.assertEqual(resolve_keyword_group(alias), "全端")

    def test_front_end_aliases_resolve_to_front_end_feed(self) -> None:
        aliases = ["前端", "frontend", "front-end", "front end", "  FRONT   END  "]
        for alias in aliases:
            with self.subTest(alias=alias):
                self.assertEqual(resolve_feed_urls(alias), [WWR_FRONT_END_FEED])
                self.assertEqual(resolve_keyword_group(alias), "前端")

    def test_ai_aliases_resolve_to_backend_and_full_stack_feeds(self) -> None:
        for alias in AI_KEYWORDS:
            with self.subTest(alias=alias):
                self.assertEqual(
                    resolve_feed_urls(alias),
                    [WWR_BACKEND_FEED, WWR_FULL_STACK_FEED],
                )
                self.assertEqual(resolve_keyword_group(alias), "ai")

    def test_unsupported_keyword_raises_clear_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported WWR keyword 'devops'"):
            resolve_feed_urls("devops")

        error = unsupported_keyword_error("devops")
        self.assertIn("後端 (backend)", str(error))
        self.assertIn("全端 (fullstack)", str(error))
        self.assertIn("前端 (frontend)", str(error))
        self.assertIn("AI (AI, LLM, RAG, GenAI, ...)", str(error))

    def test_empty_keyword_raises_clear_value_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported WWR keyword"):
            resolve_feed_urls("   ")


class WwrAdapterSkeletonTests(unittest.TestCase):
    def test_build_start_urls_delegates_to_feed_resolver(self) -> None:
        adapter = WwrJobsAdapter("後端")
        self.assertEqual(adapter.build_start_urls("AI"), [WWR_BACKEND_FEED, WWR_FULL_STACK_FEED])

    def test_get_allowed_domains_includes_wwr_domain(self) -> None:
        adapter = WwrJobsAdapter()
        self.assertEqual(
            adapter.get_allowed_domains(),
            {"weworkremotely.com", "www.weworkremotely.com"},
        )

    def test_should_visit_returns_false(self) -> None:
        adapter = WwrJobsAdapter()
        self.assertFalse(
            adapter.should_visit(
                "https://weworkremotely.com/remote-jobs/example-company"
            )
        )

    def test_parse_page_returns_empty_parsed_page(self) -> None:
        adapter = WwrJobsAdapter("後端")
        parsed = adapter.parse_page(
            WWR_BACKEND_FEED,
            BACKEND_SAMPLE_RSS,
            "後端",
        )
        self.assertEqual(len(parsed.matches), 3)
        self.assertEqual(parsed.links, [])


class WwrRssMappingTests(unittest.TestCase):
    def test_parse_rss_feed_maps_title_company_location_and_tags(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        first = matches[0]

        self.assertEqual(first["title"], "Senior Backend Engineer")
        self.assertEqual(first["company_name"], "Acme Corp")
        self.assertEqual(
            first["job_url"],
            "https://weworkremotely.com/remote-jobs/acme-corp-senior-backend-engineer",
        )
        self.assertEqual(first["location"], "Anywhere in the World | California | USA")
        self.assertEqual(
            first["tags"],
            "Back-End Programming, Ruby, Rails, PostgreSQL",
        )
        self.assertEqual(first["employment_type"], "Full-Time")
        self.assertEqual(first["content_updated_at"], "2026-06-18")
        self.assertEqual(first["matched_fields"], ["category"])
        self.assertEqual(first["matched_terms"], ["Back-End Programming"])

    def test_parse_rss_feed_extracts_company_url_from_description(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        self.assertEqual(matches[0]["company_url"], "https://acme.example")
        self.assertEqual(matches[1]["company_url"], "")

    def test_parse_rss_feed_converts_html_description_to_full_plain_text(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        self.assertIn("Build & scale APIs.", matches[0]["summary"])
        self.assertNotIn("&amp;", matches[0]["summary"])
        self.assertNotIn("<p>", matches[0]["summary"])

    def test_parse_rss_feed_splits_title_without_colon(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        solo = matches[1]
        self.assertEqual(solo["title"], "Solo Founder Role")
        self.assertEqual(solo["company_name"], "")

    def test_parse_rss_feed_skips_items_without_job_url(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        titles = [match["title"] for match in matches]
        self.assertNotIn("Missing URL Job", titles)

    def test_parse_rss_feed_uses_guid_when_link_missing(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        guid_only = matches[2]
        self.assertEqual(guid_only["title"], "Platform Engineer")
        self.assertEqual(guid_only["company_name"], "Guid Only Corp")
        self.assertEqual(
            guid_only["job_url"],
            "https://weworkremotely.com/remote-jobs/guid-only-corp-platform-engineer",
        )

    def test_parse_rss_feed_leaves_blank_date_when_pubdate_malformed(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        self.assertEqual(matches[1]["content_updated_at"], "")
        self.assertEqual(matches[2]["content_updated_at"], "2026-06-19")

    def test_parse_rss_feed_preserves_item_order(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        self.assertEqual(
            [match["title"] for match in matches],
            ["Senior Backend Engineer", "Solo Founder Role", "Platform Engineer"],
        )

    def test_ai_keyword_group_filters_items_by_title_skills_and_description(self) -> None:
        matches = parse_rss_feed(AI_FILTER_SAMPLE_RSS, "AI")
        self.assertEqual(len(matches), 4)
        self.assertEqual(matches[0]["title"], "LLM Platform Engineer")
        self.assertEqual(matches[0]["matched_fields"], ["title"])
        self.assertEqual(matches[0]["matched_terms"], ["LLM"])

        skills_match = matches[1]
        self.assertEqual(skills_match["title"], "Backend Engineer")
        self.assertEqual(skills_match["matched_fields"], ["skills"])
        self.assertEqual(skills_match["matched_terms"], ["RAG"])

        description_match = matches[2]
        self.assertEqual(description_match["title"], "Software Engineer")
        self.assertEqual(description_match["matched_fields"], ["description"])
        self.assertEqual(description_match["matched_terms"], ["Generative AI"])

    def test_ai_filter_rejects_generic_ai_disclaimer_in_description_only(self) -> None:
        matches = parse_rss_feed(AI_FILTER_SAMPLE_RSS, "AI")
        titles = [match["title"] for match in matches]
        self.assertNotIn("Recruiting Coordinator", titles)

    def test_ai_filter_does_not_match_ai_inside_paid(self) -> None:
        matches = parse_rss_feed(AI_FILTER_SAMPLE_RSS, "AI")
        titles = [match["title"] for match in matches]
        self.assertNotIn("Accounts Payable Specialist", titles)

    def test_ai_filter_does_not_match_ai_agent_inside_openai_agent(self) -> None:
        self.assertEqual(_find_matching_terms("OpenAI Agent Platform", ("AI Agent",)), [])
        self.assertEqual(
            _find_matching_terms("Senior AI Agent Engineer", ("AI Agent",)),
            ["AI Agent"],
        )

    def test_ai_filter_does_not_match_tool_calling_inside_compound_word(self) -> None:
        self.assertEqual(
            _find_matching_terms("MultiTool Calling framework", ("Tool Calling",)),
            [],
        )
        self.assertEqual(
            _find_matching_terms("Experience with Tool Calling required", ("Tool Calling",)),
            ["Tool Calling"],
        )

    def test_ai_filter_dedupes_same_job_url_across_backend_and_full_stack_feeds(self) -> None:
        backend_matches = parse_rss_feed(AI_FILTER_SAMPLE_RSS, "AI")
        full_stack_matches = parse_rss_feed(AI_DUPLICATE_FULLSTACK_RSS, "AI")
        records = flatten_job_records(
            [
                {
                    "site": "wwr",
                    "keyword": "AI",
                    "url": WWR_BACKEND_FEED,
                    "matches": backend_matches,
                },
                {
                    "site": "wwr",
                    "keyword": "AI",
                    "url": WWR_FULL_STACK_FEED,
                    "matches": full_stack_matches,
                },
            ],
            discovered_at="2026-06-27T00:00:00+00:00",
        )
        shared_records = [
            record
            for record in records
            if record.job_url
            == "https://weworkremotely.com/remote-jobs/shared-corp-ai-platform-engineer"
        ]
        self.assertEqual(len(shared_records), 1)
        self.assertEqual(shared_records[0].matched_fields, ["skills"])
        self.assertEqual(
            shared_records[0].matched_terms,
            ["LLM", "Prompt Engineering"],
        )

    def test_flatten_job_records_accepts_wwr_matches(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "後端")
        records = flatten_job_records(
            [
                {
                    "site": "wwr",
                    "keyword": "後端",
                    "url": WWR_BACKEND_FEED,
                    "matches": matches,
                }
            ],
            discovered_at="2026-06-27T00:00:00+00:00",
        )
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].source_site, "wwr")
        self.assertEqual(records[0].search_page_url, WWR_BACKEND_FEED)


class WwrRegistryIntegrationTests(unittest.TestCase):
    def test_list_sites_includes_wwr(self) -> None:
        self.assertIn("wwr", list_sites())

    def test_list_cli_sites_includes_wwr(self) -> None:
        self.assertIn("wwr", _list_cli_sites())

    def test_all_mode_excludes_wwr(self) -> None:
        self.assertIn("wwr", MULTI_SITE_EXCLUDED_SITES)
        self.assertEqual(_resolve_requested_sites("all"), ["cake", "104", "yourator"])
        self.assertNotIn("wwr", _resolve_requested_sites("all"))

    def test_direct_wwr_site_remains_available(self) -> None:
        self.assertEqual(_resolve_requested_sites("wwr"), ["wwr"])

    def test_build_site_adapter_returns_wwr_adapter(self) -> None:
        from crawler.core.models import CrawlConfig

        adapter = build_site_adapter(CrawlConfig(site="wwr", keyword="後端"))
        self.assertEqual(adapter.name, "wwr")
        self.assertEqual(adapter.build_start_urls("後端"), [WWR_BACKEND_FEED])

    def test_default_google_sheet_name_for_wwr(self) -> None:
        self.assertEqual(_default_google_sheet_name("wwr"), "wwr_jobs")

    def test_resolve_output_path_for_single_site_wwr(self) -> None:
        self.assertEqual(
            _resolve_output_path("data/results.jsonl", "wwr", multi_site=False),
            "data/results.jsonl",
        )


class WwrFailurePathTests(unittest.TestCase):
    def test_parse_rss_feed_raises_on_malformed_xml(self) -> None:
        with self.assertRaises(ET.ParseError):
            parse_rss_feed("<rss><channel><item></rss>", "後端")

    @patch("crawler.core.spider.write_results")
    @patch("crawler.core.spider.time.sleep")
    @patch("crawler.core.spider.fetch_html")
    def test_crawl_keeps_valid_ai_feed_when_other_feed_is_malformed(
        self,
        mock_fetch_html,
        _mock_sleep,
        _mock_write_results,
    ) -> None:
        def fetch_side_effect(
            _session,
            url: str,
            *,
            timeout: float,
        ) -> FetchResponse:
            if url == WWR_BACKEND_FEED:
                return FetchResponse(status_code=200, text=AI_FILTER_SAMPLE_RSS)
            return FetchResponse(status_code=200, text="<rss><channel><item></rss>")

        mock_fetch_html.side_effect = fetch_side_effect
        results = crawl(
            CrawlConfig(
                site="wwr",
                keyword="AI",
                max_pages=2,
                delay_seconds=0,
                output_path="data/test-wwr-ai-failure.jsonl",
            )
        )

        self.assertEqual(len(results), 2)
        successful = [result for result in results if not result.get("error")]
        failed = [result for result in results if result.get("error")]
        self.assertEqual(len(successful), 1)
        self.assertEqual(len(failed), 1)
        self.assertEqual(successful[0]["url"], WWR_BACKEND_FEED)
        self.assertGreater(len(successful[0]["matches"]), 0)
        self.assertEqual(failed[0]["url"], WWR_FULL_STACK_FEED)

    @patch("crawler.core.spider.write_results")
    @patch("crawler.core.spider.time.sleep")
    @patch("crawler.core.spider.fetch_html")
    def test_crawl_records_fetch_error_for_failed_ai_feed(
        self,
        mock_fetch_html,
        _mock_sleep,
        _mock_write_results,
    ) -> None:
        def fetch_side_effect(
            _session,
            url: str,
            *,
            timeout: float,
        ) -> FetchResponse:
            if url == WWR_BACKEND_FEED:
                return FetchResponse(status_code=200, text=AI_FILTER_SAMPLE_RSS)
            raise TimeoutError("feed timeout")

        mock_fetch_html.side_effect = fetch_side_effect
        results = crawl(
            CrawlConfig(
                site="wwr",
                keyword="AI",
                max_pages=2,
                delay_seconds=0,
                output_path="data/test-wwr-ai-timeout.jsonl",
            )
        )

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].get("error"))
        self.assertEqual(results[1]["error"], "feed timeout")

    def test_build_start_urls_rejects_unsupported_keyword_before_fetch(self) -> None:
        adapter = WwrJobsAdapter("devops")
        with self.assertRaisesRegex(ValueError, "Unsupported WWR keyword 'devops'"):
            adapter.build_start_urls("devops")

    @patch("crawler.cli.crawl")
    def test_execute_requested_runs_continues_after_unsupported_wwr_keyword(
        self,
        mock_crawl,
    ) -> None:
        def crawl_side_effect(config: CrawlConfig) -> list[dict]:
            if config.keyword == "devops":
                raise ValueError("Unsupported WWR keyword 'devops'. Supported keyword groups: ...")
            return [
                {
                    "site": "wwr",
                    "keyword": config.keyword,
                    "url": WWR_BACKEND_FEED,
                    "matches": parse_rss_feed(BACKEND_SAMPLE_RSS, config.keyword)[:1],
                }
            ]

        mock_crawl.side_effect = crawl_side_effect
        args = argparse.Namespace(
            keyword="",
            output="data/results.jsonl",
            sync_google_sheet=False,
            send_email_notification=False,
            reset_google_sheet=False,
            google_sheet_id=None,
            google_sheet_name=None,
            google_service_account="",
            max_pages=9,
            per_page=20,
            delay=0,
            timeout=30,
            user_agent="test",
            search_url_template=None,
            send_machine_email_notification=False,
            machine_email_to="",
            smtp_host=None,
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            smtp_from_email=None,
            smtp_to_email=None,
            smtp_no_tls=False,
        )

        summaries = _execute_requested_runs(args, ["wwr"], ["後端", "devops"])

        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].keyword, "後端")
        self.assertFalse(summaries[0].error)
        self.assertEqual(summaries[1].keyword, "devops")
        self.assertIn("Unsupported WWR keyword 'devops'", summaries[1].error)


if __name__ == "__main__":
    unittest.main()
