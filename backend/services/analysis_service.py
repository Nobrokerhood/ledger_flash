from datetime import datetime, timezone
from uuid import uuid4

from backend.models.transaction import AnalysisResult, LedgerDecision, Transaction
from backend.services.learning_engine import LearningEngine
from backend.services.ledger_service import ledger_names
from backend.services.openai_service import OpenAIService
from backend.services.sheet_service import SheetService


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisService:
    def __init__(self, sheets: SheetService) -> None:
        self.sheets = sheets
        self.learning = LearningEngine(sheets)
        self.ai = OpenAIService()

    def analyze_all(self, society_id: str) -> list[dict]:
        available_ledgers = ledger_names(self.sheets.filter_by_society("Ledger_Master", society_id))
        if not available_ledgers:
            raise ValueError("Upload a ledger master for this society before running analysis")
        transactions = [
            Transaction.model_validate(row)
            for row in self.sheets.filter_by_society("Transactions", society_id)
        ]
        if not transactions:
            raise ValueError("Upload transactions for this society before running analysis")
        results = [
            self._analyze(transaction, available_ledgers, society_id).model_dump()
            for transaction in transactions
        ]
        self.sheets.replace_for_society("Analysis_Result", society_id, results)
        return results

    def _analyze(self, transaction: Transaction, ledgers: list[str], society_id: str) -> AnalysisResult:
        learned = self.learning.find_match(transaction.narration, transaction.ledger_name, society_id)
        if learned:
            correct_ledger = str(learned["correct_ledger"])
            is_current_correct = correct_ledger.casefold() == transaction.ledger_name.casefold()
            decision = LedgerDecision(
                status="correct" if is_current_correct else "mismatch",
                current_ledger=transaction.ledger_name,
                suggested_ledger=correct_ledger,
                confidence=learned["confidence"],
                reason=(
                    "Matched a previously confirmed correct posting."
                    if is_current_correct
                    else "Matched a previously approved ledger correction."
                ),
            )
            source = "learning"
        else:
            decision, source = self.ai.analyze(transaction, ledgers)
        return AnalysisResult(
            society_id=society_id,
            result_id=str(uuid4()),
            **transaction.model_dump(exclude={"ledger_name", "society_id"}),
            current_ledger=transaction.ledger_name,
            **decision.model_dump(exclude={"current_ledger"}),
            source=source,
            analyzed_at=now(),
        )
