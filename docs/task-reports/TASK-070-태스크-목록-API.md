# TASK-070. 태스크 목록 API (GET /projects/{project_id}/tasks)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
프로젝트 안의 태스크를 **번호 순서대로** 보여 주는 API를 만들었습니다. 학교 출석부처럼 1번, 2번, 3번 순서대로 줄을 세워 주고, 휴지통에 보낸 학생은 명단에서 빼 줍니다.

- 응답: 휴지통 밖 태스크의 배열, `task_number` 오름차순(FR-003)
- 각 항목은 계약의 Task 객체입니다. `code`에는 언어·복잡도·줄 수·파일 수·크기가 들어갑니다(코드가 없으면 `null`). `user_id`, `storage_path`, 휴지통 필드는 절대 나가지 않습니다.
- 오류: 로그인 안 함 `401`, 남의 프로젝트 `403`, 없거나 휴지통인 프로젝트 `404`, UUID가 아닌 값 `400`(필드명 `project_id`)
- 함께 한 일: 프로젝트 객체의 `task_count`가 이제 **휴지통 밖 태스크 수**를 셉니다(`completed_task_count`는 0 유지).

## 변경 파일
- `backend/src/api/tasks.py` (새 파일, 라우터)
- `backend/src/api/task_schemas.py` (새 파일, 응답 모양)
- `backend/src/api/router.py` (tasks 라우터 연결)
- `backend/src/api/dependencies.py` (`TaskServiceDep`, `FileStorageDep`, `CodeUploadServiceDep`)
- `backend/src/api/projects.py`, `backend/src/services/project_service.py` (`task_count`)
- `backend/tests/integration/test_tasks_api.py` (새 시험, T070–T075 공용)

## TDD 결과
- RED: 시험을 먼저 쓰고 실행하여 라우트가 없어 `404`로 실패하는 것을 확인했습니다.
- GREEN: `TestListTasks`, `TestSignInAndIds`, `TestProjectTaskCount` 등 통과. 전체 결과는 T075 보고서에 적었습니다.
- REFACTOR: 250줄 제한 때문에 응답 모양을 `task_schemas.py`로 분리했습니다.
- **기존 시험 파일은 고치지 않았습니다.** 프로젝트 API의 기존 시험(`task_count` 0)은 그대로 통과합니다.

## 기술 결정
- 라우트는 소유자 확인이 들어 있는 `*_for_user` 서비스 메서드만 씁니다(프로젝트 API와 같은 방식).
- 목록의 `task_count`는 프로젝트마다 쿼리하지 않고 `GROUP BY` 한 번으로 모아서 셉니다.
- `code`를 위해 업로드 코드 행을 `selectinload`로 한꺼번에 읽어, 목록이 길어져도 쿼리 수가 늘지 않습니다.

## 관련 개념
- **N+1 문제**: 목록 N개를 위해 쿼리를 N번 더 하는 비효율입니다. 한꺼번에 읽어 피합니다.
- **GROUP BY**: 같은 프로젝트끼리 묶어 개수를 세는 SQL입니다.

## 주의할 점 (비고)
- 프로젝트를 휴지통에 보낼 때 태스크도 함께 휴지통에 보내는 일(FR-009D)은 아직 없습니다. 휴지통 프로젝트의 태스크는 조회되지 않습니다.

## 다음 단계
T071 태스크 생성(멀티파트 업로드) API.
