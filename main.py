import uuid
from datetime import datetime
from receipt_parser import parse_receipt
from google_drive import upload_receipt, delete_receipt
from google_sheets import append_receipt_row, delete_receipt_row, update_receipt_hsa
from dashboard import update_dashboard
from watcher import start_watching


def _generate_receipt_id() -> str:
    suffix = uuid.uuid4().hex[:4].upper()
    return f"HSA-{datetime.now().strftime('%Y%m%d')}-{suffix}"


def process_receipt(image_path: str, original_filename: str, submitted_by: str = "") -> dict:
    print(f"\nProcessing receipt: {original_filename} (from {submitted_by})")

    receipt_id = _generate_receipt_id()
    parsed = parse_receipt(image_path)
    drive_file_id, drive_url = upload_receipt(
        image_path,
        receipt_date=parsed.get("receipt_date", "unknown-date"),
        merchant=parsed.get("merchant", "unknown-merchant"),
    )
    append_receipt_row(parsed, drive_url, original_filename, submitted_by, receipt_id)
    parsed["drive_url"] = drive_url
    parsed["drive_file_id"] = drive_file_id
    parsed["receipt_id"] = receipt_id
    update_dashboard()

    print(f"  Done. HSA eligible: ${parsed.get('hsa_eligible_amount', '0')}\n")
    return parsed


def delete_receipt_data(drive_file_id: str, drive_url: str):
    delete_receipt(drive_file_id)
    delete_receipt_row(drive_url)
    update_dashboard()


def recategorize_receipt(receipt_id: str, hsa_amount: float) -> bool:
    success = update_receipt_hsa(receipt_id, hsa_amount)
    if success:
        update_dashboard()
    return success


if __name__ == "__main__":
    start_watching(process_receipt, delete_receipt_data, recategorize_receipt)
