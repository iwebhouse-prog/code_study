# TASK-010. 데이터베이스 연결 및 세션 관리

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
백엔드 코드가 데이터베이스와 대화할 때 쓰는 "연결 관리자"를 만들었습니다 (`backend/src/db/session.py`).

은행 창구에 비유하면 이렇습니다. 손님(요청)이 올 때마다 창구 직원을 새로 뽑으면 너무 느리니, 직원 몇 명(연결 풀)을 미리 대기시켜 둡니다. 손님 한 명이 오면 직원 한 명이 맡아 업무를 처리하고(세션), 업무가 끝나면 다음 손님을 위해 자리로 돌아갑니다. 처리 도중 문제가 생기면 지금까지 적던 서류는 전부 파쇄(롤백)해서 장부가 반쯤 고쳐진 채로 남지 않게 합니다. 또 직원이 졸고 있지 않은지(연결이 끊기지 않았는지) 업무 시작 전에 한 번 확인합니다.

| 구성 요소 | 하는 일 |
|---|---|
| `Database(url, **옵션)` | 연결 풀(엔진)과 세션 공장 생성 |
| `Database.session()` | 세션 하나 빌려주기 → 오류 시 롤백 → 항상 반납 |
| `init_database()` / `close_database()` | 서버 시작·종료 시 한 번 호출 (T014에서 연결) |
| `get_database()` | 초기화된 DB 가져오기 (초기화 전이면 명확한 오류) |
| `get_db_session()` | FastAPI 의존성: `db: AsyncSession = Depends(get_db_session)` |

## 변경 파일
- `backend/src/db/session.py` (신규)
- `backend/tests/unit/test_db_session.py` (신규, 11개 테스트 — DB 없이 동작 확인)
- `backend/tests/integration/test_db_session.py` (신규, 5개 테스트 — 실제 PostgreSQL)

## TDD 결과
- RED: 테스트 16개 작성 → `src.db.session` 모듈이 없어 실패 확인
- GREEN: `session.py` 작성 → 16개 통과
- REFACTOR: 해당 없음 (최소 구현이 이미 단순)
- 최종: 백엔드 테스트 80개 통과, `src` 커버리지 **100%**, ruff·black·mypy strict 통과
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다

실제 DB 테스트가 확인하는 것: 쿼리 실행, commit한 데이터는 남음, 도중에 오류 나면 commit 안 한 데이터는 사라짐, 사용 후 연결이 풀로 반납됨, 잘못된 SQL 실패 후에도 다음 요청이 정상 동작.

## 기술 결정
- **commit은 서비스가 결정, 세션 관리자는 롤백·반납만 보장**: requirements-addendum CHK108(트랜잭션 롤백)의 예시처럼 서비스 코드가 `async with db.begin()` / `commit()`으로 범위를 정합니다. 세션 관리자가 자동 commit까지 하면 "어디까지가 한 묶음인지"가 코드에서 보이지 않게 됩니다.
- **`expire_on_commit=False`**: 비동기 SQLAlchemy는 commit 후 만료된 값을 자동으로 다시 불러오지 못해 오류가 납니다. commit 후에도 객체 값을 그대로 쓸 수 있게 했습니다.
- **`pool_pre_ping=True`**: CHK105 "연결을 꺼낼 때 `SELECT 1`로 확인, 끊긴 연결 재사용 방지"를 그대로 반영했습니다.
- **풀 크기·타임아웃 값은 T011 범위**: CHK105의 min 10 / max 50, 연결 대기 30초, 유휴 5분 재활용, 쿼리 30초 제한은 T011(`db/config.py`)에서 설정 파일로 만들어 `init_database(url, **옵션)`에 넘기도록 비워 두었습니다.
- **테스트 DB 분리**: 통합 테스트는 TASK-009와 같은 임시 DB `codelearning_test`를 사용합니다.

## 비고
- CHK105의 "연결 실패 시 3회 재시도 → HTTP 503" 처리는 이 파일이 아닌 T011(재시도 설정) / T016(오류 응답)에서 다룹니다.
- 다음: T011에서 `.env`의 `DATABASE_URL`과 풀 설정을 읽어 `init_database()`에 전달하는 설정 모듈을 만듭니다.
