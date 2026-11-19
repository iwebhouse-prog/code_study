# TASK-067. 파일 저장 서비스

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
업로드된 코드를 **디스크에 보관하고 다시 꺼내 주는 서비스**(`file_storage.py`)를 만들었습니다. 도서관 사물함처럼 `사용자 번호 / 태스크 번호` 칸 안에 파일을 넣고, 사물함에는 사용자가 붙인 이름 대신 **무작위 번호표(UUID)**만 붙입니다. 그래서 파일 이름에 어떤 글자가 들어 있어도 엉뚱한 곳에 저장될 수 없습니다.

- 저장 위치: `{UPLOAD_DIR}/{user_id}/{task_id}/{uuid}{확장자}`
- 저장 내용: 읽어 들인 글자를 **UTF-8 + 줄바꿈 LF**로 통일해서 기록
- `read`: 저장된 글자를 다시 읽기. 파일이 없으면 `404 file_missing`("코드 파일을 찾을 수 없습니다. 다시 업로드하세요.")
- `delete`: 롤백 때 이미 쓴 파일을 지우기(이미 없어도 오류 없음, 폴더가 비면 폴더도 정리)
- `AppConfig.upload_dir`: 환경 변수 `UPLOAD_DIR`을 읽음(기본 `storage/uploads`)

## 변경 파일
- `backend/src/services/code_analysis/file_storage.py` (새 파일)
- `backend/src/config.py` (`upload_dir` 추가)
- `backend/src/api/error_messages.py` (`TASK_MESSAGES` 추가)
- `backend/tests/unit/test_file_storage.py` (새 시험 12개)
- `backend/tests/unit/test_upload_config.py` (새 시험 5개)

## TDD 결과
- RED: 시험을 먼저 쓰고 `cannot import name 'TASK_MESSAGES'`, `upload_dir` 없음으로 실패하는 것을 확인했습니다.
- GREEN: 새 시험 17개 통과. 전체 616개 통과, `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- REFACTOR: `try/except/pass`를 `contextlib.suppress`로 바꿨습니다.
- **기존 시험 파일은 고치지 않았습니다.** 시험은 모두 임시 폴더에서 돌아 실제 `storage/uploads`를 건드리지 않습니다.

## 기술 결정
- **DB에는 업로드 폴더 기준 상대 경로를 저장**합니다. 서버를 옮겨 `UPLOAD_DIR`이 바뀌어도 기존 기록이 깨지지 않습니다.
- **`UPLOAD_DIR`의 상대 경로는 저장소 루트 기준**으로 해석합니다. 서버를 어느 폴더에서 켜든 같은 곳을 씁니다.
- `read`/`delete`는 경로가 업로드 폴더 밖을 가리키면 "없는 파일"로 취급해 폴더 탈출을 막습니다.
- 파일은 `write_bytes`로 씁니다. 글자 모드로 쓰면 윈도에서 `\n`이 `\r\n`으로 바뀌기 때문입니다.

## 관련 개념
- **UUID**: 겹칠 확률이 사실상 없는 무작위 이름표입니다.
- **경로 탈출(path traversal)**: `../../` 같은 경로로 허용된 폴더 밖의 파일에 접근하는 공격입니다.

## 주의할 점 (비고)
- 저장과 읽기는 동기 방식입니다. 파일이 최대 10MB라 MVP에는 충분하지만, 호출하는 쪽에서 필요하면 `asyncio.to_thread`로 감쌉니다.
- 태스크 영구 삭제 시 디스크 파일을 지우는 일은 아직 없습니다(휴지통 기능 단계).

## 다음 단계
T068 TaskService.
