from io import BytesIO
from pathlib import Path
import re
from typing import Any

import pandas as pd

ALIASES = {
    "voucher_number": ["voucher_number", "voucher no", "voucher", "voucher number"],
    "date": ["date", "transaction date"],
    "ledger_name": ["ledger_name", "ledger", "ledger name", "account"],
    "narration": ["narration", "description", "particulars", "remarks"],
    "amount": ["amount", "debit", "value"],
    "invoice_number": ["invoice_number", "invoice no", "invoice number"],
    "bill_number": ["bill_number", "bill no", "bill number"],
}

ACCOUNT_NAME_PATTERN = re.compile(r"Account Name:\s*(.+?)(?:\s+Group Name:|$)", re.IGNORECASE)
REFERENCE_PATTERN = re.compile(r"(?:CN/DN No\.?|Ref(?:erence)? Number\.?)\s*:?\s*([A-Za-z0-9][A-Za-z0-9/-]*)", re.IGNORECASE)


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    columns = {str(column).strip().lower(): column for column in frame.columns}
    rename = {}
    for target, choices in ALIASES.items():
        for choice in choices:
            if choice in columns:
                rename[columns[choice]] = target
                break
    return frame.rename(columns=rename)


def _account_name(page) -> str:
    text = page.extract_text() or ""
    match = ACCOUNT_NAME_PATTERN.search(text.replace("\n", " "))
    return match.group(1).strip() if match else ""


def _voucher_number(particulars: str) -> str:
    match = REFERENCE_PATTERN.search(particulars)
    return match.group(1).strip() if match else ""


def parse_tabular(content: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            frame = pd.read_csv(BytesIO(content))
        elif suffix in {".xlsx", ".xls"}:
            frame = pd.read_excel(BytesIO(content))
        else:
            raise ValueError("Upload a CSV or Excel file")
    except Exception as exc:
        raise ValueError(f"Could not read {suffix or 'file'}: {exc}") from exc
    frame = _normalize_columns(frame).fillna("")
    return frame.to_dict(orient="records")


def parse_transactions(content: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        return parse_tabular(content, filename)
    try:
        import pdfplumber

        rows: list[dict[str, Any]] = []
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                ledger_name = _account_name(page)
                for table in page.extract_tables() or []:
                    if len(table) < 2:
                        continue
                    header = [str(value or "").strip() for value in table[0]]
                    frame = _normalize_columns(pd.DataFrame(table[1:], columns=header)).fillna("")
                    if "narration" not in frame.columns:
                        continue
                    for row in frame.to_dict(orient="records"):
                        narration = str(row.get("narration", "")).strip()
                        if not narration or narration.replace(" ", "").casefold() == "total":
                            continue
                        row["ledger_name"] = str(row.get("ledger_name", "")).strip() or ledger_name
                        row["voucher_number"] = str(row.get("voucher_number", "")).strip() or _voucher_number(narration)
                        rows.append(row)
        if not rows:
            raise ValueError("No tabular transaction data was found in the PDF")
        return rows
    except Exception as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc
