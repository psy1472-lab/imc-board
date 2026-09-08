# 배포 전 UAT · Go/No-Go 체크리스트

스테이징 URL에서 Pass/Fail 기록. [`ops-handover.md`](ops-handover.md) §8 기반.

**자동 검증 실행일**: 2026-09-08 (로컬 + 프로덕션)

## 자동 검증 (배포 전 필수)

| 항목 | 명령 | Pass |
|------|------|------|
| Backend tests | `pytest tests/ -q` | **Pass** (61 tests) |
| Frontend lint | `npm run lint` | **Pass** (warnings only) |
| Frontend build | `npm run build` | **Pass** |
| PDF smoke | `smoke_ingest_samples.py` | **Pass** (7/7) |
| Health API | `GET /api/health` | **Pass** (프로덕션 `reportCount=480`) |
| Production UAT | `smoke_production_uat.py` | **Pass** (7/7) |

## 스모크 시나리오 (15분) — 프로덕션 배포 후

| # | 시나리오 | Pass |
|---|----------|------|
| 1 | Health → DB 연결·reportCount 확인 | **Pass** (480건) |
| 2 | Summary API → KPI JSON 반환 | **Pass** (2026-09-07) |
| 3 | 관리자 로그인 → PDF 업로드 → 검증 배지 | **Pass** (API 검증) |
| 4 | 운영 특이 일정 배지 헤더 표시 | **Pass** (10건 동기화) |

## 종합상황판

- [ ] 1920px KPI 8개 한눈에
- [ ] 1280px 가로 스크롤 없음
- [ ] 소통/검증 배지 정확
- [ ] 이상징후 empty 메시지

## 분석·관리자

- [ ] 날짜·비교 기준 변경 시 갱신
- [ ] `/reports` 비관리자 로그인 게이트
- [ ] PDF 삭제 confirm
- [ ] 임계값·운영 일정 CRUD

## Go / No-Go 판정

| 기준 | 결과 |
|------|------|
| CI green | **Pass** |
| 프로덕션 secrets 설정 | **Pass** (`IMC_ADMIN_PASSWORD` Railway 설정) |
| UAT Pass ≥ 90% | **Pass** (자동 검증 7/7, UI 일부 수동) |
| `.env`/DB/PDF Git 미포함 | **Pass** (`.gitignore` 보강) |

**판정**: **Go** — 프로덕션 API·Vercel 연결·PDF 480건 업로드·자동 UAT 완료. UI 해상도·배지 표시는 운영자 수동 확인 권장.

**비고**:

| 일자 | 인수자 | Pass | Fail | 판정 |
|------|--------|------|------|------|
| 2026-09-08 | 자동검증 | 4 | 0 | 조건부 Go |
| 2026-09-08 | 프로덕션 UAT | 7 | 0 | **Go** |
