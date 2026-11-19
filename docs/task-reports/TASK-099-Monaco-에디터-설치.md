# TASK-099. Monaco 에디터 설치와 설정

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
학습 문서 화면의 왼쪽에 코드를 보여 줄 **Monaco 에디터**(VS Code의 편집기 부분)를 설치하고, 인터넷(CDN)에서 받지 않고 **우리 앱에 포함해서** 쓰도록 설정했습니다. 에디터는 크기가 커서, 처음 필요할 때만 따로 내려받도록(지연 로딩) 했습니다.

- 설치: `@monaco-editor/react` 4.7.0, `monaco-editor` 0.57.0 (버전 고정, `^` 없음)
- `MonacoEditor.tsx`: 읽기 전용 에디터. 줄 범위 강조, 강조 줄로 스크롤, 사용자가 스크롤할 때 맨 위 보이는 줄 알림.
- `LazyCodeEditor.tsx`: `React.lazy`로 에디터를 불러오는 얇은 껍데기(불러오는 동안 안내 문구). 시험에서는 이 부분을 가짜로 바꿉니다.

## 변경 파일
- `frontend/package.json`, `frontend/package-lock.json` (패키지 2개)
- `frontend/src/components/document/MonacoEditor.tsx` (새 파일)
- `frontend/src/components/document/LazyCodeEditor.tsx` (새 파일)
- `frontend/src/index.css` (강조 줄 스타일 `.code-highlight-line`)
- `frontend/tests/unit/monaco-setup.test.ts` (새 파일, 시험 5개)

## TDD 결과
- RED: 에디터 파일과 지연 로딩 사용처가 없어 3개 시험이 실패했습니다(버전 고정 2개는 설치 직후라 통과).
- GREEN: 에디터와 지연 로딩 껍데기를 만들어 5개 모두 통과했습니다. 시험 정규식이 `import type`을 정적 가져오기로 잘못 봐서 정규식을 고쳤습니다(내가 만든 새 시험).
- REFACTOR: 에디터 인스턴스를 `useState`로 들고 있어, 에디터가 뜨기 전에 온 강조 요청도 뜬 뒤에 적용됩니다.
- **이 작업에서 기존 테스트 파일은 고치지 않았습니다.**

## 기술 결정
- `loader.config({ monaco })`로 로컬 번들을 사용합니다. CDN 주소가 없는지도 시험합니다.
- 웹 워커는 따로 설정하지 않습니다. 0.57 버전은 워커 파일 주소를 `new URL(..., import.meta.url)`로 스스로 지정하고 Vite가 이를 별도 파일로 만듭니다(처음에 `?worker` 가져오기를 시도했으나 이 버전에서는 경로가 없어 빌드가 실패해 제거했습니다). 워커 파일은 필요할 때만 내려받습니다.
- 프로그램이 스크롤시킨 경우(강조 줄로 이동)는 "사용자 스크롤"로 알리지 않습니다. 되먹임을 막기 위해서입니다.

## 관련 개념
- **지연 로딩(lazy loading)**: 큰 코드를 처음부터 받지 않고 필요할 때 받는 방식.
- **웹 워커**: 화면을 멈추지 않도록 뒤에서 계산하는 별도 스레드.

## 주의할 점 (비고)
- jsdom에서는 Monaco가 동작하지 않아 실제 동작(강조, 스크롤 알림)은 브라우저 시험(T109~T114)에서 확인해야 합니다.
- Monaco 덩어리는 큽니다(`MonacoEditor` 약 1.3MB + `editor.api` 약 2.7MB, 언어 워커 포함 별도 파일). 메인 번들에는 들어가지 않습니다.

## 다음 단계
T100 CodePanel.
