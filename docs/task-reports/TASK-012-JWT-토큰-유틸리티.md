# TASK-012. JWT 토큰 유틸리티

## 상태
완료

## 날짜
2026-10-30

## 작업 요약
로그인한 사용자에게 줄 **출입증(JWT 토큰)을 만들고, 받은 출입증이 진짜인지 확인하는 도구**를 만들었습니다 (`backend/src/utils/jwt.py`).

놀이공원에 비유하면 토큰은 두 종류입니다.
- **액세스 토큰 = 하루 입장권(15분)**: 놀이기구(API)를 탈 때마다 보여 주는 표. 짧게 유효해서 잃어버려도 피해가 작습니다.
- **리프레시 토큰 = 재발급 쿠폰(7일)**: 입장권이 만료되면 새 입장권으로 바꿀 때만 쓰는 쿠폰.

두 표는 **서로 다른 도장(비밀키)**으로 찍고, 표에 "입장권/쿠폰" 종류도 적어 둡니다. 그래서 쿠폰을 입장권처럼 내밀어도 통하지 않습니다.

| 함수 | 하는 일 |
|---|---|
| `JWTConfig.from_env()` | `.env`에서 비밀키·알고리즘·유효 시간을 읽고 검증 |
| `create_access_token(user_id, config)` | 15분짜리 액세스 토큰 발급 |
| `create_refresh_token(user_id, config)` | 7일짜리 리프레시 토큰 발급 |
| `decode_token(token, "access"/"refresh", config)` | 서명·만료·종류를 확인하고 내용(`TokenPayload`) 반환 |

토큰 안에 들어가는 정보: `sub`(사용자 ID), `type`(access/refresh), `jti`(토큰 고유번호), `iat`(발급 시각), `exp`(만료 시각).

오류는 두 가지입니다.
- `TokenExpiredError`: 만료됨 → 프론트가 리프레시를 시도하면 됨 (T038)
- `InvalidTokenError`: 위조·손상·종류 불일치 등 (만료 오류도 이것의 한 종류라, "쓸 수 있나?"만 궁금하면 이것 하나만 잡으면 됨)

## 변경 파일
- `backend/src/utils/jwt.py` (신규)
- `backend/tests/unit/test_jwt.py` (신규, 테스트 25개 + 세부 케이스 12개)
- `.env` — `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET`의 예시 값(`change-me-...`)을 무작위 64자리 키로 교체 (다른 줄은 그대로)
- `specs/001-ai-code-learning-platform/tasks.md` — T012 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src.utils.jwt` 모듈이 없어 실패 확인
- GREEN: `jwt.py` 작성 → HS512 + 32자 키 조합에서 PyJWT의 "키가 너무 짧다" 경고 발견 → 알고리즘별 최소 키 길이로 수정 후 전체 통과
- REFACTOR: ruff 보안 규칙(S105)의 오탐을 피하도록 비교문을 사전 조회로 변경, black 포맷 적용, `.env` 읽기 경로 테스트 추가
- 최종: 백엔드 테스트 121개 통과, `src` 커버리지 **100%**, ruff·black·mypy strict 통과
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **알고리즘을 서버 설정으로 고정**: 토큰 머리글에 적힌 알고리즘을 믿지 않고 `.env`의 값(HS256)만 허용합니다. 서명 없는 `none` 토큰이나 다른 알고리즘으로 만든 토큰은 거부됩니다(테스트로 확인).
- **HMAC 계열(HS256/384/512)만 허용**: 비밀키 하나로 서명하는 방식이라 RS256 같은 공개키 방식 설정은 시작 시 거부합니다.
- **알고리즘별 최소 키 길이**: HS256=32자, HS384=48자, HS512=64자 (RFC 7518 3.2).
- **잘못된 키는 서버 시작 시 바로 거부**: 비어 있음, `.env.example`의 `change-me` 그대로, 너무 짧음, 두 키가 같음 → 모두 해결 방법(`openssl rand -hex 32`)과 함께 오류.
- **`jti`(토큰 고유번호) 포함**: 같은 사람이 같은 초에 두 번 로그인해도 토큰이 달라져, `refresh_tokens.token_hash`의 UNIQUE 제약과 충돌하지 않습니다.
- **사용자 ID는 UUID로 검사**: `sub`가 UUID가 아니면 거부해, T026에서 바로 DB 조회에 쓸 수 있습니다.
- **T011과 같은 설정 방식(dataclass + python-dotenv)**: 숫자 검사 함수는 DB 설정 모듈에서 빌려오지 않고 따로 두었습니다(JWT 도구가 DB 모듈에 의존하지 않도록). 설정이 더 늘어나는 T014에서 공통 설정으로 합칠지 검토합니다.

## 비고
- 리프레시 토큰을 DB에 저장할 때의 SHA-256 해시, 토큰 교체(rotate), 폐기(revoke)는 **T026 TokenService** 범위라 이번에 넣지 않았습니다.
- HTTPOnly 쿠키에 담는 작업은 인증 API(T027 이후)에서 합니다.
- `.env`의 비밀키를 바꿨으므로, 다른 PC에서 작업하면 그 PC의 `.env`에도 `openssl rand -hex 32`로 만든 키를 넣어야 합니다.
