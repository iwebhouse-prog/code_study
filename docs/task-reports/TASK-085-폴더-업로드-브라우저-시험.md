# TASK-085. 폴더 업로드 브라우저 시험

## 상태
완료 (통과)

## 날짜
2026-11-16

## 작업 요약
폴더를 통째로 올렸을 때 **폴더 구조가 그대로 보존되고, `.git`·`node_modules`는 빠지는지(FR-017)** 실제 브라우저로 확인했습니다. 이사할 때 상자마다 "부엌/서랍" 이름표를 붙여 옮기고, 쓰레기 봉투는 두고 가는 것과 같습니다.

시험 폴더 `my-app/`:
```
my-app/src/App.jsx, my-app/src/utils.js, my-app/public/index.html
my-app/node_modules/react/index.js   ← 빠져야 함
my-app/.git/config                   ← 빠져야 함
```

| 단계 | 기대 | 결과 |
|---|---|---|
| 폴더 탭 → 폴더 선택 | 파일 3개 + "제외된 폴더: node_modules, .git" | 통과 — 실제로 나온 이름만 표시 |
| 태스크 만들기 | 201, 완료 창에 상대 경로 3개 | 통과 — "Task 2. React 폴더 구조 익히기", `my-app/public/index.html`, `my-app/src/App.jsx`, `my-app/src/utils.js`(경로순) |
| "태스크 보기" | 상세 화면 "Task 2. …", 탭 3개 | 통과 — 학습 문서 / 연습 문제 / 질문하기 |
| `GET /tasks/{id}/code` | 경로·내용 보존 | 통과 — 파일별 언어 html/javascript/javascript, 대표 언어 javascript, 난이도 beginner, 10줄 |
| DB·디스크 | 파일 행 3개, 각자 UUID 이름 | 통과 |

## 변경 파일
- `docs/task-reports/screenshots/T085-folder-upload-confirmation.png`
- `specs/001-ai-code-learning-platform/tasks.md` (T085 완료 표시)
- 코드 변경 없음

## TDD 결과
- 수동 시험이라 RED/GREEN 단계가 없습니다. 시험 파일과 코드는 고치지 않았습니다.

## 기술 결정
- 단위 시험(jsdom)에서는 흉내만 냈던 `webkitdirectory`와 실제 multipart 전송을 이번에 **실제 브라우저(Chromium)로 처음 검증**했습니다.
- 대표 언어가 javascript인 이유: JS 파일 6줄 대 HTML 4줄로, 줄 수가 많은 쪽(T065 규칙)입니다.

## 관련 개념
- **상대 경로**: 올린 폴더를 기준으로 한 위치(`my-app/src/App.jsx`). 원래 컴퓨터의 전체 경로는 보내지 않습니다.

## 주의할 점 (비고)
- 제외는 브라우저가 먼저 해서 서버 응답의 `excluded_paths`는 비어 있었습니다. 그래서 완료 창에는 제외 목록이 다시 나오지 않습니다(선택 단계에서 이미 안내). 서버 쪽 제외 기능은 백엔드 단위 시험으로 확인되어 있습니다.
- 크롬 계열 외 브라우저(Firefox·Safari)는 확인하지 않았습니다.

## 다음 단계
T086 코드 붙여넣기.
