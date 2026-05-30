from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import ALLOWED_ORIGINS, BASE_DIR
from backend.routes import analysis, learning, ledger, reports, transactions
from backend.services.sheet_service import sheet_service

app = FastAPI(title="Ledger Flash", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(ledger.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(learning.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "storage": sheet_service.mode}


@app.get("/api/dashboard-stats")
def dashboard_stats():
    results = sheet_service.all("Analysis_Result")
    mismatches = [row for row in results if row["status"] == "mismatch"]
    correct = [row for row in results if row["status"] == "correct"]
    return {
        "total_transactions": len(sheet_service.all("Transactions")),
        "correct_entries": len(correct),
        "potential_errors": len(mismatches),
        "learning_records": len(sheet_service.all("Learning_Data")),
        "accuracy_percentage": round(len(correct) * 100 / len(results), 1) if results else 0,
        "storage": sheet_service.mode,
    }


app.mount("/", StaticFiles(directory=BASE_DIR / "frontend", html=True), name="frontend")
