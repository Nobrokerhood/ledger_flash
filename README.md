# Ledger Flash

Ledger Flash flags transactions that may have been posted to the wrong ledger, suggests a correction, and learns from approved review decisions.

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
- `GOOGLE_SERVICE_ACCOUNT_FILE`: path to the Google service-account JSON file.
- `ALLOWED_ORIGINS`: comma-separated frontend origins.
- `MAX_UPLOAD_MB`: maximum accepted upload size.

When both Google Sheets settings are present, the app creates missing worksheets automatically: `Ledger_Master`, `Transactions`, `Analysis_Result`, `Learning_Data`, and `Audit_History`.

## Input columns

Ledger master CSV or Excel files need a `ledger_name` column. Transaction CSV, Excel, or tabular PDF files should include:

```text
voucher_number,date,ledger_name,narration,amount,invoice_number,bill_number
```

Common alternatives such as `voucher no`, `ledger`, `description`, `particulars`, `invoice no`, and `bill no` are accepted.

## Deploy on Render

Create a Blueprint from this repository using `render.yaml`, add the environment variables in Render, and provide a persistent Google Sheet for production storage.
