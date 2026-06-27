import unittest
from pathlib import Path

from crawler.records import flatten_job_records
from crawler.sites.wwr import (
    AI_KEYWORDS,
    WWR_BACKEND_FEED,
    WWR_FRONT_END_FEED,
    WWR_FULL_STACK_FEED,
    WwrJobsAdapter,
    parse_rss_feed,
    resolve_feed_urls,
    resolve_keyword_group,
    unsupported_keyword_error,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "wwr"
BACKEND_SAMPLE_RSS = (FIXTURES_DIR / "backend_sample.rss").read_text(encoding="utf-8")


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

    def test_ai_keyword_group_does_not_set_category_matched_fields_yet(self) -> None:
        matches = parse_rss_feed(BACKEND_SAMPLE_RSS, "AI")
        self.assertEqual(matches[0]["matched_fields"], [])
        self.assertEqual(matches[0]["matched_terms"], [])

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


if __name__ == "__main__":
    unittest.main()
