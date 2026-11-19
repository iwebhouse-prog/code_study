# TASK-071. 태스크 생성·업로드 API (POST /projects/{project_id}/tasks)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
제목·설명과 **코드를 한 번에 올려 태스크를 만드는 API**를 만들었습니다. 우편 접수처에서 편지(제목·설명)와 소포(코드 파일)를 한 창구에서 받는 것과 같습니다. 요청은 `multipart/form-data`입니다.

- 필드: `title`(5~255자), `description`(500자 이하, 빈 값 → `null`), `upload_method`(`file|folder|paste`), `files`(반복 필드, 폴더는 파일 이름 자리에 상대 경로), 붙여넣기는 `code`와 `language`
- 성공 `201`: Task 객체 + `files[]`(경로·이름 순) + `excluded_paths[]`
- 오류(공통 오류 형식 + 한국어 `suggestion`): `validation_error`(필드별 메시지), `no_files`, `too_many_files`, `file_too_large`(413), `unsupported_file_type`, `binary_file`, `unsupported_encoding`, `invalid_file_path`, `403`, `404`
- 프로젝트의 `last_activity_at`을 갱신하고, 실패하면 아무것도 저장하지 않으며 디스크에 쓴 파일도 지웁니다.

## 변경 파일
- `backend/src/api/tasks.py` (`create_task`, `read_upload_form`)
- `backend/src/api/task_schemas.py` (`UploadResponse`, `FileResponse`)
- `backend/tests/integration/test_tasks_api.py` (`TestCreateFileTask`, `TestCreateFolderTask`, `TestCreatePasteTask`, `TestCreateErrors`)

## TDD 결과
- RED: 시험을 먼저 쓰고 라우트가 없어 실패하는 것을 확인했습니다.
- GREEN: 생성·폴더·붙여넣기·오류 시험 통과(2.4MB 붙여넣기, 10MB 초과 413 포함).
- REFACTOR: 첫 구현의 `UploadFile` 검사가 맞지 않아(`no_files`로 오판) 스타렛 쪽 클래스로 고쳤습니다.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- 폼을 `request.form()`으로 직접 읽습니다. FastAPI의 `Form()`은 텍스트 칸을 **1MB까지만** 받아, 큰 붙여넣기가 이유 모를 `400`이 되기 때문입니다. 한도를 10MB로 올려 계약대로 `file_too_large`가 나오게 했습니다. 문서(OpenAPI)에는 `openapi_extra`로 폼 모양을 적었습니다.
- 파라미터 4개 제한을 지키려고 폼 읽기를 의존성(`UploadInputDep`)으로 묶었습니다.
- `files[].language`는 확장자로 정합니다(`.jsx` → `javascript`). 전체 업로드의 `detected_language`만 내용을 보고 판단합니다.

## 관련 개념
- **멀티파트(multipart)**: 글자와 파일을 한 요청에 담는 방식입니다. 칸마다 이름표가 붙습니다.
- **원자성**: 여러 저장 단계가 전부 성공하거나 전부 취소되는 성질입니다.

## 주의할 점 (비고)
- 요청 본문은 한 번에 메모리로 읽습니다. 10MB 검사는 다 읽은 뒤에 하므로, 아주 큰 요청은 프록시(nginx 등)의 본문 크기 제한으로 먼저 막는 것이 안전합니다.
- 계약의 오류 표에 `upload_method` 메시지가 없어 "업로드 방식을 선택하세요."로 정했습니다.

## 다음 단계
T072 태스크 상세 조회 API.
