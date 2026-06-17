import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from backend.config import DATA_DIR, GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_ID

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
GOOGLE_ENV_FIELDS = {
    "project_id": "GOOGLE_PROJECT_ID",
    "private_key_id": "GOOGLE_PRIVATE_KEY_ID",
    "private_key": "GOOGLE_PRIVATE_KEY",
    "client_email": "GOOGLE_CLIENT_EMAIL",
    "client_id": "GOOGLE_CLIENT_ID",
}

SHEETS = {
    "Ledger_Master": ["ledger_id", "ledger_name", "created_at"],
    "Transactions": [
        "transaction_id", "voucher_number", "date", "ledger_name", "narration",
        "amount", "invoice_number", "bill_number",
    ],
    "Analysis_Result": [
        "result_id", "transaction_id", "voucher_number", "date", "invoice_number",
        "bill_number", "narration", "amount", "current_ledger",
        "suggested_ledger", "confidence", "reason", "status", "source",
        "analyzed_at",
    ],
    "Learning_Data": [
        "narration", "wrong_ledger", "correct_ledger", "timestamp",
    ],
    "Audit_History": ["result_id", "action", "timestamp"],
}


class SheetService:
    """Google Sheets storage with a JSON fallback for zero-config local use."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._file = Path(DATA_DIR) / "ledger_flash.json"
        self._client = self._connect()
        self.ensure_sheets()

    def _connect(self):
        if not GOOGLE_SHEET_ID:
            return None
        try:
            import gspread

            client = self._google_client(gspread)
            return client.open_by_key(GOOGLE_SHEET_ID)
        except Exception as exc:
            raise RuntimeError(f"Google Sheets connection failed: {exc}") from exc

    @staticmethod
    def _google_client(gspread):
        if GOOGLE_SERVICE_ACCOUNT_FILE:
            credential_file = Path(GOOGLE_SERVICE_ACCOUNT_FILE)
            if not credential_file.exists():
                raise RuntimeError(
                    f"GOOGLE_SERVICE_ACCOUNT_FILE does not exist: {credential_file}"
                )
            return gspread.service_account(filename=str(credential_file))

        values = {field: os.getenv(variable, "") for field, variable in GOOGLE_ENV_FIELDS.items()}
        missing = [
            GOOGLE_ENV_FIELDS[field]
            for field, value in values.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Set GOOGLE_SERVICE_ACCOUNT_FILE for local use or configure these "
                f"Render variables: {', '.join(missing)}"
            )

        from google.oauth2.service_account import Credentials

        values["private_key"] = values["private_key"].replace("\\n", "\n")
        values["type"] = "service_account"
        values["token_uri"] = "https://oauth2.googleapis.com/token"
        credentials = Credentials.from_service_account_info(values, scopes=GOOGLE_SCOPES)
        return gspread.authorize(credentials)

    @property
    def mode(self) -> str:
        return "google-sheets" if self._client else "local-json"

    def ensure_sheets(self) -> None:
        if self._client:
            existing = {sheet.title for sheet in self._client.worksheets()}
            for title, headers in SHEETS.items():
                if title not in existing:
                    sheet = self._client.add_worksheet(title=title, rows=1000, cols=len(headers))
                    sheet.append_row(headers)
            return
        if not self._file.exists():
            self._write({name: [] for name in SHEETS})

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        with self._file.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        with self._file.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)

    def all(self, sheet_name: str) -> list[dict[str, Any]]:
        self._validate_name(sheet_name)
        if self._client:
            return self._client.worksheet(sheet_name).get_all_records()
        with self._lock:
            return self._read()[sheet_name]

    def replace(self, sheet_name: str, rows: list[dict[str, Any]]) -> None:
        self._validate_name(sheet_name)
        normalized = [{key: row.get(key, "") for key in SHEETS[sheet_name]} for row in rows]
        if self._client:
            sheet = self._client.worksheet(sheet_name)
            sheet.clear()
            sheet.update([SHEETS[sheet_name], *[[row[key] for key in SHEETS[sheet_name]] for row in normalized]])
            return
        with self._lock:
            data = self._read()
            data[sheet_name] = normalized
            self._write(data)

    def append(self, sheet_name: str, row: dict[str, Any]) -> None:
        self.append_many(sheet_name, [row])

    def append_many(self, sheet_name: str, rows: list[dict[str, Any]]) -> None:
        self._validate_name(sheet_name)
        normalized = [{key: row.get(key, "") for key in SHEETS[sheet_name]} for row in rows]
        if not normalized:
            return
        if self._client:
            self._client.worksheet(sheet_name).append_rows(
                [[row[key] for key in SHEETS[sheet_name]] for row in normalized]
            )
            return
        with self._lock:
            data = self._read()
            data[sheet_name].extend(normalized)
            self._write(data)

    def update(self, sheet_name: str, key: str, value: str, updates: dict[str, Any]) -> dict[str, Any]:
        self._validate_name(sheet_name)
        if self._client:
            rows = self._client.worksheet(sheet_name).get_all_records()
            for row in rows:
                if str(row.get(key)) == value:
                    row.update(updates)
                    sheet = self._client.worksheet(sheet_name)
                    sheet.clear()
                    sheet.update([SHEETS[sheet_name], *[[r[k] for k in SHEETS[sheet_name]] for r in rows]])
                    return row
            raise KeyError(f"{sheet_name} record not found")
        with self._lock:
            data = self._read()
            rows = data[sheet_name]
            for row in rows:
                if str(row.get(key)) == value:
                    row.update(updates)
                    self._write(data)
                    return row
        raise KeyError(f"{sheet_name} record not found")

    @staticmethod
    def _validate_name(sheet_name: str) -> None:
        if sheet_name not in SHEETS:
            raise ValueError(f"Unknown sheet: {sheet_name}")


sheet_service = SheetService()
