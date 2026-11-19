# TASK-022. Tailwind CSS와 shadcn/ui 설정

## 상태
완료

## 날짜
2026-11-04

## 작업 요약
앱의 **겉모습을 만드는 도구와 기본 부품**을 준비했습니다. 지금까지 화면은 브라우저 기본 모양이었지만, 이제 공통 색·글꼴·버튼을 쓸 수 있습니다.

- **Tailwind CSS 3**: `className="bg-primary text-sm"`처럼 클래스 이름으로 모양을 정하는 도구입니다.
- **테마(`src/index.css`)**: 주요 색(파랑), 위험 색(빨강), 테두리 색, 모서리 둥글기를 변수로 한 곳에 모았습니다. 여기만 고치면 앱 전체 색이 바뀝니다.
- **한글 글꼴**: 시스템 글꼴을 우선해서(맑은 고딕, Apple SD Gothic Neo 등) 글꼴 파일 다운로드 없이 표시됩니다.
- **shadcn/ui 부품 5종** (`src/components/ui/`): 인증 폼(T032~)과 대시보드(T054)에 바로 쓸 것만 넣었습니다.

| 부품 | 용도 |
|---|---|
| `Button` | 버튼. 종류(기본·위험·외곽선·보조·투명·링크), 크기, `asChild`(라우터 링크를 버튼 모양으로) |
| `Input`, `Label` | 입력 폼. 라벨을 누르면 입력칸으로 이동 |
| `Card` | 카드 틀 (제목·설명·본문·바닥글) |
| `Alert` | 안내·오류 상자. 스크린 리더가 알림으로 읽음 |

- **`cn()` 도우미** (`src/lib/utils.ts`): 클래스를 합칠 때 충돌하면 뒤의 값이 이깁니다(`px-2` + `px-4` → `px-4`).
- **`@/` 경로**: `@/components/ui/button`처럼 `src` 기준으로 불러올 수 있습니다.
- **실제 적용**: 404 페이지를 `Card`·`Button`으로 다시 만들어 실제 동작을 확인했습니다.

## 변경 파일
- `frontend/tailwind.config.ts`, `frontend/postcss.config.js`, `frontend/components.json` (신규)
- `frontend/src/index.css`, `frontend/src/lib/utils.ts` (신규)
- `frontend/src/components/ui/` (신규 5개: `button`, `input`, `label`, `card`, `alert`)
- `frontend/src/main.tsx` — 스타일시트 불러오기
- `frontend/src/pages/NotFound.tsx` — `Card`·`Button` 적용
- `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json` — `@/` 경로 설정
- `frontend/tests/unit/ui.test.tsx` (신규, 10개), `frontend/tests/unit/tailwind-setup.test.ts` (신규, 6개)
- `frontend/package.json`, `package-lock.json` — 패키지 9개 추가
- `specs/001-ai-code-learning-platform/quickstart.md` — 의존성 목록 갱신 (`shadcn-ui` 항목 삭제: 실제 패키지가 아님)
- `specs/001-ai-code-learning-platform/tasks.md` — T022 완료 표시

## TDD 결과
- RED: 테스트 작성 → 설정 파일과 부품이 없어 실패 확인
- GREEN: 설정·부품 작성 → 13개 통과, 3개 실패(Vitest가 테스트 중 `.css` 불러오기를 비움, `?raw`도 동일) → `index.css`를 파일에서 직접 읽도록 테스트 수정 후 16개 통과
- REFACTOR: Prettier 정리, 404 페이지에 부품 적용
- 최종: 프론트엔드 테스트 96개 통과, 문장·함수·줄 커버리지 **100%**, 분기 98.7% (남은 1개는 `routes.tsx` 운영 모드 분기 — 테스트가 개발 모드로만 실행됨), 타입 검사·ESLint·Prettier·프로덕션 빌드 통과 (CSS 9.2kB, gzip 2.8kB)
- 실제 브라우저 확인(`/no/such/page`, 계산된 스타일): 버튼 배경 `rgb(36, 99, 235)`(`--primary`), 높이 40px, 모서리 6px / 카드 모서리 12px / 페이지 배경 `rgb(244, 244, 245)`(`--muted`) / 글꼴에 "Malgun Gothic" 포함
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **Tailwind 3.x**: quickstart.md의 지정 버전대를 따랐습니다. 최신 4.x는 설정 방식이 달라, 옮기려면 별도 작업이 필요합니다. 같은 이유로 `tailwind-merge`도 Tailwind 3용인 2.x를 씁니다(3.x는 Tailwind 4 전용).
- **shadcn 부품은 CLI 없이 직접 작성 (계획과 다른 부분)**: `npx shadcn add`가 3분 넘게 아무 출력 없이 멈춰 중단했습니다. shadcn/ui는 패키지가 아니라 프로젝트에 넣는 소스 코드이므로, 같은 구조(new-york 스타일, cva 변형, `cn`)로 작성했습니다. `components.json`을 만들어 두어 CLI가 동작하는 환경이면 이후 부품을 CLI로 추가할 수 있습니다.
- **필요한 부품만 설치**: tabs(T083), dialog(삭제 확인), dropdown-menu(상단 메뉴) 등은 쓰는 Task에서 추가합니다.
- **밝은 테마만**: 명세에 다크 모드 요구가 없어 `.dark` 변수를 넣지 않았습니다.
- **`forwardRef` 대신 일반 props**: React 19는 `ref`를 일반 prop으로 전달합니다.
- **기본 버튼에 `type`을 강제하지 않음**: 기존 shadcn 동작과 같습니다. 폼 안에서는 `type="submit"`/`type="button"`을 직접 적어야 합니다.

## 비고
- **Tailwind 기본 초기화(Preflight)의 영향**: 제목·목록의 브라우저 기본 모양이 사라져, 자리 표시용 페이지(`Dashboard` 등)와 개발 테스트 페이지(`/dev-test`, `/dev/query-test`)의 제목이 일반 글씨처럼 보입니다. 각 페이지 Task에서 스타일을 입힙니다.
- **접근성 대비**: 주요 버튼(파랑 배경 + 흰 글씨)의 명암 대비는 이번에 측정하지 않았으므로 각 화면 작업에서 확인해야 합니다.
- `npm install` 후 나오는 보안 경고(moderate)는 T018 비고와 같은 기존 eslint 개발 도구 경고입니다.
- 이것으로 Phase 2 기반 작업(T008~T022)이 모두 완료되었습니다.
