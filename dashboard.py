from collections import defaultdict
from datetime import datetime
from googleapiclient.discovery import build
from google_auth import get_credentials
from config import GOOGLE_SHEETS_ID

CATEGORIES = ["Medical", "Dental", "Vision", "Pharmacy", "Other"]


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
        range="Sheet1!A2:J",
    ).execute()
    return result.get("values", [])


def _build_summaries(rows):
    category_totals = defaultdict(float)
    monthly_eligible = defaultdict(float)
    cumulative = []
    running_total = 0.0

    for row in rows:
        if len(row) < 7:
            continue
        category = row[4] if len(row) > 4 else "Other"
        receipt_date = row[2] if len(row) > 2 else ""
        try:
            hsa = float(row[7]) if len(row) > 7 and row[7] else 0.0
        except (ValueError, TypeError):
            hsa = 0.0

        category_totals[category if category in CATEGORIES else "Other"] += hsa

        if receipt_date:
            try:
                month = datetime.strptime(receipt_date, "%Y-%m-%d").strftime("%b %Y")
                monthly_eligible[month] += hsa
            except ValueError:
                pass

        running_total += hsa
        cumulative.append([row[0] if row else "", round(running_total, 2)])

    return category_totals, monthly_eligible, cumulative


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


def _chart_request(sheet_id, chart_type, title, data_range, anchor_col, anchor_row):
    series_range = {
        "sheetId": sheet_id,
        "startRowIndex": data_range[0],
        "endRowIndex": data_range[1],
        "startColumnIndex": data_range[2] + 1,
        "endColumnIndex": data_range[2] + 2,
    }
    domain_range = {
        "sheetId": sheet_id,
        "startRowIndex": data_range[0],
        "endRowIndex": data_range[1],
        "startColumnIndex": data_range[2],
        "endColumnIndex": data_range[2] + 1,
    }

    if chart_type == "PIE":
        spec = {
            "title": title,
            "pieChart": {
                "legendPosition": "RIGHT_LEGEND",
                "domain": {"sourceRange": {"sources": [domain_range]}},
                "series": {"sourceRange": {"sources": [series_range]}},
            },
        }
    elif chart_type == "COLUMN":
        spec = {
            "title": title,
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
        }
    else:  # LINE
        spec = {
            "title": title,
            "basicChart": {
                "chartType": "LINE",
                "legendPosition": "BOTTOM_LEGEND",
                "axis": [
                    {"position": "BOTTOM_AXIS", "title": "Date"},
                    {"position": "LEFT_AXIS", "title": "Cumulative ($)"},
                ],
                "domains": [{"domain": {"sourceRange": {"sources": [domain_range]}}}],
                "series": [{"series": {"sourceRange": {"sources": [series_range]}}}],
            },
        }

    return {
        "addChart": {
            "chart": {
                "spec": spec,
                "position": {
                    "overlayPosition": {
                        "anchorCell": {
                            "sheetId": sheet_id,
                            "rowIndex": anchor_row,
                            "columnIndex": anchor_col,
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
    category_totals, monthly_eligible, cumulative = _build_summaries(rows)

    # --- Write summary tables ---
    # Table 1: Category (A1) — used by pie chart
    cat_table = [["Category", "HSA Eligible ($)"]] + [
        [c, round(category_totals.get(c, 0.0), 2)] for c in CATEGORIES
    ]
    # Table 2: Monthly (D1) — used by bar chart
    monthly_table = [["Month", "HSA Eligible ($)"]] + [
        [m, round(v, 2)] for m, v in sorted(monthly_eligible.items(),
        key=lambda x: datetime.strptime(x[0], "%b %Y"))
    ]
    # Table 3: Cumulative (G1) — used by line chart
    cumulative_table = [["Date Processed", "Cumulative HSA ($)"]] + cumulative

    service.spreadsheets().values().clear(
        spreadsheetId=GOOGLE_SHEETS_ID, range="Dashboard!A1:Z1000"
    ).execute()

    for range_start, table in [("Dashboard!A1", cat_table), ("Dashboard!D1", monthly_table), ("Dashboard!G1", cumulative_table)]:
        service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEETS_ID,
            range=range_start,
            valueInputOption="USER_ENTERED",
            body={"values": table},
        ).execute()

    # --- Recreate charts ---
    _delete_existing_charts(service, sheet_id)

    n_monthly = max(len(monthly_table), 2)
    n_cumulative = max(len(cumulative_table), 2)

    requests = [
        _chart_request(sheet_id, "PIE",    "Spending by Category",          [1, 7, 0],          0, 8),
        _chart_request(sheet_id, "COLUMN", "Monthly HSA Eligible Spending",  [1, n_monthly, 3],  5, 8),
        _chart_request(sheet_id, "LINE",   "Cumulative HSA Withdrawable",    [1, n_cumulative, 6], 10, 8),
    ]
    service.spreadsheets().batchUpdate(
        spreadsheetId=GOOGLE_SHEETS_ID, body={"requests": requests}
    ).execute()

    print("  Dashboard updated.")
