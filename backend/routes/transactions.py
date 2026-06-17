from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.config import MAX_UPLOAD_BYTES
from backend.services.auth_service import get_current_user
from backend.services.pdf_parser import parse_transactions
from backend.services.sheet_service import sheet_service

router = APIRouter()


def _amount(value) -> float:
    try:
        return float(str(value).replace(",", "").strip() or 0)
    except ValueError:
        return 0


@router.post("/upload-transactions")
async def upload_transactions(
    file: UploadFile = File(...),
    society_id: str = Form(default=""),
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds upload size limit")
    try:
        source_rows = parse_transactions(content, file.filename or "")
        rows = []
        for source in source_rows:
            ledger = str(source.get("ledger_name", "")).strip()
            if not ledger:
                continue
            rows.append({
                "society_id": society_id,
                "transaction_id": str(uuid4()),
                "voucher_number": str(source.get("voucher_number", "")),
                "date": str(source.get("date", "")),
                "ledger_name": ledger,
                "narration": str(source.get("narration", "")),
                "amount": _amount(source.get("amount", 0)),
                "invoice_number": str(source.get("invoice_number", "")),
                "bill_number": str(source.get("bill_number", "")),
            })
        if not rows:
            raise ValueError("No valid transactions found. Include a ledger_name column.")
        sheet_service.replace_for_society("Transactions", society_id, rows)
        return {"message": "Transactions uploaded", "count": len(rows)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
