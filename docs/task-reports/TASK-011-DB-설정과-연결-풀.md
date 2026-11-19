# TASK-011. 데이터베이스 설정과 연결 풀

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
`.env`에 적힌 DB 주소와 연결 풀 설정을 읽어서, TASK-010의 연결 관리자(`Database`)를 만들어 주는 설정 모듈을 만들었습니다 (`backend/src/db/config.py`).

TASK-010이 "은행 창구 직원(연결)을 관리하는 방법"이었다면, 이번 작업은 **"직원을 몇 명 둘지, 손님을 얼마나 기다리게 할지"를 정하는 운영 규칙표**입니다. 평소에는 직원 10명, 바쁠 때는 최대 50명까지 늘리고, 빈 창구가 없으면 손님은 30초까지 기다립니다. 5분 넘게 한가한 직원은 교대시키고(오래된 연결 교체), 한 업무가 30초 넘게 걸리면 중단합니다. 또 은행 문을 열 때 금고(DB)가 응답하지 않으면 5초 간격으로 세 번까지 다시 확인한 뒤, 그래도 안 되면 "영업 불가"를 알립니다.

| 설정 (`.env`) | 기본값 | 의미 (requirements-addendum CHK105) |
|---|---|---|
| `DATABASE_URL` | (필수) | `postgresql+asyncpg://`로 시작해야 함 |
| `DB_POOL_SIZE` | 10 | 평소 유지하는 연결 수 |
| `DB_MAX_OVERFLOW` | 40 | 바쁠 때 추가 연결 (합계 최대 50) |
| `DB_POOL_TIMEOUT` | 30초 | 빈 연결을 기다리는 최대 시간 |
| `DB_POOL_RECYCLE` | 300초 | 오래된 연결 교체 주기 |
| `DB_COMMAND_TIMEOUT` | 30초 | 쿼리 하나의 최대 실행 시간 |
| (고정) | 3회 × 5초 | 시작 시 DB 연결 재시도 |

주요 함수:
- `DatabaseConfig.from_env()` — 환경변수 → `.env` 순서로 읽고 값 검증
- `connect_database(config)` — 연결 풀 생성 + DB 응답 확인(재시도) → 실패 시 `DatabaseUnavailableError` (T014에서 서버 시작 시 호출, T016에서 503 응답으로 변환 예정)

## 변경 파일
- `backend/src/db/config.py` (신규)
- `backend/src/db/session.py` (`Database.ping()` 추가)
- `backend/alembic/env.py` (DB 주소 읽기를 `DatabaseConfig`로 통일 — 중복 코드 제거)
- `.env.example`, `.env` (`DB_*` 풀 설정 5개 추가. `.env`의 기존 값은 그대로 유지)
- `backend/tests/unit/test_db_config.py` (신규, 13개), `backend/tests/integration/test_db_config.py` (신규, 3개)

## TDD 결과
- RED: 테스트 16개 작성 → `src.db.config` 모듈이 없어 실패 확인
- GREEN: `config.py`, `Database.ping()` 작성 → 16개 통과
- REFACTOR:
  - Python 3.12 전용 문법(`def f[T]`)을 썼던 것을 프로젝트 기준(3.11+)에 맞게 `TypeVar`로 변경
  - `alembic/env.py`의 DB 주소 읽기 코드를 `DatabaseConfig.from_env()`로 교체 → 같은 규칙을 한 곳에서 관리
- 최종: 백엔드 테스트 96개 통과(건너뜀 0), `src` 커버리지 **100%**, ruff·black·mypy strict 통과, `alembic current` 정상
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다

실제 DB 테스트가 확인하는 것: 설정대로 연결·등록됨, `ping()` 성공, `command_timeout=0.5초`일 때 3초짜리 쿼리(`pg_sleep(3)`)가 중간에 끊김.

## 기술 결정
- **pydantic-settings 대신 dataclass + python-dotenv**: 필요한 값이 6개뿐이라 새 라이브러리 없이 처리했습니다. 설정이 늘어나는 T012(JWT) 이후 필요하면 그때 도입을 검토합니다.
- **CHK105의 "min 10 / max 50"을 `pool_size=10`, `max_overflow=40`으로 해석**: SQLAlchemy 풀은 "기본 개수 + 추가 허용 개수" 방식이라 합계가 50이 되도록 했습니다(테스트로 확인).
- **쿼리 제한 시간은 asyncpg `command_timeout`**: DB 서버 설정을 바꾸지 않고 앱 쪽에서 모든 쿼리에 30초 제한을 겁니다.
- **재시도 대기 함수 주입(`sleep=`)**: 테스트에서 실제로 5초씩 기다리지 않고도 "3번 시도, 2번 대기, 실패 시 풀 정리"를 확인합니다.
- **sync 드라이버 URL 거부**: `postgresql://`(동기)로 적으면 실행 중 알 수 없는 오류가 나므로, 시작할 때 바로 알려 줍니다.

## 비고
- 작업 중 Docker Desktop이 꺼져 있어(PC 재시작 후 미실행) 통합 테스트가 건너뛰어졌습니다. Docker Desktop을 실행하고 `docker compose up -d`로 DB·Redis를 다시 올린 뒤 전체 테스트를 재실행해 통과를 확인했습니다. Docker Desktop 설정에서 "Start Docker Desktop when you sign in"을 켜 두면 편합니다.
- 잘못된 비밀번호처럼 재시도해도 소용없는 오류도 현재는 3회 재시도합니다(최대 10초 지연). 운영상 문제가 되면 오류 종류별로 구분하도록 개선할 수 있습니다.
