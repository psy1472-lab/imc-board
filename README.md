# IMC Operations Dashboard

중부권IMC 일일소통현황 PDF를 분석해 운영 데이터를 저장하고 종합상황판 대시보드를 제공하는 MVP입니다.

## 구조

- `backend/` FastAPI + PDF parser + SQLite 저장소
- `frontend/` Vite + React + Recharts 대시보드
- `samples/` PDF 샘플 7건
- `supabase/migrations/` Supabase용 스키마 (로컬은 SQLite 사용)

## 빠른 시작

### 1. Backend

```powershell
cd backend
pip install -r requirements.txt
$env:PYTHONPATH='src'
python -c "from pathlib import Path; from application.report_parser import ReportParser; from infrastructure.db.sqlite_repository import SqliteRepository; base=Path('..').resolve(); parser=ReportParser(); repo=SqliteRepository(str(base/'data'/'imc_dashboard.db')); [repo.save_report(str(p), parser.parse(str(p))) for p in sorted((base/'samples').glob('*.pdf')) if p.suffix=='.pdf']"
uvicorn interfaces.api.main:app --reload --app-dir src --port 8000
```

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

브라우저에서 `http://localhost:5173` 접속

## API

- `POST /api/reports/upload`
- `GET /api/reports/dates`
- `GET /api/dashboard/summary?date=2026-06-17&compare=prev_day`
- `POST /api/reports/upload`

## 현재 상태

- 표준 6페이지 PDF ingest 성공
- 토·일·공휴일 축약형(compact) PDF: 내용 기반 형식 감지(`소통물량`), sparse 시간대 정렬, 형식별 검증 프로필 적용
- 형식 인벤토리: `backend/scripts/pdf_format_inventory.py` → `docs/pdf_format_matrix.json`
- Supabase: `003_postgres_initial.sql` (Postgres) + 전환 계획 `docs/supabase-postgres-migration-plan.md`
- 로컬 MVP: SQLite (`data/imc_dashboard.db`)

## 배포

운영 배포 가이드: [`docs/deployment.md`](docs/deployment.md)

| 플랫폼 | 역할 |
|--------|------|
| GitHub | 소스·CI (`.github/workflows/ci.yml`) |
| Vercel | Frontend (`frontend/`, `vercel.json`) |
| Railway/Render | Backend API (`backend/Dockerfile`) |
| Supabase | Postgres (2차 전환) |

**포트**: Backend `8000`, Frontend dev `5173` (Vite proxy → 8000)

**환경변수**: [`.env.example`](.env.example), [`frontend/.env.example`](frontend/.env.example)

## 검증

```powershell
cd backend
$env:PYTHONPATH='src'
python -m pytest tests/ -q
python scripts/smoke_ingest_samples.py

cd ../frontend
npm run lint
npm run build
```
