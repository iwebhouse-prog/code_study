# TASK-001. 프로젝트 디렉토리 구조 생성

## 상태
완료

## 날짜
2026-10-27

## 작업 요약
plan.md에 정의된 웹 애플리케이션 구조대로 폴더를 만들었습니다. 이사 전에 새 집에 "주방", "침실", "서재" 이름표를 붙인 빈 방을 먼저 준비해 두는 것과 같습니다. 앞으로 만들 코드가 어느 방에 들어갈지 미리 정해 두면, 나중에 파일이 늘어나도 헤매지 않습니다.

- **backend/** — 서버(FastAPI) 코드. `models`(데이터 모양), `api`(요청 창구), `services`(실제 일 처리: auth, code_analysis, ai, document, practice, qa, progress), `db`, `utils`, `tasks`(Celery 백그라운드 작업)
- **backend/tests/** — `unit`, `integration`, `contract` 세 종류 테스트 폴더
- **frontend/** — 화면(React) 코드. `components`(auth, project, task, upload, document, practice, qa, progress, trash), `pages`, `services`, `hooks`, `stores`, `lib`, `utils`, 그리고 `tests/unit`, `tests/integration`
- **storage/uploads/** — 사용자가 올린 코드 파일 보관 창고

## 변경 파일
- `backend/src/**/__init__.py`, `backend/tests/**/__init__.py` (18개, 빈 파일)
- `frontend/src/**/.gitkeep`, `frontend/tests/**/.gitkeep`, `storage/uploads/.gitkeep` (빈 파일)
- `backend/tests/unit/test_project_structure.py` (구조 검증 테스트)

## TDD 결과
- RED: 구조 검증 테스트 작성 후 실행 → 5개 모두 실패 확인
- GREEN: 폴더 생성 후 재실행 → T001 관련 4개 통과 (나머지 1개는 T001A 몫)
- REFACTOR: 해당 없음 (폴더만 만드는 작업)
- 커밋: 저장소가 아직 Git 저장소가 아니어서 RED/GREEN 커밋을 남기지 못했습니다
- 테스트 커버리지: 해당 없음 (검증할 실행 코드가 없음)

## 기술 결정
- **백엔드 폴더에는 `__init__.py`, 나머지 빈 폴더에는 `.gitkeep`**: 파이썬은 `__init__.py`가 있어야 폴더를 "꺼내 쓸 수 있는 묶음(패키지)"으로 인식합니다. Git은 빈 폴더를 기억하지 못하므로, 프런트엔드·저장소 폴더에는 자리 표시용 `.gitkeep`을 넣었습니다.
- **plan.md에 없는 `stores/`, `lib/`, `components/trash/`, `services/qa/`, `tasks/` 추가**: tasks.md의 T017, T019, T021, T134, T178이 이 경로를 사용하므로 미리 만들었습니다.
- **테스트는 표준 `unittest`로 작성**: 아직 pytest가 설치되지 않았기 때문입니다(T002에서 설치). pytest도 이 형식을 그대로 인식합니다.
- `alembic/`(T008), `frontend/public/`(T003 Vite 초기화)은 각 담당 Task에서 생성되도록 남겨 두었습니다.

## 비고
- 다음 단계: T002(백엔드 의존성), T003(Vite 프런트엔드 초기화). T003에서 Vite가 `frontend/`에 파일을 만들 때 기존 폴더와 충돌하지 않는지 확인이 필요합니다.
- Git 저장소 초기화(`git init`)와 feature 브랜치 생성이 되어야 constitution의 TDD 커밋 규칙을 지킬 수 있습니다.
