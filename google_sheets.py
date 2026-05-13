from datetime import datetime
from googleapiclient.discovery import build
from google_auth import get_credentials
from config import GOOGLE_SHEETS_ID, SHEETS_HEADERS

# Column layout (0-indexed):
# 0  Receipt ID          (A)
# 1  Date Processed      (B)
# 2  Submitted By        (C)
# 3  Receipt Date        (D)
# 4  Merchant            (E)
# 5  Total               (F)
# 6  HSA Eligible Amount (G)
# 7  Notes               (H)
# 8  Drive File URL      (I)
# 9  Original Filename   (J)
# Summary written to L1:M2 (clear of data)


def _ensure_headers(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!A1:J1",
    ).execute()
    existing = result.get("values", [])
    if not existing or existing[0] != SHEETS_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range="Sheet1!A1",
            valueInputOption="RAW",
            body={"values": [SHEETS_HEADERS]},
        ).execute()


def append_receipt_row(parsed: dict, drive_url: str, original_filename: str,
                       submitted_by: str = "", receipt_id: str = ""):
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    _ensure_headers(service)

    row = [
        receipt_id,
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        submitted_by,
        parsed.get("receipt_date", ""),
        parsed.get("merchant", ""),
        parsed.get("total", ""),
        parsed.get("hsa_eligible_amount", ""),
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
        range="Sheet1!A:J",
    ).execute()
    rows = result.get("values", [])

    row_index = None
    for i, row in enumerate(rows):
        if len(row) > 8 and row[8] == drive_url:  # Drive File URL at index 8
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


def update_receipt_hsa(receipt_id: str, hsa_amount: float) -> bool:
    """Find a row by Receipt ID and update its HSA Eligible Amount. Returns True on success."""
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!A:G",
    ).execute()
    rows = result.get("values", [])

    row_index = None
    for i, row in enumerate(rows):
        if row and row[0] == receipt_id:
            row_index = i
            break

    if row_index is None:
        print(f"  Receipt ID {receipt_id} not found in Sheets.")
        return False

    sheet_row = row_index + 1
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range=f"Sheet1!G{sheet_row}",  # Column G = HSA Eligible Amount
        valueInputOption="USER_ENTERED",
        body={"values": [[hsa_amount]]},
    ).execute()

    _update_summary(service)
    print(f"  Updated HSA amount for {receipt_id} to ${hsa_amount}")
    return True


def _update_summary(service):
    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!L1:M2",
        valueInputOption="USER_ENTERED",
        body={"values": [
            ["Total HSA Withdrawable", ""],
            ["=SUM(G2:G)", ""],
        ]},
    ).execute()
