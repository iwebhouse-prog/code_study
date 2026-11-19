# TASK-065. 언어 감지 서비스

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
올린 코드가 **어떤 프로그래밍 언어인지 자동으로 알아내는 서비스**(`language_detector.py`)를 만들었습니다(FR-020). 결과는 `uploaded_code.detected_language`에 저장할 이름(`python`, `javascript` 등)입니다. 도서관 사서가 책 표지(확장자)를 먼저 보고, 표지가 없으면 첫 장(셔뱅)을, 그래도 모르면 내용(Pygments)을 훑어 분류하는 순서와 같습니다.

**파일 하나** (`detect_file_language`)
1. **확장자**: 업로드 가능한 12개 확장자를 모두 언어에 연결했습니다. `.jsx`는 javascript, `.tsx`는 typescript입니다. 확장자가 있으면 내용과 상관없이 확장자를 따릅니다.
2. **셔뱅**: `.txt`라면 첫 줄 `#!/usr/bin/env node`, `#!/usr/bin/python3.12` 같은 표시를 직접 읽습니다.
3. **Pygments 추측**: 그래도 모르면 Pygments의 `guess_lexer`로 추측하되, 지원하는 10개 언어일 때만 받아들이고 나머지는 `text`로 둡니다.

**업로드 전체** (`detect_language`): 언어별 줄 수를 합쳐 **가장 많은 언어**를 대표 언어로 정합니다. Markdown·text는 코드 파일이 하나도 없을 때만 대표가 됩니다. 동점이면 먼저 나온 파일의 언어입니다.

## 변경 파일
- `backend/src/services/code_analysis/language_detector.py` (새 파일)
- `backend/tests/unit/test_language_detector.py` (새 시험 20개)
- `backend/pyproject.toml` (mypy 예외 목록에 pygments 추가)

## TDD 결과
- 구현 전에 Pygments를 직접 돌려 보니 **추측이 자주 틀렸습니다.** 셔뱅 없는 파이썬 코드를 "Tera Term macro"로 보고, `node` 셔뱅은 알아보지 못했습니다. 그래서 위 2·3단계 규칙을 시험에 먼저 적었습니다.
- RED: `No module named ...language_detector`로 실패를 확인했습니다.
- 첫 구현의 셔뱅 정규식이 `#!/usr/bin/env node`에서 `usr`를 프로그램 이름으로 읽는 **버그**가 있어 node 시험이 실패했습니다. 파이썬 시험은 Pygments 덕분에 우연히 통과하고 있었습니다. 정규식 대신 단어 단위로 읽도록 구현을 고쳤습니다.
- 분기 커버리지에서 빈 셔뱅(`#!`) 경로가 비어 있어, 이번 작업에서 새로 쓴 시험 파일에 경계 시험을 더했습니다. 또 Pygments가 대신 맞혀 주지 못하도록 셔뱅 뒤에 한글 메모를 붙인 시험으로 파서만 검증합니다.
- GREEN: 전체 576개 통과, `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- **Pygments는 마지막 수단입니다.** 짧은 코드에서는 틀린 추측이 많아, 지원 언어 목록 밖의 결과는 버립니다.
- Pygments는 앞부분 10,000자만 읽습니다. 모든 언어 규칙을 다 돌려 보기 때문에 큰 파일 전체를 주면 느립니다.
- Pygments는 타입 정보를 제공하지 않아, celery·kombu와 같은 방식으로 mypy 예외에 넣었습니다(새 패키지 설치 없음).

## 관련 개념
- **셔뱅(shebang)**: 스크립트 첫 줄의 `#!`. 이 파일을 어떤 프로그램으로 실행할지 적어 둔 표시입니다.

## 주의할 점 (비고)
- 시험 도중 Docker가 꺼져 있어 DB 시험 209개가 건너뛰어진 것을 발견했고, Docker를 다시 켜고 전체를 다시 돌려 576개 통과를 확인했습니다.
- 붙여넣기 업로드(FR-013)는 사용자가 언어를 고르므로 감지 대신 선택값을 씁니다. `SUPPORTED_LANGUAGES`를 T069·T078에서 선택지 검사에 쓸 수 있습니다.

## 다음 단계
T066 코드 복잡도 분석기.
