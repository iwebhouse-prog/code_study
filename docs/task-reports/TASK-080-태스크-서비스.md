# TASK-080. 태스크 서비스 (task-service)

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
화면과 서버 사이의 **통역사**입니다. 서버는 `task_number`처럼 밑줄 표기로 말하고, 화면 코드는 `taskNumber`로 말하므로 둘을 번역합니다. 프로젝트 서비스(T053)와 같은 방식입니다.

제공하는 기능:
1. `list(projectId)`: 프로젝트의 태스크 목록
2. `create(projectId, 입력)`: 태스크 만들기 + 코드 올리기
3. `get`, `update`, `remove`: 조회, 수정(제목/설명), 삭제(휴지통)
4. `getCode(taskId)`: 파일별 코드 내용

`create`는 JSON이 아니라 **택배 상자(multipart 폼)**로 보냅니다. 필드 이름은 계약서와 정확히 같습니다: `title`, `description`(비었으면 생략), `upload_method`, 파일마다 `files` 부분(폴더면 파일 이름 자리에 상대 경로), 붙여넣기는 `code`와 `language`.

## 변경 파일
- `frontend/src/services/task-service.ts` (새 파일)
- `frontend/src/lib/query-keys.ts` (`projectTasksKey`, `taskKey` 추가. 기존 키는 그대로)
- `frontend/tests/unit/task-service.test.ts` (새 파일, 시험 14개)
- `frontend/tests/helpers/tasks.ts` (새 파일: 시험용 태스크 예시 데이터)

## TDD 결과
- RED: 시험을 먼저 썼고 서비스 파일이 없어 실패하는 것을 확인했습니다.
- GREEN: 14개 통과. 확인한 것: 이름 변환(null 보존 포함), 각 요청의 방식과 주소, 파일 업로드 폼 필드(파일 여러 개, 폴더 경로, 붙여넣기), 업로드 결과의 파일 목록과 제외 경로 변환, 오류 시 `ApiError`와 `suggestion` 전달.
- REFACTOR: 주소 만드는 함수(`taskUrl`, `projectTasksUrl`)로 중복을 정리했습니다.
- **이 작업에서 기존 테스트 파일은 고치지 않았습니다.**

## 기술 결정
- 입력 타입을 "파일/폴더" 형태와 "붙여넣기" 형태로 나눈 유니온 타입으로 만들어, 잘못된 조합이 컴파일 단계에서 걸리게 했습니다.
- 태스크 목록 캐시 이름을 `['projects', 프로젝트id, 'tasks']`로 했습니다. 프로젝트 캐시의 하위라서 한 번의 무효화로 프로젝트와 태스크가 함께 새로 고쳐집니다.
- 브라우저가 경계 문자열(boundary)을 붙이도록 `Content-Type`을 직접 지정하지 않았습니다.

## 관련 개념
- **multipart/form-data**: 파일과 글자를 한 요청에 담는 전송 형식입니다.
- **캐시 키**: TanStack Query가 데이터를 구분하는 이름표입니다.

## 주의할 점 (비고)
- 순서 변경: 태스크 카드(T079)가 이 파일의 `Task` 타입이 필요해서 T080을 T079보다 먼저 했습니다(둘 다 독립 작업이라 문제 없음).
- 실제 백엔드로 하는 확인은 이후 브라우저 시험에서 합니다. 지금은 가짜 응답으로만 시험했습니다.

## 다음 단계
T079 태스크 카드.
