# Ledger Flash

Ledger Flash flags transactions that may have been posted to the wrong ledger, suggests a correction, and learns from approved review decisions.

Live application: [https://ledger-flash.onrender.com](https://ledger-flash.onrender.com)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000`. Use the files in `sample_data/` to try the flow.

## Configuration

The app works immediately with file-backed JSON storage and a deterministic local analysis fallback. For production, configure:

- `GEMINI_API_KEY`: enables Gemini 2.5 Flash analysis.
- `GOOGLE_SHEET_ID`: ID of the spreadsheet used for application data.
- `GOOGLE_SERVICE_ACCOUNT_FILE`: local path to the Google service-account JSON file.
- `ALLOWED_ORIGINS`: comma-separated frontend origins.
- `MAX_UPLOAD_MB`: maximum accepted upload size.

For Render, leave `GOOGLE_SERVICE_ACCOUNT_FILE` empty and set:

- `GOOGLE_PROJECT_ID`
- `GOOGLE_PRIVATE_KEY_ID`
- `GOOGLE_PRIVATE_KEY`
- `GOOGLE_CLIENT_EMAIL`
- `GOOGLE_CLIENT_ID`

Copy these values from the service-account JSON file. Paste `GOOGLE_PRIVATE_KEY` as the complete private key, including its `BEGIN PRIVATE KEY` and `END PRIVATE KEY` lines. The app accepts both real line breaks and escaped `\n` sequences.

When the Google Sheet ID and either credential method are present, the app creates missing worksheets automatically: `Ledger_Master`, `Transactions`, `Analysis_Result`, `Learning_Data`, and `Audit_History`.

## Input columns

Ledger master CSV or Excel files need a `ledger_name` column. Transaction CSV, Excel, or tabular PDF files should include:

```text
voucher_number,date,ledger_name,narration,amount,invoice_number,bill_number
```

Common alternatives such as `voucher no`, `ledger`, `description`, `particulars`, `invoice no`, and `bill no` are accepted.

## Deploy on Render

Create a Blueprint from this repository using `render.yaml`, then add `GOOGLE_SHEET_ID`, the Render Google credential variables above, and `GEMINI_API_KEY` in the Render dashboard.

If configuring the Render service manually instead of using the Blueprint, use:

```bash
gunicorn backend.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```
