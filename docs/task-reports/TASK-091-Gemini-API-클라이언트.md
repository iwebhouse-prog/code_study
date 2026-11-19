# TASK-091. Gemini API 클라이언트

## 상태
완료

## 날짜
2026-11-17

## 작업 요약
학습 문서와 질문 답변을 만들 **Google Gemini API를 부르는 얇은 포장 계층**(`gemini_client.py`)을 만들었습니다. 해외 거래처와 통화하는 전담 비서에 비유하면, 비서는 전화를 걸고(요청), 너무 오래 걸리면 끊고(시간 제한), 실패하면 "다시 걸면 될 일인지, 다시 걸어도 소용없는 일인지"를 메모로 남깁니다. 다시 걸지 말지는 상사(T093 생성 서비스)가 정합니다.

1. **설정** `GeminiConfig.from_env()`: `.env`의 `GOOGLE_API_KEY`, `GEMINI_MODEL`(기본 `gemini-3-flash-preview`)을 읽습니다. 키가 없거나 `.env.example`의 `change-me…` 그대로면 시작부터 거절합니다(JWT 설정과 같은 방식). 키는 `repr`과 로그에 절대 나오지 않습니다.
2. **두 가지 호출** (research.md §3의 시간 제한):
   - `generate_text()` — 질문 답변용, 기본 20초.
   - `generate_json()` — 문서용, 3분. JSON 모드로 요청하고, JSON Schema를 주면 그 모양을 따르게 하며, 받은 글을 JSON 객체로 해석해 돌려줍니다.
3. **오류 분류** (`retryable` = 다시 시도하면 나아질 수 있음):

| 상황 | 오류 | 재시도 |
|---|---|---|
| 시간 초과 | `AITimeoutError` | 예 |
| 429 사용량 한도 | `AIRateLimitError` | 예 |
| 5xx, 네트워크 끊김 | `AIServiceUnavailableError` | 예 |
| 빈 답, 잘린 답, 깨진 JSON | `AIInvalidResponseError` | 예 |
| 400/401/403/404 (잘못된 키·모델·요청) | `AIRequestError` | 아니오 |
| 안전 필터 차단 | `AIBlockedError` | 아니오 |

4. **기록**: 호출마다 모델, 걸린 시간, 입력·출력 토큰 수, 결과를 한 줄로 남깁니다(비용 추적). 프롬프트 내용은 남기지 않습니다.

## 변경 파일
- `backend/src/services/ai/gemini_client.py` (새 파일)
- `backend/tests/unit/test_gemini_client.py` (새 시험 24개)

## TDD 결과
- RED: `No module named ...gemini_client`로 실패를 확인했습니다.
- GREEN: 새 시험 24개 통과(가짜 클라이언트 사용, 실제 API 호출 없음). 이후 전체 실행에서 기존 린트 시험(`test_ruff_passes`)이 **제가 새로 쓴 시험 파일**의 `with` 중첩 규칙(SIM117) 위반 2곳을 잡아, 그 파일만 고쳐 통과시켰습니다. 전체 827개 통과, `src` 줄·분기 커버리지 100%. ruff, black, mypy(strict) 통과.
- **기존 시험 파일은 고치지 않았습니다.**

## 실제 API 확인
`.env`의 키로 실제 호출을 두 번 했습니다: 한국어 설명(2.8초, 출력 28토큰)과 JSON Schema 응답(4.5초, 출력 143토큰) 모두 정상이었습니다.

## 기술 결정
- **재시도는 여기서 하지 않습니다.** 분류만 하고, 지수 백오프 최대 3회(research.md)는 T093이 맡습니다. 역할이 섞이면 시험과 수정이 어려워집니다.
- 공식 SDK(`google-genai` 2.33)의 비동기 API를 쓰고, 시험에서는 SDK 대신 가짜 객체를 넣을 수 있게 했습니다.

## 관련 개념
- **JSON 모드 / JSON Schema**: AI에게 "이 모양의 JSON으로만 답하라"고 지정하는 기능입니다.

## 주의할 점 (비고)
- 실제 호출 시험에서 스키마의 `output`이라는 이름을 AI가 "실행 결과"가 아닌 "설명"으로 해석했습니다. 필드 이름과 설명을 분명히 쓰는 일은 T092 프롬프트 설계의 몫입니다.
- 안전 설정(safety settings)은 API 기본값을 씁니다.

## 다음 단계
T092 7장 문서 생성 프롬프트.
