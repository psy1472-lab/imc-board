from __future__ import annotations

import hashlib
import os

from fastapi import Header, HTTPException

ADMIN_PASSWORD_ENV = "IMC_ADMIN_PASSWORD"
_FALLBACK_PASSWORD = "imc-admin"


def admin_token_for_password(password: str) -> str:
    return hashlib.sha256(f"imc-admin:{password}".encode()).hexdigest()


def get_admin_password() -> str:
    raw = os.getenv(ADMIN_PASSWORD_ENV)
    if raw is None:
        return _FALLBACK_PASSWORD
    return raw.strip()


def get_admin_auth_status() -> dict[str, bool | int]:
    raw = os.getenv(ADMIN_PASSWORD_ENV)
    env_set = raw is not None
    effective = raw.strip() if env_set else _FALLBACK_PASSWORD
    return {
        "envVarSet": env_set,
        "usingFallback": not env_set,
        "passwordLength": len(effective),
    }


def issue_admin_token(password: str) -> str:
    return admin_token_for_password(password)


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="admin authentication required")
    token = authorization.removeprefix("Bearer ").strip()
    expected = admin_token_for_password(get_admin_password())
    if token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
