from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.models.transaction import CorrectionRequest, ReviewRequest
from backend.services.ledger_service import ledger_names
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


@router.post("/submit-correction")
def submit_correction(request: CorrectionRequest):
    try:
        ledger_by_name = {
            name.casefold(): name
            for name in ledger_names(sheet_service.all("Ledger_Master"))
        }
        correct_ledger = ledger_by_name.get(request.correct_ledger.casefold())
        if not correct_ledger:
            raise HTTPException(400, "Correct ledger must be selected from the ledger master")

        rows = sheet_service.all("Analysis_Result")
        result = next(row for row in rows if str(row["result_id"]) == request.result_id)
        current_ledger = str(result["current_ledger"]).strip()
        is_current_correct = correct_ledger.casefold() == current_ledger.casefold()

        sheet_service.append("Learning_Data", {
            "narration": result["narration"],
            "wrong_ledger": current_ledger,
            "correct_ledger": correct_ledger,
            "timestamp": _timestamp(),
        })
        updated = sheet_service.update(
            "Analysis_Result",
            "result_id",
            request.result_id,
            {
                "suggested_ledger": correct_ledger,
                "status": "approved",
                "reason": (
                    "Reviewer confirmed the current ledger."
                    if is_current_correct
                    else "Reviewer selected the correct ledger."
                ),
            },
        )
        action = "confirmed-current" if is_current_correct else f"corrected:{correct_ledger}"
        sheet_service.append("Audit_History", {
            "result_id": request.result_id,
            "action": action,
            "timestamp": _timestamp(),
        })
        return updated
    except StopIteration as exc:
        raise HTTPException(404, "Analysis result not found") from exc
    except KeyError as exc:
        raise HTTPException(404, "Analysis result not found") from exc


@router.get("/learning-data")
def learning_data():
    return sheet_service.all("Learning_Data")
