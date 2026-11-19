# TASK-018. React Router 경로 구조

## 상태
완료

## 날짜
2026-11-03

## 작업 요약
프론트엔드에 **주소(URL)마다 어떤 화면을 보여 줄지 정하는 길 안내판**을 만들었습니다 (`frontend/src/routes.tsx`, `frontend/src/App.tsx`).

건물 안내도에 비유하면, 지금까지는 로비(제목 한 줄)만 있었습니다. 이제 "3층 = 휴지통", "프로젝트 방 번호 = `/projects/방번호`"처럼 층별 안내도를 붙였습니다. 각 방(페이지)은 아직 이름표만 붙은 빈 방이고, 실제 내용은 담당 Task가 채웁니다.

| 주소 | 화면 | 내용을 채울 Task | 구역 |
|---|---|---|---|
| `/login` | 로그인 | T036 | 공개 |
| `/register` | 회원가입 | T035 | 공개 |
| `/` | 내 프로젝트 (대시보드) | T054 | 로그인 필요 |
| `/projects/:projectId` | 프로젝트 상세 | T055 | 로그인 필요 |
| `/tasks/:taskId` | 태스크 상세 (문서·연습·Q&A 탭) | T083 | 로그인 필요 |
| `/trash` | 휴지통 | T181 | 로그인 필요 |
| 그 외 모든 주소 | "페이지를 찾을 수 없습니다" + 내 프로젝트로 이동 링크 | 이번 Task | - |

- **로그인 필요 구역**은 하나의 묶음(그룹)으로 만들어 두었습니다. T037에서 이 묶음 전체에 "로그인 안 했으면 로그인 화면으로" 검사(ProtectedRoute)를 한 번에 씌우고, 공통 상단 메뉴도 여기에 넣으면 됩니다(명세: 로그인·회원가입 화면에는 메뉴 없음).
- **주소 만들기 도우미 `paths`** (`frontend/src/lib/paths.ts`): 링크를 만들 때 `'/projects/' + id`처럼 직접 쓰지 않고 `paths.project(id)`를 씁니다. 주소가 바뀌어도 한 곳만 고치면 되고, 특수문자도 안전하게 처리됩니다.

## 변경 파일
- `frontend/src/routes.tsx` (신규) — 전체 경로 구조
- `frontend/src/App.tsx` — 라우터 연결 (제목만 있던 화면을 교체)
- `frontend/src/lib/paths.ts` (신규) — 주소 만들기 도우미
- `frontend/src/pages/` (신규 7개) — `Dashboard`, `Login`, `Register`, `ProjectDetail`, `TaskDetail`, `Trash`(자리 표시용), `NotFound`(완성)
- `frontend/tests/unit/App.test.tsx` — 경로 테스트로 교체 (13개)
- `frontend/package.json`, `package-lock.json` — `react-router-dom@^6.30.6` 추가
- `specs/001-ai-code-learning-platform/quickstart.md` — react-router-dom 버전 표기 갱신
- `specs/001-ai-code-learning-platform/tasks.md` — T018 완료 표시

## TDD 결과
- RED: 테스트 13개 작성 → 경로가 없어 13개 모두 실패 확인
- GREEN: 페이지·경로 작성 → 12개 통과, 1개 실패("뒤로 가기" 테스트가 화면 갱신 전에 검사 — 테스트 쪽 문제) → `act()`로 감싸 13개 통과
- REFACTOR:
  - ESLint(react-refresh)가 `App.tsx`에서 컴포넌트가 아닌 `routes`를 함께 내보내는 것을 지적(개발 중 화면 즉시 반영이 깨짐) → 경로 구조를 `routes.tsx`로 분리
  - `App`이 다시 그려질 때마다 라우터를 새로 만들던 것을 `useState`로 한 번만 만들도록 수정 (개발 모드 StrictMode의 두 번 그리기에도 안전)
- 최종: 프론트엔드 테스트 13개 통과, 커버리지 **100%**(10개 파일), 타입 검사·ESLint·Prettier·프로덕션 빌드 통과
- 실제 실행 확인: 개발 서버(5173)에서 7개 주소 모두 200과 앱 페이지 반환 → 깊은 주소에서 새로고침해도 화면 유지(명세 "새로고침해도 탐색 상태 유지")
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **React Router v6 (6.30.6)**: research.md·quickstart.md가 v6로 정해 두어 그대로 따랐습니다. 최신 v7은 v6와 사용법이 거의 같아, 필요하면 나중에 옮길 수 있습니다.
- **데이터 라우터(`createBrowserRouter`) 방식**: 경로를 객체 배열(`routes`)로 정의해, 테스트에서 같은 경로를 메모리 라우터로 그대로 검증합니다(브라우저 주소창 없이).
- **태스크 주소는 `/tasks/:taskId`**: 백엔드 API(`/api/v1/tasks/{task_id}`)와 같은 모양입니다. 프로젝트 정보는 태스크 데이터에 들어 있어 주소에 넣지 않았습니다. 문서·연습·Q&A 탭은 T083에서 페이지 안에서 정합니다.
- **404 화면 문구는 백엔드와 같음**: "요청한 페이지를 찾을 수 없습니다."(CHK084 같은 오류는 같은 문장).
- **페이지 지연 로딩은 나중에**: Monaco 편집기처럼 무거운 화면이 생길 때 T196에서 `React.lazy`로 나눕니다.

## 비고
- **브라우저 화면 확인은 하지 못했습니다**: Chrome 확장이 연결되어 있지 않았습니다. 화면 내용은 테스트로, 주소별 응답은 개발 서버로 확인했습니다.
- **npm 감사 경고(moderate)**: `npm install` 후 eslint 개발 도구의 `minimatch` 취약점 경고가 나옵니다. 이번 작업 전부터 있던 것이고, 개발 도구 전용이라 사용자 브라우저에는 들어가지 않습니다. 자동 수정(`--force`)은 typescript-eslint를 크게 낮추는 변경이라 하지 않았습니다.
- 지금은 아무나 모든 주소에 들어갈 수 있습니다. 로그인 검사는 T037에서 붙입니다.
