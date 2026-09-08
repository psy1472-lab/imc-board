# Supabase Postgres 전환 계획

## 현재 상태

- **운영 DB**: SQLite (`SqliteRepository`, ~2,400 LOC)
- **Migration**: `001_initial_schema.sql`, `002_operation_period.sql` (SQLite 문법)
- **Postgres 스키마**: `003_postgres_initial.sql` (신규, Supabase CLI용)

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

## 1차 배포 권장

**Railway + SQLite + Volume**으로 먼저 운영하고, 안정화 후 Postgres 전환.

Postgres URL 설정 시 factory가 `NotImplementedError`를 반환하도록 가드되어 있음.

## 검증 체크리스트

- [ ] `003_postgres_initial.sql` Supabase에 적용
- [ ] `PostgresRepository` Protocol 100% 구현
- [ ] pytest 전체 green (in-memory SQLite + integration Postgres)
- [ ] PDF ingest → summary API 동일 결과
- [ ] connection pool / pgbouncer 설정
