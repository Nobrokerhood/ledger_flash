from datetime import datetime, timezone
from uuid import uuid4

from backend.models.transaction import AnalysisResult, LedgerDecision, Transaction
from backend.services.learning_engine import LearningEngine
from backend.services.openai_service import OpenAIService
from backend.services.sheet_service import SheetService


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisService:
    def __init__(self, sheets: SheetService) -> None:
        self.sheets = sheets
        self.learning = LearningEngine(sheets)
        self.ai = OpenAIService()

    def analyze_all(self) -> list[dict]:
        ledger_names = [row["ledger_name"] for row in self.sheets.all("Ledger_Master")]
        if not ledger_names:
            raise ValueError("Upload a ledger master before running analysis")
        transactions = [Transaction.model_validate(row) for row in self.sheets.all("Transactions")]
        if not transactions:
            raise ValueError("Upload transactions before running analysis")
        results = [self._analyze(transaction, ledger_names).model_dump() for transaction in transactions]
        self.sheets.replace("Analysis_Result", results)
        return results

    def _analyze(self, transaction: Transaction, ledgers: list[str]) -> AnalysisResult:
        learned = self.learning.find_match(transaction.narration, transaction.ledger_name)
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
            result_id=str(uuid4()),
            **transaction.model_dump(exclude={"ledger_name"}),
            current_ledger=transaction.ledger_name,
            **decision.model_dump(exclude={"current_ledger"}),
            source=source,
            analyzed_at=now(),
        )
