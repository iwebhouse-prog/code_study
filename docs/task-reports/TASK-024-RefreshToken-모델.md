# TASK-024. RefreshToken 모델

## 상태
완료

## 날짜
2026-11-05

## 작업 요약
로그인 세션을 기록하는 `refresh_tokens` 표를 코드로 다루는 **RefreshToken 모델**을 만들고, User 모델과 서로 연결했습니다 (`backend/src/models/refresh_token.py`).

호텔에 비유하면 이 표는 **"발급한 객실 카드 대장"**입니다. 카드(리프레시 토큰) 자체가 아니라 카드의 지문(SHA-256 해시)만 적어 둡니다. 대장이 유출되어도 카드를 복제할 수 없습니다. 분실 신고가 들어오면 그 줄에 "폐기"를 표시하고(`revoked`), 줄을 지우지는 않습니다. 기기마다 카드가 따로 있어서 한 사람이 여러 줄을 가질 수 있습니다.

| 필드 | DB 타입 | 규칙 |
|---|---|---|
| `id` | UUID | 기본 키, DB가 자동 생성 |
| `user_id` | UUID | 필수, `users.id` 참조, 사용자 삭제 시 함께 삭제(CASCADE) |
| `token_hash` | VARCHAR(255) | 필수, 중복 불가 |
| `expires_at` | 시각(시간대 포함) | 필수 |
| `created_at` | 시각(시간대 포함) | DB가 자동 입력 |
| `revoked` | BOOLEAN | 기본값 `false` |
| `revoked_at` | 시각(시간대 포함) | 선택 |

연결: `token.user`(토큰의 주인), `user.refresh_tokens`(사용자의 토큰 목록).

## 변경 파일
- `backend/src/models/refresh_token.py` (신규)
- `backend/src/models/user.py` — `refresh_tokens` 관계 추가
- `backend/src/models/__init__.py` — 두 모델을 함께 등록
- `backend/tests/unit/test_refresh_token_model.py` (신규, 14개), `backend/tests/integration/test_refresh_token_model.py` (신규, 7개)
- `backend/tests/integration/db_utils.py` — 모델·DB 비교 헬퍼 `schema_differences()` 추가
- `backend/tests/integration/test_user_model.py` — 위 헬퍼를 쓰도록 변경
- `backend/pyproject.toml` — 테스트 폴더에서만 ruff `S107` 제외
- `specs/001-ai-code-learning-platform/tasks.md` — T024 완료 표시

## TDD 결과
- RED: 단위·통합 테스트 작성 → `src.models.refresh_token` 모듈이 없어 실패 확인
- GREEN: 모델과 관계 작성 → 21개 통과
- REFACTOR: T023의 비교 테스트 3개를 공용 헬퍼 `schema_differences()` 하나로 통합 (남은 모델 8개에서도 재사용)
- 최종: 백엔드 테스트 257개 통과(DB·Redis 통합 테스트 포함, 건너뜀 0), `src` 줄·분기 커버리지 **100%**, ruff·black·mypy strict 통과
- 실제 DB 확인: 마이그레이션 표와 일치, 저장 후 기본값 읽기, 폐기해도 행 유지, 중복 해시 거부, 없는 사용자 거부, 한 사용자의 여러 세션, 사용자 삭제 시 토큰 삭제
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **`device_info` 컬럼 없음 (명세 간 차이)**: requirements-addendum에는 `device_info`가 있지만 T009 마이그레이션과 data-model.md에는 없습니다. 이 Task의 조건이 "T009 스키마와 일치"이므로 넣지 않았습니다. 이 값을 쓰는 세션 목록 화면은 부록에서도 Phase 2 범위입니다. 그때 마이그레이션을 새로 추가하면 됩니다.
- **`TimestampMixin`을 쓰지 않음**: 표에 `updated_at`이 없어서 `created_at`만 직접 선언했습니다.
- **`revoked`, `created_at`은 모델이 DB보다 엄격함**: 마이그레이션에서는 NULL 허용이지만 기본값이 항상 채워집니다. `if token.revoked`를 `None` 걱정 없이 쓸 수 있도록 NULL이 아닌 값으로 선언했습니다(T023의 `created_at`과 같은 판단). 비교 테스트에 두 컬럼만 예외로 적었습니다.
- **관계는 `lazy="raise"`**: 비동기 세션은 지연 로딩이 안 됩니다. 불러오지 않은 관계를 읽으면 알아보기 어려운 `MissingGreenlet` 대신 명확한 오류가 납니다. 읽으려면 `selectinload(User.refresh_tokens)`를 씁니다.
- **사용자 삭제는 DB의 CASCADE에 맡김(`passive_deletes=True`)**: 토큰을 한 줄씩 불러와 지우지 않습니다.
- **`src/models/__init__.py`에서 모델을 함께 불러옴**: 두 모델이 서로를 이름으로 참조하므로, 어느 쪽을 먼저 불러와도 둘 다 등록되어야 합니다. 새 모델을 만들면 여기에 추가해야 합니다.

## 비고
- 토큰 해시 계산(SHA-256), 교체(rotate), 폐기, 재사용 감지는 **T026 TokenService** 범위입니다. 모델은 데이터 구조만 정의합니다.
- 만료된 토큰을 정리하는 작업은 아직 없습니다. 표가 계속 커지므로 예약 작업이 필요한지 T026 이후 검토합니다.
- `revoked`와 `revoked_at`은 항상 같이 설정해야 합니다. 모델이 강제하지 않으므로 T026에서 폐기 처리를 한 함수로 묶어야 합니다.
