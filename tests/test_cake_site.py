import unittest
import json

from crawler.sites.cake import (
    CAKE_IT_JOBS_SEARCH_URL_TEMPLATE,
    CAKE_IT_JOBS_URL,
    CakeItJobsAdapter,
    _expand_search_terms,
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

    def test_parse_page_extracts_matching_job_cards(self) -> None:
        adapter = CakeItJobsAdapter()
        parsed = adapter.parse_page(
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

        self.assertEqual(parsed.title, "Cake Job Search")
        self.assertEqual(parsed.meta_description, "IT jobs")
        self.assertEqual(len(parsed.matches), 1)
        self.assertEqual(parsed.matches[0]["title"], "AI Backend Engineer")
        self.assertEqual(parsed.matches[0]["company_name"], "Circle AI")
        self.assertEqual(parsed.matches[0]["matched_fields"], ["title", "summary"])
        self.assertIn("backend", parsed.matches[0]["matched_terms"])

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

    def test_parse_page_reads_structured_fields_from_next_data(self) -> None:
        adapter = CakeItJobsAdapter("後端")
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

        parsed = adapter.parse_page(
            "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
            html,
            "後端",
        )

        self.assertEqual(len(parsed.matches), 1)
        match = parsed.matches[0]
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


if __name__ == "__main__":
    unittest.main()
