# TASK-023. User 모델

## 상태
완료

## 날짜
2026-11-05

## 작업 요약
DB의 `users` 표를 파이썬 코드로 다룰 수 있게 해 주는 **User 모델**을 만들었습니다 (`backend/src/models/user.py`).

표는 T009 마이그레이션이 이미 만들어 두었고, 모델은 그 표의 "파이썬 쪽 설계도"입니다. 이제 서비스 코드(T025)가 SQL을 직접 쓰지 않고 `User(email=..., password_hash=...)`, `user.last_login_at = ...`처럼 다룰 수 있습니다.

| 필드 | 형식 | 규칙 |
|---|---|---|
| `id` | UUID | DB가 자동 생성 |
| `email` | 문자열 255 | 필수, 중복 불가, 이메일 형식 검사(`valid_email`) |
| `password_hash` | 문자열 255 | 필수 (T013 bcrypt 해시) |
| `skill_level` | 문자열 50 | 기본값 `Complete Beginner` |
| `created_at`, `updated_at` | 시각(시간대 포함) | DB가 자동 입력, 수정 시 `updated_at` 갱신 |
| `last_login_at` | 시각(시간대 포함) | 선택 |

`repr(user)`에는 id와 이메일만 나옵니다. 로그에 비밀번호 해시가 찍히지 않게 하기 위해서입니다(data-model.md).

## 변경 파일
- `backend/src/models/user.py` (신규)
- `backend/src/models/base.py` — `TimestampMixin`에 `eager_defaults` 추가 (아래 기술 결정 참고)
- `backend/tests/unit/test_user_model.py` (신규, 10개), `backend/tests/integration/test_user_model.py` (신규, 8개)
- `backend/tests/unit/test_models_base.py` — `eager_defaults` 테스트 추가
- `backend/pyproject.toml` — 테스트 폴더에서만 ruff `S106` 제외 (T013의 `S105`와 같은 이유)
- `specs/001-ai-code-learning-platform/tasks.md` — T023 완료 표시

## TDD 결과
- RED: 단위·통합 테스트 작성 → `src.models.user` 모듈이 없어 실패 확인
- GREEN: `user.py` 작성 → 2개 실패
  - `MissingGreenlet`: 수정 후 `updated_at`을 읽으면 오류 (**실제 버그** → `TimestampMixin`에서 수정)
  - `KeyError: 'CHAR'`: 테스트가 타입을 기본 표기로 비교한 문제 → PostgreSQL 표기로 비교하도록 테스트 수정
- REFACTOR: 구조 변경 없음 (ruff `S106` 설정만 추가)
- 최종: 백엔드 테스트 238개 통과(DB·Redis 통합 테스트 포함, 건너뜀 0), `src` 줄·분기 커버리지 **100%**, ruff·black·mypy strict 통과
- 실제 DB 확인: Alembic으로 만든 표와 컬럼 이름·형식·길이·NULL 허용 여부를 비교. 저장 후 기본값 읽기, 이메일 조회, 중복 이메일 거부, 잘못된 이메일 거부(`valid_email`)
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **`TimestampMixin`에 `eager_defaults=True` (T009 코드 수정)**: `updated_at`은 저장할 때 DB가 정하는 값이라, SQLAlchemy는 저장 뒤 이 값을 비워 두고 나중에 읽을 때 가져오려 합니다. 비동기 세션에서는 이 "나중에 가져오기"가 금지라 `MissingGreenlet` 오류가 납니다. UPDATE와 함께 값을 받아 오도록 설정했습니다. 공통 믹스인에서 고쳤으므로 앞으로 만들 시간 컬럼 모델도 모두 안전합니다. 이대로 두었다면 `last_login_at`을 갱신하는 로그인(T025)에서 오류가 났을 것입니다.
- **`created_at`, `updated_at`은 모델이 DB보다 엄격함 (T009와의 차이)**: 마이그레이션에서는 이 두 컬럼이 NULL 허용이지만, 항상 기본값으로 채워지므로 모델은 NULL이 아닌 값으로 선언합니다(T009의 믹스인 그대로). 코드에서 `None` 검사를 하지 않아도 됩니다. 통합 테스트에 이 두 컬럼만 예외로 명시했습니다. 나머지 컬럼은 모두 일치합니다.
- **`skill_level`은 NULL 허용으로 선언**: 마이그레이션과 맞췄습니다. 기본값이 있어 실제로 비는 일은 없습니다.
- **`projects`, `refresh_tokens` 관계는 넣지 않음**: 상대 모델이 아직 없어서 넣으면 앱이 시작되지 않습니다. T024, T043에서 추가합니다.
- **Alembic `target_metadata`는 그대로 `None`**: 이 프로젝트의 마이그레이션은 수동 SQL입니다(T009 Task 정의).

## 비고
- **이메일 대소문자**: DB의 중복 검사는 대소문자를 구분해서 `A@x.com`과 `a@x.com`을 다른 계정으로 봅니다. T025 회원가입에서 소문자로 통일해야 합니다.
- **`updated_at`은 ORM을 거친 수정에서만 갱신됩니다**: DB 트리거가 없어서, 직접 쓴 SQL UPDATE로는 바뀌지 않습니다.
- 작업 시작 시 Docker Desktop이 꺼져 있어 실행하고 `docker compose up -d`로 DB·Redis를 올렸습니다.
