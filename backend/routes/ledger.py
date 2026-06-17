from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from backend.config import MAX_UPLOAD_BYTES
from backend.services.auth_service import get_current_user
from backend.services.ledger_service import clean_ledger_rows
from backend.services.pdf_parser import parse_ledger_names
from backend.services.sheet_service import sheet_service

router = APIRouter()


@router.get("/ledgers")
def ledgers(society_id: str = "", current_user: dict = Depends(get_current_user)):
    rows = (
        sheet_service.filter_by_society("Ledger_Master", society_id)
        if society_id
        else sheet_service.all("Ledger_Master")
    )
    return clean_ledger_rows(rows)


@router.post("/upload-ledger")
async def upload_ledger(
    file: UploadFile = File(...),
    society_id: str = Form(default=""),
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds upload size limit")
    try:
        names = parse_ledger_names(content, file.filename or "")
        rows = [
            {
                "society_id": society_id,
                "ledger_id": str(uuid4()),
                "ledger_name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            for name in names
        ]
        if not rows:
            raise ValueError("No ledger names were found")
        sheet_service.replace_for_society("Ledger_Master", society_id, rows)
        return {"message": "Ledger master uploaded", "count": len(rows)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
