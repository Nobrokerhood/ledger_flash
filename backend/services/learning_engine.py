from difflib import SequenceMatcher
from typing import Any

from backend.services.sheet_service import SheetService


class LearningEngine:
    def __init__(self, sheets: SheetService) -> None:
        self.sheets = sheets

    def find_match(self, narration: str, wrong_ledger: str) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        best_score = 0
        for row in self.sheets.all("Learning_Data"):
            if row.get("wrong_ledger", "").casefold() != wrong_ledger.casefold():
                continue
            score = round(SequenceMatcher(None, narration.casefold(), str(row.get("narration", "")).casefold()).ratio() * 100)
            if score > best_score:
                best, best_score = row, score
        if best and best_score > 90:
            return {**best, "confidence": best_score}
        return None
