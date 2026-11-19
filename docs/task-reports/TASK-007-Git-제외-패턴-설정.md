# TASK-007. Git 제외 패턴 설정 (.gitignore)

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
Git에 올리면 안 되는 파일을 골라내는 목록 `.gitignore`를 프로젝트 루트에 만들었습니다.

이사할 때 "가져갈 짐"과 "두고 갈 짐"을 나누는 것과 같습니다. 설계도·코드·문서는 챙겨 가지만, 비밀번호가 적힌 쪽지(`.env`), 언제든 다시 살 수 있는 물건(설치된 라이브러리 `node_modules`, `.venv`), 쓰레기(캐시·빌드 결과물)는 두고 갑니다. 특히 비밀번호 쪽지를 실수로 상자에 넣으면 누구나 볼 수 있게 되므로, 아예 상자에 못 들어가게 막아 두는 것이 핵심입니다.

| 구분 | 제외(올리지 않음) | 예외로 포함(올림) |
|---|---|---|
| 비밀값 | `.env`, `.env.*`, `*.key`, `*.pem` | `.env.example` |
| Python | `.venv/`, `venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `htmlcov/` | — |
| Node | `node_modules/`, `dist/`, `coverage/`, `*.log`, `*.tsbuildinfo` | `package-lock.json` |
| 업로드 | `storage/uploads/*` (사용자 코드) | `storage/uploads/.gitkeep` |
| 편집기·OS | `.vscode/*`, `.idea/`, `.claude/settings.local.json`, `.DS_Store`, `Thumbs.db` | `.vscode/settings.json`, `.vscode/extensions.json` |

## 변경 파일
- `.gitignore` (신규)
- `backend/tests/unit/test_gitignore.py` (신규, 제외 규칙 검증 테스트)

## TDD 결과
- RED: 검증 테스트 작성 → `.gitignore`가 없어 3개 모두 실패 확인
- GREEN: `.gitignore` 작성 → 반드시 제외할 파일 21종, 반드시 포함할 파일 11종 모두 기대대로 동작. 전체 백엔드 테스트 30개 통과
- REFACTOR: TASK-006의 린트 검사가 새 테스트의 규칙 위반 3건(긴 줄, git 실행 경로)을 잡아내 수정
- 실제 검증: 임시 Git 저장소로 현재 프로젝트 폴더를 검사 → 올라갈 파일 109개, 그중 `.env`·가상환경·`node_modules`·캐시는 0개
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 해당 없음 (설정 작업)

## 기술 결정
- **테스트를 실제 Git으로 수행**: 패턴을 눈으로 확인하는 대신, 임시 폴더에 Git 저장소를 만들고 `git check-ignore`로 "이 파일이 제외되는가"를 직접 물어봅니다. Git의 실제 판단과 테스트 결과가 항상 같습니다.
- **`.env.*`를 막고 `.env.example`만 허용**: `.env.local`, `.env.production` 등 어떤 이름의 비밀 파일이 생겨도 자동으로 막힙니다.
- **`storage/uploads/*` + `.gitkeep` 예외**: 업로드 폴더 자체는 남기되, 사용자가 올린 코드는 절대 올라가지 않게 했습니다(FR-081 데이터 보안).
- **`.vscode/`는 공유 설정 2개만 포함**: 팀이 함께 쓰는 자동 포맷 설정·추천 확장은 올리고, 개인 설정(디버그 구성 등)은 제외합니다.
- **`.claude/`는 에이전트·명령어 정의를 포함, 개인 설정만 제외**: speckit 명령과 에이전트 정의는 팀이 공유해야 하는 개발 도구입니다.
- **`package-lock.json`은 포함**: 모든 사람이 정확히 같은 버전의 라이브러리를 설치하기 위해 필요합니다.
- `frontend/.gitignore`(Vite 템플릿)는 그대로 두었습니다. 루트 규칙과 함께 적용됩니다.

## 비고
- 아직 Git 저장소가 아닙니다. `git init` 후 첫 커밋 전에 `git status`로 `.env`가 목록에 없는지 다시 확인하는 것을 권장합니다.
- `backend/venv/`(TASK-002에서 만든 이전 가상환경)는 제외되지만 디스크에는 남아 있습니다. `.venv/`를 사용하므로 삭제해도 됩니다.
- Phase 1(Setup) 8개 Task가 모두 완료되었습니다. 다음은 Phase 2(Foundational)의 T008(Alembic)입니다.
