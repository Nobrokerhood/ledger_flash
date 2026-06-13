import re
from typing import Any


ACCOUNT_NAME_PREFIX = re.compile(r"^Account Name\s*[:-]\s*(.+)$", re.IGNORECASE)
DATE_VALUE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:\s+00:00:00)?$")
INVALID_PREFIXES = (
    "society name",
    "units#",
    "period-",
    "period:",
    "group name",
    "account#",
    "account no",
    "statement of account",
)
INVALID_VALUES = {"date", "particulars", "voucher type", "debit", "credit", "balance", "type", "tower/unit", "total"}


def normalize_ledger_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        return ""

    account_match = ACCOUNT_NAME_PREFIX.match(name)
    if account_match:
        return account_match.group(1).strip()

    lowered = name.casefold()
    if lowered in INVALID_VALUES or lowered.startswith(INVALID_PREFIXES):
        return ""
    if DATE_VALUE.match(name):
        return ""
    return name


def ledger_names(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        name = normalize_ledger_name(row.get("ledger_name", ""))
        key = name.casefold()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
    return names


def clean_ledger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = normalize_ledger_name(row.get("ledger_name", ""))
        if not name:
            continue
        key = name.casefold()
        if key not in by_name:
            by_name[key] = {**row, "ledger_name": name}
    return list(by_name.values())
