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

### 운영 URL (현재)

| 항목 | 값 |
|------|-----|
| Vercel | `https://frontend-flame-tau-97.vercel.app` |
| Railway API | `https://imc-dashboard-api-production-2929.up.railway.app` |
| Railway 프로젝트 | `charming-transformation` / `imc-dashboard-api` |

### 배포 설정

1. GitHub repo 연결 (`psy1472-lab/imc-board`, branch `main`)
2. **Root Directory**: 비움
3. `railway.toml` (repo root) → `dockerfilePath = "backend/Dockerfile"`
4. Volume 마운트: `/var/data`
5. 환경변수:

| 변수 | 값 |
|------|-----|
| `DATA_DIR` | `/var/data` |
| `DATABASE_URL` | `sqlite:////var/data/imc_dashboard.db` |
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

### 프로덕션 PDF 일괄 업로드 (로컬 → Railway)

로컬 `data/uploads/`에 PDF가 있을 때:

```powershell
$pw = (railway variables --json | ConvertFrom-Json).IMC_ADMIN_PASSWORD
python backend/scripts/upload_production_pdfs.py --password $pw
```

업로드 후 자동 UAT:

```powershell
python backend/scripts/smoke_production_uat.py --password $pw
```

로컬 운영 설정(특이 일정·임계값) 동기화:

```powershell
python backend/scripts/sync_production_config.py --password $pw
```

GitHub Actions `production-smoke.yml`이 6시간마다 health·summary·특이 일정을 검증합니다.

### 관리자 비밀번호 배포 확인

Public Railway URL과 Vercel이 같은 백엔드를 보는지 `GET /api/health`로 확인합니다.

```json
{
  "status": "ok",
  "adminAuth": {
    "envVarSet": true,
    "usingFallback": false,
    "passwordLength": 12
  }
}
```

| `adminAuth` | 의미 |
|-------------|------|
| `usingFallback: true` | `IMC_ADMIN_PASSWORD` 미주입 → 코드 기본값 사용 중. Railway **Public domain 서비스** Variables 확인 후 Redeploy |
| `envVarSet: true`, `usingFallback: false` | 환경변수 정상 주입 |
| Vercel `/api/health`와 Railway 직접 `/api/health`의 `adminAuth`가 다름 | `vercel.json` destination 또는 `VITE_API_BASE`가 다른 백엔드를 가리킴 |

Railway Variables는 **Public domain이 연결된 서비스**의 **Production** 환경에 설정합니다.

## 5. Supabase (2차 — Postgres)

1. 프로젝트 생성 → `DATABASE_URL` 복사
2. `supabase link` → `003_postgres_initial.sql` 적용
3. [`docs/supabase-postgres-migration-plan.md`](supabase-postgres-migration-plan.md) 따라 `PostgresRepository` 구현 후 전환

## 환경변수 매트릭스

| 변수 | Vercel | Railway/Render | Supabase |
|------|--------|----------------|----------|
| `VITE_API_BASE` | 프록시 사용 시 불필요 / 직접 호출 시 필수 | - | - |
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
