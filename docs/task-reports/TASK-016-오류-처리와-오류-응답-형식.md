# TASK-016. 오류 처리와 오류 응답 형식

## 상태
완료

## 날짜
2026-11-02

## 작업 요약
서버에서 어떤 문제가 생기든 **항상 같은 모양의 한국어 오류 응답**이 나가도록 만들었습니다 (`backend/src/api/exceptions.py`, `backend/src/api/error_messages.py`).

병원 안내 데스크에 비유하면, 예전에는 문제가 생길 때마다 직원이 제각각 영어 메모(`{"detail":"Not Found"}`)를 건넸습니다. 이제는 **모든 창구가 같은 양식의 안내문**을 줍니다. 무엇이 문제인지(`error`), 쉬운 한국어 설명(`message`), 필요하면 자세한 내용(`details`), 다음에 할 일(`suggestion`)이 담깁니다.

```json
{
  "error": "not_found",
  "message": "요청한 프로젝트를 찾을 수 없습니다.",
  "details": {"project_id": "p1"},
  "suggestion": "프로젝트 목록에서 다시 선택하세요."
}
```
(`details`, `suggestion`은 있을 때만 포함)

| 상황 | 상태 코드 | `error` |
|---|---|---|
| 입력값 오류 (필수 항목 누락, 글자 수 등) | 400 | `validation_error` (+ 항목별 메시지) |
| 로그인 필요 / 권한 없음 | 401 / 403 | `unauthorized` / `forbidden` |
| 없는 주소·데이터 | 404 | `not_found` |
| 지원하지 않는 요청 방식 | 405 | `method_not_allowed` |
| 동시 수정 충돌 | 409 | `conflict` |
| 요청 과다 | 429 | `rate_limit_exceeded` (+ `Retry-After` 헤더, "8분 후 다시 시도하세요") |
| 예상 못 한 서버 오류 | 500 | `internal_error` |
| DB 연결 불가 | 503 | `service_unavailable` |

앞으로 서비스 코드에서는 `raise NotFoundError("요청한 프로젝트를 찾을 수 없습니다.")`처럼 **예외를 던지기만 하면** 위 형식으로 응답됩니다. `AppError`를 상속하면 `file_too_large` 같은 새 오류도 쉽게 만들 수 있습니다.

입력값 오류 예시 (`POST`에 비밀번호만 짧게 보낸 경우):
```json
{
  "error": "validation_error",
  "message": "입력값이 올바르지 않습니다. 표시된 항목을 확인한 뒤 다시 시도하세요.",
  "details": {"fields": [
    {"field": "email", "message": "필수 입력 항목입니다."},
    {"field": "password", "message": "최소 8자 이상 입력하세요."}
  ]}
}
```

## 변경 파일
- `backend/src/api/exceptions.py` (신규) — `ErrorResponse` 형식, `AppError`와 하위 오류 5종, 처리 함수 등록, `UnhandledErrorMiddleware`
- `backend/src/api/error_messages.py` (신규) — 한국어 오류 메시지 사전 (CHK084 "메시지 상수 파일")
- `backend/src/main.py` — 오류 처리 등록, 미들웨어 추가
- `backend/tests/unit/test_exceptions.py` (신규, 테스트 21개 + 세부 케이스 15개)
- `specs/001-ai-code-learning-platform/tasks.md` — T016 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src.api.exceptions` 모듈이 없어 실패 확인
- GREEN: `error_messages.py`, `exceptions.py` 작성, `main.py`에 연결 → 20개 통과
- REFACTOR:
  - ruff가 실제 코드의 `assert`(최적화 모드에서 사라지는 검사)를 지적 → 처리 함수가 정확한 예외 타입을 받게 하고, 등록할 때만 `cast`로 Starlette 타입에 맞춤
  - "응답을 보내던 중 생긴 오류" 테스트 추가 (이미 200을 보냈으면 500으로 바꿀 수 없으니 그대로 둠)
  - FastAPI가 항상 오류 위치를 맨 앞에 넣는다는 점을 이용해 필드 이름 계산을 단순화
- 최종: 백엔드 테스트 192개 통과(DB 통합 테스트 포함), `src` 줄·분기 커버리지 **100%**, ruff·black·mypy strict 통과
- 실제 실행 확인: 서버 재시작 후 `/api/v1/nope` → 404 한국어 JSON, `DELETE /api/v1` → 405 + `allow: GET`, 프론트엔드 주소에서 요청한 오류 응답에도 CORS 헤더 포함
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **500 오류는 "미들웨어"로 처리**: FastAPI 기본 방식의 500 응답은 CORS 바깥에서 만들어져 CORS 헤더가 빠집니다. 그러면 브라우저는 "서버 오류" 대신 엉뚱한 "CORS 오류"를 보여 주고, 프론트엔드는 응답 내용을 읽지 못합니다. 그래서 가장 안쪽 미들웨어에서 잡아 CORS·보안 헤더가 붙도록 했습니다(테스트로 확인). 개발 모드(`DEBUG=true`)에서도 같은 JSON을 주고, 자세한 오류 내용은 서버 로그에만 남깁니다.
- **입력값 오류는 422가 아닌 400**: CHK084가 입력값 오류를 400으로 정했습니다.
- **입력값을 응답에 되돌려 주지 않음**: FastAPI 기본 422 응답은 사용자가 보낸 값을 그대로 담아 돌려줍니다. 비밀번호가 응답과 로그에 남을 수 있어 항목 이름과 메시지만 보냅니다.
- **직접 만든 검사 메시지는 그대로 사용**: Pydantic 검사 함수에서 `ValueError("사용할 수 없는 닉네임입니다.")`처럼 한국어로 던지면 그 문장이 그대로 나갑니다. 회원가입 비밀번호 규칙(T025/T028)에서 쓰면 됩니다.
- **DB 연결 문제는 503 + 기술 정보 숨김**: `127.0.0.1:5432`, `ECONNREFUSED` 같은 내부 정보는 응답에 넣지 않습니다(CHK084 "나쁜 오류 메시지" 예시). 로그에는 오류 종류만 경고로 남깁니다.
- **FastAPI가 직접 내는 영어 오류(`Not Found` 등)도 한국어로 교체**: 상태 코드별로 메시지 사전의 문장을 씁니다. `WWW-Authenticate`, `Allow` 같은 헤더는 유지합니다.
- **429의 대기 시간**: 명세 예시는 `retry_after`를 바깥에 두었지만, 형식을 하나로 맞추려고 `details.retry_after`에 넣고 표준 `Retry-After` 헤더도 함께 보냅니다.

## 비고
- 작업 중 실행 중이던 서버(`--reload`)가 테스트 파일 변경을 감지한 뒤 "Reloading..."에서 멈춰 예전 코드로 계속 응답했습니다. Windows에서 WatchFiles가 가끔 이렇게 멈춥니다. 서버를 다시 시작해 해결했으니, 같은 증상이 보이면 서버를 껐다 켜면 됩니다.
- 4xx 오류의 로그 기록(누가, 어떤 요청)은 T193 요청 로그에서 다룹니다. 지금은 500(전체 오류 내용)과 503(오류 종류)만 기록합니다.
- 프론트엔드는 이제 모든 오류에서 `error`(분기용 코드)와 `message`(화면 표시용)를 읽으면 됩니다. API 호출 코드(T034 등)에서 이 형식에 맞추면 됩니다.
- `httpx2` 사용 중단 예정 경고 1건은 T014 비고와 같은 상태입니다(설치 승인 대기).
