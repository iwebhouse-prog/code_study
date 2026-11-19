# TASK-066. 코드 복잡도 분석기

## 상태
완료

## 날짜
2026-11-16

## 작업 요약
올린 코드가 **초급(beginner)·중급(intermediate)·고급(advanced) 중 어디에 해당하는지 판정하는 분석기**(`complexity_analyzer.py`)를 만들었습니다(FR-021). 결과는 `uploaded_code.complexity_level`과 `total_lines`에 저장됩니다. 등산로 난이도를 길이·경사·갈림길 수로 매기듯, research.md가 정한 세 가지 잣대를 씁니다.

| 잣대 | 세는 방법 | 중급 이상 | 고급 |
|---|---|---|---|
| 코드 줄 수 | 주석·독스트링·빈 줄 제외 | 100줄 | 500줄 |
| 함수 수 | 언어별 함수 정의 표시 | 5개 | 20개 |
| 중첩 깊이 | 중괄호 `{}` 또는 파이썬 들여쓰기 단계 | 3 | 5 |

세 잣대 중 **하나라도** 기준에 닿으면 그 단계가 됩니다. 업로드 전체는 코드 파일의 줄·함수를 더하고, 깊이는 가장 깊은 파일을 씁니다. Markdown·텍스트는 전체 줄 수에만 더해집니다.

## 변경 파일
- `backend/src/services/code_analysis/complexity_analyzer.py` (새 파일)
- `backend/src/services/code_analysis/language_detector.py` (`_line_count` → 공개 함수 `count_lines`로 이름만 변경해 함께 사용)
- `backend/tests/unit/test_complexity_analyzer.py` (새 시험 23개)

## TDD 결과
- 구현 전에 Pygments 토큰을 직접 확인했습니다. 파이썬·Java·C는 함수 이름에 `Name.Function` 표시를 붙이지만, **JavaScript·TypeScript는 붙이지 않아** `function` 키워드와 화살표(`=>`)를 따로 셉니다. `.jsx`/`.tsx`는 전용 분석기(JSX, TSX)로 읽어야 깨지지 않는 것도 확인했습니다.
- 기대값은 예제 코드를 보고 손으로 계산해 먼저 적었습니다.
- RED: `No module named ...complexity_analyzer`로 실패를 확인했습니다.
- GREEN: 새 시험 23개가 첫 구현에서 통과. 전체 599개 통과(건너뜀 0), `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 기술 결정
- **기준 숫자는 명세에 없어 제가 정했습니다.** 완전 초보자 기준이고, 500줄은 명세의 "큰 코드(500줄 이상)" 안내와 맞췄습니다. 상수(`INTERMEDIATE`, `ADVANCED`) 한 곳만 바꾸면 조정됩니다.
- **글자 대신 토큰으로 셉니다.** 그래서 주석이나 문자열 안의 `{`, `def`는 세지 않습니다. C의 `#include`는 주석이 아니라 코드로 셉니다.
- `.txt`라도 파이썬 셔뱅이 있으면 T065의 감지 결과대로 파이썬으로 분석합니다.

## 관련 개념
- **토큰**: 코드를 "키워드, 이름, 기호, 주석"처럼 의미 단위로 자른 조각입니다.

## 주의할 점 (비고)
- **속도**: 1MB 파이썬 파일에 약 3.5초, 10MB에 약 34초가 걸렸습니다. 웹 요청 안에서 돌리면 너무 느리므로 **T069에서 Celery 백그라운드 작업으로 실행**해야 합니다.
- 근사치의 한계: JS 클래스의 메서드 축약형(`m() {}`), C++ 클래스 메서드는 함수로 세지지 않고, JSX의 `{값}`은 깊이를 조금 늘립니다. 파이썬은 여러 줄 괄호 정렬이 깊이를 늘릴 수 있습니다. HTML은 깊이를 재지 않습니다.

## 다음 단계
T067 파일 저장 서비스(`storage/uploads/{user_id}/{task_id}/`).
