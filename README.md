# HSSave

An automated HSA (Health Savings Account) receipt manager. Send a receipt photo to a private Discord channel and HSSave will:

1. Parse the receipt using Google Gemini AI
2. Determine HSA eligibility based on IRS Publication 502 rules
3. Upload the image to Google Drive
4. Log the details to Google Sheets
5. Refresh a visual Dashboard with charts
6. Reply in Discord with a summary and your monthly Gemini usage

React with 🚫 to any bot confirmation message to delete that receipt from Drive and Sheets.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Bot](#running-the-bot)
- [Google Sheets Structure](#google-sheets-structure)
- [HSA Eligibility Logic](#hsa-eligibility-logic)
- [Deleting a Receipt](#deleting-a-receipt)
- [Costs](#costs)
- [Limitations](#limitations)
- [Hosting on a Cloud Server](#hosting-on-a-cloud-server)

---

## How It Works

```
Take receipt photo on phone
        ↓
Send photo to #hsa-receipts Discord channel
        ↓
Bot downloads the image
        ↓
Gemini 2.5 Flash parses receipt + checks IRS Publication 502 eligibility
        ↓
Image uploaded to Google Drive (named by date + merchant)
        ↓
Row appended to Google Sheets with all receipt details
        ↓
Dashboard tab refreshed with updated charts
        ↓
Bot replies in Discord with summary + monthly Gemini usage
```

---

## Prerequisites

- Python 3.10+
- A personal Google account (Gmail)
- A Discord account and server
- API keys for Gemini and Discord (both free to obtain)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/justinchai2/HSSave.git
cd HSSave
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get a Gemini API key

1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your **personal Gmail account** (not a work/school account — the free tier is not available on org accounts)
3. Click **"Create API key"** and copy it

> **Important:** If you get a `429 RESOURCE_EXHAUSTED` error with `limit: 0`, your account needs billing enabled. Go to [console.cloud.google.com](https://console.cloud.google.com), select your project, and enable billing. Costs are negligible (~$0.002/month at personal use volume).

### 4. Set up Google APIs

#### 4a. Enable the APIs

Visit each link and click **"Enable"**:
- [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)
- [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)

#### 4b. Create OAuth 2.0 credentials

1. Go to [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
2. Click **"+ Create Credentials"** → **"OAuth 2.0 Client ID"**
3. If prompted, configure the OAuth consent screen first:
   - Choose **External**
   - Fill in app name (e.g. `HSSave`) and your email
   - Save and continue through all steps
4. Back on Create Credentials → choose **Desktop app** → click **Create**
5. Download the JSON file, rename it to `credentials.json`, and place it in the project root

#### 4c. Add yourself as a test user

1. Go to [console.cloud.google.com/apis/auth/audience](https://console.cloud.google.com/apis/auth/audience)
2. Under **"Test users"**, click **"+ Add Users"**
3. Enter your Gmail address and save

#### 4d. Get your Google Drive folder ID

1. Create a folder in Google Drive for your receipts
2. Open the folder in your browser — the URL will look like:
   `https://drive.google.com/drive/folders/1A2B3C4D5E6F7G8H9I0J`
3. Copy everything after `/folders/` — that is your folder ID

#### 4e. Get your Google Sheets ID

1. Create a new blank Google Sheet at [sheets.google.com](https://sheets.google.com)
2. The URL will look like:
   `https://docs.google.com/spreadsheets/d/1A2B3C4D5E6F7G8H9I0J/edit`
3. Copy everything between `/d/` and `/edit` — that is your sheet ID

### 5. Set up the Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **"New Application"** → name it `HSSave`
3. Go to **Bot** in the left sidebar → click **"Add Bot"**
4. Under **Token**, click **"Reset Token"** and copy it
5. Scroll down to **Privileged Gateway Intents** → enable **Message Content Intent** → Save
6. Go to **OAuth2 → URL Generator**:
   - Under Scopes: check **bot**
   - Under Bot Permissions: enter `68672` in the permissions integer field
   - Copy the generated URL, open it in your browser, select your server, and click **Authorize**
7. In your Discord server, create a channel called exactly `hsa-receipts`

### 6. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in all values:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_DRIVE_FOLDER_ID=your_google_drive_folder_id_here
GOOGLE_SHEETS_ID=your_google_sheets_id_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

---

## Running the Bot

```bash
python main.py
```

On first run, a browser window will open asking you to authorize Google Drive and Sheets access. Sign in with your Gmail and click **Allow**. A `token.json` file is saved so this only happens once.

The bot will print:
```
Starting HSSave Discord bot...
HSSave bot is online as HSSave#1234
Listening for receipts in #hsa-receipts
```

Keep this terminal open (or see [Hosting on a Cloud Server](#hosting-on-a-cloud-server) to run it 24/7).

---

## Google Sheets Structure

### Sheet1 (Receipts)

| Column | Description |
|---|---|
| Date Processed | When HSSave processed the image |
| Receipt Date | Date printed on the receipt |
| Merchant | Store or provider name |
| Category | Medical / Dental / Vision / Pharmacy / Other |
| Items | All line items on the receipt |
| Total | Total amount charged |
| HSA Eligible Amount | IRS-eligible portion only |
| HSA Eligible Items | Which specific items qualify |
| HSA Ineligible Items | Which items do not qualify |
| Notes | Prescription numbers, patient info, flags |
| Drive File URL | Link to image in Google Drive |
| Original Filename | Source filename from your phone |

A **Total HSA Withdrawable** cell (L2) automatically sums all HSA eligible amounts — this is the figure you can submit for reimbursement.

### Dashboard (Charts)

Automatically created and refreshed after every receipt:

- **Spending by Category** — pie chart (Medical / Dental / Vision / Pharmacy / Other)
- **Monthly HSA Eligible Spending** — bar chart by month
- **Cumulative HSA Withdrawable** — line chart showing your running total over time

---

## HSA Eligibility Logic

Eligibility is determined by Gemini AI using the full **IRS Publication 502** eligible expense list embedded in the prompt. Each receipt returns:

- `hsa_eligible_amount` — dollar total of qualifying items
- `hsa_eligible_items` — specific items that qualify
- `hsa_ineligible_items` — specific items that do not qualify

**Common eligible expenses:** prescription drugs, doctor/dental/vision visits, copays, hearing aids, medical equipment, therapy, chiropractic care, LASIK, lab fees.

**Common ineligible expenses:** cosmetic procedures, gym memberships, general vitamins, toiletries, teeth whitening.

> **Note:** AI eligibility decisions are a best-effort interpretation and should not replace professional tax advice. Always verify unusual items before submitting for reimbursement.

---

## Deleting a Receipt

To undo a receipt that was processed by mistake:

1. Find the bot's confirmation reply in `#hsa-receipts`
2. React to it with 🚫
3. The bot will delete the image from Google Drive, remove the row from Google Sheets, and refresh the Dashboard

> **Limitation:** Deletion only works for receipts processed in the **current bot session**. If the bot was restarted after the receipt was processed, you will need to delete it manually from Google Drive and Google Sheets.

---

## Costs

| Service | Monthly Cost | Notes |
|---|---|---|
| Gemini 2.5 Flash | ~$0.002 | At ~10 receipts/month. ~$0.0002 per receipt |
| Google Drive API | Free | Up to 15GB included with Google account |
| Google Sheets API | Free | No usage limits for personal use |
| Discord bot | Free | |
| Cloud server (optional) | ~$6/month | DigitalOcean 1GB Droplet — only needed for 24/7 uptime |

**Running locally (PC always on): ~$0.002/month**
**Running on a cloud server: ~$6/month**

---

## Limitations

- **Bot must be running** to process receipts. If your PC is off, receipts sent to Discord will not be processed until the bot is restarted.
- **Deletion is session-only.** The 🚫 delete reaction only works for receipts processed since the last bot startup.
- **HEIC support** (iPhone default format) depends on your system having HEIC decoding support. If images fail to parse, convert to JPG before sending.
- **AI eligibility is not guaranteed.** Gemini uses IRS Publication 502 as a guide but is not a tax professional. Unusual or ambiguous items should be manually verified.
- **Receipt image quality matters.** Blurry, dark, or partially cropped receipts may result in missing or inaccurate fields. Retake the photo if results look wrong.
- **Google OAuth token expiry.** The `token.json` file handles automatic refresh, but if it ever expires you will need to re-authorize by deleting `token.json` and restarting the bot.
- **Single channel only.** The bot only listens to `#hsa-receipts`. Receipts sent to any other channel are ignored.

---

## Hosting on a Cloud Server

To run HSSave 24/7 without keeping your PC on:

1. Create a [DigitalOcean](https://digitalocean.com) account (~$6/month for a 1GB Droplet)
2. Create an Ubuntu 22.04 Droplet
3. SSH into the server and install Python 3.10+
4. Upload your project files (excluding `.env`, `credentials.json`, `token.json`)
5. Set environment variables on the server
6. Run the bot with a process manager like `pm2` or `screen` so it restarts automatically

> **Note:** You will need to complete the Google OAuth browser authorization step locally first to generate `token.json`, then upload that file to the server.

---

## Supported Image Formats

`.jpg` `.jpeg` `.png` `.webp` `.heic`
