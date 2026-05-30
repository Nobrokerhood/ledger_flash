from fastapi import APIRouter, HTTPException

from backend.services.analysis_service import AnalysisService
from backend.services.sheet_service import sheet_service

router = APIRouter()


@router.post("/analyze")
def analyze():
    try:
        results = AnalysisService(sheet_service).analyze_all()
        return {"message": "Analysis complete", "count": len(results), "results": results}
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/results")
def results():
    return sheet_service.all("Analysis_Result")
