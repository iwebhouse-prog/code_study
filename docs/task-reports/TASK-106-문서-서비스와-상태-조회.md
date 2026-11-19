# TASK-106. 문서 서비스와 상태 조회 (document-service)

## 상태
완료

## 날짜
2026-11-18

## 작업 요약
서버의 학습 문서 API(`contracts/documents-api.md`)를 부르는 **서비스**와, 3초마다 상태를 확인하는 **훅**입니다. 백엔드(T094~T098)가 아직 없어 가짜 HTTP로만 시험했습니다.

- `documentService.getStatus(taskId)`: `GET /tasks/{id}/document/status`
- `documentService.getDocument(taskId)`: `GET /tasks/{id}/document`
- `documentService.regenerate(taskId)`: `POST /tasks/{id}/document/regenerate`
- 모든 응답은 snake_case에서 camelCase로 바꿉니다. 서버가 이상한 모양(예: 상태 값 없음)을 주면 오류를 던져 화면이 오류 문구를 보여 줍니다(앱이 멈추지 않음).
- `useLearningDocument(taskId)` 훅: 상태가 `pending`/`in_progress`인 동안 3초마다 다시 묻고(`refetchInterval`), `completed`가 되면 문서를 한 번 받고, `failed`면 멈춥니다. `regenerate`가 성공하면 상태를 `pending`으로 바꿔 폴링이 다시 시작됩니다.

## 변경 파일
- `frontend/src/services/document-service.ts`, `document-types.ts` (새 파일)
- `frontend/src/hooks/useLearningDocument.ts` (새 파일)
- `frontend/src/lib/query-keys.ts` (문서 상태/문서/코드 키 3개 추가)
- `frontend/tests/unit/document-service.test.ts` (시험 12개), `useLearningDocument.test.tsx` (시험 7개)
- `frontend/tests/fixtures/even-odd-document.json` (실제 생성 예시), `tests/helpers/documents.ts`

## TDD 결과
- RED: 두 시험 파일 모두 모듈이 없어 로드 실패를 확인했습니다.
- GREEN: 구현 후 19개 모두 통과(가짜 타이머로 3초 폴링 확인).
- REFACTOR: 응답을 안전하게 읽는 작은 함수(`text`, `list`, `record`)로 매핑 코드를 정리했습니다.
- **이 작업에서 기존 테스트 파일은 고치지 않았습니다.**

## 기술 결정
- 상태 질의는 `staleTime: 0`입니다. 페이지를 떠났다 돌아오면 바로 최신 상태를 물어야 하기 때문입니다.
- 문서 본문은 `completed`일 때만 요청합니다(`enabled`).
- `use_cases`는 스키마상 문자열이지만 목록으로 와도 쉼표로 이어 붙입니다.
- 빠진 필드는 빈 문자열/빈 목록으로 채워 일부가 깨진 문서도 보여 줍니다.

## 관련 개념
- **폴링**: 일정 간격으로 서버에 상태를 다시 묻는 방식.
- **쿼리 키**: TanStack Query가 데이터를 구분하는 이름표.
- **방어적 매핑**: 외부 데이터를 믿지 않고 모양을 확인하며 변환.

## 주의할 점 (비고)
- 실제 백엔드와의 연결은 확인하지 못했습니다(계약 문서 기준).
- 3초 폴링은 화면이 가려져 있으면(다른 탭) 브라우저 기본 동작대로 멈춥니다.

## 다음 단계
T105 DocumentViewer, T107 상태 화면, T108 태스크 상세 연결.
