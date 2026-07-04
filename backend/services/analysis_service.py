from datetime import datetime, timezone
from uuid import uuid4

from backend.models.transaction import AnalysisResult, LedgerDecision, Transaction
from backend.services.learning_engine import LearningEngine
from backend.services.ledger_service import ledger_names
from backend.services.gemini_service import GeminiService
from backend.services.sheet_service import SheetService


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisService:
    def __init__(self, sheets: SheetService) -> None:
        self.sheets = sheets
        self.learning = LearningEngine(sheets)
        self.ai = GeminiService()

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

        # Phase 1: Check learning engine for each transaction
        results: list[AnalysisResult | None] = [None] * len(transactions)
        gemini_indices: list[int] = []

        for i, tx in enumerate(transactions):
            learned = self.learning.find_match(tx.narration, tx.ledger_name, society_id)
            if learned:
                correct_ledger = str(learned["correct_ledger"])
                is_current_correct = correct_ledger.casefold() == tx.ledger_name.casefold()
                decision = LedgerDecision(
                    status="correct" if is_current_correct else "mismatch",
                    current_ledger=tx.ledger_name,
                    suggested_ledger=correct_ledger,
                    confidence=learned["confidence"],
                    reason=(
                        "Matched a previously confirmed correct posting."
                        if is_current_correct
                        else "Matched a previously approved ledger correction."
                    ),
                )
                results[i] = self._build_result(tx, decision, "learning", society_id)
            else:
                gemini_indices.append(i)

        # Phase 2: Batch-process remaining transactions through Gemini
        from backend.config import GEMINI_BATCH_SIZE

        for batch_start in range(0, len(gemini_indices), GEMINI_BATCH_SIZE):
            batch_idx = gemini_indices[batch_start:batch_start + GEMINI_BATCH_SIZE]
            batch_txns = [transactions[i] for i in batch_idx]

            batch_results = self.ai.analyze_batch(batch_txns, available_ledgers)

            for j, idx in enumerate(batch_idx):
                decision, source = batch_results[j]
                results[idx] = self._build_result(transactions[idx], decision, source, society_id)

        final = [r.model_dump() for r in results]  # type: ignore[union-attr]
        self.sheets.replace_for_society("Analysis_Result", society_id, final)
        return final

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
        return self._build_result(transaction, decision, source, society_id)

    def _build_result(
        self,
        transaction: Transaction,
        decision: LedgerDecision,
        source: str,
        society_id: str,
    ) -> AnalysisResult:
        return AnalysisResult(
            society_id=society_id,
            result_id=str(uuid4()),
            **transaction.model_dump(exclude={"ledger_name", "society_id"}),
            current_ledger=transaction.ledger_name,
            **decision.model_dump(exclude={"current_ledger"}),
            source=source,
            analyzed_at=now(),
        )

