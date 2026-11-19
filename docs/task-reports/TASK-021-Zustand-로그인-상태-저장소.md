# TASK-021. Zustand 로그인 상태 저장소

## 상태
완료

## 날짜
2026-11-04

## 작업 요약
화면들이 **"지금 누가 로그인했는지"를 함께 보는 공용 게시판**을 만들었습니다 (`frontend/src/stores/auth-store.ts`).

상단 메뉴의 사용자 이름, 로그인 필요 화면의 출입 검사(T037) 등이 모두 이 게시판 하나를 봅니다.

| 값·함수 | 내용 |
|---|---|
| `status` | `unknown`(확인 전) / `authenticated`(로그인됨) / `anonymous`(비로그인) |
| `user` | `{ id, email, skillLevel }` 또는 `null` |
| `setUser(user)` | 로그인 확인됨 → `authenticated` |
| `clearUser()` | 로그아웃·세션 없음 → `anonymous` |

사용 예:
```tsx
const email = useAuthStore((state) => state.user?.email)   // 화면에서
useAuthStore.getState().clearUser()                        // 화면 밖에서 (T038 토큰 갱신 실패 시)
```

## 변경 파일
- `frontend/src/stores/auth-store.ts` (신규)
- `frontend/tests/unit/auth-store.test.tsx` (신규, 7개)
- `frontend/package.json`, `package-lock.json` — `zustand@^4.5.7` 추가
- `specs/001-ai-code-learning-platform/quickstart.md` — 버전 표기 갱신
- `specs/001-ai-code-learning-platform/tasks.md` — T021 완료 표시

## TDD 결과
- RED: 테스트 작성 → `src/stores/auth-store` 파일이 없어 실패 확인
- GREEN: `auth-store.ts` 작성 → 7개 통과
- REFACTOR: 코드가 작아 구조 변경 없음
- 최종: 프론트엔드 테스트 76개 통과, 문장·함수·줄 커버리지 **100%**, 분기 98.61% (남은 1개는 `routes.tsx` 운영 모드 분기 — 테스트가 개발 모드로만 실행됨), 타입 검사·ESLint·Prettier·프로덕션 빌드 통과
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **Task 제목은 "JWT state"지만 토큰은 저장하지 않음 (명세와 다른 해석)**: research.md 8장이 토큰을 HTTPOnly 쿠키에 두기로 정했습니다. 쿠키의 토큰은 페이지의 어떤 스크립트도 읽을 수 없어서, 악성 스크립트가 끼어들어도(XSS) 훔칠 수 없습니다. 저장소에 복사하면 이 보호가 사라지고, 애초에 읽을 방법도 없습니다. 그래서 저장소는 "누가 로그인했는가"라는 **JWT에서 얻은 결과**만 담습니다. 상태 키가 4개로 고정인지 테스트로 묶어, 나중에 토큰 필드가 추가되면 테스트가 실패합니다.
- **`unknown` 상태를 따로 둠**: 새로고침 직후에는 `GET /auth/me`(T029A) 응답 전까지 로그인 여부를 모릅니다. 이때 비로그인으로 처리하면 로그인한 사용자가 잠깐 로그인 화면으로 튕겨 나갑니다. T037 ProtectedRoute는 `unknown`이면 기다리고, `anonymous`일 때만 이동시키면 됩니다.
- **브라우저 저장소에 저장하지 않음(persist 미사용)**: 로그인 여부는 쿠키가 결정하므로 복사본은 오래된 값이 될 수 있고, 이메일이 스크립트에 노출됩니다. 테스트로 확인했습니다.
- **Zustand 4.x**: quickstart.md의 지정 버전대를 따랐습니다. React 19에서 동작합니다(테스트로 확인). 최신 5.x와 사용법 차이는 작습니다.
- **`skillLevel`은 프론트엔드 표기(camelCase)**: 백엔드 응답(`skill_level`)을 바꾸는 일은 T034 인증 서비스에서 합니다.

## 비고
- 저장소는 값을 보관만 합니다. 실제로 `GET /auth/me`를 호출해 `setUser`/`clearUser`를 부르는 일은 T034·T038에서 합니다. 그때까지 `status`는 계속 `unknown`입니다.
- 로그아웃할 때는 `clearUser()`와 함께 TanStack Query 보관함도 비워야 합니다(`queryClient.clear()`). 그렇지 않으면 이전 사용자의 데이터가 다음 사용자 화면에 보일 수 있습니다. T034/T038에서 처리해야 합니다.
- `npm install` 후 나오는 보안 경고(moderate)는 T018 비고와 같은 기존 eslint 개발 도구 경고입니다.
- 이전 세션에서 띄운 백엔드·프론트엔드 개발 서버는 세션 종료와 함께 꺼졌습니다(8000, 5173 포트 비어 있음 확인).
