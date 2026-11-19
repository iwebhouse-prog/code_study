# TASK-068. 태스크 서비스 (TaskService)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
태스크의 규칙을 담당하는 `TaskService`를 만들었습니다. 식당의 **주문 접수 담당자**처럼, 주문서(제목·설명)가 규칙에 맞는지 보고, 번호표를 한 장씩 뽑아 주고, 남의 주문서는 건드리지 못하게 막습니다.

- `create_for_user` / `add_for_user`: 프로젝트 행을 잠근(`SELECT … FOR UPDATE`) 뒤 `next_number_query`로 번호를 구해 저장합니다. 동시에 5개를 만들어도 1~5가 겹치지 않습니다. `add_for_user`는 커밋하지 않아, 코드 업로드(T069)와 **한 덩어리(원자적)**로 저장할 수 있습니다.
- `list_for_user`: 휴지통 밖 태스크를 `task_number` 오름차순으로.
- `get_for_user`, `update_for_user`(제목·설명만), `move_to_trash_for_user`(30일 휴지통).
- 남의 것은 `403`, 없거나 휴지통(프로젝트가 휴지통인 경우 포함)이면 `404`.
- 생성·수정·삭제 때 프로젝트의 `last_activity_at`을 현재 시각으로 갱신합니다.
- 검증(계약의 한국어 메시지): 제목 5~255자(앞뒤 공백 제거 후), 설명 500자 이하(빈 값 → `null`), 업로드 방식 `file|folder|paste`.

## 변경 파일
- `backend/src/services/task_service.py` (새 파일)
- `backend/src/services/project_service.py` (`get`/`get_for_user`에 `lock` 옵션 추가)
- `backend/src/api/error_messages.py` (`TASK_MESSAGES` 확장)
- `backend/tests/unit/test_task_service.py` (새 시험 14개, 검증 규칙)
- `backend/tests/integration/test_task_service.py` (새 시험 31개, 실제 PostgreSQL)

## TDD 결과
- RED: 시험을 먼저 쓰고 `src.services.task_service`가 없어 수집 단계에서 실패하는 것을 확인했습니다.
- GREEN: 새 시험 45개 통과(동시 생성 시험 포함). 전체 661개 통과, `src` 줄·분기 커버리지 100%, ruff·black·mypy(strict) 통과.
- REFACTOR: 폐기 예정인 `Row.tuple()` 경고를 `task, project = row`로 정리했습니다.
- **기존 시험 파일은 고치지 않았습니다.** `ProjectService`는 선택 인자(`lock=False`)만 더했기 때문에 기존 시험이 그대로 통과합니다.

## 기술 결정
- **번호표 충돌 방지는 "행 잠금"**으로 합니다. 먼저 온 요청이 끝날 때까지 다음 요청이 기다리므로 `task_number`가 겹치지 않습니다(DB 고유 제약은 최후 방어선).
- 프로젝트 소유 확인·휴지통 처리는 `ProjectService`를 재사용해 규칙이 한곳에만 있습니다.
- 수정은 **제목과 설명을 둘 다 검사한 뒤** 바꿉니다. 한쪽이 틀리면 아무것도 바뀌지 않습니다.
- `description`을 `None`/빈 문자열로 보내면 지우고, 아예 안 보내면(`UNSET`) 그대로 둡니다.

## 관련 개념
- **행 잠금(`FOR UPDATE`)**: 한 사람이 쓰는 동안 다른 사람이 같은 칸을 못 쓰게 자물쇠를 거는 방법입니다.
- **원자성**: 여러 저장 작업이 "전부 되거나 전부 안 되거나" 둘 중 하나로만 끝나는 성질입니다.

## 주의할 점 (비고)
- 제목·설명 검사는 `FieldValidationError` 하나씩만 보고합니다(여러 필드가 동시에 틀려도 첫 번째만).
- 프로젝트를 휴지통에 보낼 때 그 안의 태스크도 함께 휴지통에 보내는 일(FR-009D)은 아직 하지 않았습니다. 대신 휴지통 프로젝트의 태스크는 조회되지 않습니다.

## 다음 단계
T069 CodeUploadService.
