from pydantic import BaseModel, Field


class Ledger(BaseModel):
    ledger_id: str = Field(min_length=1)
    ledger_name: str = Field(min_length=1)
    created_at: str
