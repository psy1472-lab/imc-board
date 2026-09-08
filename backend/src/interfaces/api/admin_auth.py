from __future__ import annotations

import hashlib
import os

from fastapi import Header, HTTPException

ADMIN_PASSWORD_ENV = "IMC_ADMIN_PASSWORD"


def admin_token_for_password(password: str) -> str:
    return hashlib.sha256(f"imc-admin:{password}".encode()).hexdigest()


def get_admin_password() -> str:
    return os.getenv(ADMIN_PASSWORD_ENV, "imc-admin")


def issue_admin_token(password: str) -> str:
    return admin_token_for_password(password)


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="admin authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    expected = admin_token_for_password(get_admin_password())
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
