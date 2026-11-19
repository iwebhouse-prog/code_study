# TASK-069. 코드 업로드 서비스

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
파일·폴더·붙여넣기로 들어온 코드를 **검사하고, 읽고, 분석하고, 저장하는 서비스**를 만들었습니다. 택배 접수대처럼 상자를 열어 규칙에 맞는지 확인하고(검사), 내용물을 읽고(디코딩), 무게·종류를 적고(분석), 창고에 넣은 뒤 송장을 남깁니다(DB). 중간에 하나라도 실패하면 **창고에 넣은 물건도 도로 치웁니다**.

검사 순서(계약 그대로, 처음 실패에서 멈춤): 제외 경로 제거 → 파일 수 → 전체 크기 → 파일별로 경로 → 확장자 → 바이너리 → 인코딩.

- 안전하지 않은 경로(절대 경로, `..`, 드라이브 글자, 255자 초과 이름) → `400 invalid_file_path`
- UTF-8(BOM 허용) → CP949 순으로 읽고, 둘 다 안 되면 `400 unsupported_encoding`
- 붙여넣기: `pasted<확장자>`로 저장하고, 고른 언어를 그대로 `detected_language`로 저장
- 언어 감지(T065)·복잡도(T066)는 `asyncio.to_thread`로 별도 스레드에서 실행
- 프로젝트 소유 확인 → 태스크 필드 검증 → 업로드 검사 순서로 오류를 냅니다.

## 변경 파일
- `backend/src/services/code_analysis/upload_files.py` (새 파일: 검사·디코딩, DB 없는 순수 함수)
- `backend/src/services/code_analysis/code_upload_service.py` (새 파일: 저장·롤백)
- `backend/src/api/error_messages.py` (인코딩·경로·붙여넣기 메시지 추가)
- `backend/src/utils/file_validator.py` (`_UploadError` → `UploadError`로 이름만 공개)
- `backend/tests/unit/test_upload_files.py` (새 시험 32개)
- `backend/tests/integration/test_code_upload_service.py` (새 시험 17개, 실제 PostgreSQL + 임시 폴더)

## TDD 결과
- RED: 시험을 먼저 쓰고 `upload_files` 모듈이 없어 수집 단계에서 실패하는 것을 확인했습니다.
- GREEN: 새 시험 49개 통과. 전체 710개 통과, `src` 줄·분기 커버리지 100%, ruff·black·mypy(strict) 통과.
- REFACTOR: 파일 250줄 제한을 위해 "검사(순수)"와 "저장(DB)"을 두 파일로 나눴습니다.
- **기존 시험 파일은 고치지 않았습니다.** `file_validator.py`의 클래스 이름 변경은 소스 파일이며, 기존 시험은 그 이름을 쓰지 않아 영향이 없습니다.

## 기술 결정
- `validate_upload()` 대신 그 안의 부품(`validate_file_count`, `validate_total_size`, `validate_extension`, `validate_text`)을 직접 호출합니다. 계약이 파일별로 "경로 → 확장자 → …" 순서를 요구해서, 경로 검사를 확장자 검사보다 앞에 끼워야 했기 때문입니다.
- **원자적 저장**: 프로젝트 잠금과 태스크 추가(커밋 없음) → 파일 쓰기 → 코드 행 추가 → 한 번에 커밋. 예외가 나면 `rollback()` 후 이미 쓴 파일을 삭제합니다.
- 파일 목록은 저장 전에 `(file_path, file_name)` 순으로 정렬해 응답이 DB 정렬과 같게 합니다.
- `file_size_bytes`/`upload_size_bytes`는 올라온 원본 바이트 수입니다.

## 관련 개념
- **인코딩**: 글자를 바이트로 바꾸는 약속입니다. 한글 윈도 메모장은 예전에 CP949로 저장했습니다.
- **롤백(되돌리기)**: 저장 도중 실패했을 때 DB 변경을 없던 일로 만드는 것입니다.

## 주의할 점 (비고)
- 파일 쓰기는 이벤트 루프에서 동기로 실행됩니다(최대 10MB라 MVP에서는 충분).
- 전체 크기 제한은 요청을 다 읽은 뒤 검사합니다. 아주 큰 요청을 미리 막으려면 프록시의 본문 크기 제한이 필요합니다.
- 응답의 파일 순서는 Python 정렬 기준이고, 이후 조회는 DB 정렬 기준입니다. 대소문자가 섞인 이름은 환경에 따라 순서가 다를 수 있습니다.

## 다음 단계
T070–T075 태스크 API 엔드포인트.
