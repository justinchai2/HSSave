from receipt_parser import parse_receipt
from google_drive import upload_receipt, delete_receipt
from google_sheets import append_receipt_row, delete_receipt_row
from dashboard import update_dashboard
from watcher import start_watching


def process_receipt(image_path: str, original_filename: str) -> dict:
    print(f"\nProcessing receipt: {original_filename}")

    parsed = parse_receipt(image_path)
    drive_file_id, drive_url = upload_receipt(
        image_path,
        receipt_date=parsed.get("receipt_date", "unknown-date"),
        merchant=parsed.get("merchant", "unknown-merchant"),
    )
    append_receipt_row(parsed, drive_url, original_filename)
    parsed["drive_url"] = drive_url
    parsed["drive_file_id"] = drive_file_id
    update_dashboard()

    print(f"  Done. HSA eligible: ${parsed.get('hsa_eligible_amount', '0')}\n")
    return parsed


def delete_receipt_data(drive_file_id: str, drive_url: str):
    delete_receipt(drive_file_id)
    delete_receipt_row(drive_url)
    update_dashboard()


if __name__ == "__main__":
    start_watching(process_receipt, delete_receipt_data)
