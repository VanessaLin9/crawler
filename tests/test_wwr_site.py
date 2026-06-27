import unittest

from crawler.sites.wwr import (
    AI_KEYWORDS,
    WWR_BACKEND_FEED,
    WWR_FRONT_END_FEED,
    WWR_FULL_STACK_FEED,
    WwrJobsAdapter,
    resolve_feed_urls,
    resolve_keyword_group,
    unsupported_keyword_error,
)


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
            "<rss></rss>",
            "後端",
        )
        self.assertEqual(parsed.matches, [])
        self.assertEqual(parsed.links, [])


if __name__ == "__main__":
    unittest.main()
