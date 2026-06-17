from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.services.auth_service import get_current_user
from backend.services.report_service import excel_report, pdf_report
from backend.services.sheet_service import sheet_service

router = APIRouter()


@router.get("/download-report")
def download_report(
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    society_id: str = "",
    current_user: dict = Depends(get_current_user),
):
    rows = (
        sheet_service.filter_by_society("Analysis_Result", society_id)
        if society_id
        else sheet_service.all("Analysis_Result")
    )
    if not rows:
        raise HTTPException(404, "Run analysis before downloading a report")
    if format == "pdf":
        return StreamingResponse(
            BytesIO(pdf_report(rows)),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=ledger-flash-audit.pdf"},
        )
    return StreamingResponse(
        BytesIO(excel_report(rows)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ledger-flash-audit.xlsx"},
    )
