# TASK-009. 기본 모델 클래스와 초기 DB 스키마 마이그레이션

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
서비스의 모든 데이터를 담을 10개 테이블을 데이터베이스에 만들고, 앞으로 만들 모델 코드가 공통으로 쓸 "기본 틀"을 준비했습니다.

도서관에 비유하면 이번 작업은 **책장 10개를 설치하고 각 칸에 규칙표를 붙인 것**입니다. "이 칸에는 이메일 형식만", "과제 제목은 5글자 이상", "업로드는 10MB까지" 같은 규칙을 책장 자체에 새겨 두었기 때문에, 프로그램 코드에 실수가 있어도 잘못된 데이터는 아예 꽂히지 않습니다. 또 "회원 카드를 폐기하면 그 회원의 프로젝트·과제·진도 기록도 함께 정리"되도록 연결해 두었습니다.

**1) 기본 모델 클래스** (`backend/src/models/base.py`)

| 이름 | 역할 |
|---|---|
| `Base` | 모든 모델의 부모. 날짜는 시간대 포함, ID는 UUID로 자동 매핑 |
| `UUIDPrimaryKeyMixin` | `id` (DB가 `gen_random_uuid()`로 생성) |
| `TimestampMixin` | `created_at`, `updated_at` (수정 시 자동 갱신) |
| `SoftDeleteMixin` | `deletion_status`(기본 'active'), `trashed_at`, `scheduled_deletion_at` (휴지통 30일 보관) |

**2) 초기 마이그레이션** (`backend/alembic/versions/001_initial_schema.py`)
users, projects, tasks, uploaded_code, code_files, learning_documents, practice_problems, questions, progress, refresh_tokens — 테이블 10개, 인덱스 24개, CHECK·UNIQUE·FK 제약을 data-model.md의 SQL 그대로 작성했습니다.

## 변경 파일
- `backend/src/models/base.py` (신규)
- `backend/alembic/versions/001_initial_schema.py` (신규)
- `backend/tests/unit/test_models_base.py` (신규, 8개 테스트)
- `backend/tests/integration/test_initial_schema.py`, `schema_expectations.py`, `db_utils.py` (신규, 18개 테스트)
- `.env.example`, `.env`: DB·Redis 주소 `localhost` → `127.0.0.1`
- `backend/tests/unit/test_env_example.py`, `tests/integration/test_alembic_migrations.py`: 위 주소 변경 반영

## TDD 결과
- RED: 단위 테스트(모듈 없음으로 실패) + 통합 테스트 18개 실패 확인
- GREEN: `base.py`, `001_initial_schema.py` 작성 → 전부 통과
- REFACTOR:
  - 테스트 실행이 108초로 느려 원인을 측정 → Windows에서 `localhost`는 IPv6를 먼저 시도해 **연결마다 2초 지연**(127.0.0.1은 0.01초). 테스트 기대값을 먼저 바꾼 뒤(RED) 설정을 `127.0.0.1`로 변경 → 전체 9초
  - 린트(S608)가 테스트의 f-string SQL 조합을 지적 → 고정값 문자열로 재작성
  - 테스트 파일이 254줄로 constitution 한도(250줄) 초과 → 기대값 목록을 별도 파일로 분리(215줄)
- 최종: 백엔드 테스트 64개 통과, `src` 커버리지 **100%**, ruff·black·mypy strict 통과
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다

통합 테스트가 실제 DB에서 확인하는 것: 테이블 10개·인덱스 24개 존재, 부분 인덱스(active 전용), 기본값(skill_level, deletion_status, generation_status), 잘못된 이메일·중복 이메일·짧은 과제 제목·중복 과제 번호·10MB 초과·지원 안 하는 확장자·7챕터 미만 문서·6번 연습문제·3자 미만 질문·8개 챕터 진도 거부, 회원 삭제 시 연쇄 삭제, downgrade 후 재-upgrade.

## 기술 결정
- **수동 SQL 마이그레이션**: tasks.md 지시(no autogenerate)에 따라 data-model.md의 SQL을 그대로 옮겼습니다. 문서와 DB가 한 글자 단위로 대응해 검토가 쉽습니다.
- **통합 테스트 전용 DB `codelearning_test`**: 매 테스트 클래스마다 새로 만들고 끝나면 삭제합니다. 개발용 DB(`codelearning`)의 데이터를 건드리지 않습니다.
- **`updated_at` 자동 갱신은 ORM에서**: data-model.md에는 DB 트리거가 없어, SQLAlchemy `onupdate`로 처리합니다. ORM을 거치지 않는 직접 SQL 수정은 갱신되지 않습니다.
- **모델 클래스(User 등)는 만들지 않음**: T023 이후 Task 범위입니다. 각 모델은 이 마이그레이션 스키마와 일치해야 합니다.

## 비고 — ⚠️ 스펙 확인이 필요한 사항
1. **learning_documents 생성 순서 충돌**: `content`가 `NOT NULL`이고 7개 챕터를 모두 요구하므로, "생성 대기(pending)" 상태의 문서 행을 **내용 없이 먼저 만들 수 없습니다**(테스트로 확인). 그런데 T095(생성 대기열·상태 추적)는 생성 전에 상태 행이 필요해 보입니다. T094 전에 ① `content`를 NULL 허용 + "completed일 때만 7챕터 필수"로 바꾸는 002 마이그레이션, 또는 ② 상태 추적을 다른 곳(Celery 결과)에 두는 방식 중 결정이 필요합니다.
2. **이메일 정규식의 `[A-Z|a-z]`**: 원문 그대로 옮겼으나 `|` 문자도 허용하는 오타로 보입니다. 실제 영향은 거의 없어 수정하지 않았습니다.
3. **requirements-addendum.md의 `ai_generation_metrics` 테이블**: data-model.md에는 정의가 없어 이번 스키마에 포함하지 않았습니다. 필요 시 별도 마이그레이션으로 추가합니다.
4. 개발용 DB `codelearning`은 현재 001까지 적용된 상태입니다.
