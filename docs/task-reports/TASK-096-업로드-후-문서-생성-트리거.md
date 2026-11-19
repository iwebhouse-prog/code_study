# TASK-096. 업로드 후 문서 생성 트리거

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
코드 업로드가 DB에 **커밋된 직후** 학습 문서 생성을 자동으로 접수하도록 연결했습니다. 택배 접수에 비유하면, 물건이 창고에 확실히 들어온 뒤에 배송 요청을 넣고, 배송 요청이 실패해도 입고 자체는 성공으로 남기는 것입니다.

- `CodeUploadService`에 선택 인자 `document_queue`를 추가했습니다. `create_task_with_code`가 `_store`(커밋)를 마친 뒤에만 `enqueue(task.id)`를 호출합니다.
- 업로드 실패(롤백) 시에는 접수하지 않습니다.
- 의존성(`get_code_upload_service`)이 `DocumentQueueService`를 넣어 줍니다.

## 변경 파일
- `backend/src/services/code_analysis/code_upload_service.py` (`DocumentQueue` 프로토콜, 선택 인자, 호출)
- `backend/src/api/dependencies.py` (`get_document_queue_service`, `DocumentQueueServiceDep`)
- `backend/tests/integration/test_document_upload_trigger.py` (시험 6개, 새 파일)
- `backend/tests/conftest.py` (새 파일)

## TDD 결과
- RED: 큐 인자가 없어 시험 5개가 `TypeError` 등으로 실패(업로드 실패 시 접수 없음 시험은 처음부터 통과).
- GREEN: 최소 구현으로 통과. 기존 `test_tasks_api`, `test_code_upload_service`도 그대로 통과했습니다.
- 전체 964개 통과, `src` 100%.
- **기존 시험 파일은 고치지 않았습니다.** 대신 새 `tests/conftest.py`가 모든 시험에서 `generate_document.apply_async`를 가짜로 바꿔, 기존 API 시험이 업로드할 때 실제 Redis로 메시지를 보내지 않게 했습니다.

## 기술 결정 (위치 설명)
tasks.md는 "TaskService에"라고 했지만 `TaskService.add_for_user`는 **커밋하지 않고**, 커밋은 `CodeUploadService._store`에서 일어납니다. 트리거를 TaskService에 두면 커밋 전에 작업이 나가 worker가 태스크를 못 찾을 수 있으므로, 커밋하는 곳 바로 뒤인 `CodeUploadService`에 두었습니다.
- 인자를 선택으로 둔 이유: 기존 시험이 `CodeUploadService(session, storage)`로 만들기 때문입니다(기존 시험 불변 원칙).
- `enqueue`가 예외를 올리지 않으므로 Redis가 꺼져 있어도 업로드는 201로 성공하고 문서는 `pending`으로 남습니다.

## 관련 개념
- **의존성 주입**: 서비스가 큐를 직접 만들지 않고 받아서 쓰므로, 시험에서 가짜로 바꾸기 쉽습니다.

## 주의할 점 (비고)
- 큐 전송이 실패해 `pending`에 머문 문서는 현재 계약상 "다시 만들기"가 `failed`에만 허용되어 자동 복구 경로가 없습니다. 운영 시 재접수 점검 작업이 필요할 수 있습니다.
- 실제 worker와 Redis로 끝까지 도는 시험은 하지 않았습니다.

## 다음 단계
T097, T098 문서 조회 API.
