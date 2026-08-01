from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from crawler.records import LEGACY_SHEET_COLUMNS_V24, JobRecord, SHEET_COLUMNS


DEFAULT_GOOGLE_SERVICE_ACCOUNT = "secrets/google-service-account.json"
DEFAULT_GOOGLE_SHEET_NAME = "cake_jobs"


@dataclass(slots=True)
class SheetSyncResult:
    appended_count: int
    appended_records: list[JobRecord]
    skipped_count: int
    sheet_name: str
    spreadsheet_id: str
    header_upgraded_from_legacy: bool = False


def sync_job_records(
    records: list[JobRecord],
    spreadsheet_id: str,
    sheet_name: str,
    service_account_path: str,
    reset_sheet: bool = False,
) -> SheetSyncResult:
    service = _build_sheets_service(service_account_path)
    _ensure_sheet_exists(service, spreadsheet_id, sheet_name)
    if reset_sheet:
        _clear_sheet(service, spreadsheet_id, sheet_name)
    header_upgraded = _ensure_header_row(service, spreadsheet_id, sheet_name)
    if header_upgraded:
        print(
            f"Google Sheet '{sheet_name}' header upgraded from 24 to "
            f"{len(SHEET_COLUMNS)} columns; existing rows were kept."
        )
    existing_urls = _fetch_existing_job_urls(service, spreadsheet_id, sheet_name)

    appended_records = [
        record
        for record in records
        if record.job_url not in existing_urls
    ]
    rows_to_append = [record.to_sheet_row() for record in appended_records]
    if rows_to_append:
        _append_rows(service, spreadsheet_id, sheet_name, rows_to_append)

    return SheetSyncResult(
        appended_count=len(rows_to_append),
        appended_records=appended_records,
        skipped_count=len(records) - len(rows_to_append),
        sheet_name=sheet_name,
        spreadsheet_id=spreadsheet_id,
        header_upgraded_from_legacy=header_upgraded,
    )


def _build_sheets_service(service_account_path: str):
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Sheets sync requires installed dependencies. Run `pip install -e .` "
            "or install from pyproject.toml before using --sync-google-sheet."
        ) from exc

    credentials_path = Path(service_account_path)
    if not credentials_path.is_file():
        raise FileNotFoundError(
            f"Service account JSON not found: {service_account_path}"
        )

    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _ensure_sheet_exists(service, spreadsheet_id: str, sheet_name: str) -> None:
    spreadsheet = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id)
        .execute()
    )
    existing_titles = {
        sheet["properties"]["title"]
        for sheet in spreadsheet.get("sheets", [])
    }
    if sheet_name in existing_titles:
        return

    (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name,
                            }
                        }
                    }
                ]
            },
        )
        .execute()
    )


def _ensure_header_row(service, spreadsheet_id: str, sheet_name: str) -> bool:
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!1:1",
        )
        .execute()
    )
    values = response.get("values", [])
    if not values:
        _update_values(
            service,
            spreadsheet_id,
            f"{sheet_name}!1:1",
            [SHEET_COLUMNS],
        )
        return False

    header = values[0]
    if header == SHEET_COLUMNS:
        return False

    # 僅在 header 精確等於 V24 時升級（PR #11）：只改第 1 列、不清空資料列、不 backfill。
    # 其他變形 header 寧願失敗，避免默默對錯欄位。
    if header == LEGACY_SHEET_COLUMNS_V24:
        _update_values(
            service,
            spreadsheet_id,
            f"{sheet_name}!1:1",
            [SHEET_COLUMNS],
        )
        return True

    if "job_url" not in header:
        raise ValueError(
            f"Sheet '{sheet_name}' has an unexpected header row: {header}. "
            "Create an empty sheet or add a header containing 'job_url'."
        )

    raise ValueError(
        f"Sheet '{sheet_name}' header does not match the current schema or the "
        f"supported legacy 24-column schema. Current schema ends with "
        f"'application_deadline'; unsupported header: {header}."
    )


def _fetch_existing_job_urls(
    service,
    spreadsheet_id: str,
    sheet_name: str,
) -> set[str]:
    response = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A2:A",
        )
        .execute()
    )
    return {
        row[0].strip()
        for row in response.get("values", [])
        if row and row[0].strip()
    }


def _append_rows(
    service,
    spreadsheet_id: str,
    sheet_name: str,
    rows: list[list[str]],
) -> None:
    (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:{_column_letter(len(SHEET_COLUMNS))}",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        )
        .execute()
    )


def _clear_sheet(service, spreadsheet_id: str, sheet_name: str) -> None:
    (
        service.spreadsheets()
        .values()
        .clear(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:ZZ",
            body={},
        )
        .execute()
    )


def _update_values(service, spreadsheet_id: str, range_name: str, values: list[list[str]]) -> None:
    (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            body={"values": values},
        )
        .execute()
    )


def _column_letter(index: int) -> str:
    result = ""
    value = index
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result
