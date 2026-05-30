from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.models.transaction import ReviewRequest
from backend.services.sheet_service import sheet_service

router = APIRouter()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/approve-suggestion")
def approve(request: ReviewRequest):
    try:
        rows = sheet_service.all("Analysis_Result")
        result = next(row for row in rows if row["result_id"] == request.result_id)
        if result["status"] == "mismatch":
            sheet_service.append("Learning_Data", {
                "narration": result["narration"],
                "wrong_ledger": result["current_ledger"],
                "correct_ledger": result["suggested_ledger"],
                "timestamp": _timestamp(),
            })
        updated = sheet_service.update("Analysis_Result", "result_id", request.result_id, {"status": "approved"})
        sheet_service.append("Audit_History", {"result_id": request.result_id, "action": "approved", "timestamp": _timestamp()})
        return updated
    except (KeyError, StopIteration) as exc:
        raise HTTPException(404, "Analysis result not found") from exc


@router.post("/reject-suggestion")
def reject(request: ReviewRequest):
    try:
        updated = sheet_service.update("Analysis_Result", "result_id", request.result_id, {"status": "rejected"})
        sheet_service.append("Audit_History", {"result_id": request.result_id, "action": "rejected", "timestamp": _timestamp()})
        return updated
    except KeyError as exc:
        raise HTTPException(404, "Analysis result not found") from exc


@router.get("/learning-data")
def learning_data():
    return sheet_service.all("Learning_Data")
