# TASK-090. 학습 문서(LearningDocument) 모델

## 상태
완료

## 날짜
2026-11-17

## 작업 요약
AI가 만든 **7장짜리 학습 문서를 저장하는 `learning_documents` 표의 모델**을 만들었습니다. 문서 내용은 장마다 구조가 달라 JSONB(DB 안의 JSON) 한 칸에 통째로 담습니다. 인쇄소의 작업 지시서에 비유하면, "대기 → 인쇄 중 → 완성/실패" 상태 칸과 완성된 책(내용)이 한 장에 붙어 있는 셈입니다.

1. **칸 구성**: 태스크 id(태스크당 하나), 내용(JSONB), 생성 상태, 시작·완료 시각, 실패 이유, Celery 작업 id, 만든·수정 시각. 실제 DB와 같은지 확인했습니다.
2. **내용 규칙(DB)**: 내용은 JSON 객체여야 하고 `chapter1`~`chapter7` 열쇠가 모두 있어야 합니다. 하나라도 빠지면 DB가 거절합니다.
3. **빈 문서**: 내용 칸은 비울 수 없어서, 생성을 기다리는 문서는 `LearningDocument.empty_content()`(7개 장이 모두 빈 `{}`)로 만듭니다.
4. **상태 바꾸기는 메서드로만**:

| 메서드 | 가능한 이전 상태 | 결과 |
|---|---|---|
| `start(celery_task_id)` | pending, failed | in_progress, 시작 시각·작업 id 기록, 이전 오류 지움 |
| `complete(content)` | in_progress | completed, 7개 장 확인 후 내용 저장 |
| `fail(error)` | in_progress | failed, 실패 이유 기록 |

5. **완성 문서는 고정(FR-038)**: completed가 된 문서의 내용을 바꾸려 하면 `ValueError`가 납니다. 실패한 문서는 다시 `start`할 수 있어 재시도(T093)에 쓰입니다.
6. **관계**: `Task.learning_document`(하나 또는 없음), 태스크가 지워지면 함께 지워집니다.

## 변경 파일
- `backend/src/models/learning_document.py` (새 파일)
- `backend/src/models/task.py` (`learning_document` 관계 추가)
- `backend/src/models/__init__.py` (등록)
- `backend/tests/unit/test_learning_document_model.py` (새 시험 22개)
- `backend/tests/integration/test_learning_document_model.py` (새 시험 10개, 실제 PostgreSQL)

## TDD 결과
- RED: `cannot import name 'LearningDocument'`로 실패를 확인했습니다.
- GREEN: 새 시험 31개 통과(처음 실행 때 Docker가 꺼져 DB 시험 10개가 건너뛰어졌고, Docker를 켜고 다시 돌려 모두 통과 확인). 전체 803개 통과, `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- **상태 변경을 메서드 세 개로만** 하게 한 것은 프로젝트의 휴지통 메서드(T043)와 같은 방식입니다. 상태·시각·오류 칸이 서로 어긋날 수 없습니다.
- 장 열쇠 목록(`CHAPTER_KEYS`)으로 DB 검사 규칙을 만들어, 모델과 DB 규칙이 한 곳에서 나옵니다.
- JSONB를 "변경 추적 없는" 기본형으로 둬, 딕셔너리를 제자리에서 고쳐도 저장되지 않습니다. 고정되어야 하는 문서에 맞는 선택입니다.

## 관련 개념
- **JSONB**: PostgreSQL이 JSON을 해석된 형태로 저장하는 형식. 안의 값으로 검색·검사할 수 있습니다.
- **상태 기계**: 정해진 순서로만 상태가 바뀌게 하는 설계입니다.

## 주의할 점 (비고)
- 각 장 안의 세부 구조(개념 카드 5개 등)는 DB가 검사하지 않습니다. 프롬프트(T092)와 생성 서비스(T093)에서 검사해야 합니다.
- "생성 중"이 오래 멈춘 문서(작업자가 죽은 경우)를 다시 살리는 규칙은 대기열 서비스(T095)에서 정해야 합니다.

## 다음 단계
T091 Gemini API 클라이언트.
