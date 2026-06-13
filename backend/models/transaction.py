from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _string(value) -> str:
    if value is None:
        return ""
    return str(value)


class Transaction(BaseModel):
    transaction_id: str
    voucher_number: str = ""
    date: str = ""
    ledger_name: str = Field(min_length=1)
    narration: str = ""
    amount: float = 0
    invoice_number: str = ""
    bill_number: str = ""

    @field_validator(
        "transaction_id",
        "voucher_number",
        "date",
        "ledger_name",
        "narration",
        "invoice_number",
        "bill_number",
        mode="before",
    )
    @classmethod
    def coerce_string_fields(cls, value):
        return _string(value)


class AnalysisResult(BaseModel):
    result_id: str
    transaction_id: str
    voucher_number: str = ""
    date: str = ""
    invoice_number: str = ""
    bill_number: str = ""
    narration: str = ""
    amount: float = 0
    current_ledger: str
    suggested_ledger: str
    confidence: int = Field(ge=0, le=100)
    reason: str
    status: Literal["correct", "mismatch", "approved", "rejected"]
    source: Literal["openai", "gemini", "learning", "heuristic"]
    analyzed_at: str

    @field_validator(
        "result_id",
        "transaction_id",
        "voucher_number",
        "date",
        "invoice_number",
        "bill_number",
        "narration",
        "current_ledger",
        "suggested_ledger",
        "reason",
        "analyzed_at",
        mode="before",
    )
    @classmethod
    def coerce_string_fields(cls, value):
        return _string(value)


class ReviewRequest(BaseModel):
    result_id: str


class LedgerDecision(BaseModel):
    status: Literal["correct", "mismatch"]
    current_ledger: str
    suggested_ledger: str
    confidence: int = Field(ge=0, le=100)
    reason: str
