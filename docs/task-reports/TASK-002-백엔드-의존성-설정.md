# TASK-002. 백엔드 파이썬 프로젝트 의존성 설정

## 상태
완료

## 날짜
2026-10-27

## 작업 요약
백엔드가 사용할 외부 라이브러리 목록 `backend/requirements.txt`를 만들고, 가상환경(`backend/venv`)에 설치해 실제로 동작하는지 확인했습니다.

요리를 시작하기 전에 장보기 목록을 쓰는 것과 같습니다. 목록에 "우유"라고만 쓰면 사람마다 다른 우유를 사 오듯, 버전을 적지 않으면 컴퓨터마다 다른 버전이 설치됩니다. 그래서 모든 항목에 `==버전`을 붙여 누가 설치해도 똑같은 재료가 준비되도록 했습니다. 가상환경은 "이 프로젝트 전용 냉장고"로, 다른 프로젝트의 재료와 섞이지 않게 해 줍니다.

| 분류 | 라이브러리 |
|---|---|
| 웹 서버 | fastapi, uvicorn, python-multipart(파일 업로드) |
| 데이터베이스 | sqlalchemy, asyncpg, alembic, pydantic |
| 인증 | PyJWT(로그인 토큰), bcrypt(비밀번호 암호화) |
| AI | google-genai(Gemini), httpx |
| 비동기 작업 | celery, redis |
| 코드 분석 | pygments(언어 감지) |
| 테스트 | pytest, pytest-asyncio, pytest-cov |

## 변경 파일
- `backend/requirements.txt` (신규)
- `backend/tests/unit/test_dependencies.py` (신규, 의존성 검증 테스트)
- `backend/venv/` (가상환경, Git 제외 대상)
- `specs/001-ai-code-learning-platform/quickstart.md` (requirements 예시를 실제 파일과 일치시킴)

## TDD 결과
- RED: 테스트 4개 작성 → requirements.txt 없음, 모듈 없음으로 4개 모두 실패 확인
- GREEN: requirements.txt 작성 및 설치 → 전체 9개 테스트 통과 (TASK-001 구조 테스트 포함), `pip check` 충돌 없음
- REFACTOR: 사용 중단 예고된 `multipart` 대신 `python_multipart`를 import하도록 테스트 수정 → 경고 0건, 9개 통과
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 해당 없음 (실행 코드 없음)

## 기술 결정
quickstart.md의 원래 목록(2023년 버전)을 그대로 쓰지 않고 다음을 바꿨습니다.

- **google-generativeai → google-genai**: 예전 SDK는 지원이 종료되었고, plan.md가 지정한 Gemini 3 Flash Preview는 새 SDK로 호출합니다.
- **passlib → bcrypt 직접 사용**: passlib은 더 이상 관리되지 않으며 최신 bcrypt와 함께 쓰면 오류가 납니다. research.md의 결정(bcrypt, cost 12)은 그대로 지킵니다.
- **python-jose → PyJWT**: python-jose 3.3.0에는 알려진 보안 취약점이 있고, FastAPI 공식 문서도 PyJWT를 사용합니다.
- **나머지는 최신 버전으로 고정**: 2023년 버전 중 일부(python-multipart 0.0.6 등)에 보안 취약점이 알려져 있어, 설치 시점의 최신 버전을 함께 검증한 뒤 고정했습니다.
- Ruff/Black/MyPy는 T006(린팅 설정)에서, 이메일 검증·설정 관리 라이브러리는 필요해지는 Task에서 추가합니다.

## 비고
- 설치: `cd backend; python -m venv venv; venv\Scripts\activate; pip install -r requirements.txt`
- VS Code가 전역 Python을 가리키면 requirements.txt에 "not installed" 힌트가 뜹니다. 인터프리터를 `backend/venv`로 선택하면 사라집니다.
- T012(JWT), T013(비밀번호 해싱)은 위 결정에 따라 PyJWT와 bcrypt로 구현해야 합니다.
