import unittest
from unittest.mock import patch

from crawler.sites.yourator import YOURATOR_JOBS_URL, YouratorJobsAdapter


class YouratorSiteAdapterTests(unittest.TestCase):
    def test_build_start_urls_uses_jobs_listing(self) -> None:
        adapter = YouratorJobsAdapter()
        self.assertEqual(adapter.build_start_urls("後端"), [YOURATOR_JOBS_URL])

    def test_should_visit_stays_on_jobs_pagination(self) -> None:
        adapter = YouratorJobsAdapter("後端")
        self.assertTrue(adapter.should_visit("https://www.yourator.co/jobs?page=2"))
        self.assertTrue(adapter.should_visit("https://www.yourator.co/jobs"))
        self.assertFalse(
            adapter.should_visit("https://www.yourator.co/search?s=%E5%BE%8C%E7%AB%AF")
        )
        self.assertFalse(
            adapter.should_visit("https://www.yourator.co/jobs?category%5B%5D=23")
        )
        self.assertFalse(
            adapter.should_visit("https://www.yourator.co/companies/linkst/jobs/46716")
        )

    @patch("crawler.sites.yourator._fetch_search_api_page")
    @patch("crawler.sites.yourator._fetch_job_detail")
    @patch("crawler.sites.yourator._fetch_jobs_api_page")
    def test_parse_page_extracts_matches_from_jobs_api(
        self,
        mock_fetch_jobs_api_page,
        mock_fetch_job_detail,
        mock_fetch_search_api_page,
    ) -> None:
        adapter = YouratorJobsAdapter("後端", per_page=20)
        mock_fetch_jobs_api_page.return_value = {
            "hasMore": True,
            "currentPage": 1,
            "nextPage": 2,
            "jobs": [
                {
                    "id": 46716,
                    "name": "AI Platform Engineer",
                    "path": "/companies/linkst/jobs/46716",
                    "salary": "NT$ 36,000 - 40,000 (月薪)",
                    "location": "臺北市",
                    "tags": ["Backend", "AI Product"],
                    "lastActiveAt": "一天內更新",
                    "company": {
                        "path": "/companies/linkst",
                        "brand": "智林國際股份有限公司",
                        "enName": "linkst",
                        "badges": ["verified"],
                    },
                },
                {
                    "id": 46724,
                    "name": "Digital Marketing Specialist",
                    "path": "/companies/linkst/jobs/46724",
                    "salary": "NT$ 32,000 - 40,000 (月薪)",
                    "location": "臺北市",
                    "tags": ["廣告投放"],
                    "lastActiveAt": "一天內更新",
                    "company": {
                        "path": "/companies/linkst",
                        "brand": "智林國際股份有限公司",
                        "enName": "linkst",
                    },
                },
            ],
        }
        mock_fetch_job_detail.return_value.summary = (
            "負責管理後端環境與 API，協助快速迭代產品功能。"
        )
        mock_fetch_job_detail.return_value.content_updated_at = "2026-04-08"
        mock_fetch_search_api_page.return_value = {"jobs": []}

        parsed = adapter.parse_page(
            "https://www.yourator.co/jobs",
            """
            <html>
              <head>
                <title>Yourator Jobs</title>
                <meta name="description" content="recent jobs">
              </head>
              <body></body>
            </html>
            """,
            "後端",
        )

        mock_fetch_jobs_api_page.assert_called_once_with(1)
        mock_fetch_job_detail.assert_called_once_with(
            "https://www.yourator.co/companies/linkst/jobs/46716"
        )
        mock_fetch_search_api_page.assert_called_once_with("後端")
        self.assertEqual(parsed.title, "Yourator Jobs")
        self.assertEqual(parsed.meta_description, "recent jobs")
        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
        self.assertEqual(match["title"], "AI Platform Engineer")
        self.assertEqual(match["company_name"], "智林國際股份有限公司")
        self.assertEqual(match["job_url"], "https://www.yourator.co/companies/linkst/jobs/46716")
        self.assertEqual(match["company_url"], "https://www.yourator.co/companies/linkst")
        self.assertEqual(match["salary_min"], "36000")
        self.assertEqual(match["salary_max"], "40000")
        self.assertEqual(match["salary_currency"], "TWD")
        self.assertEqual(match["salary_type"], "per_month")
        self.assertEqual(match["salary_display"], "NT$ 36,000 - 40,000 (月薪)")
        self.assertEqual(match["location"], "臺北市")
        self.assertEqual(match["tags"], "Backend, AI Product")
        self.assertEqual(match["content_updated_at"], "2026-04-08")
        self.assertEqual(match["matched_fields"], ["tags", "summary"])
        self.assertIn("backend", match["matched_terms"])
        self.assertIn("後端", match["matched_terms"])
        self.assertIn("https://www.yourator.co/jobs?page=2", parsed.links)

    @patch("crawler.sites.yourator._fetch_search_api_page")
    @patch("crawler.sites.yourator._fetch_job_detail")
    @patch("crawler.sites.yourator._fetch_jobs_api_page")
    def test_parse_page_does_not_use_relative_last_active_text_as_content_updated_at(
        self,
        mock_fetch_jobs_api_page,
        mock_fetch_job_detail,
        mock_fetch_search_api_page,
    ) -> None:
        adapter = YouratorJobsAdapter("後端")
        mock_fetch_jobs_api_page.return_value = {
            "hasMore": False,
            "currentPage": 1,
            "nextPage": None,
            "jobs": [
                {
                    "id": 46716,
                    "name": "Backend Engineer",
                    "path": "/companies/linkst/jobs/46716",
                    "salary": "NT$ 36,000 - 40,000 (月薪)",
                    "location": "臺北市",
                    "tags": ["Backend"],
                    "lastActiveAt": "一天內更新",
                    "company": {
                        "path": "/companies/linkst",
                        "brand": "智林國際股份有限公司",
                        "enName": "linkst",
                    },
                }
            ],
        }
        mock_fetch_job_detail.return_value.summary = "負責後端 API 開發。"
        mock_fetch_job_detail.return_value.content_updated_at = ""
        mock_fetch_search_api_page.return_value = {"jobs": []}

        parsed = adapter.parse_page(
            "https://www.yourator.co/jobs",
            "<html><head><title>Yourator Jobs</title></head><body></body></html>",
            "後端",
        )

        self.assertEqual(len(parsed.matches), 1)
        self.assertEqual(parsed.matches[0]["content_updated_at"], "")

    @patch("crawler.sites.yourator._fetch_search_api_page")
    @patch("crawler.sites.yourator._fetch_job_detail")
    @patch("crawler.sites.yourator._fetch_jobs_api_page")
    def test_parse_page_normalizes_negotiable_salary_floor(
        self,
        mock_fetch_jobs_api_page,
        mock_fetch_job_detail,
        mock_fetch_search_api_page,
    ) -> None:
        adapter = YouratorJobsAdapter("後端")
        mock_fetch_jobs_api_page.return_value = {
            "hasMore": False,
            "currentPage": 1,
            "nextPage": None,
            "jobs": [
                {
                    "id": 28715,
                    "name": ".Net Engineer 後端工程師",
                    "path": "/companies/tutorabc/jobs/28715",
                    "salary": "面議（經常性薪資達4萬元）",
                    "location": "臺北市",
                    "tags": ["Backend Engineer"],
                    "lastActiveAt": "一天內更新",
                    "company": {
                        "path": "/companies/tutorabc",
                        "brand": "TutorABC",
                        "enName": "tutorabc",
                    },
                }
            ],
        }
        mock_fetch_job_detail.return_value.summary = "3年以上後端開發經驗尤佳。"
        mock_fetch_job_detail.return_value.content_updated_at = "2026-04-08"
        mock_fetch_search_api_page.return_value = {"jobs": []}

        parsed = adapter.parse_page(
            "https://www.yourator.co/jobs",
            "<html><head><title>Yourator Jobs</title></head><body></body></html>",
            "後端",
        )

        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
        self.assertEqual(match["salary_min"], "40000")
        self.assertEqual(match["salary_max"], "")
        self.assertEqual(match["salary_currency"], "TWD")
        self.assertEqual(match["salary_type"], "negotiable")
        self.assertEqual(match["salary_display"], "面議（經常性薪資達4萬元）")

    @patch("crawler.sites.yourator._fetch_search_api_page")
    @patch("crawler.sites.yourator._fetch_job_detail")
    @patch("crawler.sites.yourator._fetch_jobs_api_page")
    def test_parse_page_merges_search_api_results_on_first_page(
        self,
        mock_fetch_jobs_api_page,
        mock_fetch_job_detail,
        mock_fetch_search_api_page,
    ) -> None:
        adapter = YouratorJobsAdapter("後端")
        mock_fetch_jobs_api_page.return_value = {
            "hasMore": False,
            "currentPage": 1,
            "nextPage": None,
            "jobs": [],
        }
        mock_fetch_job_detail.return_value.summary = ""
        mock_fetch_job_detail.return_value.content_updated_at = ""
        mock_fetch_search_api_page.return_value = {
            "jobs": [
                {
                    "id": 41093,
                    "name": "Senior Backend Engineer",
                    "content": "<p>負責後端服務開發，使用 Golang 或 Python 撰寫高效服務。</p>",
                    "country": {"code": "TW", "name": "台灣"},
                    "city": {"code": "TPE", "name": "臺北市"},
                    "salary": "NT$ 1,300,000 - 2,000,000 (年薪)",
                    "tags": [{"id": 1, "name": "backend"}],
                    "category": {"id": 23, "name": "後端工程"},
                    "company": {
                        "brand": "漸強實驗室 Crescendo Lab Ltd.",
                        "enName": "CrescendoLab",
                    },
                }
            ]
        }

        parsed = adapter.parse_page(
            "https://www.yourator.co/jobs",
            "<html><head><title>Yourator Jobs</title></head><body></body></html>",
            "後端",
        )

        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
        self.assertEqual(
            match["job_url"],
            "https://www.yourator.co/companies/CrescendoLab/jobs/41093",
        )
        self.assertEqual(match["salary_type"], "per_year")
        self.assertEqual(match["location"], "台灣 臺北市")
        self.assertEqual(match["matched_fields"], ["title", "summary", "tags", "category"])
        self.assertEqual(match["tags"], "backend")
        self.assertIn("backend", match["matched_terms"])
        self.assertIn("後端", match["matched_terms"])


if __name__ == "__main__":
    unittest.main()
