import json
from time import sleep

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.models.transaction import GeminiDecision, Transaction


class GeminiService:
    def __init__(self) -> None:
        self.client = None
        if GEMINI_API_KEY:
            from google import genai

            self.client = genai.Client(api_key=GEMINI_API_KEY)

    def analyze(self, transaction: Transaction, ledgers: list[str]) -> tuple[GeminiDecision, str]:
        if not self.client:
            return self._heuristic(transaction, ledgers), "heuristic"
        prompt = (
            "You are an expert accountant. Determine whether the transaction narration belongs "
            "to the selected current ledger. Suggest only a ledger from the available list. "
            "Return a concise reason.\n\n"
            f"Available ledgers: {json.dumps(ledgers)}\n"
            f"Current ledger: {transaction.ledger_name}\n"
            f"Narration: {transaction.narration}"
        )
        last_error = None
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": GeminiDecision,
                    },
                )
                return GeminiDecision.model_validate_json(response.text), "gemini"
            except Exception as exc:
                last_error = exc
                sleep(2**attempt)
        fallback = self._heuristic(transaction, ledgers)
        fallback.reason = f"{fallback.reason} Gemini was unavailable, so Ledger Flash used local analysis."
        return fallback, "heuristic"

    @staticmethod
    def _heuristic(transaction: Transaction, ledgers: list[str]) -> GeminiDecision:
        narration = transaction.narration.casefold()
        current = transaction.ledger_name
        current_words = set(current.casefold().split())
        candidates = []
        for ledger in ledgers:
            words = set(ledger.casefold().split())
            score = round(100 * len(words & set(narration.split())) / max(len(words), 1))
            if ledger.casefold() in narration:
                score = 98
            candidates.append((score, ledger))
        score, suggested = max(candidates, default=(0, current))
        current_hit = current.casefold() in narration or bool(current_words & set(narration.split()))
        if suggested.casefold() == current.casefold() or (current_hit and score < 90):
            return GeminiDecision(status="correct", current_ledger=current, suggested_ledger=current, confidence=max(score, 75), reason="Narration is consistent with the selected ledger.")
        return GeminiDecision(status="mismatch", current_ledger=current, suggested_ledger=suggested, confidence=max(score, 70), reason=f"Narration is more consistent with {suggested}.")
