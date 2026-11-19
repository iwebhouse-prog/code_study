# TASK-094. Celery 문서 생성 작업

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
T093의 문서 생성 서비스를 **백그라운드 작업자(Celery worker)가 실행하도록 감쌌습니다.** 식당에 비유하면 손님(웹 요청)이 주문서(task_id)만 두고 가면, 주방(worker)이 주문서를 보고 요리를 만들어 진열대(DB)에 올려 두는 구조입니다.

`generate_document(task_id)` 작업의 순서는 다음과 같습니다.
1. 태스크와 업로드된 코드 파일을 읽습니다. 태스크가 없으면 `skipped`로 끝냅니다.
2. 문서 행이 없으면 `pending`으로 만들고, 이미 `completed`/`in_progress`이면 건너뜁니다.
3. `doc.start(celery_task_id)` 후 커밋하고, 파일을 읽어 `DocumentGenerationService.generate`를 호출한 뒤 `doc.complete(content)`로 저장합니다.
4. 실패는 모두 `generation_error`에 `"<reason>: <영어 상세>"`로 기록합니다.

| 상황 | 기록 |
|---|---|
| `DocumentGenerationError` | `ai_unavailable: after 4 attempts: …` 처럼 reason 그대로 |
| `SoftTimeLimitExceeded` (270초) | `timeout: …` |
| 그 밖의 모든 예외 | `internal_error: 예외이름: 메시지` (스택 트레이스 로그) |

## 변경 파일
- `backend/src/tasks/document_generation.py` (새 파일)
- `backend/src/tasks/celery_app.py` (`TASK_MODULES`에 모듈 등록)
- `backend/tests/integration/test_document_generation_task.py` (시험 19개, 새 파일)
- `backend/tests/conftest.py` (새 파일, 아래 T096 보고서 참고)

## TDD 결과
- RED: 모듈이 없어 `ImportError`로 수집 단계에서 실패.
- GREEN: 첫 구현 후 9개가 실패했고, 새 행의 `generation_status`가 flush 전에는 `None`이라 `start()`가 거부하는 것이 원인이었습니다. 생성 시 `"pending"`을 명시해 해결했습니다.
- 시험이 찾아낸 문제: AI가 일하는 동안 문서가 `failed`로 바뀌어도 늦게 온 결과가 그 위에 `completed`를 덮어쓰는 **갱신 유실**이 있었습니다. 행을 잠그고 "아직 내 실행인지"(`in_progress` + 같은 celery id) 확인하는 `_still_ours`를 추가했습니다.
- REFACTOR: black/ruff/mypy 정리. `src` 줄·분기 100%.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- 비동기 일은 `asyncio.run`으로 실행하고, 실행마다 `Database`를 새로 만들어 끝에 `dispose`합니다(이벤트 루프가 매번 새로 생기기 때문).
- `GenerationRuntime`(DB, 저장소, AI)을 주입할 수 있게 하여 시험이 실제 Gemini, Redis, 개발 DB를 쓰지 않습니다.
- Celery 재시도는 끄고(`max_retries=0`) 재시도는 서비스(T093)와 사용자 "다시 만들기"에 맡깁니다.

## 관련 개념
- **멱등성**: `acks_late` 설정에서는 작업이 두 번 올 수 있으므로, 이미 진행 중/완료된 문서는 건너뜁니다.

## 주의할 점 (비고)
- 실제 worker는 띄우지 않았습니다. Windows에서는 `--pool=solo`에서 소프트 타임리밋(시그널 기반)이 동작하지 않을 수 있어, 그 경우 300초 후 상태 API의 "stale" 규칙이 대신 `timeout`으로 보여 줍니다.
- 한 실행의 전체 마감(270초)은 AI 재시도가 쌓이면 빠듯할 수 있습니다.

## 다음 단계
T095 문서 큐 서비스(상태 계산, 다시 만들기).
