from datetime import datetime
from googleapiclient.discovery import build
from google_auth import get_credentials
from config import GOOGLE_SHEETS_ID, SHEETS_HEADERS


def _ensure_headers(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!A1:N1",
    ).execute()
    existing = result.get("values", [])
    if not existing or existing[0] != SHEETS_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [SHEETS_HEADERS]},
        ).execute()


def append_receipt_row(parsed: dict, drive_url: str, original_filename: str, submitted_by: str = ""):
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    _ensure_headers(service)

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        submitted_by,
        parsed.get("receipt_date", ""),
        parsed.get("merchant", ""),
        parsed.get("category", ""),
        parsed.get("items", ""),
        parsed.get("total", ""),
        parsed.get("hsa_eligible_amount", ""),
        parsed.get("hsa_eligible_items", ""),
        parsed.get("hsa_ineligible_items", ""),
        parsed.get("notes", ""),
        drive_url,
        original_filename,
    ]

    service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    print(f"  Logged to Sheets: {parsed.get('merchant')} — ${parsed.get('total')} (by {submitted_by})")
    _update_summary(service)


def delete_receipt_row(drive_url: str):
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    spreadsheet = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEETS_ID).execute()
    sheet_id = spreadsheet["sheets"][0]["properties"]["sheetId"]

    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!A:M",
    ).execute()
    rows = result.get("values", [])

    row_index = None
    for i, row in enumerate(rows):
        if len(row) > 11 and row[11] == drive_url:
            row_index = i
            break

    if row_index is None:
        print("  Row not found in Sheets.")
        return

    service.spreadsheets().batchUpdate(
        spreadsheetId=GOOGLE_SHEETS_ID,
        body={"requests": [{"deleteDimension": {"range": {
            "sheetId": sheet_id,
            "dimension": "ROWS",
            "startIndex": row_index,
            "endIndex": row_index + 1,
        }}}]},
    ).execute()
    print("  Deleted row from Sheets.")


def _update_summary(service):
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!M1:N2",
        valueInputOption="USER_ENTERED",
        body={"values": [
            ["Total HSA Withdrawable", ""],
            ["=SUM(H2:H)", ""],
        ]},
    ).execute()
