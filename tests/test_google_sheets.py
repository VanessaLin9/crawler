from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from crawler.google_sheets import _ensure_header_row, sync_job_records
from crawler.records import LEGACY_SHEET_COLUMNS_V24, JobRecord, SHEET_COLUMNS


def _job_record(job_url: str = "https://example.com/1") -> JobRecord:
    return JobRecord(
        job_url=job_url,
        title="Engineer",
        company_name="ACME",
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
        summary="",
        source_site="wwr",
        search_page_url="",
        content_updated_at="2026-07-23",
        discovered_at="2026-07-23T00:00:00+00:00",
        application_deadline="2026-08-22",
    )


def _service_with_header(header: list[str] | None) -> tuple[MagicMock, MagicMock]:
    service = MagicMock()
    values_api = MagicMock()
    service.spreadsheets.return_value.values.return_value = values_api
    if header is None:
        values_api.get.return_value.execute.return_value = {"values": []}
    else:
        values_api.get.return_value.execute.return_value = {"values": [header]}
    return service, values_api


class GoogleSheetHeaderTests(unittest.TestCase):
    def test_empty_header_writes_current_schema(self) -> None:
        service, values_api = _service_with_header(None)

        upgraded = _ensure_header_row(service, "sheet-id", "wwr_jobs")

        self.assertFalse(upgraded)
        values_api.update.assert_called_once()
        body = values_api.update.call_args.kwargs["body"]
        self.assertEqual(body["values"], [SHEET_COLUMNS])

    def test_current_header_is_noop(self) -> None:
        service, values_api = _service_with_header(SHEET_COLUMNS)

        upgraded = _ensure_header_row(service, "sheet-id", "wwr_jobs")

        self.assertFalse(upgraded)
        values_api.update.assert_not_called()

    def test_exact_legacy_header_upgrades_first_row_only(self) -> None:
        service, values_api = _service_with_header(LEGACY_SHEET_COLUMNS_V24)

        upgraded = _ensure_header_row(service, "sheet-id", "wwr_jobs")

        self.assertTrue(upgraded)
        values_api.update.assert_called_once()
        kwargs = values_api.update.call_args.kwargs
        self.assertEqual(kwargs["range"], "wwr_jobs!1:1")
        self.assertEqual(kwargs["body"]["values"], [SHEET_COLUMNS])
        values_api.clear.assert_not_called()

    def test_legacy_upgrade_second_pass_is_noop(self) -> None:
        service, values_api = _service_with_header(LEGACY_SHEET_COLUMNS_V24)
        first = _ensure_header_row(service, "sheet-id", "wwr_jobs")
        values_api.get.return_value.execute.return_value = {"values": [SHEET_COLUMNS]}
        second = _ensure_header_row(service, "sheet-id", "wwr_jobs")

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(values_api.update.call_count, 1)

    def test_missing_column_header_fails_closed(self) -> None:
        service, _values_api = _service_with_header(LEGACY_SHEET_COLUMNS_V24[:-1])

        with self.assertRaisesRegex(ValueError, "does not match the current schema"):
            _ensure_header_row(service, "sheet-id", "wwr_jobs")

    def test_reordered_header_fails_closed(self) -> None:
        reordered = list(LEGACY_SHEET_COLUMNS_V24)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        service, _values_api = _service_with_header(reordered)

        with self.assertRaisesRegex(ValueError, "does not match the current schema"):
            _ensure_header_row(service, "sheet-id", "wwr_jobs")

    def test_extra_column_header_fails_closed(self) -> None:
        service, _values_api = _service_with_header(
            LEGACY_SHEET_COLUMNS_V24 + ["bonus_column"]
        )

        with self.assertRaisesRegex(ValueError, "does not match the current schema"):
            _ensure_header_row(service, "sheet-id", "wwr_jobs")

    def test_renamed_header_fails_closed(self) -> None:
        renamed = list(LEGACY_SHEET_COLUMNS_V24)
        renamed[-1] = "found_at"
        service, _values_api = _service_with_header(renamed)

        with self.assertRaisesRegex(ValueError, "does not match the current schema"):
            _ensure_header_row(service, "sheet-id", "wwr_jobs")


class GoogleSheetSyncTests(unittest.TestCase):
    @patch("crawler.google_sheets._append_rows")
    @patch("crawler.google_sheets._fetch_existing_job_urls", return_value=set())
    @patch("crawler.google_sheets._ensure_header_row", return_value=True)
    @patch("crawler.google_sheets._ensure_sheet_exists")
    @patch("crawler.google_sheets._build_sheets_service")
    def test_sync_appends_after_successful_header_upgrade(
        self,
        _mock_build: MagicMock,
        _mock_ensure_sheet: MagicMock,
        _mock_ensure_header: MagicMock,
        _mock_fetch_urls: MagicMock,
        mock_append: MagicMock,
    ) -> None:
        result = sync_job_records(
            records=[_job_record()],
            spreadsheet_id="sheet-id",
            sheet_name="wwr_jobs",
            service_account_path="secrets/google-service-account.json",
        )

        self.assertEqual(result.appended_count, 1)
        self.assertTrue(result.header_upgraded_from_legacy)
        mock_append.assert_called_once()
        self.assertEqual(mock_append.call_args.args[3][0][-1], "2026-08-22")

    @patch("crawler.google_sheets._append_rows")
    @patch("crawler.google_sheets._fetch_existing_job_urls")
    @patch("crawler.google_sheets._ensure_header_row")
    @patch("crawler.google_sheets._ensure_sheet_exists")
    @patch("crawler.google_sheets._build_sheets_service")
    def test_header_update_failure_does_not_append(
        self,
        _mock_build: MagicMock,
        _mock_ensure_sheet: MagicMock,
        mock_ensure_header: MagicMock,
        mock_fetch_urls: MagicMock,
        mock_append: MagicMock,
    ) -> None:
        mock_ensure_header.side_effect = RuntimeError("sheets update failed")

        with self.assertRaisesRegex(RuntimeError, "sheets update failed"):
            sync_job_records(
                records=[_job_record()],
                spreadsheet_id="sheet-id",
                sheet_name="wwr_jobs",
                service_account_path="secrets/google-service-account.json",
            )

        mock_fetch_urls.assert_not_called()
        mock_append.assert_not_called()


if __name__ == "__main__":
    unittest.main()
