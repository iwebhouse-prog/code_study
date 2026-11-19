# TASK-062. 업로드 코드(UploadedCode) 모델

## 상태
완료

## 날짜
2026-11-12

## 작업 요약
태스크 하나에 올린 코드의 **요약 정보(언어, 난이도, 줄 수, 파일 수, 크기)를 담는 `uploaded_code` 표의 모델**을 만들었습니다. 택배에 비유하면 상자 겉에 붙은 송장입니다. 상자 안의 물건 하나하나(파일)는 T063의 CodeFile이 맡고, 이 모델은 "몇 개, 몇 바이트, 어떤 종류"를 적어 둡니다.

1. **칸 구성**: 태스크 id, 감지된 언어, 난이도, 총 줄 수, 파일 수, 크기(바이트), 만든 시각. 마이그레이션과 같은지 실제 DB로 확인했습니다.
2. **태스크당 하나**: `task_id`가 유일(UNIQUE)하여 같은 태스크에 두 번째 업로드를 넣으면 DB가 거절합니다.
3. **크기 제한**: 10MB(10,485,760바이트)까지만 허용합니다(FR-014). 딱 10MB는 통과, 1바이트라도 넘으면 거절됩니다.
4. **난이도**: `beginner`, `intermediate`, `advanced`만 허용합니다.
5. **관계**: `Task.uploaded_code`로 하나만 불러오고(없으면 `None`), 태스크가 지워지면 함께 지워집니다.

## 변경 파일
- `backend/src/models/uploaded_code.py` (새 파일)
- `backend/src/models/task.py` (`uploaded_code` 관계 추가)
- `backend/src/models/__init__.py` (UploadedCode 등록)
- `backend/tests/unit/test_uploaded_code_model.py` (새 시험 12개)
- `backend/tests/integration/test_uploaded_code_model.py` (새 시험 10개, 실제 PostgreSQL)

## TDD 결과
- RED: 시험을 먼저 쓰고 `cannot import name 'UploadedCode'`로 실패하는 것을 확인했습니다.
- GREEN: 새 시험 22개 통과. 전체 503개 통과, `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.** 새로 쓴 시험 파일에는 black 자동 정리만 했습니다.

## 기술 결정
- **`TimestampMixin`을 쓰지 않았습니다.** 이 표에는 `updated_at`이 없기 때문입니다(업로드는 고치지 않고 새로 올림). 대신 `created_at`만 직접 두고 `eager_defaults`를 켜서 저장 직후에도 읽을 수 있게 했습니다.
- **언어·난이도는 비워 둘 수 있습니다.** 파일을 먼저 저장하고 분석(T065, T066)이 나중에 채우는 순서이기 때문입니다.
- **휴지통 칸이 없습니다.** 휴지통은 태스크 단위로만 하고, 업로드 코드는 태스크가 영구 삭제될 때 함께 지워집니다(data-model.md).
- 10MB는 `MAX_UPLOAD_BYTES` 상수로 두어, T064 파일 검증에서 같은 값을 쓰게 했습니다.

## 관련 개념
- **일대일 관계**: 태스크 하나에 업로드 코드 하나. `uselist=False`로 목록 대신 하나의 값(또는 `None`)을 돌려줍니다.

## 주의할 점 (비고)
- DB 크기 제한은 마지막 방어선입니다. 실제 사용자 안내 메시지는 업로드 단계(T064, T069)에서 먼저 보여 주어야 합니다.

## 다음 단계
T063 CodeFile 모델 (UploadedCode에 `files` 관계 추가).
