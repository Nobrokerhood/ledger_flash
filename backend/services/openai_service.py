import json
from time import sleep

import google.generativeai as genai

from backend.config import GEMINI_API_KEY, GEMINI_MODEL
from backend.models.transaction import LedgerDecision, Transaction


class GeminiService:
    def __init__(self) -> None:
        self.model = None

        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_MODEL)

    def analyze(
        self,
        transaction: Transaction,
        ledgers: list[str]
    ) -> tuple[LedgerDecision, str]:

        if not self.model:
            return self._heuristic(transaction, ledgers), "heuristic"

        system_prompt = (
            "You are an expert accountant reviewing ledger postings. "
            "Decide whether the transaction narration belongs to the selected ledger. "
            "If it is incorrect, suggest exactly one ledger from the available ledger list. "
            "Return a confidence score from 0 to 100 and a concise accounting reason."
        )

        user_prompt = (
            f"Available ledgers: {json.dumps(ledgers)}\n"
            f"Current ledger: {transaction.ledger_name}\n"
            f"Narration: {transaction.narration}"
        )

        prompt = f"""
{system_prompt}

{user_prompt}

Return ONLY valid JSON in this exact format:

{{
    "status": "correct",
    "current_ledger": "{transaction.ledger_name}",
    "suggested_ledger": "{transaction.ledger_name}",
    "confidence": 95,
    "reason": "Short explanation"
}}

Rules:
1. status must be either "correct" or "mismatch"
2. suggested_ledger must be one of the available ledgers
3. confidence must be an integer between 0 and 100
4. Return only JSON and no markdown
"""

        last_error = None

        for attempt in range(3):
            try:
                response = self.model.generate_content(prompt)

                response_text = response.text.strip()

                # Remove markdown code fences if Gemini adds them
                response_text = response_text.replace("```json", "")
                response_text = response_text.replace("```", "")
                response_text = response_text.strip()

                parsed_json = json.loads(response_text)

                parsed = LedgerDecision(**parsed_json)

                return parsed, "gemini"

            except Exception as exc:
                last_error = exc
                sleep(2**attempt)

        fallback = self._heuristic(transaction, ledgers)

        fallback.reason = (
            f"{fallback.reason} Gemini was unavailable, so Ledger Flash used local analysis."
        )

        return fallback, "heuristic"

    @staticmethod
    def _heuristic(
        transaction: Transaction,
        ledgers: list[str]
    ) -> LedgerDecision:

        narration = transaction.narration.casefold()
        narration_words = set(narration.split())

        current = transaction.ledger_name
        current_words = set(current.casefold().split())

        candidates = []

        for ledger in ledgers:
            words = set(ledger.casefold().split())

            score = round(
                100 * len(words & narration_words)
                / max(len(words), 1)
            )

            if ledger.casefold() in narration:
                score = 98

            candidates.append((score, ledger))

        score, suggested = max(
            candidates,
            default=(0, current)
        )

        current_hit = (
            current.casefold() in narration
            or bool(current_words & narration_words)
        )

        if (
            suggested.casefold() == current.casefold()
            or (current_hit and score < 90)
        ):
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