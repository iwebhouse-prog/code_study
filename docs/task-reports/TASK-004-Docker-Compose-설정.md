# TASK-004. Docker Compose 설정 (PostgreSQL, Redis)

## 상태
완료 (2026-10-29 실제 컨테이너 실행·연결 확인 완료)

## 날짜
2026-10-29

## 작업 요약
개발에 필요한 데이터베이스(PostgreSQL)와 작업 대기열(Redis)을 명령어 한 줄로 켤 수 있도록 루트에 `docker-compose.yml`을 만들었습니다.

Docker는 "조립식 컨테이너 창고"와 같습니다. PostgreSQL이나 Redis를 컴퓨터에 직접 설치하면 버전이 사람마다 다르고 지우기도 번거롭습니다. 대신 미리 포장된 컨테이너를 내려받아 켜고 끄기만 하면, 팀원 모두가 똑같은 환경에서 일할 수 있습니다.

| 서비스 | 이미지 | 포트 | 역할 |
|---|---|---|---|
| `db` | postgres:17-alpine | 5432 | 사용자·프로젝트·문서 데이터 저장 |
| `redis` | redis:7-alpine | 6379 | Celery 작업 대기열 |

## 변경 파일
- `docker-compose.yml` (신규)
- `backend/tests/unit/test_docker_compose.py` (신규, 설정 검증 테스트)

## TDD 결과
- RED: 설정 검증 테스트 5개 작성 → 파일이 없어 5개 모두 실패 확인
- GREEN: `docker-compose.yml` 작성 → 전체 백엔드 테스트 14개 통과
- REFACTOR: 해당 없음
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 해당 없음 (실행 코드 없음)

## 기술 결정
- **서비스 이름 `db`, `redis`**: quickstart.md의 `DATABASE_URL=...@db:5432`, `REDIS_URL=redis://redis:6379`와 맞췄습니다.
- **PostgreSQL 17**: 요구사항(15 이상)을 만족합니다. 18은 데이터 저장 경로가 바뀌어 볼륨 설정이 달라지므로 17로 정했습니다.
- **비밀번호 등은 `.env`에서 읽기**: constitution V(민감 정보 하드코딩 금지)를 따릅니다. `.env`가 없을 때를 위해 quickstart와 같은 개발용 기본값(postgres/postgres/codelearning)을 두었습니다. `.env.example`은 T005에서 만듭니다.
- **포트를 `127.0.0.1`에만 열기**: 같은 와이파이의 다른 기기가 개발용 DB에 접속하지 못하게 막습니다.
- **헬스체크 추가**: 이후 백엔드 컨테이너를 붙일 때 "DB가 준비된 뒤에 시작"하도록 만들 수 있습니다.
- **볼륨(`postgres_data`, `redis_data`)**: 컨테이너를 껐다 켜도 데이터가 남습니다. Redis 영속성 세부 설정은 T213에서 합니다.
- **Dockerfile이 없으므로 `.dockerignore`는 만들지 않았습니다.**

## 비고
- **실행 확인 (Docker Desktop 4.97.0 / Engine 29.9.2)**: `docker compose up -d` 후 두 서비스 모두 `healthy`.
  - PostgreSQL 17.11: `pg_isready` → accepting connections, 호스트에서 asyncpg로 `codelearning` DB 접속 성공
  - Redis 7.4.12: `redis-cli ping` → PONG, 호스트에서 redis-py로 set/get/delete 성공
- 이 PC의 Git Bash/VS Code 터미널은 Docker 설치 전에 열려 `docker`가 PATH에 없을 수 있습니다. 터미널을 새로 열면 해결됩니다.
- quickstart.md는 compose가 백엔드·프론트엔드·Celery까지 띄운다고 설명하지만, T004 범위는 PostgreSQL과 Redis뿐입니다. 나머지는 해당 서비스가 준비된 뒤 추가하고 문서도 T189에서 맞추는 것을 권장합니다.
- 테스트가 쓰는 PyYAML은 `uvicorn[standard]`를 통해 설치됩니다.
