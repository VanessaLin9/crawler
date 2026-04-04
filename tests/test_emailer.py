import unittest
import json

from crawler.emailer import (
    _build_json_body,
    _build_json_subject,
    _build_plain_text_body,
    _build_subject,
)
from crawler.records import JobRecord


class EmailerTests(unittest.TestCase):
    def test_build_subject_includes_site_keyword_and_count(self) -> None:
        self.assertEqual(
            _build_subject("cake", "後端", 3),
            "[Crawler] cake 後端 new jobs: 3",
        )

    def test_build_subject_uses_alert_prefix_when_crawl_issues_exist(self) -> None:
        self.assertEqual(
            _build_subject("104", "後端", 0, ["104 API failed"]),
            "[Crawler Alert] 104 後端 issues detected",
        )

    def test_build_plain_text_body_lists_new_jobs(self) -> None:
        body = _build_plain_text_body(
            site="cake",
            keyword="後端",
            records=[
                JobRecord(
                    job_url="https://www.cake.me/jobs/1",
                    title="Backend Engineer",
                    company_name="ACME",
                    company_url="https://www.cake.me/companies/acme",
                    keyword="後端",
                    location="台北市, 台灣",
                    salary_min="100000",
                    salary_max="150000",
                    salary_currency="TWD",
                    salary_type="per_month",
                    salary_display="100000 - 150000 TWD per_month",
                    openings_count="2",
                    employment_type="full_time",
                    seniority_level="mid_senior_level",
                    experience_required_years="3",
                    management_responsibility="none",
                    tags="Python, Backend",
                    matched_fields=["title"],
                    matched_terms=["backend"],
                    summary="Build backend services",
                    source_site="cake",
                    search_page_url="https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                    content_updated_at="2026-03-22T12:00:00Z",
                    discovered_at="2026-03-22T12:00:00+00:00",
                )
            ],
            sheet_name="cake_jobs",
            spreadsheet_id="sheet123",
        )

        self.assertIn("New jobs: 1", body)
        self.assertIn("Backend Engineer", body)
        self.assertIn("Company: ACME", body)
        self.assertIn("Salary: 100000 - 150000 TWD per_month", body)
        self.assertIn("Worksheet: cake_jobs", body)
        self.assertIn("https://docs.google.com/spreadsheets/d/sheet123/edit", body)

    def test_build_plain_text_body_lists_crawl_issues(self) -> None:
        body = _build_plain_text_body(
            site="104",
            keyword="後端",
            records=[],
            sheet_name="104_jobs",
            spreadsheet_id="sheet123",
            crawl_issues=[
                "104 search API request failed after establishing an anonymous session. Cookie/session behavior may have changed. (page: https://www.104.com.tw/jobs/search/?keyword=%E5%BE%8C%E7%AB%AF)"
            ],
        )

        self.assertIn("New jobs: 0", body)
        self.assertIn("Crawl issues detected:", body)
        self.assertIn("Cookie/session behavior may have changed", body)

    def test_build_json_subject_includes_site_keyword_and_count(self) -> None:
        self.assertEqual(
            _build_json_subject("cake", "後端", 3),
            "[Crawler JSON] cake 後端 new jobs: 3",
        )

    def test_build_json_body_returns_machine_readable_payload(self) -> None:
        body = _build_json_body(
            site="cake",
            keyword="後端",
            records=[
                JobRecord(
                    job_url="https://www.cake.me/jobs/1",
                    title="Backend Engineer",
                    company_name="ACME",
                    company_url="https://www.cake.me/companies/acme",
                    keyword="後端",
                    location="台北市, 台灣",
                    salary_min="100000",
                    salary_max="150000",
                    salary_currency="TWD",
                    salary_type="per_month",
                    salary_display="100000 - 150000 TWD per_month",
                    openings_count="2",
                    employment_type="full_time",
                    seniority_level="mid_senior_level",
                    experience_required_years="3",
                    management_responsibility="none",
                    tags="Python, Backend",
                    matched_fields=["title"],
                    matched_terms=["backend"],
                    summary="Build backend services",
                    source_site="cake",
                    search_page_url="https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                    content_updated_at="2026-03-22T12:00:00Z",
                    discovered_at="2026-03-22T12:00:00+00:00",
                )
            ],
            sheet_name="cake_jobs",
            spreadsheet_id="sheet123",
        )

        payload = json.loads(body)
        self.assertEqual(payload["site"], "cake")
        self.assertEqual(payload["keyword"], "後端")
        self.assertEqual(payload["new_jobs_count"], 1)
        self.assertEqual(payload["sheet_name"], "cake_jobs")
        self.assertEqual(
            payload["sheet_url"],
            "https://docs.google.com/spreadsheets/d/sheet123/edit",
        )
        self.assertEqual(payload["jobs"][0]["title"], "Backend Engineer")
        self.assertEqual(payload["jobs"][0]["job_url"], "https://www.cake.me/jobs/1")


if __name__ == "__main__":
    unittest.main()
