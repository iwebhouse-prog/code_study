# TASK-073. 태스크 수정 API (PATCH /tasks/{task_id})

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
태스크의 **제목과 설명만** 바꾸는 API입니다. 이름표는 바꿔 달 수 있지만 번호표와 상자(코드)는 그대로 두는 것과 같습니다.

- 본문(JSON): `{ "title"?: string, "description"?: string | null }`
- 보내지 않은 필드는 그대로, `"description": null` 또는 `""`이면 설명을 지웁니다.
- `task_number`, `upload_method`, 코드는 바꿀 수 없습니다(FR-004). 본문에 들어 있어도 **무시**되고 응답은 원래 값 그대로입니다.
- `200`: 수정된 Task 객체. 프로젝트의 `last_activity_at`도 갱신됩니다.
- `400 validation_error`: 제목 5자 미만/255자 초과(`title`), `title: null`, 설명 500자 초과(`description`)에 계약의 한국어 메시지
- `403`, `404`, `401`

## 변경 파일
- `backend/src/api/tasks.py` (`update_task`)
- `backend/src/api/task_schemas.py` (`TaskUpdate`)
- `backend/tests/integration/test_tasks_api.py` (`TestUpdateTask`)

## TDD 결과
- RED: 시험을 먼저 쓰고 라우트가 없어 실패하는 것을 확인했습니다.
- GREEN: `TestUpdateTask`의 시험 모두 통과. 전체 결과는 T075 보고서에 적었습니다.
- REFACTOR: 프로젝트 수정 API와 같은 `changes()` 방식(보낸 필드만 서비스로 전달)을 재사용했습니다.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- "안 보냄"과 "null로 지움"을 구분하기 위해 `model_fields_set`으로 **실제로 보낸 필드만** 서비스에 넘깁니다(`UNSET` 표식, 프로젝트 API와 동일).
- 제목이 `null`이면 제목을 지울 수 없으므로 "최소 5자 이상" 메시지로 `400`을 돌려줍니다.
- 서비스는 제목과 설명을 **둘 다 검사한 뒤** 값을 바꿔서, 한쪽이 틀리면 아무것도 바뀌지 않습니다.

## 관련 개념
- **PATCH와 PUT**: PATCH는 바꿀 필드만 보내는 부분 수정, PUT은 전체 교체입니다.
- **무시되는 필드**: 모르는 필드를 오류로 막지 않고 조용히 넘기는 것은 FastAPI/pydantic의 기본 동작입니다.

## 주의할 점 (비고)
- 계약은 "바꿀 수 없다"고만 적었고 오류로 거절하라고 하지 않아서, 금지 필드는 무시하는 쪽으로 구현했습니다. 거절이 필요하면 계약과 함께 결정해야 합니다.

## 다음 단계
T074 태스크 삭제(휴지통) API.
