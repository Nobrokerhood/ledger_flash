from io import BytesIO
from pathlib import Path
import re
from typing import Any

import pandas as pd

ALIASES = {
    "voucher_number": ["voucher_number", "voucher no", "voucher", "voucher number"],
    "date": ["date", "transaction date"],
    "ledger_name": ["ledger_name", "ledger", "ledger name", "account name", "account"],
    "narration": ["narration", "description", "particulars", "remarks"],
    "amount": ["amount", "debit", "value"],
    "invoice_number": ["invoice_number", "invoice no", "invoice number"],
    "bill_number": ["bill_number", "bill no", "bill number"],
}

ACCOUNT_NAME_PATTERN = re.compile(
    r"Account Name\s*[:-]\s*(.+?)(?:\s+Group Name|\s+Units?#|\s+Account No|\s+Account#|\s+Period|$)",
    re.IGNORECASE,
)
REFERENCE_PATTERNS = [
    # Match reference/ref no/Reference Number followed by an alphanumeric reference
    re.compile(r"(?:CN/DN No\.?|Ref(?:erence)?(?: Number| no)?\.?)\s*:?\s*([A-Za-z0-9][A-Za-z0-9/-]*)", re.IGNORECASE),
    # Match Cheque Number followed by alphanumeric/number
    re.compile(r"Cheque Number\s*:?\s*([A-Za-z0-9][A-Za-z0-9/-]*)", re.IGNORECASE),
]
DATE_COLUMN_PATTERN = re.compile(r"^date$", re.IGNORECASE)
PARTICULARS_COLUMN_PATTERN = re.compile(r"^particulars$", re.IGNORECASE)


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    columns = {str(column).strip().lower(): column for column in frame.columns}
    rename = {}
    for target, choices in ALIASES.items():
        for choice in choices:
            if choice in columns:
                rename[columns[choice]] = target
                break
    return frame.rename(columns=rename)


def _account_name_from_text(text: str) -> str:
    match = ACCOUNT_NAME_PATTERN.search(text.replace("\n", " "))
    return match.group(1).strip() if match else ""


def _voucher_number(particulars: str) -> str:
    if not particulars:
        return ""
    text = str(particulars)
    lower = text.lower()
    key = "ref no."
    idx = lower.find(key)
    if idx != -1:
        # Start right after 'Ref no.' and extract until one of the terminating markers
        start = idx + len(key)
        substr = text[start:]
        lower_sub = substr.lower()
        markers = [" cheque", " tran. id", " being"]
        end_pos = None
        for m in markers:
            pos = lower_sub.find(m)
            if pos != -1 and (end_pos is None or pos < end_pos):
                end_pos = pos
        if end_pos is not None:
            candidate = substr[:end_pos]
        else:
            # No terminating marker found: take the first token-like sequence
            m = re.match(r"\s*([A-Za-z0-9\-\_/]+)", substr)
            candidate = m.group(1) if m else substr
        return candidate.strip()

    # Fallback: try other reference patterns
    for pattern in REFERENCE_PATTERNS:
        match = pattern.search(particulars)
        if match:
            return match.group(1).strip()
    return ""


def _cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d-%b-%Y")
    return str(value).strip()


def _is_total_row(row: dict[str, Any]) -> bool:
    text = " ".join(_cell(value) for value in row.values()).casefold()
    return bool(re.search(r"tota\s*l", text))


def _statement_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    account_name = ""
    header_index = None

    for index, row in frame.iterrows():
        values = [_cell(value) for value in row.tolist()]
        line = " ".join(value for value in values if value)
        account_name = account_name or _account_name_from_text(line)
        has_date = any(DATE_COLUMN_PATTERN.match(value) for value in values)
        has_particulars = any(PARTICULARS_COLUMN_PATTERN.match(value) for value in values)
        if has_date and has_particulars:
            header_index = index
            break

    if header_index is None:
        return []

    header = [_cell(value) or f"Column {column}" for column, value in enumerate(frame.iloc[header_index])]
    table = pd.DataFrame(frame.iloc[header_index + 1:].values, columns=header)
    table = _normalize_columns(table).fillna("")
    if "date" not in table.columns or "narration" not in table.columns:
        return []

    rows = []
    for row in table.to_dict(orient="records"):
        row = {key: _cell(value) for key, value in row.items()}
        narration = row.get("narration", "").strip()
        date = row.get("date", "").strip()
        if not narration or not date or _is_total_row(row):
            continue
        row["ledger_name"] = row.get("ledger_name", "").strip() or account_name
        row["voucher_number"] = row.get("voucher_number", "").strip() or _voucher_number(narration)
        rows.append(row)
    return rows


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

    # Post-process rows to normalize cell values and extract voucher from narration when missing
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        row = {key: _cell(value) for key, value in raw.items()}
        narration = row.get("narration", "").strip()
        # Ensure voucher_number is populated from narration if not present
        row["voucher_number"] = row.get("voucher_number", "").strip() or (_voucher_number(narration) if narration else "")
        rows.append(row)
    return rows


def parse_ledger_names(content: bytes, filename: str) -> list[str]:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            frames = [pd.read_csv(BytesIO(content), header=None)]
        elif suffix in {".xlsx", ".xls"}:
            workbook = pd.ExcelFile(BytesIO(content))
            frames = [pd.read_excel(workbook, sheet_name=sheet, header=None) for sheet in workbook.sheet_names]
        else:
            raise ValueError("Upload a CSV or Excel file")
    except Exception as exc:
        raise ValueError(f"Could not read {suffix or 'file'}: {exc}") from exc

    from backend.services.ledger_service import normalize_ledger_name

    # Statement exports contain transaction columns. In that format only explicit
    # Account Name values are valid ledger-master entries.
    statement_names = []
    for frame in frames:
        for value in frame.to_numpy().flatten():
            match = ACCOUNT_NAME_PATTERN.search(_cell(value))
            if match:
                name = normalize_ledger_name(match.group(1))
                if name and name.casefold() not in {item.casefold() for item in statement_names}:
                    statement_names.append(name)
    has_statement_header = any(
        _cell(value).casefold() == "statement of account"
        for frame in frames
        for value in frame.to_numpy().flatten()
    )
    if has_statement_header:
        return statement_names

    aliases = {choice.casefold() for choice in ALIASES["ledger_name"]}
    names: list[str] = []
    seen: set[str] = set()
    for frame in frames:
        ledger_column = None
        header_index = None
        for index, row in frame.iterrows():
            for column, value in enumerate(row.tolist()):
                if _cell(value).casefold() in aliases:
                    header_index = index
                    ledger_column = column
                    break
            if ledger_column is not None:
                break

        if ledger_column is not None and header_index is not None:
            values = frame.iloc[header_index + 1:, ledger_column].tolist()
        else:
            nonempty_columns = [
                column
                for column in frame.columns
                if any(_cell(value) for value in frame[column].tolist())
            ]
            if len(nonempty_columns) != 1:
                continue
            values = frame[nonempty_columns[0]].tolist()

        for value in values:
            name = normalize_ledger_name(_cell(value))
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                names.append(name)
    return names


def parse_statement_tabular(content: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".csv":
            frames = [pd.read_csv(BytesIO(content), header=None)]
        elif suffix in {".xlsx", ".xls"}:
            workbook = pd.ExcelFile(BytesIO(content))
            frames = [pd.read_excel(workbook, sheet_name=sheet, header=None) for sheet in workbook.sheet_names]
        else:
            return []
    except Exception as exc:
        raise ValueError(f"Could not read {suffix or 'file'}: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for frame in frames:
        rows.extend(_statement_rows(frame))
    return rows


def parse_transactions(content: bytes, filename: str) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        statement_rows = parse_statement_tabular(content, filename)
        return statement_rows or parse_tabular(content, filename)
    try:
        import pdfplumber

        rows: list[dict[str, Any]] = []
        ledger_name = ""
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                ledger_name = _account_name_from_text(page.extract_text() or "") or ledger_name
                for table in page.extract_tables() or []:
                    if len(table) < 2:
                        continue
                    header = [str(value or "").strip() for value in table[0]]
                    frame = _normalize_columns(pd.DataFrame(table[1:], columns=header)).fillna("")
                    if "narration" not in frame.columns:
                        continue
                    for row in frame.to_dict(orient="records"):
                        row = {key: _cell(value) for key, value in row.items()}
                        narration = row.get("narration", "").strip()
                        if not narration or _is_total_row(row):
                            continue
                        row["ledger_name"] = row.get("ledger_name", "").strip() or ledger_name
                        row["voucher_number"] = row.get("voucher_number", "").strip() or _voucher_number(narration)
                        rows.append(row)
        if not rows:
            raise ValueError("No tabular transaction data was found in the PDF")
        return rows
    except Exception as exc:
        raise ValueError(f"Could not read PDF: {exc}") from exc
