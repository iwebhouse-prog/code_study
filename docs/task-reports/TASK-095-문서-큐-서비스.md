# TASK-095. 문서 생성 큐 서비스

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
**주문을 접수하고(enqueue), 진행 상황을 알려 주고(status), 실패한 주문을 다시 넣는(regenerate)** 서비스를 만들었습니다. 접수창구 직원에 비유하면, 번호표(pending 행)를 먼저 확정해 둔 뒤에 주방에 전달하고, 전달이 안 돼도 번호표는 남깁니다.

- `enqueue(task_id)`: 행이 없으면 `pending`으로 만들고 **커밋한 뒤** Celery 작업을 보냅니다. 큐(Redis) 오류와 DB 오류는 로그만 남기고 예외를 올리지 않습니다.
- `status(task_id)`: 계약의 Status 객체를 만듭니다. 예상 시간은 `clamp(30 + 0.3 × 줄 수, 30, 180)`초이며, `pending`은 전체 예상값, `in_progress`는 `max(예상 − 경과, 5)`입니다.
- 정체 규칙: `in_progress`가 300초를 넘으면 `failed/timeout`으로 보고합니다(DB 행은 바꾸지 않음).
- `regenerate(task_id)`: `failed` 또는 정체된 실행만 `pending`으로 되돌리고 커밋 후 다시 큐에 넣습니다. 그 밖의 상태는 `409 document_not_failed`입니다.
- `get_completed(task_id)`: `completed`만 돌려주고, 아니면 `409 document_not_ready`(details.status)입니다.

## 변경 파일
- `backend/src/services/document/document_queue_service.py` (새 파일)
- `backend/src/models/learning_document.py` (`is_stale`, `can_restart`, `restart` 추가)
- `backend/src/api/error_messages.py` (`DOCUMENT_MESSAGES` 추가)
- 시험(새 파일): `tests/unit/test_learning_document_restart.py` (10개), `tests/integration/test_document_queue_service.py` (23개)

## TDD 결과
- RED: 서비스 모듈과 모델 메서드를 임시로 치우고 실행해 `ImportError`와 메서드 부재로 실패하는 것을 확인했습니다. 다만 구현 초안을 시험 직후 바로 써 두었기 때문에, 첫 실행은 이 방식(치우고 재확인)으로 한 것입니다.
- GREEN: 시험 파일의 도우미 두 곳을 고쳤습니다(속성 대입 순서 때문에 검증자가 거부, 실행 중인 이벤트 루프 안에서 `asyncio.run`을 호출). 구현은 그대로 통과했습니다.
- 전체: 964개 통과, `src` 줄·분기 100%, ruff/black/mypy 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- `completed` 문서는 어떤 경로로도 바뀌지 않습니다(`restart`는 `ValueError`).
- `regenerate`는 행을 `FOR UPDATE`로 잠가 두 번 빠르게 눌러도 한 번만 다시 시작합니다.
- 전송 함수를 생성자에 주입할 수 있어 시험이 Redis를 쓰지 않습니다. 기본 전송은 `apply_async(retry=False)`로, Redis가 꺼져 있으면 요청이 오래 멈추지 않고 바로 실패합니다.

## 관련 개념
- **커밋 후 전송**: 작업자가 문서 행을 찾지 못하는 경쟁 상태를 막으려고 반드시 DB 커밋 뒤에 메시지를 보냅니다.

## 주의할 점 (비고)
- 정체 판단은 `generation_started_at` 기준이라, 아직 시작 전인 `pending`이 오래 남아도 정체로 보지 않습니다(큐 전송 실패 시 `regenerate`는 `failed`만 허용하므로 사용자가 다시 누를 방법이 없음). 필요하면 별도 규칙을 정해야 합니다.
- 날짜는 `...Z` 형식으로 나갑니다(`+00:00`과 같은 시각).

## 다음 단계
T096 업로드 직후 문서 생성 트리거.
