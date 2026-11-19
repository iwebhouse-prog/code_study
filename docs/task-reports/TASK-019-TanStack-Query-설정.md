# TASK-019. TanStack Query 설정

## 상태
완료

## 날짜
2026-11-03

## 작업 요약
화면이 서버에서 데이터를 가져올 때 쓰는 **공용 "데이터 보관함과 규칙"**을 만들고 앱 전체에 연결했습니다 (`frontend/src/lib/queryClient.ts`).

도서관 대출 데스크에 비유하면, 같은 책(데이터)을 30초 안에 또 찾으면 서고에 다시 가지 않고 데스크에 있는 책을 바로 줍니다. 30초가 지나면 일단 데스크의 책을 먼저 보여 주고 뒤에서 새 판이 있는지 확인합니다(stale-while-revalidate, research.md 10장). 서고에 갔다가 실패했을 때는 이유에 따라 다르게 행동합니다.

| 상황 | 동작 | 이유 |
|---|---|---|
| 같은 데이터를 30초 안에 다시 요청 | 서버에 다시 묻지 않음 | 불필요한 요청 줄이기 |
| 4xx 오류 (400·401·403·404·409·429 등) | **재시도 안 함** | 다시 물어도 같은 답. 429에 재시도하면 요청 제한만 더 쌓임 |
| 네트워크 오류, 5xx 서버 오류 | **최대 2번 재시도** | 잠깐의 장애일 수 있음 |
| 저장·수정·삭제 요청(mutation) | **재시도 안 함** | 같은 프로젝트·태스크가 두 번 만들어질 수 있음 |

이제 어느 페이지에서든 `useQuery`/`useMutation`을 바로 쓸 수 있습니다.

## 변경 파일
- `frontend/src/lib/queryClient.ts` (신규) — `createQueryClient()`, `shouldRetryQuery()`, `getHttpStatus()`, 설정 상수
- `frontend/src/App.tsx` — `QueryClientProvider`로 앱 전체 감싸기
- `frontend/tests/unit/queryClient.test.tsx` (신규, 21개), `frontend/tests/unit/AppProviders.test.tsx` (신규, 1개)
- `frontend/package.json`, `package-lock.json` — `@tanstack/react-query@^5.105.3` 추가
- `specs/001-ai-code-learning-platform/quickstart.md` — 버전 표기 갱신
- `specs/001-ai-code-learning-platform/tasks.md` — T019 완료 표시

## TDD 결과
- RED: 클라이언트 테스트 작성 → `src/lib/queryClient` 파일이 없어 실패 확인
- GREEN: `queryClient.ts` 작성 → 21개 통과
- RED: "모든 페이지에서 공용 클라이언트를 쓸 수 있다" 테스트 작성 → `No QueryClient set` 오류로 실패 확인
- GREEN: `App.tsx`에 `QueryClientProvider` 연결 → 통과
- REFACTOR: 구조 변경 없음 (Prettier 정리만)
- 최종: 프론트엔드 테스트 35개 통과, 커버리지 **100%**(문장·분기·함수·줄), 타입 검사·ESLint·Prettier·프로덕션 빌드 통과
- 커밋: Git 저장소가 아니어서 RED/GREEN/REFACTOR 커밋을 남기지 못했습니다

## 기술 결정
- **오류에서 상태 코드 읽기(`getHttpStatus`)**: axios 오류(`error.response.status`, T020 예정)와 상태 코드를 직접 가진 오류(`error.status`) 둘 다 읽습니다. 그래서 T020에서 API 클라이언트를 만들 때 재시도 규칙을 고치지 않아도 됩니다.
- **클라이언트를 함수로 생성 + `useState`로 한 번만**: 테스트마다 깨끗한 보관함을 쓰고, 앱에서는 다시 그려져도(StrictMode 포함) 보관함이 초기화되지 않습니다. T018의 라우터와 같은 방식입니다.
- **재시도 간격은 기본값(1초, 2초… 지수 증가)**: 테스트에서만 0으로 바꿔 빠르게 확인합니다.
- **창 포커스 시 새로고침은 기본값(켜짐) 유지**: 다른 탭에서 돌아왔을 때 오래된 데이터면 뒤에서 새로 받습니다. 30초 안이면 요청하지 않습니다.
- **개발자 도구(React Query Devtools)는 넣지 않음**: 필요해지면 개발 모드에서만 추가합니다.

## 비고
- 문서 생성 상태 확인(research.md "상태 API 폴링")은 T098/T108에서 해당 쿼리에만 `refetchInterval`을 걸어 처리합니다. 공용 기본값에는 넣지 않았습니다.
- 데이터 종류별 보관함 이름(query key) 규칙은 실제 API 호출을 만드는 Task(T034, T054 등)에서 정합니다.
- `npm install` 후 나오는 보안 경고(moderate)는 T018 비고와 같은 기존 eslint 개발 도구 경고입니다.
