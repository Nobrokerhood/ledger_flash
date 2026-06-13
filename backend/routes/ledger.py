from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.config import MAX_UPLOAD_BYTES
from backend.services.pdf_parser import parse_tabular
from backend.services.sheet_service import sheet_service

router = APIRouter()


@router.get("/ledgers")
def ledgers():
    return sheet_service.all("Ledger_Master")


@router.post("/upload-ledger")
async def upload_ledger(file: UploadFile = File(...)):
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds upload size limit")
    try:
        source_rows = parse_tabular(content, file.filename or "")
        rows = []
        for source in source_rows:
            name = str(source.get("ledger_name") or source.get("ledger") or next(iter(source.values()), "")).strip()
            if name:
                rows.append({
                    "ledger_id": str(uuid4()),
                    "ledger_name": name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
        if not rows:
            raise ValueError("No ledger names were found")
        sheet_service.replace("Ledger_Master", rows)
        return {"message": "Ledger master uploaded", "count": len(rows)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
