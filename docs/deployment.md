# 배포 가이드 (GitHub · Vercel · Railway/Render · Supabase)

## 아키텍처

```
Browser → Vercel (SPA) → Railway/Render (FastAPI) → SQLite (1차) / Supabase Postgres (2차)
                              ↓
                         Volume: data/ (DB, PDF, ML cache)
```

## 1. GitHub

```powershell
git init
git add .
git status   # .env, data/, *.db 제외 확인
git commit -m "Initial commit: IMC operations dashboard"
git remote add origin https://github.com/<org>/<repo>.git
git push -u origin main
```

CI: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — push/PR 시 pytest + frontend build.

## 2. Railway (Backend, 1차 권장)

1. GitHub repo 연결
2. `railway.toml` / `backend/Dockerfile` 사용
3. **Volume** 마운트: `/app/data`
4. 환경변수:

| 변수 | 값 |
|------|-----|
| `DATA_DIR` | `/app/data` |
| `DATABASE_URL` | `sqlite:////app/data/imc_dashboard.db` |
| `IMC_ADMIN_PASSWORD` | (강력한 비밀번호) |
| `CORS_ORIGINS` | `https://<vercel-app>.vercel.app,*.vercel.app` 또는 |
| `CORS_ALLOW_VERCEL` | `true` (모든 `*.vercel.app` 허용) |
| `PORT` | (Railway 자동) |

5. Health check: `GET /api/health`

## 3. Render (Backend 대안)

`render.yaml` Blueprint 사용. Disk `/var/data` 마운트.

## 4. Vercel (Frontend)

1. Import GitHub repo
2. **Root Directory**: `frontend`
3. Build: `npm run build`, Output: `dist`

### API 연결 (두 가지 중 하나)

**A. Vercel 프록시 (권장, `VITE_API_BASE` 불필요)**  
[`frontend/vercel.json`](../frontend/vercel.json)에서 `/api/*` → Railway URL로 rewrite.  
Railway URL이 다르면 `vercel.json`의 `destination`을 수정 후 재배포.

**B. 직접 호출**  
Vercel 환경변수: `VITE_API_BASE=https://<railway-host>`  
Railway에 `CORS_ALLOW_VERCEL=true` 또는 `CORS_ORIGINS=*.vercel.app` 설정.

### 데이터 없음 vs 연결 오류

- **「보고서 날짜를 불러오지 못했습니다」** → API 연결/CORS 문제
- **「보고서가 없습니다」** → 연결 성공, Railway DB에 PDF 미업로드 (관리자 메뉴에서 업로드)

## 5. Supabase (2차 — Postgres)

1. 프로젝트 생성 → `DATABASE_URL` 복사
2. `supabase link` → `003_postgres_initial.sql` 적용
3. [`docs/supabase-postgres-migration-plan.md`](supabase-postgres-migration-plan.md) 따라 `PostgresRepository` 구현 후 전환

## 환경변수 매트릭스

| 변수 | Vercel | Railway/Render | Supabase |
|------|--------|----------------|----------|
| `VITE_API_BASE` | 필수 | - | - |
| `IMC_ADMIN_PASSWORD` | - | 필수 | - |
| `DATABASE_URL` | - | 필수 | Dashboard |
| `CORS_ORIGINS` | - | Vercel URL | - |
| `DATA_DIR` | - | Volume path | - |
| `SUPABASE_SERVICE_KEY` | - | Storage 사용 시 | secrets |

## 로컬 개발

```powershell
# Backend (port 8000)
cd backend
pip install -r requirements.txt
$env:PYTHONPATH='src'
uvicorn interfaces.api.main:app --reload --app-dir src --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## 배포 후 스모크 (15분)

1. `GET <api>/api/health` → `status: ok`, `database.reportCount`
2. 관리자 로그인 → PDF 업로드
3. `GET <api>/api/dashboard/summary?date=...`
4. Vercel URL에서 종합상황판 KPI 표시

## Go / No-Go

**Go**: CI green, admin password 변경, CORS 제한, health/upload/summary 통과  
**No-Go**: 기본 `imc-admin` 비밀번호, CORS `*`, SQLite 다중 인스턴스, PDF 파싱 실패

자세한 UAT: [`docs/deployment-uat-checklist.md`](deployment-uat-checklist.md)
