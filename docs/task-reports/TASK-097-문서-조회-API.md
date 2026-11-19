# TASK-097. 문서 조회 API (GET /tasks/{task_id}/document)

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
완성된 7장 학습 문서를 돌려주는 엔드포인트를 만들었습니다. 도서관 열람에 비유하면, 책이 서가에 꽂혀 있을 때만(`completed`) 빌려주고, 아직 제본 중이면 "준비 중"이라고 알려 줍니다.

- `200`: `{task_id, status, completed_at, content}` — `content`는 저장된 JSONB 그대로입니다.
- `409 document_not_ready`: 아직 완성 전. 메시지 "학습 문서가 아직 준비되지 않았습니다.", `details.status`에 현재 상태(정체된 실행은 `failed`)를 담습니다.
- `404 document_not_found`: 문서 행이 없는 태스크(T096 이전에 만든 태스크).
- `401`, `403`(다른 사용자 태스크), `404 not_found`(없거나 휴지통), `400`(UUID 아님)은 태스크 API와 같은 규칙입니다.

## 변경 파일
- `backend/src/api/documents.py` (새 파일, T098과 공유)
- `backend/src/api/router.py` (documents 라우터 등록)
- `backend/src/api/dependencies.py` (`DocumentQueueServiceDep`)
- `backend/tests/integration/test_documents_api.py` (시험 16개, T097·T098·다시 만들기 공용)

## TDD 결과
- RED: 라우트가 없어 첫 시험이 실패(404).
- GREEN: 구현 후 한 번에 통과. 전체 964개 통과, `src` 줄·분기 100%, ruff/black/mypy 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- 소유권 검사는 `TaskService.get_for_user`에 맡겨, 문서 내용을 읽기 전에 403/404가 먼저 나옵니다.
- 응답에는 `generation_error`, 저장 경로, `celery_task_id`를 절대 넣지 않습니다(시험이 비밀 문자열이 응답에 없는지 확인).
- 조회는 읽기 전용이며 문서를 다시 생성하지 않습니다(FR-038).

## 관련 개념
- **HTTP 409 Conflict**: 요청 자체는 올바르지만 리소스의 현재 상태와 맞지 않을 때 쓰는 상태 코드입니다.

## 주의할 점 (비고)
- `completed_at` 등 날짜는 Pydantic 기본 형식인 `2026-11-18T01:02:00Z`로 나갑니다. 계약 예시의 `+00:00`과 같은 시각이며, JavaScript `Date`는 둘 다 읽습니다.
- `/document`의 `status`는 항상 `completed`입니다(그 외 상태는 409).

## 다음 단계
T098 상태 API.
