# TASK-005. 환경 설정 템플릿 (.env.example)

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
프로그램이 필요로 하는 설정값(DB 주소, API 키, 비밀번호 등)의 "빈 양식"을 만들었습니다.

은행 창구에 비치된 "작성 예시" 서류와 같습니다. 예시 서류에는 어떤 칸을 채워야 하는지는 다 나와 있지만, 실제 계좌번호나 비밀번호는 적혀 있지 않습니다. 개발자는 이 양식을 복사해(`.env`) 자기 값을 채워 쓰고, 진짜 값이 담긴 `.env`는 절대 공유하지 않습니다.

| 파일 | 사용처 | 주요 항목 |
|---|---|---|
| `.env.example` (루트) | 백엔드, docker-compose | PostgreSQL, Redis, Gemini, JWT, CORS, 업로드 설정 |
| `frontend/.env.example` | React(Vite) | API 주소, 실행 환경 |

## 변경 파일
- `.env.example` (신규)
- `frontend/.env.example` (신규)
- `backend/tests/unit/test_env_example.py` (신규, 템플릿 검증 테스트)

## TDD 결과
- RED: 검증 테스트 7개 작성 → 파일이 없어 7개 모두 실패 확인
- GREEN: 두 템플릿 작성 → 전체 백엔드 테스트 21개 통과
- 추가 확인: `docker compose --env-file .env.example config`로 compose가 템플릿 값을 그대로 읽는 것 확인
- REFACTOR: 해당 없음
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 해당 없음 (실행 코드 없음)

테스트가 확인하는 것: 필요한 항목이 모두 있는지, 비밀값(API 키, JWT 비밀키)이 `change-me...` 자리표시자인지, DATABASE_URL이 POSTGRES_* 값과 일치하는지, 토큰 수명(15분/7일)과 Gemini 모델명이 문서와 같은지.

## 기술 결정
- **DATABASE_URL 호스트는 `localhost`, 드라이버는 `postgresql+asyncpg`**: 현재 백엔드는 Docker 밖(내 PC)에서 실행되므로 컨테이너 이름 `db` 대신 `localhost`로 접속합니다. SQLAlchemy 비동기 엔진은 `+asyncpg` 표기가 필요합니다. quickstart.md 예시(`postgresql://...@db:5432`)는 백엔드도 컨테이너로 띄울 때의 값입니다.
- **문서에 없던 항목 추가**: `GEMINI_MODEL`(research.md의 gemini-3-flash-preview), `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES=15`, `REFRESH_TOKEN_EXPIRE_DAYS=7`(research.md 인증 결정). 코드에 하드코딩하지 않고 설정으로 바꿀 수 있게 하기 위함입니다.
- **REDIS_URL 하나로 Celery 브로커 겸용**: constitution III(Redis = Celery 브로커 + 캐시)에 따라 별도 변수를 두지 않았습니다.
- **프론트엔드 템플릿 분리**: Vite는 `frontend/` 폴더의 `.env` 파일만 읽고, `VITE_`로 시작하는 값은 브라우저에 그대로 노출되므로 비밀값이 섞이지 않도록 따로 두었습니다.
- **`.env` 파일 자체는 만들지 않음**: 루트 `.gitignore`가 아직 없어(T007) 실수로 커밋될 위험이 있기 때문입니다. docker-compose는 `.env`가 없어도 같은 기본값으로 동작합니다.

## 비고
- 사용법: `cp .env.example .env` 후 `GOOGLE_API_KEY`와 JWT 비밀키 2개를 실제 값으로 교체 (`openssl rand -hex 32` 또는 `python -c "import secrets; print(secrets.token_hex(32))"`)
- T007에서 루트 `.gitignore`에 `.env`를 반드시 포함하고, `.env.example`은 제외 대상이 아니도록 해야 합니다.
- T011(DB 설정)·T012(JWT)는 이 항목 이름을 그대로 읽어야 합니다.
