# TASK-003. 프론트엔드 React 프로젝트 초기화 (Vite + TypeScript)

## 상태
완료

## 날짜
2026-10-29

## 작업 요약
사용자가 보게 될 화면(프론트엔드)의 기본 틀을 만들었습니다. 건물로 치면 골조와 전기 배선까지 끝내고, 방 하나에 "AI Code Learning Platform"이라는 문패만 달아 둔 상태입니다. 이후 로그인 화면, 대시보드 같은 방은 이 골조 위에 하나씩 채워 넣습니다.

- **Vite**: 코드를 고치면 브라우저에 즉시 반영해 주는 개발 도구입니다(`npm run dev`).
- **TypeScript (strict 모드)**: 숫자 자리에 글자를 넣는 실수 같은 것을 실행 전에 잡아 줍니다.
- **Vitest + Testing Library**: 화면이 제대로 그려지는지 자동으로 확인하는 검사 도구입니다(`npm test`).

## 변경 파일
- `frontend/package.json`, `package-lock.json` (신규)
- `frontend/vite.config.ts` (Vite + Vitest 설정: jsdom 환경, v8 커버리지)
- `frontend/tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` (strict 모드 명시, tests 폴더 포함)
- `frontend/index.html` (lang="ko", 제목 설정), `frontend/public/favicon.svg`
- `frontend/src/main.tsx`, `frontend/src/App.tsx`
- `frontend/tests/setup.ts`, `frontend/tests/unit/App.test.tsx`
- `frontend/.gitignore` (`coverage` 추가)

## TDD 결과
- RED: `App.test.tsx` 작성 → `src/App`이 없어 실패 확인
- GREEN: 제목 하나만 보여 주는 최소 `App.tsx` 작성 → 1개 테스트 통과
- REFACTOR: TypeScript strict 모드 명시, 테스트 폴더 타입 검사 포함, 페이지 제목·언어 설정 → `tsc -b`, `vite build`, 테스트 모두 통과
- 커밋: Git 저장소가 아니어서 커밋하지 못했습니다
- 테스트 커버리지: 100% (App.tsx)

## 기술 결정
- **React 19 사용**: plan.md의 "React 18+" 조건을 만족하는 현재 Vite 템플릿 기본값입니다. quickstart.md 예시의 React 18 / Vite 5 / Vitest 1은 2023년 기준이라 따르지 않았습니다.
- **템플릿의 oxlint 제거**: 최신 Vite 템플릿은 oxlint를 기본으로 넣지만, constitution V는 ESLint + Prettier를 지정합니다. 린트 설정은 T006에서 ESLint로 추가합니다.
- **데모 이미지·CSS 제거**: 템플릿의 예시 화면(로고, 카운터 버튼, App.css/index.css)은 쓰지 않으므로 지웠습니다. 스타일은 T022(Tailwind)에서 들어옵니다.
- **템플릿은 임시 폴더에서 생성 후 복사**: `frontend/`에 이미 TASK-001의 폴더가 있어 Vite가 비어 있지 않은 폴더에 바로 생성하지 못하기 때문입니다.
- **설치 범위 최소화**: React Router(T018), TanStack Query(T019), axios(T020), Zustand(T021), Tailwind/shadcn(T022), Monaco(T099)는 각 Task에서 설치합니다.

## 비고
- 실행: `cd frontend; npm install; npm run dev` → http://localhost:5173
- 명령: `npm test`(테스트), `npm run typecheck`(타입 검사), `npm run build`(배포용 빌드), `npx vitest run --coverage`(커버리지)
- quickstart.md의 package.json 예시는 아직 예전 버전입니다. 이후 Task에서 라이브러리가 모두 들어오면 T189에서 갱신하는 것을 권장합니다.
