# TASK-063. 코드 파일(CodeFile) 모델

## 상태
완료

## 날짜
2026-11-12

## 작업 요약
업로드 하나에 들어 있는 **파일 한 개 한 개를 기록하는 `code_files` 표의 모델**을 만들었습니다. T062의 UploadedCode가 택배 상자의 송장이라면, CodeFile은 상자 안 물건 목록의 한 줄입니다. 파일 내용 자체는 디스크(`storage_path`)에 있고(T067), 이 행은 이름·경로·확장자·크기 같은 설명을 담습니다.

1. **칸 구성**: 업로드 id, 원래 파일 이름, 폴더 안 상대 경로, 확장자, 크기, 저장 위치, MIME 형식, 만든 시각. 마이그레이션과 같은지 실제 DB로 확인했습니다.
2. **확장자 제한(FR-015)**: `.py .js .ts .jsx .tsx .html .css .java .cpp .c .txt .md` 12가지만 허용합니다. `.exe`는 거절됩니다.
3. **필수 칸**: 파일 이름과 저장 위치가 없으면 DB가 거절합니다.
4. **관계**: `UploadedCode.files`로 여러 파일을 불러오며, 폴더 구조처럼 **경로 → 이름 순**으로 정렬됩니다. 업로드나 태스크를 지우면 파일 행도 함께 지워집니다.

## 변경 파일
- `backend/src/models/code_file.py` (새 파일)
- `backend/src/models/uploaded_code.py` (`files` 관계 추가)
- `backend/src/models/__init__.py` (CodeFile 등록)
- `backend/tests/unit/test_code_file_model.py` (새 시험 13개)
- `backend/tests/integration/test_code_file_model.py` (새 시험 10개, 실제 PostgreSQL)

## TDD 결과
- RED: 시험을 먼저 쓰고 `cannot import name 'CodeFile'`로 실패하는 것을 확인했습니다.
- GREEN: 새 시험 23개 통과. 전체 526개 통과, `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.** 새로 쓴 시험 파일에는 black 자동 정리만 했습니다.

## 기술 결정
- **확장자 목록은 상수 하나(`SUPPORTED_EXTENSIONS`)에서 만듭니다.** DB 검사 규칙도 이 상수로 만들어서, T064 파일 검증과 목록이 어긋날 수 없습니다.
- **시험으로 확인한 두 가지 빈틈**(T064·T069에서 처리해야 함):
  - DB 검사는 **대소문자를 구분**합니다. `.PY`는 거절되므로 저장 전에 소문자로 바꿔야 합니다.
  - SQL 규칙상 **확장자가 비어 있으면(NULL) 검사를 통과**합니다. `Makefile`처럼 확장자 없는 파일은 업로드 서비스가 먼저 막아야 합니다.
- 업로드처럼 파일도 수정하지 않으므로 `updated_at`이 없고, `created_at`만 `eager_defaults`로 바로 읽게 했습니다.

## 관련 개념
- **일대다 관계**: 업로드 하나에 파일 여러 개. `files`는 목록을 돌려줍니다.
- **CASCADE 삭제**: 부모(태스크 → 업로드)가 지워지면 자식(파일 행)도 DB가 자동으로 지웁니다.

## 주의할 점 (비고)
- 업로드당 파일 1~20개(FR-018)와 바이너리 거절(FR-016)은 DB가 아닌 업로드 단계의 규칙이라 T064·T069에서 구현합니다.
- 디스크의 실제 파일은 DB가 지우지 않습니다. 영구 삭제 시 파일 정리는 저장 서비스(T067)와 휴지통 정리 작업의 몫입니다.

## 다음 단계
T064 파일 검증 도구(확장자·크기·바이너리 판별).
