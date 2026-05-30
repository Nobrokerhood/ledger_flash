from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    transaction_id: str
    voucher_number: str = ""
    date: str = ""
    ledger_name: str = Field(min_length=1)
    narration: str = ""
    amount: float = 0
    invoice_number: str = ""
    bill_number: str = ""


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
    source: Literal["gemini", "learning", "heuristic"]
    analyzed_at: str


class ReviewRequest(BaseModel):
    result_id: str


class GeminiDecision(BaseModel):
    status: Literal["correct", "mismatch"]
    current_ledger: str
    suggested_ledger: str
    confidence: int = Field(ge=0, le=100)
    reason: str
