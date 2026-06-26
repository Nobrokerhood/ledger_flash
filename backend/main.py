from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import ALLOWED_ORIGINS, BASE_DIR, GEMINI_API_KEY, GEMINI_MODEL
from backend.routes import analysis, learning, ledger, reports, transactions
from backend.routes import auth as auth_router
from backend.services.auth_service import get_current_user
from backend.services.sheet_service import sheet_service

app = FastAPI(title="Ledger Flash", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router.router, prefix="/api")
app.include_router(ledger.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(learning.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "storage": sheet_service.mode,
        "ai_provider": "gemini" if GEMINI_API_KEY else "heuristic",
        "ai_model": GEMINI_MODEL if GEMINI_API_KEY else None,
    }


@app.get("/api/dashboard-stats")
def dashboard_stats(society_id: str = "", current_user: dict = Depends(get_current_user)):
    results = (
        sheet_service.filter_by_society("Analysis_Result", society_id)
        if society_id
        else sheet_service.all("Analysis_Result")
    )
    txns = (
        sheet_service.filter_by_society("Transactions", society_id)
        if society_id
        else sheet_service.all("Transactions")
    )
    learning_rows = (
        sheet_service.filter_by_society("Learning_Data", society_id)
        if society_id
        else sheet_service.all("Learning_Data")
    )
    correct = [row for row in results if row["status"] == "correct"]
    mismatches = [row for row in results if row["status"] == "mismatch"]
    return {
        "total_transactions": len(txns),
        "correct_entries": len(correct),
        "potential_errors": len(mismatches),
        "learning_records": len(learning_rows),
        "accuracy_percentage": round(len(correct) * 100 / len(results), 1) if results else 0,
        "storage": sheet_service.mode,
    }


app.mount("/css", StaticFiles(directory=BASE_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=BASE_DIR / "js"), name="js")


@app.get("/", include_in_schema=False)
def frontend():
    return FileResponse(BASE_DIR / "index.html")
