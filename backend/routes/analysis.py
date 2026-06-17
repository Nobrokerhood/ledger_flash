from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services.analysis_service import AnalysisService
from backend.services.auth_service import get_current_user
from backend.services.sheet_service import sheet_service

router = APIRouter()


class AnalyzeRequest(BaseModel):
    society_id: str = ""


@router.post("/analyze")
def analyze(request: AnalyzeRequest, current_user: dict = Depends(get_current_user)):
    try:
        results = AnalysisService(sheet_service).analyze_all(request.society_id)
        return {"message": "Analysis complete", "count": len(results), "results": results}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/results")
def results(society_id: str = "", current_user: dict = Depends(get_current_user)):
    if society_id:
        return sheet_service.filter_by_society("Analysis_Result", society_id)
    return sheet_service.all("Analysis_Result")
