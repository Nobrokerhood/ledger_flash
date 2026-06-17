from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import ALLOWED_EMAIL_DOMAIN, GOOGLE_OAUTH_CLIENT_ID
from backend.services.auth_service import create_jwt, verify_google_token
from backend.services.sheet_service import sheet_service

router = APIRouter()


class GoogleCredential(BaseModel):
    credential: str


@router.get("/auth/config")
def auth_config():
    return {"client_id": GOOGLE_OAUTH_CLIENT_ID, "domain": ALLOWED_EMAIL_DOMAIN}


@router.post("/auth/google")
def google_login(body: GoogleCredential):
    try:
        user = verify_google_token(body.credential)
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except Exception as exc:
        raise HTTPException(401, f"Google login failed: {exc}")
    sheet_service.append("Login_Sessions", {
        "session_id": str(uuid4()),
        "email": user["email"],
        "name": user["name"],
        "login_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"token": create_jwt(user), "user": user}
