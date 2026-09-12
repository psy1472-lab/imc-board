# Supabase Postgres 전환 계획

## 현재 상태

- **운영 DB**: Supabase Postgres (`PostgresRepository`, Session pooler, `imc_app` role)
- **Railway**: `DATABASE_URL` → `postgresql://imc_app.vmrwhmfswndjiyctslde:***@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres`
- **데이터**: report 480건, 최신 `2026-09-07` (2026-09-09 전환 완료)
- **PDF**: Railway Volume `/var/data/uploads` 유지
- **Migration**: `001_initial_schema.sql`, `002_operation_period.sql` (SQLite 참고), Postgres `imc_dashboard_initial`

## 전환 단계

### Phase A — 스키마 (1일)

1. `supabase init` / `supabase link --project-ref <ref>`
2. `003_postgres_initial.sql`을 Supabase migration으로 적용
3. `supabase db reset` 로컬 스모크

### Phase B — Repository 분리 (3–4일)

1. `domain/repository.py` — Protocol/ABC 정의 (`save_report`, `get_dashboard_summary`, …)
2. `SqliteRepository`가 Protocol 구현 (기존 코드 유지)
3. `PostgresRepository` 신규 — psycopg3 + connection pool
4. [`repository_factory.py`](../backend/src/infrastructure/db/repository_factory.py)에서 `DATABASE_URL` 분기

### Phase C — 데이터 타입 매핑

| SQLite | Postgres |
|--------|----------|
| `TEXT` date | `DATE` |
| `raw_values TEXT` (JSON string) | `JSONB` |
| `INSERT OR IGNORE` | `ON CONFLICT DO NOTHING` |
| WAL lock | connection pool + row locks |

### Phase D — Storage (선택, 1일)

- PDF 원본: Supabase Storage bucket `reports`
- `file_path` → `storage://reports/YYYY-MM-DD.pdf`
- upload/download API에서 Storage SDK 사용

### Phase E — 배포 전환

1. Railway env: `DATABASE_URL=postgresql://...?pgbouncer=true`
2. SQLite → Postgres 데이터 마이그레이션 스크립트 (일회성)
3. 단일 인스턴스 → 다중 인스턴스 가능

## 검증 체크리스트

- [x] `003_postgres_initial.sql` Supabase에 적용 (2026-09-08)
- [x] `PostgresRepository` 구현 (`PostgresRepository` + `postgres_adapter.py`)
- [x] pytest green (SQLite 68 + Postgres adapter unit tests)
- [x] PDF ingest → summary API 동일 결과 (Postgres integration, smoke 8/8, 2026-09-09)
- [x] Railway Session pooler 전환 (`imc_app` role, port 5432)

## Railway Postgres 전환 (완료 2026-09-09)

1. Supabase Session pooler URL → Railway `DATABASE_URL` (백엔드 전용 `imc_app` DB role)
2. 데이터 이전: `python backend/scripts/migrate_sqlite_to_supabase_rest.py` (또는 `migrate_sqlite_to_postgres.py` + psycopg)
3. Railway Redeploy → `/api/health`에서 `"database": "postgres"`, `reportCount: 480`

## Supabase 적용 결과 (2026-09-08)

- Migration `imc_dashboard_initial` 적용 완료
- 테이블 14개 생성 (`report_metadata` ~ `operation_period`)
- **RLS 미설정**: 백엔드 전용 DB URL 사용 시 서버에서만 접근. Supabase anon key로 클라이언트 직접 접근 금지.

데이터 마이그레이션 (로컬 SQLite → Supabase):

```powershell
# 방법 A — PostgREST (DATABASE_URL 불필요, anon key 사용)
python backend/scripts/migrate_sqlite_to_supabase_rest.py --dry-run
python backend/scripts/migrate_sqlite_to_supabase_rest.py

# 방법 B — psycopg (Session pooler URL 필요)
pip install psycopg[binary]
$env:DATABASE_URL = "postgresql://..."   # Supabase connection string
python backend/scripts/migrate_sqlite_to_postgres.py --dry-run
python backend/scripts/migrate_sqlite_to_postgres.py
```

## 보안 (운영)

- **`postgres` superuser 비밀번호**와 **`IMC_ADMIN_PASSWORD`**는 별개입니다. Connect UI에서 복사한 DB URL의 비밀번호를 사용하세요.
- Railway에는 백엔드 전용 **`imc_app`** role URL을 사용합니다 (`postgres` superuser URL 사용 금지).
- Supabase **RLS 미설정** IMC 테이블 — anon key로 프론트 직접 DB 접근 금지.
- `imc_app` DB 비밀번호는 Supabase Dashboard에서 주기적으로 로테이션하고 Railway `DATABASE_URL`을 함께 갱신하세요.
