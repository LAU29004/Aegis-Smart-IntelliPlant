"""JWT auth + password hashing (salted SHA-256 — demo-grade; use bcrypt in prod)."""
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import JWT_ALGORITHM, JWT_EXPIRY_HOURS, JWT_SECRET
from .database import User, get_db

from google.oauth2 import id_token
from google.auth.transport import requests
from .config import GOOGLE_CLIENT_ID
from typing import Callable

_SALT = "intelliplant"
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return hashlib.sha256((_SALT + password).encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def create_token(user: User) -> str:
    payload = {
        "sub": user.user_id,
        "email": user.email,
        "role": user.role,
        "plant_id": user.plant_id,
        "department": user.department,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, payload.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user

def require_roles(*allowed_roles: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to access this resource.",
            )
        return user

    return dependency


def user_public(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "plant_id": user.plant_id,
        "department": user.department,
    }

def verify_google_token(token: str):
    try:
        payload = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID,
        )

        return {
            "email": payload["email"],
            "name": payload.get("name", ""),
            "picture": payload.get("picture"),
        }

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid Google token",
        )