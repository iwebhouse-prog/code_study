# TASK-075. 태스크 코드 조회 API (GET /tasks/{task_id}/code)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
태스크에 올린 **파일 목록과 파일 내용**을 돌려주는 API입니다. 사물함 목록(DB)을 보고 사물함 속 물건(디스크의 파일)을 꺼내 주는 일입니다.

- `200`: `{ task_id, detected_language, files: [{ id, file_name, file_path, file_extension, file_size_bytes, language, content }] }`
- 파일 순서는 업로드 결과와 같은 `file_path`, `file_name` 순서입니다. `content`는 UTF-8 + LF입니다(저장할 때 통일).
- 디스크에서 파일이 사라졌으면 `404 file_missing` ("코드 파일을 찾을 수 없습니다. 다시 업로드하세요.").
- 코드 없이 만들어진 태스크는 `files: []`, `detected_language: null`을 돌려줍니다.
- `403`, `404 not_found`, `400`(UUID 아님), `401`

## 변경 파일
- `backend/src/api/tasks.py` (`get_task_code`)
- `backend/src/api/task_schemas.py` (`CodeResponse`, `FileContentResponse`)
- `backend/src/services/task_service.py` (`get_with_files_for_user`)
- `backend/tests/integration/test_tasks_api.py` (`TestGetCode`)

## TDD 결과
- RED: 시험을 먼저 쓰고 라우트가 없어 실패하는 것을 확인했습니다.
- GREEN: `TestGetCode` 모두 통과(파일 삭제 후 `file_missing` 포함). 전체 772개 통과(T067~T075 합계), `src` 줄·분기 100%, ruff·black·mypy(strict) 통과.
- REFACTOR: 파일 목록을 꺼내는 `files_of()`를 업로드 응답과 코드 조회가 함께 씁니다.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- 파일 읽기는 `asyncio.to_thread`로 감싸 서버가 읽는 동안 다른 요청을 막지 않게 했습니다.
- 저장 경로는 업로드 폴더 기준 상대 경로이고, 읽을 때 폴더 밖을 가리키면 "없는 파일"로 취급해 폴더 탈출을 막습니다.
- 파일이 하나라도 없으면 일부만 보내지 않고 `file_missing`으로 전체를 실패시킵니다.

## 관련 개념
- **file_missing**: DB 기록은 있는데 실제 파일이 없는 상태입니다. 디스크를 지웠거나 옮겼을 때 생깁니다.
- **지연 로딩 방지**: 파일 행을 `selectinload`로 미리 읽어, 비동기 환경에서 나중에 읽다가 오류가 나지 않게 합니다.

## 주의할 점 (비고)
- 파일 수는 최대 20개, 합계 10MB라 한 번에 응답으로 보내도 되지만, 이후 큰 파일을 지원하게 되면 페이지 나누기나 개별 파일 조회가 필요합니다.
- 계약대로 `language`는 확장자로 정합니다. 내용이 파이썬인 `.txt`도 `text`로 나옵니다.

## 다음 단계
프런트엔드 T076–T083(태스크 화면)과 연결 확인.
