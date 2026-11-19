# TASK-015. API 라우터 구조 (/api/v1)

## 상태
완료

## 날짜
2026-11-02

## 작업 요약
앞으로 만들 모든 사용자용 API(회원, 프로젝트, 작업, 학습 문서 등)가 들어갈 **`/api/v1` 주소 아래의 공통 입구**를 만들었습니다 (`backend/src/api/router.py`).

건물에 비유하면 `/api/v1`은 **"1관" 출입구**입니다. 지금은 입구와 안내판만 세웠고, 각 매장(회원 `/auth`, 프로젝트 `/projects` 등)은 해당 Task에서 이 입구 안에 하나씩 입점합니다. 나중에 API를 크게 바꿔야 하면 `/api/v2`라는 "2관"을 새로 열어, 기존 1관을 쓰는 화면을 깨뜨리지 않고 옮겨 갈 수 있습니다.

| 주소 | 결과 | 용도 |
|---|---|---|
| `GET /api/v1` | `200 {"name":"AI Code Learning Platform API","version":"v1"}` | 프론트엔드가 API 주소(`VITE_API_BASE_URL`)를 제대로 가리키는지 확인 |
| `GET /api/v1/` | `307` → `/api/v1`로 이동 | 끝에 `/`를 붙여도 안내됨 (FastAPI 기본 동작) |
| `GET /api/v1/없는주소` | `404` | |
| `GET /health` | `200` (T014, 그대로) | 서버 감시용이라 `/api/v1` 밖에 둠 |

## 변경 파일
- `backend/src/api/router.py` (신규) — `API_PREFIX`, `create_api_router()`, `GET /api/v1`
- `backend/src/main.py` — 앱에 `/api/v1` 라우터 연결 (2줄)
- `backend/tests/unit/test_api_router.py` (신규, 테스트 8개)
- `specs/001-ai-code-learning-platform/tasks.md` — T015 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src.api.router` 모듈이 없어 실패 확인
- GREEN: `router.py` 작성, `main.py`에 연결 → 8개 통과
- REFACTOR: 코드가 작아 구조 변경 없음 (black·ruff·mypy 정리만)
- 최종: 백엔드 테스트 171개 통과(DB 통합 테스트 포함, 건너뜀 0), `src` 커버리지 **100%**, ruff·black·mypy strict 통과
- 실제 실행 확인: uvicorn으로 실행 → `/api/v1` 200, `/api/v1/` 307, `/api/v1/nope` 404, `/health` 200(DB ok)
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **주소 접두사를 한 곳(`API_PREFIX`)에서 관리**: 프론트엔드 `.env.example`의 `VITE_API_BASE_URL=http://localhost:8000/api/v1`과 같은 값인지 테스트로 묶었습니다.
- **라우터를 함수(`create_api_router()`)로 매번 새로 생성**: 파일 수준 전역 라우터를 쓰면 테스트에서 앱을 여러 번 만들 때 경로가 공유·누적될 수 있어, T014의 `create_app()`과 같은 방식으로 맞췄습니다(테스트로 확인).
- **빈 기능 파일(auth.py 등)은 미리 만들지 않음**: 내용 없는 파일은 테스트할 것이 없고 API 문서에도 안 보이므로, 각 기능 Task(T028 auth 등)에서 만들어 `router.include_router(...)` 한 줄로 연결합니다. 연결 위치는 `router.py`에 주석으로 표시했습니다.
- **`GET /api/v1` 응답은 Pydantic 모델(`ApiInfo`)**: `/docs`에 응답 형태가 자동으로 표시됩니다.

## 비고
- 작업 시작 시 PC 재시작으로 Docker Desktop이 꺼져 있어 DB 통합 테스트 30개가 건너뛰어졌습니다. Docker Desktop을 실행하고 `docker compose up -d`로 DB·Redis를 올린 뒤 전체 테스트를 다시 돌려 통과를 확인했습니다.
- 루트 주소 `/`는 여전히 404입니다(의도). 필요하면 `/docs`나 `/api/v1`로 안내하도록 추가할 수 있습니다.
- `httpx2` 사용 중단 예정 경고 1건은 T014 비고와 같은 상태입니다(설치 승인 대기).
