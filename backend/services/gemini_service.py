import json
import re
import traceback
import sys
from time import monotonic, sleep

import google.generativeai as genai
import google.api_core.exceptions as google_exceptions
import grpc
from pydantic import ValidationError

from backend.config import (
    GEMINI_API_KEY,
    GEMINI_MAX_RETRIES,
    GEMINI_MODEL,
    GEMINI_REQUEST_DELAY_SECONDS,
)
from backend.models.transaction import LedgerDecision, Transaction


def _retry_delay_seconds(exc: Exception) -> float | None:
    """Best-effort extraction of the server-suggested retry delay (e.g. from a 429 RetryInfo)."""
    for source in (getattr(exc, "metadata", None), getattr(exc, "details", None), str(exc)):
        if not source:
            continue
        text = source if isinstance(source, str) else str(source)
        match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", text) or re.search(r"'retryDelay':\s*'(\d+)s'", text)
        if match:
            return float(match.group(1))
    return None


class GeminiService:
    def __init__(self) -> None:
        self.model = None
        self._last_request_at: float | None = None

        print("--------------------------------------------------")
        print("Gemini initialized")
        print(f"Model: {GEMINI_MODEL}")
        print(f"Gemini API Key Configured: {'YES' if GEMINI_API_KEY else 'NO'}")

        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel(GEMINI_MODEL)
                print("Gemini Client Initialized Successfully")
            except Exception as exc:
                print(f"Gemini client initialization failed: {exc}")
                traceback.print_exc()
        print("--------------------------------------------------")

    def _throttle(self) -> None:
        """Space out requests so we stay under Gemini's per-minute rate limit."""
        if self._last_request_at is not None:
            elapsed = monotonic() - self._last_request_at
            remaining = GEMINI_REQUEST_DELAY_SECONDS - elapsed
            if remaining > 0:
                sleep(remaining)
        self._last_request_at = monotonic()

    def analyze(
        self,
        transaction: Transaction,
        ledgers: list[str]
    ) -> tuple[LedgerDecision, str]:

        if not self.model:
            print("Gemini model not initialized. Falling back to heuristic.")
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

        print("\n--------------------------------------------------")
        print("Sending request...")
        print(f"Prompt size: {len(prompt)} chars")
        print("\nPrompt:")
        print(prompt)
        print("Waiting for response...")

        last_error = None

        for attempt in range(GEMINI_MAX_RETRIES):
            try:
                print(f"Attempt {attempt + 1} of {GEMINI_MAX_RETRIES}...")
                self._throttle()
                response = self.model.generate_content(
                    prompt, request_options={"timeout": 60}
                )
                
                print("Response received")
                
                print("\nRaw Gemini Response:")
                print(response)

                response_text = ""
                try:
                    response_text = response.text
                except Exception as text_exc:
                    print(f"Failed to get response.text: {text_exc}")
                    print(f"Response prompt feedback: {getattr(response, 'prompt_feedback', None)}")
                    print(f"Response candidates: {getattr(response, 'candidates', None)}")
                    raise text_exc

                print("\nResponse Text:")
                print(response_text)

                # Remove markdown code fences if Gemini adds them
                response_text_clean = response_text.strip()
                
                # Robust extraction of JSON content from markdown block fences or first/last braces
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response_text_clean)
                if match:
                    response_text_clean = match.group(1).strip()
                else:
                    first_brace = response_text_clean.find("{")
                    last_brace = response_text_clean.rfind("}")
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        response_text_clean = response_text_clean[first_brace:last_brace + 1].strip()
                    else:
                        response_text_clean = response_text_clean.replace("```json", "")
                        response_text_clean = response_text_clean.replace("```", "")
                        response_text_clean = response_text_clean.strip()
                
                print("\nCleaned Response Text for JSON parsing:")
                print(response_text_clean)

                # Parse JSON
                parsed_json = json.loads(response_text_clean)
                print("JSON parsed successfully")

                # Validate LedgerDecision
                parsed = LedgerDecision(**parsed_json)
                print("LedgerDecision validated")
                
                print("Returning source = gemini")
                print("--------------------------------------------------")
                return parsed, "gemini"

            except (google_exceptions.GoogleAPICallError, grpc.RpcError) as exc:
                last_error = exc
                print("\n--------------------------------------------------")
                print("Gemini request failed")
                print("\nException Type:")
                print(type(exc).__name__)
                print("\nMessage:")
                print(str(exc))
                
                # Check for HTTP status code if available
                status_code = getattr(exc, "status_code", None)
                if status_code is None:
                    status_code = getattr(getattr(exc, "errors", None), "code", None)
                if status_code is None:
                    status_code = getattr(exc, "code", None)
                print(f"\nHTTP Status: {status_code}")
                
                print("\nTraceback:")
                traceback.print_exc()
                print("--------------------------------------------------")

                if attempt < GEMINI_MAX_RETRIES - 1:
                    is_rate_limited = isinstance(exc, google_exceptions.ResourceExhausted)
                    retry_after = _retry_delay_seconds(exc)
                    if retry_after is not None:
                        wait_seconds = retry_after
                    elif is_rate_limited:
                        wait_seconds = min(60, 10 * (2**attempt))
                    else:
                        wait_seconds = min(30, 2**attempt)
                    print(f"Waiting {wait_seconds}s before retrying...")
                    sleep(wait_seconds)
            # Catching programming bugs or formatting exceptions here to log them
            # but NOT falling back to heuristic. They propagate up.
            except (json.JSONDecodeError, ValidationError, TypeError, AttributeError, KeyError) as prog_exc:
                print("\n--------------------------------------------------")
                print("Gemini integration encountered a programming or parsing exception")
                print("\nException Type:")
                print(type(prog_exc).__name__)
                print("\nMessage:")
                print(str(prog_exc))
                print("\nTraceback:")
                traceback.print_exc()
                print("--------------------------------------------------")
                raise prog_exc

        print("\nGemini request failed. Switching to heuristic fallback.")
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
