from collections import defaultdict
from datetime import datetime
from googleapiclient.discovery import build
from google_auth import get_credentials
from config import GOOGLE_SHEETS_ID


def _get_or_create_sheet(service, title):
    spreadsheet = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEETS_ID).execute()
    for sheet in spreadsheet["sheets"]:
        if sheet["properties"]["title"] == title:
            return sheet["properties"]["sheetId"]
    result = service.spreadsheets().batchUpdate(
        spreadsheetId=GOOGLE_SHEETS_ID,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    ).execute()
    return result["replies"][0]["addSheet"]["properties"]["sheetId"]


def _read_receipts(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Sheet1!A2:G",
    ).execute()
    return result.get("values", [])


def _build_monthly_table(rows):
    monthly_eligible = defaultdict(float)

    for row in rows:
        if len(row) < 7:
            continue
        # 0=Receipt ID, 3=Receipt Date, 6=HSA Eligible Amount
        receipt_date = row[3] if len(row) > 3 else ""
        try:
            hsa = float(row[6]) if len(row) > 6 and row[6] else 0.0
        except (ValueError, TypeError):
            hsa = 0.0

        if receipt_date:
            try:
                month = datetime.strptime(receipt_date, "%Y-%m-%d").strftime("%b %Y")
                monthly_eligible[month] += hsa
            except ValueError:
                pass

    table = [["Month", "HSA Eligible ($)"]] + [
        [m, round(v, 2)]
        for m, v in sorted(
            monthly_eligible.items(),
            key=lambda x: datetime.strptime(x[0], "%b %Y"),
        )
    ]
    return table


def _delete_existing_charts(service, sheet_id):
    spreadsheet = service.spreadsheets().get(spreadsheetId=GOOGLE_SHEETS_ID).execute()
    for sheet in spreadsheet["sheets"]:
        if sheet["properties"]["sheetId"] == sheet_id:
            charts = sheet.get("charts", [])
            if charts:
                requests = [{"deleteEmbeddedObject": {"objectId": c["chartId"]}} for c in charts]
                service.spreadsheets().batchUpdate(
                    spreadsheetId=GOOGLE_SHEETS_ID,
                    body={"requests": requests},
                ).execute()


def _column_chart_request(sheet_id, n_rows):
    domain_range = {
        "sheetId": sheet_id,
        "startRowIndex": 0,
        "endRowIndex": n_rows,
        "startColumnIndex": 0,
        "endColumnIndex": 1,
    }
    series_range = {
        "sheetId": sheet_id,
        "startRowIndex": 0,
        "endRowIndex": n_rows,
        "startColumnIndex": 1,
        "endColumnIndex": 2,
    }
    return {
        "addChart": {
            "chart": {
                "spec": {
                    "title": "Monthly HSA Eligible Spending",
                    "basicChart": {
                        "chartType": "COLUMN",
                        "legendPosition": "BOTTOM_LEGEND",
                        "axis": [
                            {"position": "BOTTOM_AXIS", "title": "Month"},
                            {"position": "LEFT_AXIS", "title": "USD ($)"},
                        ],
                        "domains": [{"domain": {"sourceRange": {"sources": [domain_range]}}}],
                        "series": [{"series": {"sourceRange": {"sources": [series_range]}}}],
                    },
                },
                "position": {
                    "overlayPosition": {
                        "anchorCell": {
                            "sheetId": sheet_id,
                            "rowIndex": 0,
                            "columnIndex": 3,
                        },
                        "widthPixels": 480,
                        "heightPixels": 300,
                    }
                },
            }
        }
    }


def update_dashboard():
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)
    sheet_id = _get_or_create_sheet(service, "Dashboard")

    rows = _read_receipts(service)
    monthly_table = _build_monthly_table(rows)

    # Clear and rewrite the monthly table starting at A1
    service.spreadsheets().values().clear(
        spreadsheetId=GOOGLE_SHEETS_ID, range="Dashboard!A1:Z1000"
    ).execute()

    service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEETS_ID,
        range="Dashboard!A1",
        valueInputOption="USER_ENTERED",
        body={"values": monthly_table},
    ).execute()

    # Recreate the single bar chart
    _delete_existing_charts(service, sheet_id)

    n_rows = max(len(monthly_table), 2)
    service.spreadsheets().batchUpdate(
        spreadsheetId=GOOGLE_SHEETS_ID,
        body={"requests": [_column_chart_request(sheet_id, n_rows)]},
    ).execute()

    print("  Dashboard updated.")
