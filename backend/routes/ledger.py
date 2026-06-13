from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import MAX_UPLOAD_BYTES
from backend.services.ledger_service import clean_ledger_rows
from backend.services.pdf_parser import parse_ledger_names
from backend.services.sheet_service import sheet_service

router = APIRouter()


@router.get("/ledgers")
def ledgers():
    return clean_ledger_rows(sheet_service.all("Ledger_Master"))


@router.post("/upload-ledger")
async def upload_ledger(file: UploadFile = File(...)):
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds upload size limit")
    try:
        names = parse_ledger_names(content, file.filename or "")
        rows = [{
            "ledger_id": str(uuid4()),
            "ledger_name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        } for name in names]
        if not rows:
            raise ValueError("No ledger names were found")
        sheet_service.replace("Ledger_Master", rows)
        return {"message": "Ledger master uploaded", "count": len(rows)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
