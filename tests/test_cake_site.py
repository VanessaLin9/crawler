import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from crawler.core.fetcher import FetchResponse, FetchSession, fetch_html
from crawler.core.models import CrawlConfig
from crawler.core.spider import crawl
from crawler.sites.base import SiteAdapter
from crawler.sites.cake import (
    CAKE_CLIENT_SEARCH_API_URL,
    CAKE_IT_JOBS_SEARCH_URL_TEMPLATE,
    CAKE_IT_JOBS_URL,
    CakeItJobsAdapter,
    _expand_search_terms,
    _parse_legacy_html_matches,
)
from crawler.sites.generic import build_generic_adapter


SAMPLE_API_JOB = {
    "path": "sports-game-system-backend",
    "title": "【體育遊戲系統】後端工程師 (台中市西區)",
    "description": "維護高品質系統與 API 服務",
    "locations": ["臺中市, 台灣"],
    "salary": {
        "min": "50000",
        "max": "100000",
        "currency": "TWD",
        "type": "per_month",
    },
    "seniority_level": "entry_level",
    "job_type": "full_time",
    "number_of_management": "none",
    "number_of_openings": 1,
    "tags": ["後端", "Python"],
    "page": {
        "path": "cloudlatitudesoftware",
        "name": "緯雲股份有限公司",
    },
    "min_work_exp_year": 1,
    "content_updated_at": "2026-03-17T06:17:16.052728Z",
}


def _api_payload(*, page: int = 1, total_pages: int = 1, data: list | None = None) -> str:
    return json.dumps(
        {
            "total_pages": total_pages,
            "current_page": page,
            "data": [SAMPLE_API_JOB] if data is None else data,
        },
        ensure_ascii=False,
    )


class CakeSiteAdapterTests(unittest.TestCase):
    def test_build_start_urls_uses_it_jobs_page(self) -> None:
        adapter = CakeItJobsAdapter()
        self.assertEqual(
            adapter.build_start_urls("後端"),
            [CAKE_IT_JOBS_SEARCH_URL_TEMPLATE.format(keyword="%E5%BE%8C%E7%AB%AF")],
        )

    def test_build_start_urls_falls_back_when_keyword_is_empty(self) -> None:
        adapter = CakeItJobsAdapter()
        self.assertEqual(adapter.build_start_urls(" "), [CAKE_IT_JOBS_URL])

    def test_should_visit_stays_on_it_listing_pages(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        self.assertTrue(
            adapter.should_visit(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2"
            )
        )
        self.assertFalse(
            adapter.should_visit(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?locale=en"
            )
        )
        self.assertFalse(
            adapter.should_visit("https://www.cake.me/companies/devcore/jobs/pentest")
        )
        self.assertFalse(
            adapter.should_visit("https://www.cake.me/jobs/%E5%89%8D%E7%AB%AF/for-it?page=2")
        )

    def test_expand_search_terms_for_backend_keyword(self) -> None:
        expanded = _expand_search_terms("後端")
        self.assertIn("backend", expanded)
        self.assertIn("後端工程師", expanded)

    def test_expand_search_terms_for_fullstack_keyword(self) -> None:
        expanded = _expand_search_terms("全端")
        self.assertIn("full-stack", expanded)
        self.assertIn("full stack engineer", expanded)
        self.assertIn("全端工程師", expanded)

    def test_default_adapter_fetch_page_uses_html_get(self) -> None:
        adapter = build_generic_adapter("https://example.com/search?q={keyword}")
        session = FetchSession(user_agent="test-agent/1.0")
        with patch(
            "crawler.sites.base.fetch_html",
            return_value=FetchResponse(status_code=200, text="<html></html>"),
        ) as mock_fetch_html:
            response = adapter.fetch_page(
                session,
                "https://example.com/search?q=backend",
                timeout=5.0,
            )

        mock_fetch_html.assert_called_once_with(
            session,
            "https://example.com/search?q=backend",
            timeout=5.0,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(adapter, SiteAdapter)
        self.assertIs(adapter.fetch_page.__func__, SiteAdapter.fetch_page)

    def test_parse_page_matches_fullstack_titles_for_fullstack_keyword(self) -> None:
        adapter = CakeItJobsAdapter("全端")
        body = _api_payload(
            data=[
                {
                    "path": "software-engineer-fullstack",
                    "title": "Software Engineer (Full-stack)",
                    "description": "Build web applications across the stack",
                    "locations": ["台北市, 台灣"],
                    "salary": {
                        "min": "80000",
                        "max": "120000",
                        "currency": "TWD",
                        "type": "per_month",
                    },
                    "seniority_level": "mid_senior_level",
                    "job_type": "full_time",
                    "number_of_management": "none",
                    "number_of_openings": 1,
                    "tags": ["JavaScript", "React"],
                    "page": {
                        "path": "acme",
                        "name": "ACME",
                    },
                    "min_work_exp_year": 2,
                    "content_updated_at": "2026-03-17T06:17:16.052728Z",
                }
            ]
        )

        parsed = adapter.parse_page(
            "https://www.cake.me/jobs/%E5%85%A8%E7%AB%AF/for-it",
            body,
            "全端",
        )

        self.assertEqual(len(parsed.matches), 1)
        self.assertEqual(parsed.matches[0]["title"], "Software Engineer (Full-stack)")
        self.assertIn("full-stack", parsed.matches[0]["matched_terms"])

    def test_parse_page_uses_api_results_for_page_two(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        body = _api_payload(page=2, total_pages=63, data=[SAMPLE_API_JOB])

        parsed = adapter.parse_page(
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2",
            body,
            "後端",
        )

        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
        self.assertEqual(match["title"], "【體育遊戲系統】後端工程師 (台中市西區)")
        self.assertEqual(match["company_name"], "緯雲股份有限公司")
        self.assertEqual(match["location"], "臺中市, 台灣")
        self.assertEqual(match["salary_display"], "50000 - 100000 TWD per_month")
        self.assertEqual(match["employment_type"], "full_time")
        self.assertEqual(match["seniority_level"], "entry_level")
        self.assertEqual(match["content_updated_at"], "2026-03-17")
        self.assertEqual(
            match["job_url"],
            "https://www.cake.me/companies/cloudlatitudesoftware/jobs/sports-game-system-backend",
        )
        self.assertEqual(
            parsed.links,
            ["https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=3"],
        )

    def test_parse_page_stops_pagination_on_last_page(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        parsed = adapter.parse_page(
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=3",
            _api_payload(page=3, total_pages=3, data=[SAMPLE_API_JOB]),
            "後端",
        )
        self.assertEqual(parsed.links, [])

    @patch("crawler.sites.cake.urlopen")
    def test_fetch_page_posts_search_api_for_page_one(self, mock_urlopen) -> None:
        adapter = CakeItJobsAdapter("後端", per_page=20)
        response = MagicMock()
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = _api_payload().encode("utf-8")
        response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = response

        session = FetchSession(user_agent="search-crawler/test")
        result = adapter.fetch_page(
            session,
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
            timeout=7.5,
        )

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, CAKE_CLIENT_SEARCH_API_URL)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Origin"), "https://www.cake.me")
        self.assertEqual(
            request.get_header("Referer"),
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
        )
        self.assertEqual(request.get_header("User-agent"), "search-crawler/test")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "query": "後端",
                "filters": {"professions": ["it"]},
                "sort_by": "popularity",
                "page": 1,
                "per_page": 20,
            },
        )
        self.assertEqual(mock_urlopen.call_args.kwargs["timeout"], 7.5)
        self.assertEqual(result.status_code, 200)

    @patch("crawler.sites.cake.urlopen")
    def test_fetch_page_reads_page_number_from_logical_url(self, mock_urlopen) -> None:
        adapter = CakeItJobsAdapter("後端", per_page=15)
        response = MagicMock()
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = b'{"data":[],"total_pages":3,"current_page":2}'
        response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = response

        adapter.fetch_page(
            FetchSession(user_agent="ua"),
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2",
            timeout=5.0,
        )

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(
            json.loads(request.data.decode("utf-8"))["page"],
            2,
        )
        self.assertEqual(
            request.get_header("Referer"),
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2",
        )

    def test_parse_page_raises_on_invalid_json(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                "{not-json",
                "後端",
            )

    def test_parse_page_raises_when_top_level_is_not_object(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "JSON object"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                "[]",
                "後端",
            )

    def test_parse_page_raises_when_data_missing(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "missing field 'data'"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"total_pages": 1}),
                "後端",
            )

    def test_parse_page_raises_when_data_is_not_list(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "field 'data' must be a list"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": {}, "total_pages": 1}),
                "後端",
            )

    def test_parse_page_raises_when_total_pages_invalid(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "total_pages"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": [], "total_pages": "3", "current_page": 1}),
                "後端",
            )

    def test_parse_page_raises_when_total_pages_is_boolean(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "total_pages"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": [], "total_pages": True, "current_page": 1}),
                "後端",
            )

    def test_parse_page_raises_when_total_pages_is_negative(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "total_pages"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": [], "total_pages": -1, "current_page": 1}),
                "後端",
            )

    def test_parse_page_raises_when_current_page_missing(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "current_page"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": [], "total_pages": 1}),
                "後端",
            )

    def test_parse_page_raises_when_current_page_mismatches_logical_url(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "current_page mismatch"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2",
                json.dumps({"data": [], "total_pages": 3, "current_page": 1}),
                "後端",
            )

    def test_parse_page_raises_when_current_page_is_boolean(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "current_page"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": [], "total_pages": 1, "current_page": True}),
                "後端",
            )

    def test_parse_page_raises_when_current_page_is_negative(self) -> None:
        adapter = CakeItJobsAdapter("後端")
        with self.assertRaisesRegex(RuntimeError, "current_page"):
            adapter.parse_page(
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                json.dumps({"data": [], "total_pages": 1, "current_page": -2}),
                "後端",
            )

    @patch("crawler.sites.cake.urlopen")
    def test_fetch_page_raises_on_http_error(self, mock_urlopen) -> None:
        adapter = CakeItJobsAdapter("後端")
        mock_urlopen.side_effect = HTTPError(
            CAKE_CLIENT_SEARCH_API_URL,
            403,
            "Forbidden",
            hdrs=None,
            fp=BytesIO(b""),
        )
        with self.assertRaisesRegex(RuntimeError, "Cake Search API HTTP error: 403"):
            adapter.fetch_page(
                FetchSession(user_agent="ua"),
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                timeout=5.0,
            )

    @patch("crawler.sites.cake.urlopen")
    def test_fetch_page_raises_on_network_error(self, mock_urlopen) -> None:
        adapter = CakeItJobsAdapter("後端")
        mock_urlopen.side_effect = URLError("dns failure")
        with self.assertRaisesRegex(RuntimeError, "Cake Search API network error"):
            adapter.fetch_page(
                FetchSession(user_agent="ua"),
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                timeout=5.0,
            )

    @patch("crawler.sites.cake.urlopen")
    def test_fetch_page_raises_on_timeout(self, mock_urlopen) -> None:
        adapter = CakeItJobsAdapter("後端")
        mock_urlopen.side_effect = TimeoutError()
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            adapter.fetch_page(
                FetchSession(user_agent="ua"),
                "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                timeout=5.0,
            )


class CakeLegacyHtmlParserHelperTests(unittest.TestCase):
    """Legacy HTML parser helpers only — not Cake production crawl path."""

    def test_legacy_html_parser_extracts_matching_job_cards(self) -> None:
        matches = _parse_legacy_html_matches(
            CAKE_IT_JOBS_URL,
            """
            <html>
              <head>
                <title>Cake Job Search</title>
                <meta name="description" content="IT jobs">
              </head>
              <body>
                <h2><a href="/companies/devcore/jobs/pentest">Penetration Tester</a></h2>
                <a href="/companies/devcore">DEVCORE</a>
                <p>Security testing and red team operations</p>

                <h2><a href="/companies/circle-ai/jobs/backend">AI Backend Engineer</a></h2>
                <a href="/companies/circle-ai">Circle AI</a>
                <p>Python, machine learning pipelines, and backend services</p>
              </body>
            </html>
            """,
            "後端",
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["title"], "AI Backend Engineer")
        self.assertEqual(matches[0]["company_name"], "Circle AI")
        self.assertEqual(matches[0]["matched_fields"], ["title", "summary"])
        self.assertIn("backend", matches[0]["matched_terms"])

    def test_legacy_html_parser_reads_structured_fields_from_next_data(self) -> None:
        next_data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "jobSearch": {
                            "activeFilterKey": '{"filters":{"professions":["it"]},"query":"後端"}',
                            "viewsByFilterKey": {
                                '{"filters":{"professions":["it"]},"query":"後端"}': {
                                    "pageMap": {"1": ["backend-engineer-1"]},
                                }
                            },
                            "entityByPathId": {
                                "backend-engineer-1": {
                                    "path": "backend-engineer-1",
                                    "title": "Backend Engineer",
                                    "description": "Build backend services",
                                    "locations": ["台北市, 台灣"],
                                    "salary": {
                                        "min": "100000",
                                        "max": "150000",
                                        "currency": "TWD",
                                        "type": "per_month",
                                    },
                                    "seniorityLevel": "mid_senior_level",
                                    "jobType": "full_time",
                                    "numberOfManagement": "none",
                                    "numberOfOpenings": 2,
                                    "tags": ["Python", "Backend"],
                                    "page": {
                                        "path": "acme",
                                        "name": "ACME",
                                    },
                                    "minWorkExpYear": 3,
                                    "contentUpdatedAt": "2026-03-22T12:00:00Z",
                                }
                            },
                        }
                    }
                }
            }
        }
        html = f"""
        <html>
          <head><title>Cake Job Search</title></head>
          <body>
            <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>
          </body>
        </html>
        """

        matches = _parse_legacy_html_matches(
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
            html,
            "後端",
        )

        self.assertEqual(len(matches), 1)
        match = matches[0]
        self.assertEqual(match["location"], "台北市, 台灣")
        self.assertEqual(match["salary_min"], "100000")
        self.assertEqual(match["salary_max"], "150000")
        self.assertEqual(match["salary_currency"], "TWD")
        self.assertEqual(match["salary_type"], "per_month")
        self.assertEqual(match["openings_count"], "2")
        self.assertEqual(match["employment_type"], "full_time")
        self.assertEqual(match["seniority_level"], "mid_senior_level")
        self.assertEqual(match["experience_required_years"], "3")
        self.assertEqual(match["management_responsibility"], "none")
        self.assertEqual(match["tags"], "Python, Backend")
        self.assertEqual(
            match["job_url"],
            "https://www.cake.me/companies/acme/jobs/backend-engineer-1",
        )


class CakeCrawlApiOnlyTests(unittest.TestCase):
    @patch("crawler.core.spider.write_results")
    @patch("crawler.core.spider.time.sleep")
    @patch("crawler.sites.base.fetch_html")
    @patch.object(CakeItJobsAdapter, "fetch_page")
    def test_crawl_skips_html_fetch_and_uses_search_api(
        self,
        mock_fetch_page,
        mock_fetch_html,
        _mock_sleep,
        _mock_write_results,
    ) -> None:
        mock_fetch_page.return_value = FetchResponse(
            status_code=200,
            text=_api_payload(total_pages=1, data=[SAMPLE_API_JOB]),
        )

        results = crawl(
            CrawlConfig(
                site="cake",
                keyword="後端",
                max_pages=1,
                delay_seconds=0,
                user_agent="search-crawler/test",
                output_path="data/test-cake-api-only.jsonl",
            )
        )

        mock_fetch_html.assert_not_called()
        mock_fetch_page.assert_called_once()
        call = mock_fetch_page.call_args
        self.assertEqual(call.args[0].user_agent, "search-crawler/test")
        self.assertEqual(
            call.args[1],
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
        )
        self.assertEqual(len(results), 1)
        self.assertNotIn("error", results[0])
        self.assertEqual(len(results[0]["matches"]), 1)
        self.assertEqual(
            results[0]["matches"][0]["job_url"],
            "https://www.cake.me/companies/cloudlatitudesoftware/jobs/sports-game-system-backend",
        )

    @patch("crawler.core.spider.write_results")
    @patch("crawler.core.spider.time.sleep")
    @patch("crawler.sites.base.fetch_html")
    @patch.object(CakeItJobsAdapter, "fetch_page")
    def test_crawl_records_api_http_error_without_fake_success(
        self,
        mock_fetch_page,
        mock_fetch_html,
        _mock_sleep,
        _mock_write_results,
    ) -> None:
        mock_fetch_page.side_effect = RuntimeError("Cake Search API HTTP error: 403 Forbidden")

        results = crawl(
            CrawlConfig(
                site="cake",
                keyword="後端",
                max_pages=1,
                delay_seconds=0,
                output_path="data/test-cake-api-http-error.jsonl",
            )
        )

        mock_fetch_html.assert_not_called()
        self.assertEqual(len(results), 1)
        self.assertIn("Cake Search API HTTP error: 403", results[0]["error"])
        self.assertNotIn("matches", results[0])

    @patch("crawler.core.spider.write_results")
    @patch("crawler.core.spider.time.sleep")
    @patch("crawler.sites.base.fetch_html")
    @patch.object(CakeItJobsAdapter, "fetch_page")
    def test_crawl_records_schema_error_without_fake_success(
        self,
        mock_fetch_page,
        mock_fetch_html,
        _mock_sleep,
        _mock_write_results,
    ) -> None:
        mock_fetch_page.return_value = FetchResponse(
            status_code=200,
            text=json.dumps({"total_pages": 1}),
        )

        results = crawl(
            CrawlConfig(
                site="cake",
                keyword="後端",
                max_pages=1,
                delay_seconds=0,
                output_path="data/test-cake-api-schema-error.jsonl",
            )
        )

        mock_fetch_html.assert_not_called()
        self.assertEqual(len(results), 1)
        self.assertIn("missing field 'data'", results[0]["error"])
        self.assertNotIn("matches", results[0])

    @patch("crawler.core.spider.write_results")
    @patch("crawler.core.spider.time.sleep")
    @patch("crawler.sites.cake.urlopen")
    @patch("crawler.sites.base.fetch_html", wraps=fetch_html)
    def test_crawl_posts_api_with_expected_payload_and_never_calls_html_fetch(
        self,
        mock_fetch_html,
        mock_urlopen,
        _mock_sleep,
        _mock_write_results,
    ) -> None:
        response = MagicMock()
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = _api_payload(
            total_pages=2,
            data=[SAMPLE_API_JOB],
        ).encode("utf-8")
        response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = response

        results = crawl(
            CrawlConfig(
                site="cake",
                keyword="後端",
                max_pages=1,
                per_page=20,
                delay_seconds=0,
                user_agent="search-crawler/test",
                output_path="data/test-cake-api-payload.jsonl",
            )
        )

        mock_fetch_html.assert_not_called()
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, CAKE_CLIENT_SEARCH_API_URL)
        self.assertEqual(request.get_header("User-agent"), "search-crawler/test")
        self.assertEqual(
            request.get_header("Referer"),
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
        )
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "query": "後端",
                "filters": {"professions": ["it"]},
                "sort_by": "popularity",
                "page": 1,
                "per_page": 20,
            },
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["links"],
            ["https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2"],
        )


if __name__ == "__main__":
    unittest.main()
