from io import BytesIO

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.services.report_service import excel_report, pdf_report
from backend.services.sheet_service import sheet_service

router = APIRouter()


@router.get("/download-report")
def download_report(format: str = Query("xlsx", pattern="^(xlsx|pdf)$")):
    rows = sheet_service.all("Analysis_Result")
    if not rows:
        raise HTTPException(404, "Run analysis before downloading a report")
    if format == "pdf":
        return StreamingResponse(BytesIO(pdf_report(rows)), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=ledger-flash-audit.pdf"})
    return StreamingResponse(BytesIO(excel_report(rows)), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=ledger-flash-audit.xlsx"})
