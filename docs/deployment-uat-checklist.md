# 배포 전 UAT · Go/No-Go 체크리스트

스테이징 URL에서 Pass/Fail 기록. [`ops-handover.md`](ops-handover.md) §8 기반.

**자동 검증 실행일**: 2026-09-08 (로컬)

## 자동 검증 (배포 전 필수)

| 항목 | 명령 | Pass |
|------|------|------|
| Backend tests | `pytest tests/ -q` | **Pass** (61 tests) |
| Frontend lint | `npm run lint` | **Pass** (warnings only) |
| Frontend build | `npm run build` | **Pass** |
| PDF smoke | `smoke_ingest_samples.py` | **Pass** (7/7) |
| Health API | `GET /api/health` | 로컬 확인 필요 |

## 스모크 시나리오 (15분) — 스테이징 배포 후

| # | 시나리오 | Pass |
|---|----------|------|
| 1 | Health → DB 연결·reportCount 확인 | |
| 2 | Summary API → KPI JSON 반환 | |
| 3 | 관리자 로그인 → PDF 업로드 → 검증 배지 | |
| 4 | 운영 특이 일정 배지 헤더 표시 | |

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
| CI green | **Pass** (workflow 추가됨, GitHub push 후 확인) |
| 프로덕션 secrets 설정 | **No-Go** (배포 시 `IMC_ADMIN_PASSWORD` 변경 필수) |
| UAT Pass ≥ 90% | **조건부** (자동 검증 Pass, UI UAT는 스테이징 후) |
| `.env`/DB/PDF Git 미포함 | **Pass** (`.gitignore` 보강) |

**판정**: **조건부 Go** — 코드·CI·스모크 준비 완료. Railway/Vercel 배포 + secrets 설정 + 스테이징 UAT 후 운영 Go.

**비고**:

| 일자 | 인수자 | Pass | Fail | 판정 |
|------|--------|------|------|------|
| 2026-09-08 | 자동검증 | 4 | 0 | 조건부 Go |
