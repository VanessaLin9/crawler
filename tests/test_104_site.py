import unittest
from unittest.mock import patch

from crawler.sites.site104 import JOB104_SEARCH_URL, OneOhFourJobsAdapter


class OneOhFourSiteAdapterTests(unittest.TestCase):
    def test_build_start_urls_uses_keyword_query(self) -> None:
        adapter = OneOhFourJobsAdapter()
        self.assertEqual(
            adapter.build_start_urls("後端"),
            ["https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF"],
        )

    def test_parse_page_uses_api_results(self) -> None:
        adapter = OneOhFourJobsAdapter("後端", per_page=30)
        api_response = {
            "data": [
                {
                    "appearDate": "20260327",
                    "custName": "背景模式股份有限公司",
                    "description": "熟悉 TypeScript、NestJS 與 RESTful API 開發。",
                    "descSnippet": "熟悉 TypeScript、NestJS 與 [[[後端]]] API 開發。",
                    "jobAddrNoDesc": "台中市西屯區",
                    "jobAddress": "市政路",
                    "jobName": "Backend Engineer 後端工程師",
                    "jobNameSnippet": "Backend Engineer [[[後端]]]工程師",
                    "link": {
                        "job": "https://www.104.com.tw/job/8znis",
                        "cust": "https://www.104.com.tw/company/1a2x6bnoys",
                    },
                    "pcSkills": [
                        {"description": "TypeScript"},
                        {"description": "NestJS"},
                    ],
                    "salaryHigh": 75000,
                    "salaryLow": 50000,
                    "tags": {
                        "remote": {"desc": "遠端工作", "param": "isRemoteWork"}
                    },
                }
            ],
            "metadata": {
                "pagination": {"count": 30, "currentPage": 1, "lastPage": 3, "total": 90}
            },
        }

        with patch("crawler.sites.site104._fetch_search_api_page", return_value=api_response) as mock_fetch:
            parsed = adapter.parse_page(
                JOB104_SEARCH_URL,
                """
                <html>
                  <head>
                    <title>104 工作搜尋</title>
                    <meta name="description" content="job search">
                  </head>
                  <body></body>
                </html>
                """,
                "後端",
            )

        mock_fetch.assert_called_once_with("後端", 1, 30)
        self.assertEqual(parsed.title, "104 工作搜尋")
        self.assertEqual(parsed.meta_description, "job search")
        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
        self.assertEqual(match["title"], "Backend Engineer 後端工程師")
        self.assertEqual(match["company_name"], "背景模式股份有限公司")
        self.assertEqual(match["job_url"], "https://www.104.com.tw/job/8znis")
        self.assertEqual(match["company_url"], "https://www.104.com.tw/company/1a2x6bnoys")
        self.assertEqual(match["location"], "台中市西屯區 市政路")
        self.assertEqual(match["salary_min"], "50000")
        self.assertEqual(match["salary_max"], "75000")
        self.assertEqual(match["salary_currency"], "TWD")
        self.assertEqual(match["salary_type"], "unknown")
        self.assertEqual(match["salary_display"], "50000 - 75000 TWD")
        self.assertEqual(match["tags"], "TypeScript, NestJS, 遠端工作")
        self.assertEqual(match["content_updated_at"], "2026-03-27")
        self.assertEqual(match["matched_fields"], ["title", "summary"])
        self.assertIn("backend", match["matched_terms"])
        self.assertIn("後端", match["matched_terms"])
        self.assertIn(
            "https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF&page=2",
            parsed.links,
        )

    def test_should_visit_stays_on_same_keyword_listing_pages(self) -> None:
        adapter = OneOhFourJobsAdapter("後端")
        self.assertTrue(
            adapter.should_visit(
                "https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF&page=2"
            )
        )
        self.assertFalse(
            adapter.should_visit(
                "https://www.104.com.tw/jobs/search/?keyword=%E5%89%8D%E7%AB%AF&page=2"
            )
        )
        self.assertFalse(adapter.should_visit("https://www.104.com.tw/job/8znis"))
        self.assertFalse(
            adapter.should_visit(
                "https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF&order=15"
            )
        )

    def test_parse_page_filters_out_summary_only_matches(self) -> None:
        adapter = OneOhFourJobsAdapter("後端", per_page=30)
        api_response = {
            "data": [
                {
                    "appearDate": "20260327",
                    "custName": "華義國際數位娛樂股份有限公司",
                    "description": "與前端、後端工程師協調，確保功能實現。",
                    "descSnippet": "與前端、[[[後端工程師]]]協調，確保功能實現。",
                    "jobAddrNoDesc": "台北市內湖區",
                    "jobAddress": "行愛路",
                    "jobName": "資深博弈遊戲開發企劃 A",
                    "link": {
                        "job": "https://www.104.com.tw/job/noisy1",
                        "cust": "https://www.104.com.tw/company/noisy-company",
                    },
                    "pcSkills": [],
                    "tags": {},
                }
            ],
            "metadata": {
                "pagination": {"count": 30, "currentPage": 1, "lastPage": 1, "total": 1}
            },
        }

        with patch("crawler.sites.site104._fetch_search_api_page", return_value=api_response):
            parsed = adapter.parse_page(
                JOB104_SEARCH_URL,
                "<html><head><title>104 工作搜尋</title></head><body></body></html>",
                "後端",
            )

        self.assertEqual(parsed.matches, [])

    def test_parse_page_keeps_tag_matches_even_without_title_match(self) -> None:
        adapter = OneOhFourJobsAdapter("後端", per_page=30)
        api_response = {
            "data": [
                {
                    "appearDate": "20260327",
                    "custName": "測試公司",
                    "description": "負責系統協作與平台串接。",
                    "descSnippet": "負責系統協作與平台串接。",
                    "jobAddrNoDesc": "台北市中山區",
                    "jobAddress": "南京東路",
                    "jobName": "Platform Engineer",
                    "link": {
                        "job": "https://www.104.com.tw/job/taghit1",
                        "cust": "https://www.104.com.tw/company/tag-company",
                    },
                    "pcSkills": [{"description": "Backend"}],
                    "tags": {},
                }
            ],
            "metadata": {
                "pagination": {"count": 30, "currentPage": 1, "lastPage": 1, "total": 1}
            },
        }

        with patch("crawler.sites.site104._fetch_search_api_page", return_value=api_response):
            parsed = adapter.parse_page(
                JOB104_SEARCH_URL,
                "<html><head><title>104 工作搜尋</title></head><body></body></html>",
                "後端",
            )

        self.assertEqual(len(parsed.matches), 1)
        self.assertEqual(parsed.matches[0]["matched_fields"], ["tags"])

    def test_parse_page_cleans_open_ended_salary_and_detects_monthly_type(self) -> None:
        adapter = OneOhFourJobsAdapter("後端", per_page=30)
        api_response = {
            "data": [
                {
                    "appearDate": "20260327",
                    "custName": "月薪測試公司",
                    "description": "後端 API 與資料服務開發。",
                    "descSnippet": "後端 API 與資料服務開發。",
                    "jobAddrNoDesc": "台北市信義區",
                    "jobAddress": "松高路",
                    "jobName": "後端工程師（Junior）月薪40,000~65,000",
                    "link": {
                        "job": "https://www.104.com.tw/job/salary1",
                        "cust": "https://www.104.com.tw/company/salary-company",
                    },
                    "salaryLow": 40000,
                    "salaryHigh": 9999999,
                    "pcSkills": [],
                    "tags": {},
                }
            ],
            "metadata": {
                "pagination": {"count": 30, "currentPage": 1, "lastPage": 1, "total": 1}
            },
        }

        with patch("crawler.sites.site104._fetch_search_api_page", return_value=api_response):
            parsed = adapter.parse_page(
                JOB104_SEARCH_URL,
                "<html><head><title>104 工作搜尋</title></head><body></body></html>",
                "後端",
            )

        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
        self.assertEqual(match["salary_min"], "40000")
        self.assertEqual(match["salary_max"], "")
        self.assertEqual(match["salary_type"], "per_month")
        self.assertEqual(match["salary_display"], "40000 TWD per_month")

    def test_parse_page_raises_clear_error_when_api_fetch_fails(self) -> None:
        adapter = OneOhFourJobsAdapter("後端", per_page=30)

        with patch("crawler.sites.site104._fetch_search_api_page", return_value=None):
            with self.assertRaisesRegex(
                RuntimeError,
                "Cookie/session behavior may have changed",
            ):
                adapter.parse_page(
                    JOB104_SEARCH_URL,
                    "<html><head><title>104 工作搜尋</title></head><body></body></html>",
                    "後端",
                )


if __name__ == "__main__":
    unittest.main()
