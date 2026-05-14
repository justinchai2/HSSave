import json
from pathlib import Path
from google import genai
from google.genai import types
from config import GEMINI_API_KEY
from usage_tracker import record_usage

client = genai.Client(api_key=GEMINI_API_KEY)

PROMPT = """You are an HSA (Health Savings Account) receipt parser. Analyze this receipt image and extract information as JSON.

Use the official IRS Publication 502 rules below to determine HSA eligibility for each line item.

=== IRS PUBLICATION 502 — HSA ELIGIBLE EXPENSES ===
ELIGIBLE (count toward hsa_eligible_amount):
- Prescription drugs and insulin
- Doctor/physician visits and copays
- Hospital services and surgery
- Dental treatment: cleanings, fillings, extractions, braces, dentures
- Vision: eye exams, prescription glasses, contact lenses and supplies, LASIK
- Mental health: therapy, psychiatry, psychology visits
- Physical therapy and occupational therapy
- Chiropractic care
- Acupuncture
- Hearing aids and batteries
- Medical equipment: wheelchairs, crutches, blood sugar monitors, CPAP supplies
- Bandages and medical supplies
- Lab fees and diagnostic tests
- Ambulance services
- Fertility treatments
- Pregnancy test kits
- Breast pumps and lactation supplies
- Stop-smoking programs and prescription aids
- Substance abuse treatment
- Weight loss programs (only if prescribed by doctor for a specific disease)
- Vitamins and supplements (only if prescribed by doctor)
- Guide dogs and service animals
- Long-term care

NOT ELIGIBLE (exclude from hsa_eligible_amount):
- Cosmetic procedures (teeth whitening, electrolysis, hair transplants)
- Gym memberships and fitness programs (unless doctor-prescribed)
- Toiletries, toothpaste, soap, shampoo
- Non-prescription vitamins and supplements
- Maternity clothes
- Diaper service
- Health club dues
- Dancing or swimming lessons
- Funeral expenses
- Over-the-counter items that are not medical supplies (e.g. sunscreen, chapstick)
- Food and beverages (even if purchased at a pharmacy)
=== END IRS RULES ===

Return ONLY valid JSON with these fields:
{
  "receipt_date": "YYYY-MM-DD or empty string if not found",
  "merchant": "store or provider name",
  "total": "total amount charged as numeric string, e.g. 27.00",
  "hsa_eligible_amount": "sum of only IRS-eligible items as numeric string, e.g. 18.50",
  "notes": "brief explanation of any items excluded from HSA eligibility, or empty string"
}

If a field cannot be determined from the image, use an empty string."""


def parse_receipt(image_path: str) -> dict:
    print(f"  Parsing receipt: {Path(image_path).name}")

    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".heic": "image/heic",
    }
    mime_type = mime_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        image_data = f.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_data, mime_type=mime_type),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    usage = response.usage_metadata
    if usage:
        record_usage(
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=usage.candidates_token_count or 0,
        )

    raw = response.text.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
