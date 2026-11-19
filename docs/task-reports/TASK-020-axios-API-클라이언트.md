# TASK-020. axios API 클라이언트

## 상태
완료

## 날짜
2026-11-03

## 작업 요약
프론트엔드가 백엔드와 대화할 때 쓰는 **공용 전화기(API 클라이언트)**를 만들었습니다 (`frontend/src/services/api-client.ts`).

앞으로 모든 화면은 이 전화기 하나로 백엔드에 요청합니다. 전화기에는 다음 기능이 미리 들어 있습니다.

- **연결할 주소**: `.env`의 `VITE_API_BASE_URL`(기본 `http://localhost:8000/api/v1`)
- **로그인 쿠키 자동 첨부**: 토큰이 HTTPOnly 쿠키에 있어서(research.md 8장) 모든 요청에 쿠키를 함께 보냅니다(`withCredentials`).
- **30초 대기 제한**: 응답이 없으면 끊고 "서버 응답이 너무 늦습니다"를 알립니다.
- **오류 통역**: 어떤 실패든 같은 모양의 `ApiError`로 바꿔 줍니다.

| 실패 상황 | `status` | `code` | `message` |
|---|---|---|---|
| 백엔드가 공통 오류 형식(T016)으로 답함 | 404 등 | 백엔드 값 (`not_found` 등) | 백엔드의 한국어 메시지 그대로 |
| 입력값 오류(400) | 400 | `validation_error` | + `fieldErrors`로 `{ email: '필수 입력 항목입니다.' }` 형태 제공 |
| 요청 과다(429) | 429 | `rate_limit_exceeded` | + `retryAfterSeconds` (Retry-After 헤더) |
| 우리 형식이 아닌 응답 (프록시 오류 페이지 등) | 502 등 | `internal_error` / `bad_request` | 한국어 기본 메시지 |
| 서버에 연결 불가 | 없음 | `network_error` | 서버에 연결할 수 없습니다. 인터넷 연결을 확인한 뒤 다시 시도하세요. |
| 30초 초과 | 없음 | `timeout` | 서버 응답이 너무 늦습니다. 잠시 후 다시 시도하세요. |
| 요청 취소 (화면 이동 등) | - | - | **바꾸지 않고 그대로 전달** (TanStack Query가 취소를 알아보도록) |

화면에서는 `error.message`를 그대로 보여 주고, 입력 폼에서는 `error.fieldErrors[필드이름]`을 입력칸 옆에 보여 주면 됩니다.

## 변경 파일
- `frontend/src/services/api-client.ts` (신규) — `apiClient`(앱 공용), `createApiClient()`, `ApiError`, `resolveBaseUrl()`, 기본 메시지
- `frontend/tests/unit/api-client.test.ts` (신규, 17개)
- `frontend/package.json`, `package-lock.json` — `axios@^1.21.0` 추가
- `specs/001-ai-code-learning-platform/quickstart.md` — 버전 표기 갱신
- `specs/001-ai-code-learning-platform/tasks.md` — T020 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src/services/api-client` 파일이 없어 실패 확인
- GREEN: `api-client.ts` 작성 → 16개 통과
- REFACTOR: 커버리지에서 "입력 항목 정보가 없는 오류" 분기가 빠진 것을 발견 → 테스트 추가 (구조 변경 없음)
- 최종: 프론트엔드 테스트 61개 통과, 문장·함수·줄 커버리지 **100%**, 분기 98.3% (남은 1개는 T019 비고의 `routes.tsx` 운영 모드 분기 — 테스트가 개발 모드로만 실행됨), 타입 검사·ESLint·Prettier·프로덕션 빌드 통과
- 실제 백엔드 확인 (임시 테스트 파일로 실행 후 삭제):
  - `GET /api/v1` → `{"name":"AI Code Learning Platform API","version":"v1"}`
  - `/test-errors?type=notfound` → `404 not_found` + 한국어 메시지
  - `/test-errors?type=conflict` → `409 conflict`
  - `/test-errors?type=boom` → `400 validation_error`, `fieldErrors = {"type":"올바른 형식이 아닙니다."}`
  - 없는 주소 → `404 not_found`, 꺼진 서버 → `network_error`
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **axios (quickstart.md 지정)**: 쿠키 첨부, 대기 제한, 응답 가로채기(interceptor)를 설정 한 번으로 처리합니다.
- **오류는 `ApiError` 하나로**: 화면 코드가 axios 내부 구조(`error.response.data...`)를 몰라도 됩니다. `status` 필드가 있어서 T019의 재시도 규칙(`getHttpStatus`)이 그대로 동작합니다(테스트로 확인: 404 재시도 안 함, 503·네트워크 오류 재시도).
- **운영 환경에서 주소가 없으면 즉시 오류**: 개발 중에는 `.env.local`이 없어도 로컬 백엔드로 연결되지만, 운영 빌드에서 `VITE_API_BASE_URL`이 빠지면 엉뚱한 `localhost`로 요청하지 않고 바로 알립니다. 주소 끝의 `/`는 자동으로 지웁니다.
- **기본 메시지는 백엔드와 같은 문장**: `bad_request`, `internal_error` 문장은 `backend/src/api/error_messages.py`와 동일합니다(CHK084 "같은 오류는 같은 문장").
- **테스트는 axios의 adapter 자리에 가짜 응답을 넣어서**: 새 테스트 도구(msw 등)를 설치하지 않았습니다.
- **30초 대기 제한**: AI 작업을 기다리는 요청을 고려했습니다. 문서 생성처럼 긴 작업은 Celery로 넘기고 상태만 조회하므로(T094/T098) 이 시간이면 충분합니다.

## 비고
- **401 자동 토큰 갱신은 T038**(`useAuth`), **CSRF 헤더는 T199**에서 이 클라이언트의 interceptor에 추가합니다.
- **`localhost` 주소를 그대로 쓰는 이유**: 프론트엔드(`localhost:5173`)와 API(`localhost:8000`)를 같은 이름으로 써야 로그인 쿠키가 같은 사이트로 취급됩니다. `127.0.0.1`과 섞어 쓰면 쿠키가 전달되지 않을 수 있습니다.
- 작업 중 PC 재시작으로 Docker Desktop이 꺼져 있어 백엔드가 "DB 연결 3회 실패"로 시작을 거부했습니다(T011/T014 설계대로). Docker Desktop과 `docker compose up -d`로 DB·Redis를 다시 올린 뒤 확인했습니다.
- `npm install` 후 나오는 보안 경고(moderate)는 T018 비고와 같은 기존 eslint 개발 도구 경고입니다.
