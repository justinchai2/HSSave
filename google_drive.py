from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth import get_credentials
from config import GOOGLE_DRIVE_FOLDER_ID


def upload_receipt(image_path: str, receipt_date: str, merchant: str) -> str:
    """Upload image to Google Drive and return the shareable file URL."""
    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)

    path = Path(image_path)
    safe_merchant = merchant.replace("/", "-").replace("\\", "-") or "Unknown"
    drive_filename = f"{receipt_date}_{safe_merchant}{path.suffix}"

    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
    }
    mime_type = mime_map.get(ext, "image/jpeg")

    file_metadata = {
        "name": drive_filename,
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(image_path, mimetype=mime_type, resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
    ).execute()

    print(f"  Uploaded to Drive: {drive_filename}")
    return uploaded.get("id", ""), uploaded.get("webViewLink", "")


def delete_receipt(file_id: str):
    creds = get_credentials()
    service = build("drive", "v3", credentials=creds)
    service.files().delete(fileId=file_id).execute()
    print(f"  Deleted from Drive: {file_id}")
