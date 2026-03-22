import unittest

from crawler.records import SHEET_COLUMNS, flatten_job_records


class RecordTests(unittest.TestCase):
    def test_flatten_job_records_dedupes_by_job_url(self) -> None:
        results = [
            {
                "site": "cake",
                "keyword": "後端",
                "url": "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                "matches": [
                    {
                        "job_url": "https://www.cake.me/jobs/1",
                        "title": "Backend Engineer",
                        "company_name": "ACME",
                        "company_url": "https://www.cake.me/companies/acme",
                        "summary": "Backend services",
                        "location": "台北市, 台灣",
                        "salary_min": "100000",
                        "salary_max": "170000",
                        "salary_currency": "TWD",
                        "salary_type": "per_month",
                        "salary_display": "100000 - 170000 TWD per_month",
                        "openings_count": "1",
                        "employment_type": "full_time",
                        "seniority_level": "entry_level",
                        "experience_required_years": "4",
                        "management_responsibility": "none",
                        "tags": "Backend, Python",
                        "content_updated_at": "2026-03-22T12:00:00Z",
                        "matched_fields": ["title"],
                        "matched_terms": ["backend"],
                    }
                ],
            },
            {
                "site": "cake",
                "keyword": "後端",
                "url": "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it?page=2",
                "matches": [
                    {
                        "job_url": "https://www.cake.me/jobs/1",
                        "title": "Backend Engineer",
                        "company_name": "ACME",
                        "company_url": "https://www.cake.me/companies/acme",
                        "summary": "Backend services with Python",
                        "location": "台北市, 台灣",
                        "salary_min": "100000",
                        "salary_max": "170000",
                        "salary_currency": "TWD",
                        "salary_type": "per_month",
                        "salary_display": "100000 - 170000 TWD per_month",
                        "openings_count": "1",
                        "employment_type": "full_time",
                        "seniority_level": "entry_level",
                        "experience_required_years": "4",
                        "management_responsibility": "none",
                        "tags": "Backend, Python",
                        "content_updated_at": "2026-03-22T12:00:00Z",
                        "matched_fields": ["summary"],
                        "matched_terms": ["python"],
                    }
                ],
            },
        ]

        records = flatten_job_records(results, discovered_at="2026-03-22T12:00:00+00:00")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].job_url, "https://www.cake.me/jobs/1")
        self.assertEqual(records[0].matched_fields, ["title", "summary"])
        self.assertEqual(records[0].matched_terms, ["backend", "python"])
        self.assertEqual(records[0].summary, "Backend services with Python")

    def test_sheet_row_matches_expected_header_width(self) -> None:
        record = flatten_job_records(
            [
                {
                    "site": "cake",
                    "keyword": "後端",
                    "url": "https://www.cake.me/jobs/%E5%BE%8C%E7%AB%AF/for-it",
                    "matches": [
                        {
                            "job_url": "https://www.cake.me/jobs/1",
                            "title": "Backend Engineer",
                        "company_name": "ACME",
                        "company_url": "https://www.cake.me/companies/acme",
                        "summary": "Backend services",
                        "location": "台北市, 台灣",
                        "salary_min": "100000",
                        "salary_max": "170000",
                        "salary_currency": "TWD",
                        "salary_type": "per_month",
                        "salary_display": "100000 - 170000 TWD per_month",
                        "openings_count": "1",
                        "employment_type": "full_time",
                        "seniority_level": "entry_level",
                        "experience_required_years": "4",
                        "management_responsibility": "none",
                        "tags": "Backend, Python",
                        "content_updated_at": "2026-03-22T12:00:00Z",
                        "matched_fields": ["title"],
                        "matched_terms": ["backend"],
                    }
                ],
                }
            ],
            discovered_at="2026-03-22T12:00:00+00:00",
        )[0]

        self.assertEqual(len(record.to_sheet_row()), len(SHEET_COLUMNS))


if __name__ == "__main__":
    unittest.main()
