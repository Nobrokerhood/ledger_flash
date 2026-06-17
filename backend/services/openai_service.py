import json
from time import sleep

from backend.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.models.transaction import LedgerDecision, Transaction


class OpenAIService:
    def __init__(self) -> None:
        self.client = None
        if OPENAI_API_KEY:
            from openai import OpenAI

            self.client = OpenAI(api_key=OPENAI_API_KEY)

    def analyze(self, transaction: Transaction, ledgers: list[str]) -> tuple[LedgerDecision, str]:
        if not self.client:
            return self._heuristic(transaction, ledgers), "heuristic"

        system_prompt = (
            "You are an expert accountant reviewing ledger postings. Decide whether the "
            "transaction narration belongs to the selected ledger. If it is incorrect, "
            "suggest exactly one ledger from the available ledger list. Return a confidence "
            "score from 0 to 100 and a concise accounting reason."
        )
        user_prompt = (
            f"Available ledgers: {json.dumps(ledgers)}\n"
            f"Current ledger: {transaction.ledger_name}\n"
            f"Narration: {transaction.narration}"
        )

        last_error = None
        for attempt in range(3):
            try:
                response = self.client.beta.chat.completions.parse(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=LedgerDecision,
                )
                parsed = response.choices[0].message.parsed
                if parsed is None:
                    raise ValueError("OpenAI returned no structured decision")
                return parsed, "openai"
            except Exception as exc:
                last_error = exc
                status_code = getattr(exc, "status_code", None)
                if status_code is not None and status_code != 429 and status_code < 500:
                    break
                sleep(2**attempt)

        fallback = self._heuristic(transaction, ledgers)
        fallback.reason = (
            f"{fallback.reason} OpenAI was unavailable, so Ledger Flash used local analysis."
        )
        return fallback, "heuristic"

    @staticmethod
    def _heuristic(transaction: Transaction, ledgers: list[str]) -> LedgerDecision:
        narration = transaction.narration.casefold()
        narration_words = set(narration.split())
        current = transaction.ledger_name
        current_words = set(current.casefold().split())
        candidates = []
        for ledger in ledgers:
            words = set(ledger.casefold().split())
            score = round(100 * len(words & narration_words) / max(len(words), 1))
            if ledger.casefold() in narration:
                score = 98
            candidates.append((score, ledger))
        score, suggested = max(candidates, default=(0, current))
        current_hit = current.casefold() in narration or bool(current_words & narration_words)
        if suggested.casefold() == current.casefold() or (current_hit and score < 90):
            return LedgerDecision(
                status="correct",
                current_ledger=current,
                suggested_ledger=current,
                confidence=max(score, 75),
                reason="Narration is consistent with the selected ledger.",
            )
        return LedgerDecision(
            status="mismatch",
            current_ledger=current,
            suggested_ledger=suggested,
            confidence=max(score, 70),
            reason=f"Narration is more consistent with {suggested}.",
        )
