from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from application.briefing_service import BriefingService
from application.report_parser import ReportParser
from infrastructure.config import (
    max_upload_bytes,
    resolve_cors_origin_regex,
    resolve_cors_origins,
    resolve_model_cache_path,
    resolve_upload_dir,
)
from infrastructure.db.repository_factory import create_repository
from infrastructure.upload import sanitize_upload_filename
from interfaces.api.admin_auth import (
    get_admin_auth_status,
    get_admin_password,
    issue_admin_token,
    require_admin,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        briefing_service.volume_forecast_service.warm_model_cache()
    except Exception:
        pass
    yield


app = FastAPI(title="IMC Operations Dashboard API", version="0.1.0", lifespan=lifespan)
_cors_regex = resolve_cors_origin_regex()
app.add_middleware(
    CORSMiddleware,
    allow_origins=resolve_cors_origins(),
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

parser = ReportParser()
repository = create_repository()
briefing_service = BriefingService(
    repository,
    model_cache_path=resolve_model_cache_path(),
)


@app.get("/api/health")
def health():
    try:
        db_status = repository.get_health_status()
        return {
            "status": "ok",
            "database": db_status,
            "adminAuth": get_admin_auth_status(),
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc


@app.post("/api/admin/verify")
def verify_admin(payload: dict = Body(...)):
    expected_password = get_admin_password()
    password = payload.get("password")
    if isinstance(password, str):
        password = password.strip()
    if password != expected_password:
        raise HTTPException(status_code=401, detail="invalid admin password")
    return {"ok": True, "token": issue_admin_token(password)}


@app.post("/api/reports/upload")
async def upload_report(
    file: UploadFile = File(...),
    _: None = Depends(require_admin),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="PDF file required")

    try:
        safe_name = sanitize_upload_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    content = await file.read()
    if len(content) > max_upload_bytes():
        raise HTTPException(status_code=413, detail="PDF file too large")

    upload_dir = resolve_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / safe_name
    target.write_bytes(content)

    try:
        report = parser.parse(str(target))
        repository.save_report(str(target), report)
        try:
            briefing_service.volume_forecast_service.precompute_and_save(
                report.report_date.isoformat()
            )
        except Exception:
            pass
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower():
            raise HTTPException(
                status_code=503,
                detail="DB가 사용 중입니다. 잠시 후 다시 시도하거나 백엔드를 재시작해 주세요.",
            ) from exc
        raise HTTPException(status_code=500, detail="DB 저장 실패") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail="PDF 파싱 실패") from exc

    return {
        "reportDate": report.report_date.isoformat(),
        "centerName": report.center_name,
        "format": report.report_format,
        "dayType": report.day_type,
        "validation": report.validation_logs,
    }


@app.get("/api/reports/dates")
def list_dates():
    metadata = repository.list_report_date_metadata()
    response = JSONResponse(
        {
            "dates": [item["reportDate"] for item in metadata],
            "metadata": metadata,
        }
    )
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@app.get("/api/reports")
def list_reports():
    return {"reports": repository.list_reports()}


@app.get("/api/reports/{report_date}/file")
def download_report_file(report_date: str):
    file_path = repository.get_report_file_path(report_date)
    if not file_path:
        raise HTTPException(status_code=404, detail="report file not found")
    target = Path(file_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="report file missing on disk")
    return FileResponse(
        path=target,
        media_type="application/pdf",
        filename=target.name,
    )


@app.get("/api/reports/{report_date}/validation")
def report_validation(report_date: str):
    logs = repository.get_validation_logs(report_date)
    if not logs and report_date not in repository.list_report_dates():
        raise HTTPException(status_code=404, detail="report not found")
    return {"reportDate": report_date, "validation": logs}


@app.delete("/api/reports/{report_date}")
def delete_report(
    report_date: str,
    delete_file: bool = Query(True, description="Delete uploaded PDF if stored in data/uploads"),
    _: None = Depends(require_admin),
):
    result = repository.delete_report(report_date, delete_file=delete_file)
    if not result.get("deleted"):
        raise HTTPException(status_code=404, detail="report not found")
    return result


@app.get("/api/system/status")
def system_status():
    return repository.get_system_status()


@app.get("/api/system/thresholds")
def list_thresholds():
    return {"thresholds": repository.list_threshold_configs()}


@app.put("/api/system/thresholds/{metric_name}")
def update_threshold(metric_name: str, payload: dict = Body(...), _: None = Depends(require_admin)):
    try:
        repository.update_threshold_config(metric_name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="metric not found") from exc
    return {"metricName": metric_name, "updated": True}


@app.get("/api/operation-periods")
def list_operation_periods():
    return {"periods": repository.list_operation_periods()}


@app.post("/api/operation-periods")
def create_operation_period(payload: dict = Body(...), _: None = Depends(require_admin)):
    try:
        period = repository.create_operation_period(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return period


@app.put("/api/operation-periods/{period_id}")
def update_operation_period(period_id: int, payload: dict = Body(...), _: None = Depends(require_admin)):
    try:
        period = repository.update_operation_period(period_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="operation period not found")
    return period


@app.delete("/api/operation-periods/{period_id}")
def delete_operation_period(period_id: int, _: None = Depends(require_admin)):
    deleted = repository.delete_operation_period(period_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="operation period not found")
    return {"deleted": True, "id": period_id}


@app.get("/api/dashboard/volume")
def volume_analysis(date: str = Query(..., description="YYYY-MM-DD")):
    payload = repository.get_volume_analysis(date)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    return payload


@app.get("/api/dashboard/staffing")
def staffing_analysis(date: str = Query(..., description="YYYY-MM-DD")):
    payload = repository.get_staffing_analysis(date)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    return payload


@app.get("/api/dashboard/transport")
def transport_analysis(date: str = Query(..., description="YYYY-MM-DD")):
    payload = repository.get_transport_analysis(date)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    return payload


@app.get("/api/dashboard/equipment")
def equipment_analysis(date: str = Query(..., description="YYYY-MM-DD")):
    payload = repository.get_equipment_analysis(date)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    return payload


@app.get("/api/dashboard/safety")
def safety_analysis(date: str = Query(..., description="YYYY-MM-DD")):
    payload = repository.get_safety_analysis(date)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    return payload


@app.get("/api/dashboard/briefing")
def daily_briefing(
    date: str = Query(..., description="YYYY-MM-DD"),
    compare: str = Query("prev_day"),
    sections: str = Query("all", description="all | core | forecast"),
):
    if sections not in {"all", "core", "forecast"}:
        raise HTTPException(status_code=400, detail="sections must be all, core, or forecast")
    payload = briefing_service.generate(date, compare, sections=sections)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    response = JSONResponse(payload)
    if sections == "core":
        response.headers["Cache-Control"] = "public, max-age=60"
    elif sections == "forecast":
        response.headers["Cache-Control"] = "public, max-age=300"
    return response


@app.get("/api/dashboard/summary")
def dashboard_summary(
    date: str = Query(..., description="YYYY-MM-DD"),
    compare: str = Query("prev_day"),
):
    payload = repository.get_dashboard_summary(date, compare)
    if not payload:
        raise HTTPException(status_code=404, detail="report not found")
    return payload
