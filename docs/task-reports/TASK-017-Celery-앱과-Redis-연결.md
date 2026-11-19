# TASK-017. Celery 앱과 Redis 연결

## 상태
완료

## 날짜
2026-11-02

## 작업 요약
AI 문서 생성처럼 **오래 걸리는 일을 웹 요청과 분리해 뒤에서 처리하는 작업 시스템**의 기본 틀을 만들었습니다 (`backend/src/tasks/celery_app.py`).

식당에 비유하면, 손님(웹 요청)이 주문하면 홀 직원(API 서버)은 주문서를 주방 게시판(Redis)에 붙이고 바로 "접수되었습니다"라고 답합니다. 요리(AI 작업)는 주방 직원(Celery 워커)이 게시판에서 주문서를 가져가 따로 만듭니다. 그래서 3분짜리 문서 생성이 있어도 웹 화면은 멈추지 않습니다.

주문 게시판은 일의 종류별로 네 칸(큐)으로 나눴습니다(헌법 III).

| 큐 | 들어갈 작업 | 담당 Task |
|---|---|---|
| `default` | 기타 짧은 작업, 연결 확인(`system.ping`) | - |
| `document_generation` | AI 학습 문서 생성 (1~3분) | T094 |
| `practice_generation` | 연습 문제 생성 (30~60초) | T118 |
| `cleanup` | 휴지통 30일 자동 삭제 (매일) | T172 |

`src/tasks/document_generation.py` 같은 파일에 작업을 만들면 **파일 이름만으로 해당 큐에 자동 배정**됩니다.

주요 규칙:
- 작업 하나는 최대 **300초**(헌법 V). 270초에 "곧 끝내라" 신호(soft limit)를 먼저 보내, 작업이 스스로 "실패"를 기록할 시간을 줍니다.
- 워커가 작업 도중 죽으면 그 작업은 **다른 워커가 다시 실행**합니다(늦은 확인 `acks_late`). 그래서 앞으로 만들 작업은 두 번 실행돼도 문제가 없게 만들어야 합니다.
- 작업 결과는 Redis에 **1일** 보관합니다.
- 진행 상태 `STARTED`를 기록해, 문서 생성 상태 API(T098)가 "생성 중"을 보여 줄 수 있습니다.

실행: `cd backend; celery -A src.tasks.celery_app worker --loglevel=info --pool=solo` (Windows는 `--pool=solo` 필요)

## 변경 파일
- `backend/src/tasks/celery_app.py` (신규) — `CeleryConfig`, `create_celery_app()`, 모듈 변수 `app`, `system.ping` 작업
- `backend/tests/unit/test_celery_app.py` (신규, 18개), `backend/tests/integration/test_celery_app.py` (신규, 3개)
- `backend/pyproject.toml` — mypy 예외 2개 (Celery·kombu에 타입 정보가 없음, `src.tasks`에서만 `@app.task` 허용)
- `specs/001-ai-code-learning-platform/quickstart.md` — 워커 명령에 큐 목록과 Windows 안내 추가
- `specs/001-ai-code-learning-platform/tasks.md` — T017 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src.tasks.celery_app` 모듈이 없어 실패 확인
- GREEN: `celery_app.py` 작성 → 1개 실패(`result_expires`를 Celery가 숫자로 저장 — 테스트의 기대 자료형이 틀림) → 테스트 수정 후 통과. 실제 Redis와 테스트용 워커로 작업 왕복 통합 테스트 추가
- REFACTOR:
  - mypy strict가 Celery(타입 정보 없음)를 거부 → `pyproject.toml`에 범위를 좁힌 예외 추가
  - **실제 워커 실행 화면에서 네 큐가 모두 `exchange=default key=default`로 묶여 있는 것을 발견** → "큐마다 고유 라우팅 키" 단위 테스트와 "작업이 자기 큐에만 들어가는지" 통합 테스트를 먼저 추가(단위 테스트 실패 확인) → 큐마다 같은 이름의 exchange·routing key 지정 → 통과
- 최종: 백엔드 테스트 217개 통과(DB·Redis 통합 테스트 포함), `src` 줄·분기 커버리지 **100%**, ruff·black·mypy strict 통과
- 실제 실행 확인: quickstart 명령으로 워커 실행 → `default`, `document_generation` 큐에 각각 `system.ping`을 보내 둘 다 `pong`/`SUCCESS`, 각 작업은 정확히 한 번씩만 실행됨
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **JSON만 주고받기(pickle 금지)**: pickle 형식을 받으면 Redis에 쓸 수 있는 누구나 워커에서 코드를 실행할 수 있습니다.
- **Redis 재전달 시간(visibility timeout) 1시간**: 늦은 확인 방식에서는 확인 안 된 작업을 이 시간이 지나면 다시 보냅니다. 가장 긴 작업(300초)보다 짧으면 실행 중인 작업이 중복 실행되므로, 더 길어야 한다는 것을 테스트로 묶었습니다.
- **한 번에 하나씩 가져가기(`prefetch_multiplier=1`)**: 몇 분짜리 AI 작업을 한 워커가 여러 개 쌓아 두면 다른 워커가 놀게 됩니다.
- **모듈 변수 `app`**: quickstart의 `celery -A src.tasks.celery_app` 명령이 이 이름을 찾습니다. FastAPI와 달리 Celery CLI는 앱 생성 함수 방식(`--factory`)이 없어서 import 시 생성합니다. `REDIS_URL`이 없으면 docker-compose 기본값(`redis://127.0.0.1:6379/0`)을 씁니다.
- **`system.ping` 작업**: 실제 기능 작업이 아직 없어도 "워커가 살아서 작업을 처리하는지" 확인할 수 있게 넣었습니다.
- **통합 테스트는 Redis 15번 DB 사용**: 개발용 큐(0번)를 건드리지 않고, 끝나면 비웁니다.
- **시간대 UTC**: 매일 실행할 휴지통 정리(T172) 시각은 UTC 기준으로 정합니다.

## 비고
- **Windows에서는 `--pool=solo`**: Celery 기본 실행 방식(prefork)은 Windows에서 동작하지 않습니다. solo 방식에서는 300초 강제 종료가 적용되지 않으니, 시간 제한 동작은 Linux(운영 환경)에서 확인해야 합니다.
- **`/health`에 Redis 확인은 아직 없음**: 지금은 DB만 확인합니다. 문서 생성(T094)이 붙을 때 Redis·워커 상태 확인을 추가할지 검토합니다.
- Celery Beat(매일 실행 예약)는 T172에서 일정과 함께 설정합니다.
- 실행 중인 8000번 API 서버는 이번 변경 후에도 정상 응답합니다(`/health` 200).
