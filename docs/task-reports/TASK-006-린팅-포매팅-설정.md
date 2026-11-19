# TASK-006. 린팅·포매팅 설정 (Ruff, Black, MyPy / ESLint, Prettier)

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
코드의 실수를 찾아 주는 도구(린터)와 코드 모양을 통일해 주는 도구(포매터)를 백엔드·프론트엔드에 설정했습니다.

글쓰기에 비유하면, 린터는 "맞춤법 검사기", 포매터는 "문단 정렬 버튼"입니다. 맞춤법 검사기는 오타나 앞뒤가 안 맞는 문장(쓰지 않는 변수, 위험한 코드)을 빨간 줄로 알려 주고, 정렬 버튼은 누가 쓰든 들여쓰기·따옴표·줄 길이를 똑같이 맞춰 줍니다. 여러 사람이 함께 써도 한 사람이 쓴 것처럼 읽히게 됩니다.

| 영역 | 린터 | 포매터 | 타입 검사 | 설정 파일 |
|---|---|---|---|---|
| 백엔드 | Ruff | Black | MyPy (strict) | `backend/pyproject.toml` |
| 프론트엔드 | ESLint | Prettier | TypeScript (strict) | `eslint.config.js`, `.prettierrc.json` |

실행 명령:
- 백엔드: `ruff check src tests`, `black src tests`, `mypy`
- 프론트엔드: `npm run lint`, `npm run format`, `npm run format:check`

## 변경 파일
- `backend/pyproject.toml` (신규: Ruff/Black/MyPy/pytest 설정)
- `backend/requirements.txt` (ruff, black, mypy 추가)
- `backend/tests/unit/test_lint_config.py` (신규, 설정 검증 테스트)
- `backend/tests/unit/test_*.py` (새 규칙에 맞게 정리: 긴 docstring 축약, import 정렬)
- `frontend/eslint.config.js`, `frontend/.prettierrc.json`, `frontend/.prettierignore` (신규)
- `frontend/package.json` (lint/format 스크립트, ESLint·Prettier 패키지, TypeScript 6.0.3)
- `frontend/tsconfig.json` (Prettier 포맷 적용)

## TDD 결과
- RED: 검증 테스트 6개 작성 → 설정·도구가 없어 6개 모두 실패 확인
- GREEN: 설정 추가, 기존 코드의 규칙 위반 9건 수정 → 백엔드 테스트 27개 전체 통과, ESLint·Prettier·tsc·Vitest·빌드 통과
- 추가 확인: 일부러 잘못 쓴 코드(`const unused: any = 1`)를 ESLint가 오류 2건으로 잡는 것 확인
- REFACTOR: Black이 어색하게 줄바꿈한 코드 2곳을 변수로 나눠 읽기 쉽게 정리
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 해당 없음 (설정 작업)

## 기술 결정
- **TypeScript 7.0.2 → 6.0.3으로 낮춤**: ESLint가 TypeScript 코드를 읽으려면 typescript-eslint가 필요한데, 최신판(8.72.1, canary 포함)도 TypeScript 6.1 미만만 지원합니다. constitution V가 ESLint를 지정하므로 TypeScript 버전을 맞췄습니다. TASK-003의 Vite 템플릿이 oxlint를 썼던 것도 같은 이유로 보입니다. typescript-eslint가 7을 지원하면 다시 올릴 수 있습니다.
- **MyPy strict 추가**: T006 설명에는 없지만 constitution V(타입 안전성: MyPy strict 필수)를 위해 같은 파일에 함께 설정했습니다. 검사 범위는 `src`입니다.
- **Ruff 규칙**: 기본(E, W, F) + import 정렬(I), 흔한 버그(B), 최신 문법(UP), 단순화(SIM), 보안(S, bandit)을 켰습니다. 테스트에서는 `assert`(S101), 로컬 도구 실행(S603)만 허용했습니다.
- **Ruff와 Black 줄 길이 88로 통일**: 두 도구가 서로 다른 판단을 하지 않도록 맞췄습니다(테스트로 확인).
- **Prettier 규칙은 기존 코드 스타일을 따름**: 세미콜론 없음, 작은따옴표, 끝 쉼표. `eslint-config-prettier`를 마지막에 두어 ESLint와 Prettier가 충돌하지 않게 했습니다.
- **ESLint 규칙**: 기본 JS 권장 + typescript-eslint 권장 + React Hooks 규칙 + Vite Fast Refresh 규칙.

## 비고
- VS Code에서 저장할 때 자동 정렬하려면 Ruff/Black, ESLint/Prettier 확장을 설치하면 됩니다.
- T007(.gitignore)에서 `.ruff_cache/`, `.mypy_cache/`도 제외 대상에 넣어야 합니다.
