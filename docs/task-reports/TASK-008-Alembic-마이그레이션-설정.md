# TASK-008. Alembic 마이그레이션 프레임워크 설정

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
데이터베이스 구조(표, 칸)를 바꾸는 작업을 기록하고 실행하는 도구 Alembic을 설정했습니다.

건물 리모델링 공사 일지와 같습니다. "1번 공사: 거실에 벽 세우기", "2번 공사: 창문 추가"처럼 변경 내역을 번호 순서대로 적어 두면, 새 건물(새 개발자의 DB)도 일지를 처음부터 따라 하기만 하면 똑같은 구조가 됩니다. 공사를 잘못했을 때는 "되돌리기"도 기록되어 있어 이전 상태로 돌아갈 수 있습니다. 이번 Task는 공사 일지 "공책"을 준비한 것이고, 첫 번째 공사(전체 테이블 생성)는 T009에서 적습니다.

| 명령 (backend/에서 실행) | 하는 일 |
|---|---|
| `alembic revision --rev-id 001 -m "initial schema"` | 새 변경 파일 `versions/001_initial_schema.py` 생성 |
| `alembic upgrade head` | 아직 적용 안 된 변경을 모두 DB에 적용 |
| `alembic downgrade -1` | 마지막 변경 되돌리기 |
| `alembic current` | 현재 DB가 몇 번 변경까지 적용됐는지 확인 |

## 변경 파일
- `backend/alembic.ini` (신규)
- `backend/alembic/env.py` (신규, 비동기 asyncpg 연결)
- `backend/alembic/script.py.mako` (Alembic 기본 템플릿)
- `backend/alembic/versions/.gitkeep`
- `backend/requirements.txt` (`python-dotenv` 명시 추가)
- `backend/tests/unit/test_alembic_setup.py`, `backend/tests/integration/test_alembic_migrations.py` (신규)
- `backend/tests/unit/test_lint_config.py` (린트 검사 범위에 `alembic/` 추가), `test_dependencies.py` (`dotenv` 추가)
- `.env` (신규, `.env.example` 복사본 — Git 제외 확인)

## TDD 결과
- RED: 설정 테스트 5개 + 실제 DB 통합 테스트 3개 작성 → 7개 실패 확인
- GREEN: `alembic init -t async` 후 설정 수정 → 8개 통과
- 수동 검증: 임시 변경 파일(000)로 생성 → `upgrade`(테이블 생성·버전 기록 확인) → `downgrade`(테이블 삭제·기록 삭제 확인) 전 과정 확인 후 삭제. 잘못된 DB 주소는 "비밀번호 인증 실패"로 정확히 거부됨
- REFACTOR: 린트 테스트가 `alembic/` 폴더도 검사하도록 확장, `python-dotenv`를 간접 설치가 아닌 직접 의존성으로 고정 → 전체 38개 통과
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 해당 없음 (`src/` 코드 변경 없음)

## 기술 결정
- **비동기 템플릿(asyncpg) 사용**: 백엔드 전체가 SQLAlchemy 비동기 + asyncpg로 동작하므로 마이그레이션도 같은 드라이버를 씁니다. 드라이버를 하나만 설치하면 됩니다.
- **DB 주소를 `alembic.ini`에 쓰지 않음**: constitution V(민감 정보 하드코딩 금지). `env.py`가 환경변수 `DATABASE_URL`을 먼저 보고, 없으면 루트 `.env`에서 읽습니다. 둘 다 없으면 해결 방법을 알려 주는 오류를 냅니다.
- **autogenerate 끔 (`target_metadata = None`)**: tasks.md T009가 "manual SQL, no autogenerate"를 지정했습니다. 모델 코드에서 자동 추정하지 않고 data-model.md의 스키마를 그대로 손으로 옮깁니다.
- **파일 이름 `{번호}_{설명}.py`**: 기본값은 무작위 해시+날짜라 순서를 알기 어렵습니다. T009가 지정한 `001_initial_schema.py` 형식에 맞췄습니다(`--rev-id`로 번호 지정).
- **새 변경 파일 생성 시 Black 자동 실행**: 생성된 파일이 바로 T006 린트 규칙을 통과합니다.
- **통합 테스트는 DB가 꺼져 있으면 자동 건너뜀**: Docker를 켜지 않은 환경에서도 나머지 테스트는 돌아갑니다.

## 비고
- `.env`는 `.env.example`을 복사한 것입니다. `GOOGLE_API_KEY`, JWT 비밀키 2개는 아직 `change-me` 상태이므로 T012·T091 전에 실제 값으로 바꿔야 합니다.
- 다음: T009에서 `alembic revision --rev-id 001 -m "initial schema"`로 data-model.md 전체 스키마를 작성합니다.
