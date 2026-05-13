import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_NAME = os.getenv("DISCORD_CHANNEL_NAME", "hsa-receipts")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

SHEETS_HEADERS = [
    "Receipt ID",
    "Date Processed",
    "Submitted By",
    "Receipt Date",
    "Merchant",
    "Total",
    "HSA Eligible Amount",
    "Notes",
    "Drive File URL",
    "Original Filename",
]
