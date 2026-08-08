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
        self.assertIn("Keyword: 後端", body)
        self.assertIn("Backend Engineer", body)
        self.assertIn("Company: ACME", body)
        self.assertIn("Company URL: https://www.cake.me/companies/acme", body)
        self.assertIn("Salary: 100000 - 150000 TWD per_month", body)
        self.assertIn("Salary min: 100000", body)
        self.assertIn("Salary max: 150000", body)
        self.assertIn("Salary currency: TWD", body)
        self.assertIn("Salary type: per_month", body)
        self.assertIn("Openings: 2", body)
        self.assertIn("Management responsibility: none", body)
        self.assertIn("Tags: Python, Backend", body)
        self.assertIn("Matched fields: title", body)
        self.assertIn("Matched terms: backend", body)
        self.assertIn("Source site: cake", body)
        self.assertIn(
            "Search page URL: https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
            body,
        )
        self.assertIn("Discovered at: 2026-03-22T12:00:00+00:00", body)
        self.assertIn("Summary: Build backend services", body)
        self.assertIn("Posted on: 2026-03-22T12:00:00Z", body)
        self.assertIn("Apply before: N/A", body)
        self.assertIn("Worksheet: cake_jobs", body)
        self.assertIn("https://docs.google.com/spreadsheets/d/sheet123/edit", body)
        # 整封信契約為單一 keyword（CLI 每輪 site+keyword 各寄一封），
        # 頂部已顯示，不在每筆職缺重複 Keyword。
        self.assertEqual(body.count("Keyword:"), 1)
        self.assertNotIn("\nKeyword:", body.split("1. Backend Engineer", 1)[1])

    def test_build_plain_text_body_includes_posted_on_and_apply_before(self) -> None:
        body = _build_plain_text_body(
            site="wwr",
            keyword="後端",
            records=[
                JobRecord(
                    job_url="https://weworkremotely.com/remote-jobs/1",
                    title="Senior Backend Engineer",
                    company_name="Acme",
                    company_url="",
                    keyword="後端",
                    location="Anywhere in the World",
                    salary_min="",
                    salary_max="",
                    salary_currency="",
                    salary_type="",
                    salary_display="",
                    openings_count="",
                    employment_type="Full-Time",
                    seniority_level="",
                    experience_required_years="",
                    management_responsibility="",
                    tags="Back-End Programming",
                    matched_fields=["category"],
                    matched_terms=["Back-End Programming"],
                    summary="Build APIs",
                    source_site="wwr",
                    search_page_url="https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
                    content_updated_at="2026-07-24",
                    discovered_at="2026-08-02T00:00:00+00:00",
                    application_deadline="2026-08-23",
                )
            ],
            sheet_name="wwr_jobs",
            spreadsheet_id="sheet123",
        )

        self.assertIn("Posted on: 2026-07-24", body)
        self.assertIn("Apply before: 2026-08-23", body)
        self.assertIn("Tags: Back-End Programming", body)
        self.assertIn("Summary: Build APIs", body)
        self.assertIn("Matched fields: category", body)
        self.assertIn("Matched terms: Back-End Programming", body)

    def test_build_plain_text_body_formats_lists_and_empty_values(self) -> None:
        body = _build_plain_text_body(
            site="wwr",
            keyword="後端",
            records=[
                JobRecord(
                    job_url="https://weworkremotely.com/remote-jobs/1",
                    title="Backend Engineer",
                    company_name="Acme",
                    company_url="",
                    keyword="後端",
                    location="",
                    salary_min="",
                    salary_max="",
                    salary_currency="",
                    salary_type="",
                    salary_display="",
                    openings_count="",
                    employment_type="",
                    seniority_level="",
                    experience_required_years="",
                    management_responsibility="",
                    tags="",
                    matched_fields=["title", "category"],
                    matched_terms=["backend", "api"],
                    summary="",
                    source_site="wwr",
                    search_page_url="",
                    content_updated_at="",
                    discovered_at="",
                )
            ],
            sheet_name="wwr_jobs",
            spreadsheet_id="sheet123",
        )

        self.assertIn("Matched fields: title, category", body)
        self.assertIn("Matched terms: backend, api", body)
        self.assertNotIn("Matched fields: ['title'", body)
        self.assertNotIn("Matched terms: ['backend'", body)
        self.assertIn("Company URL: N/A", body)
        self.assertIn("Location: N/A", body)
        self.assertIn("Tags: N/A", body)
        self.assertIn("Summary: N/A", body)
        self.assertIn("Openings: N/A", body)

    def test_build_plain_text_body_keeps_boundary_after_multiline_summary(self) -> None:
        body = _build_plain_text_body(
            site="wwr",
            keyword="後端",
            records=[
                JobRecord(
                    job_url="https://weworkremotely.com/remote-jobs/1",
                    title="First Job",
                    company_name="Acme",
                    company_url="",
                    keyword="後端",
                    location="",
                    salary_min="",
                    salary_max="",
                    salary_currency="",
                    salary_type="",
                    salary_display="",
                    openings_count="",
                    employment_type="",
                    seniority_level="",
                    experience_required_years="",
                    management_responsibility="",
                    tags="Back-End Programming, Python",
                    matched_fields=[],
                    matched_terms=[],
                    summary="Line one\nLine two\nLine three",
                    source_site="wwr",
                    search_page_url="https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
                    content_updated_at="",
                    discovered_at="",
                ),
                JobRecord(
                    job_url="https://weworkremotely.com/remote-jobs/2",
                    title="Second Job",
                    company_name="Beta",
                    company_url="",
                    keyword="後端",
                    location="",
                    salary_min="",
                    salary_max="",
                    salary_currency="",
                    salary_type="",
                    salary_display="",
                    openings_count="",
                    employment_type="",
                    seniority_level="",
                    experience_required_years="",
                    management_responsibility="",
                    tags="",
                    matched_fields=[],
                    matched_terms=[],
                    summary="Short",
                    source_site="wwr",
                    search_page_url="",
                    content_updated_at="",
                    discovered_at="",
                ),
            ],
            sheet_name="wwr_jobs",
            spreadsheet_id="sheet123",
        )

        self.assertIn("Summary: Line one\nLine two\nLine three", body)
        self.assertIn("Matched fields: N/A", body)
        self.assertIn("Matched terms: N/A", body)
        self.assertIn("\nSummary: Line one\nLine two\nLine three\n\n2. Second Job\n", body)
        self.assertIn("Tags: Back-End Programming, Python", body)

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
        self.assertEqual(payload["jobs"][0]["application_deadline"], "")


if __name__ == "__main__":
    unittest.main()
