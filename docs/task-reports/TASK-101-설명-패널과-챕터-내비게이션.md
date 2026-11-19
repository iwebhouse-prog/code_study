# TASK-101. 설명 패널과 챕터 내비게이션 (ExplanationPanel)

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
학습 문서 화면 오른쪽의 **설명 패널**입니다. 위쪽에 7개 챕터 버튼(챕터 이동 내비게이션)이 있고, 아래에 7개 챕터가 세로로 이어 붙어 스크롤됩니다.

- 챕터 버튼을 누르면 그 챕터가 "현재 챕터"로 강조(`aria-current`)되고 패널이 그 챕터 위치로 스크롤됩니다. 키보드(Tab, Enter)로도 사용할 수 있습니다.
- 1, 2, 4장은 전용 컴포넌트(T102~T104)를, 3, 5, 6, 7장은 공용 렌더러(`SimpleChapters.tsx`)를 씁니다. 3장의 Mermaid 흐름도는 글자 그대로(미리 서식 지정 텍스트) 보여 줍니다.
- 부모가 `activeExplanationIndex`(코드 스크롤이 가리키는 4장 항목)를 바꾸면 4장이 현재 챕터가 되고, 그 항목이 안 보이면 패널 안에서만 스크롤합니다(페이지 전체는 움직이지 않음).
- 스크롤 영역은 `tabIndex=0`이라 키보드로 스크롤할 수 있습니다.

## 변경 파일
- `frontend/src/components/document/ExplanationPanel.tsx` (새 파일)
- `frontend/src/components/document/ChapterSection.tsx` (새 파일: 번호 붙은 제목 틀)
- `frontend/src/components/document/chapters/SimpleChapters.tsx` (새 파일: 3, 5, 6, 7장)
- `frontend/src/services/document-types.ts` (새 파일: 문서 내용 타입)
- `frontend/tests/helpers/documents.ts`, `frontend/tests/fixtures/even-odd-document.json` (시험용 자료)
- `frontend/tests/unit/ExplanationPanel.test.tsx` (새 파일, 시험 13개)

## TDD 결과
- RED: 시험을 먼저 썼습니다(컴포넌트 없음). 별도 실행으로 RED를 확인하지는 못했고, 시험 파일이 컴포넌트보다 먼저 만들어졌습니다.
- GREEN: 구현 뒤 13개 모두 통과, 전체 402개 통과.
- REFACTOR: 3, 5, 6, 7장을 카드 목록 렌더러 하나로 합쳤습니다.
- **이 작업에서 기존 테스트 파일은 고치지 않았습니다.**

## 기술 결정
- 한 번에 한 챕터만 보이게 하지 않고 모두 이어 붙였습니다. 그래야 "코드를 스크롤하면 4장 항목으로 스크롤"이 다른 챕터를 읽는 중에도 자연스럽습니다.
- 스크롤 위치는 `getBoundingClientRect`로 계산합니다(`scrollIntoView`는 페이지까지 움직임).
- 외부 입력으로 현재 챕터를 바꾸는 부분은 `useEffect` 대신 렌더링 중 상태 보정으로 구현했습니다.

## 관련 개념
- **스크롤 컨테이너**: 자기 안에서만 스크롤되는 영역.
- **`aria-current`**: 스크린리더에 "지금 위치"를 알리는 속성.

## 주의할 점 (비고)
- 직접 스크롤해서 다른 챕터로 넘어가도 현재 챕터 강조는 바뀌지 않습니다(버튼 클릭이나 코드 동기화 때만). 시험이 요구하지 않아 넣지 않았습니다.
- 스크롤 위치 계산은 jsdom에서 가짜 값으로 시험했고, 실제 레이아웃은 브라우저 시험에서 확인해야 합니다.

## 다음 단계
T102 Chapter1 (T101과 함께 완료), T103, T104.
