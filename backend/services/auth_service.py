from datetime import datetime, timezone, timedelta

import jwt
from fastapi import Header, HTTPException

from backend.config import ALLOWED_EMAIL_DOMAIN, GOOGLE_OAUTH_CLIENT_ID, JWT_SECRET


def verify_google_token(credential: str) -> dict:
    if not GOOGLE_OAUTH_CLIENT_ID:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID is not configured")
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests

    idinfo = id_token.verify_oauth2_token(credential, google_requests.Request(), GOOGLE_OAUTH_CLIENT_ID)
    email = idinfo.get("email", "")
    if not email.lower().endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise PermissionError(f"Access is restricted to @{ALLOWED_EMAIL_DOMAIN} accounts")
    return {
        "email": email,
        "name": idinfo.get("name", ""),
        "picture": idinfo.get("picture", ""),
    }


def create_jwt(user: dict) -> str:
    payload = {**user, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def get_current_user(authorization: str = Header(default="")) -> dict:
    if not GOOGLE_OAUTH_CLIENT_ID:
        return {"email": "local@nobroker.in", "name": "Local User", "picture": ""}
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return decode_jwt(authorization[7:])
    except Exception:
        raise HTTPException(401, "Session expired. Please log in again.")
