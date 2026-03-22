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
