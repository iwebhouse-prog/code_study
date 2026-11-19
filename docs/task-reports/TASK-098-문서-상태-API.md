# TASK-098. 문서 상태 API (GET /tasks/{task_id}/document/status)

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
프런트엔드가 3초마다 물어볼 **진행 상황 엔드포인트**와, 실패 후 **다시 만들기**(`POST .../document/regenerate`, 계약에 있는 T114용)를 함께 만들었습니다. 택배 조회 화면처럼 "접수 → 진행 중 → 완료/실패"와 남은 시간을 알려 줍니다.

- 응답: `{task_id, status, started_at, completed_at, estimated_seconds_remaining, error}`.
- `estimated_seconds_remaining`은 `pending`/`in_progress`일 때만 정수, 나머지는 `null`.
- `error`는 `failed`일 때만 `{reason, message}`이며 메시지는 `DOCUMENT_MESSAGES`의 한국어 문구입니다. 알 수 없는 reason은 `internal_error`로 보입니다.
- 300초를 넘긴 `in_progress`는 `failed` / `timeout`으로 보고합니다.
- 다시 만들기: `failed`(정체 포함)이면 `202`와 `pending` 상태 객체, 그 외에는 `409 document_not_failed`.

## 변경 파일
- `backend/src/api/documents.py` (상태, 다시 만들기 라우트와 응답 모델)
- `backend/src/api/error_messages.py` (`DOCUMENT_MESSAGES`: 실패 이유 5개 + 오류 3개)
- `backend/tests/integration/test_documents_api.py` (T097과 공용)

## TDD 결과
- RED: 라우트가 없어 실패. GREEN: 구현 후 통과. 의존성 모듈과 라우터 단위 시험도 통과.
- 최종: 전체 964개 통과(이번 5개 작업에서 새 시험 74개 추가), `src` 줄·분기 100%, ruff/black/mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- 새 응답 모델 `DocumentStatusResponse`는 서비스의 `DocumentStatus`(이유 코드만 가짐)에서 만들어, 영어 상세가 API 층까지 올라오지 않습니다.
- 상태 조회는 행을 바꾸지 않습니다(정체 실행도 보고만 함). 되돌리기는 사용자가 다시 만들기를 눌렀을 때만 일어납니다.

## 관련 개념
- **폴링**: 클라이언트가 일정 간격으로 서버에 상태를 물어 변화를 확인하는 방식입니다. 계약은 3초 간격을 정했습니다.

## 주의할 점 (비고)
- 실제 Celery worker와 Redis를 띄운 끝에서 끝까지 시험은 하지 않았습니다(요구에 따라 개발 환경에서 worker 미실행). 실제 worker 실행 확인이 별도로 필요합니다.
- `pending`이 비정상적으로 오래 가는 경우(큐 전송 실패)는 현재 규칙으로 복구할 수 없습니다.

## 다음 단계
프런트엔드 T099~T108이 이 계약으로 문서 화면을 구현합니다. 이후 T114에서 다시 만들기 버튼을 연결합니다.
