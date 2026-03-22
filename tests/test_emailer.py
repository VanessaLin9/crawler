import unittest

from crawler.emailer import _build_plain_text_body, _build_subject
from crawler.records import JobRecord


class EmailerTests(unittest.TestCase):
    def test_build_subject_includes_site_keyword_and_count(self) -> None:
        self.assertEqual(
            _build_subject("cake", "後端", 3),
            "[Crawler] cake 後端 new jobs: 3",
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


if __name__ == "__main__":
    unittest.main()
