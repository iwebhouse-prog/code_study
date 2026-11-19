# TASK-014. FastAPI 앱 초기화 (CORS, 미들웨어)

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
지금까지 만든 부품(DB 연결 T010·T011, JWT T012)을 하나로 묶어 **실제로 켜지는 API 서버**를 만들었습니다 (`backend/src/main.py`).

가게에 비유하면 이번 작업은 **"개점 준비"**입니다.
- **문 열기 전 점검**: `.env` 설정(앱·DB·JWT)을 모두 읽어 검사하고, 잘못되었으면 아예 문을 열지 않습니다. 이어서 DB에 연결해 응답을 확인합니다(T011의 3회 재시도). 문을 닫을 때는 DB 연결을 정리합니다.
- **출입 명단(CORS)**: 우리 프론트엔드(`http://localhost:5173`)만 API를 부르고 로그인 쿠키를 보낼 수 있습니다. 다른 사이트는 막힙니다.
- **기본 보안 수칙(보안 헤더)**: 모든 응답에 "파일 종류를 추측하지 마라", "다른 사이트에 액자(iframe)로 넣지 마라" 같은 브라우저용 안내문을 붙입니다. 운영(production)에서는 "항상 https로만 접속하라"(HSTS)도 붙입니다.
- **상태 확인 창구 `/health`**: DB가 살아 있으면 `200 {"status":"ok","database":"ok"}`, 죽었으면 `503`.
- **API 설명서 `/docs`**: 개발 환경에서만 열고, 운영에서는 숨깁니다.

새 설정 검사 (`src/config.py` — `AppConfig`)

| 설정 | 기본값 | 검사 |
|---|---|---|
| `ENVIRONMENT` | development | development / test / production 중 하나 |
| `DEBUG` | false | true/false/1/0만 허용, production에서 true면 거부 (오류 상세가 외부에 노출되므로) |
| `ALLOWED_ORIGINS` | (없음) | `*` 거부, 끝 `/`나 경로 포함 거부, production은 https만 |

실행 방법: `cd backend; uvicorn src.main:create_app --factory --reload --port 8000`

## 변경 파일
- `backend/src/main.py` (신규) — `create_app()` 앱 생성 함수, 시작/종료 처리, CORS, `/health`
- `backend/src/config.py` (신규) — `AppConfig`, 공통 `.env` 읽기 함수 `load_env()`
- `backend/src/api/middleware.py` (신규) — `SecurityHeadersMiddleware`
- `backend/src/db/config.py`, `backend/src/utils/jwt.py` — 각자 갖고 있던 `.env` 읽기 코드를 `load_env()`로 교체
- `backend/tests/unit/test_app_config.py` (신규, 13개), `backend/tests/unit/test_main.py` (신규, 13개), `backend/tests/integration/test_main.py` (신규, 1개)
- `backend/tests/unit/test_db_config.py`, `test_jwt.py` — `.env` 읽기 위치 변경에 맞춰 수정
- `specs/001-ai-code-learning-platform/quickstart.md` — 서버 실행 명령을 `--factory` 방식으로 수정
- `specs/001-ai-code-learning-platform/tasks.md` — T014 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src.config`, `src.main` 모듈이 없어 실패 확인
- GREEN: `config.py`, `middleware.py`, `main.py` 작성 → 26개 통과
- REFACTOR: DB·JWT·앱 설정 세 곳에 복사돼 있던 `.env` 읽기 코드를 `load_env()` 하나로 통합(T012 보고서에서 예고), 실제 DB로 앱을 켜는 통합 테스트 추가
- 최종: 백엔드 테스트 163개 통과, `src` 커버리지 **100%**, ruff·black·mypy strict 통과
- 실제 실행 확인: `.env` 설정으로 uvicorn 실행 → `/health` 200(DB ok), 보안 헤더 3종, `/docs` 200, `localhost:5173`의 사전 요청(preflight)에 CORS 허용 + 쿠키 허용 응답
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **앱 생성 함수(`create_app`) + `uvicorn --factory`**: 파일을 import만 해도 `.env`를 읽고 서버가 만들어지는 방식(`app = FastAPI()`)을 피했습니다. 테스트에서 설정·DB를 갈아 끼우기 쉽고, 실행 명령만 `src.main:create_app --factory`로 바뀝니다.
- **설정은 서버 시작 전에 모두 검사**: T012에서 약속한 "잘못된 JWT 키는 서버 시작 시 거부"를 실제로 연결했습니다(테스트로 확인).
- **CORS는 정확한 주소만 + 쿠키 허용**: 로그인 토큰을 HTTPOnly 쿠키로 보내므로(research.md 8) `allow_credentials=True`가 필요하고, 이 경우 브라우저 규칙상 `*`를 쓸 수 없습니다. 주소 끝 `/`는 브라우저가 보내는 값과 영원히 일치하지 않는 흔한 실수라 시작 시 바로 알려 줍니다.
- **보안 헤더는 순수 ASGI 미들웨어로**: FastAPI의 간편 방식(`@app.middleware`)은 스트리밍 응답을 모아서 보내는 문제가 있어, 응답 시작 시점에 헤더만 덧붙이는 방식으로 만들었습니다. HSTS는 http로 개발 중일 때 브라우저가 접속을 막아 버릴 수 있어 production에서만 붙입니다.
- **미들웨어 순서**: CORS를 가장 바깥에 두어 사전 요청(OPTIONS)에 가장 먼저 답합니다.
- **`/health`는 `/api/v1` 밖, 문서(`/docs`)에서 제외**: 서버 감시용 창구라 사용자 API와 분리했습니다.

## 비고
- **`httpx2` 경고 1건**: FastAPI 테스트 클라이언트가 "`httpx` 대신 `httpx2`를 설치하라"는 사용 중단 예정 경고를 냅니다. 설치를 시도했지만 새 외부 패키지 설치가 권한 정책에 막혀 하지 않았습니다. 지금은 동작에 영향이 없습니다. 승인해 주시면 `httpx2`를 `requirements.txt`의 Testing 항목에 추가하겠습니다.
- 이번 범위에서 뺀 것: `/api/v1` 라우터(T015), 공통 오류 응답 형식(T016), 요청 로그(T193), CSRF 보호(T199), 쿠키 보안 옵션(T201).
- CORS 허용 헤더는 현재 `Content-Type` 하나입니다. T199에서 CSRF 토큰 헤더(예: `X-CSRF-Token`)를 추가해야 합니다.
- 응답 보안 정책(CSP)은 넣지 않았습니다. JSON API에는 효과가 작고 `/docs` 화면의 외부 스크립트를 막기 때문입니다.
