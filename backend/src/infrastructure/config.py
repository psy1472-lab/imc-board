from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_database_url() -> str:
    explicit = os.getenv("DATABASE_URL", "").strip()
    if explicit:
        if explicit.startswith("sqlite:///"):
            raw_path = explicit.removeprefix("sqlite:///")
            if raw_path.startswith("./"):
                return str(project_root() / raw_path.removeprefix("./"))
            return raw_path
        return explicit
    data_dir = os.getenv("DATA_DIR", "").strip()
    base = Path(data_dir) if data_dir else project_root() / "data"
    return str(base / "imc_dashboard.db")


def resolve_model_cache_path() -> str:
    explicit = os.getenv("MODEL_CACHE_PATH", "").strip()
    if explicit:
        return explicit
    data_dir = os.getenv("DATA_DIR", "").strip()
    base = Path(data_dir) if data_dir else project_root() / "data"
    return str(base / "models" / "volume_forecast_lgb.pkl")


def resolve_upload_dir() -> Path:
    data_dir = os.getenv("DATA_DIR", "").strip()
    base = Path(data_dir) if data_dir else project_root() / "data"
    return base / "uploads"


def resolve_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [origin for origin in origins if origin != "*.vercel.app"]


def resolve_cors_origin_regex() -> str | None:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if "*.vercel.app" in raw or os.getenv("CORS_ALLOW_VERCEL", "").lower() in {"1", "true", "yes"}:
        return r"https://.*\.vercel\.app"
    explicit = os.getenv("CORS_ORIGIN_REGEX", "").strip()
    return explicit or None


def max_upload_bytes() -> int:
    raw = os.getenv("MAX_UPLOAD_MB", "20").strip()
    try:
        return int(float(raw) * 1024 * 1024)
    except ValueError:
        return 20 * 1024 * 1024


def app_port() -> int:
    raw = os.getenv("PORT", "8000").strip()
    try:
        return int(raw)
    except ValueError:
        return 8000
