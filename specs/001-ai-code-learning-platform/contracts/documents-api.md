# Documents API Contract (T094–T108)

Shared agreement between the backend (T094–T098) and frontend (T099–T108).
Change it only together. Base URL, cookies and the error body are as in
`auth-api.md` / `tasks-api.md`. Every endpoint requires sign-in, and task
ownership works exactly as in `tasks-api.md` (other user's task → `403`,
missing or trashed task → `404 not_found`, non-UUID id → `400 validation_error`).

## Generation lifecycle (backend)

1. **Trigger (T096)**: right after a task is created with its code (the upload
   transaction has committed), a `LearningDocument` row is created with status
   `pending` and `LearningDocument.empty_content()`, and the Celery task
   `src.tasks.document_generation.generate_document(task_id)` is queued on the
   `document_generation` queue. If queueing fails (e.g. Redis down) the upload
   still succeeds; the document stays `pending` and the failure is logged.
2. **Celery task (T094)**: loads the task, its code files (via FileStorage) and
   the upload's language/complexity; skips if the document is already
   `completed` or `in_progress`; calls `doc.start(celery_task_id)`, then
   `DocumentGenerationService.generate(...)` (T093), then `doc.complete(content)`.
   On `DocumentGenerationError` → `doc.fail("<reason>: <detail>")`. On Celery's
   soft time limit (270 s, constitution V) or any unexpected error →
   `doc.fail("timeout: …")` / `doc.fail("internal_error: …")`. Never re-raises
   in a way that makes Celery retry (the service already retried).
3. **Stale runs (T095)**: a document still `in_progress` more than 300 s after
   `generation_started_at` (the hard task limit) is reported as `failed` with
   reason `timeout` by the status endpoint (and may be stored as failed).

`generation_error` is stored as `"<reason>: <english detail>"`; the API only
ever shows the Korean message for the reason (below), never the detail.

## Status object

```json
{
  "task_id": "uuid",
  "status": "in_progress",
  "started_at": "2026-11-18T01:00:00+00:00",
  "completed_at": null,
  "estimated_seconds_remaining": 95,
  "error": null
}
```
- `status`: `pending | in_progress | completed | failed`.
- `estimated_seconds_remaining` (FR-024): only for `pending` / `in_progress`,
  otherwise `null`. Expected total = `clamp(30 + 0.3 × total_lines, 30, 180)`
  seconds (`total_lines` from the task's uploaded code). `pending` → the
  expected total; `in_progress` → `max(expected − elapsed, 5)`; integer seconds.
- `error`: `null` unless `failed`, then `{ "reason": "...", "message": "..." }`:

| reason | message (Korean, from `error_messages.py` `DOCUMENT_MESSAGES`) |
|---|---|
| `ai_unavailable` | AI 서비스가 잠시 응답하지 않아 학습 문서를 만들지 못했습니다. 잠시 후 다시 시도하세요. |
| `ai_rejected` | 이 코드로는 학습 문서를 만들 수 없습니다. 코드를 확인한 뒤 다시 업로드하세요. |
| `invalid_content` | 학습 문서를 만드는 중 문제가 생겼습니다. 다시 시도하세요. |
| `timeout` | 학습 문서를 만드는 데 시간이 너무 오래 걸렸습니다. 다시 시도하세요. |
| `internal_error` (and any unknown reason) | 학습 문서를 만드는 중 오류가 발생했습니다. 다시 시도하세요. |

## Endpoints

### GET /tasks/{task_id}/document/status  (T098)
- `200` → Status object · `403` · `404 not_found` (task) ·
  `404 document_not_found` ("이 태스크의 학습 문서가 없습니다.") when the task has
  no document row (tasks created before T096).

### GET /tasks/{task_id}/document  (T097)
```json
{
  "task_id": "uuid",
  "status": "completed",
  "completed_at": "2026-11-18T01:02:00+00:00",
  "content": { "chapter1": { "title": "이 코드가 하는 일", "summary": "…" }, "…": "…", "chapter7": { } }
}
```
- `content` is exactly the stored JSONB (structure: `backend/src/services/ai/document_schema.py`,
  chapters 1–7 as in data-model.md; chapter 3 `file_breakdown` is a list of
  `{file_path, role}`; chapter 4 `explanations[]` has `file_path, line_start,
  line_end, code, what_it_does, syntax_breakdown, analogy, alternative_example, notes`).
- `200` only when `completed`. Otherwise `409 document_not_ready`
  ("학습 문서가 아직 준비되지 않았습니다.") with `details.status` set to the current
  status. · `403` · `404 not_found` · `404 document_not_found`.

### POST /tasks/{task_id}/document/regenerate
Lets the user try again after a failure (T114).
- Allowed only when the status is `failed` (including a stale run reported as
  failed). The backend adds a `LearningDocument` method that moves
  `failed`/stale `in_progress` → `pending` (clearing error, times and
  `celery_task_id`; never touching a `completed` document), commits, then
  queues `generate_document` again exactly as in step 1.
- `202` → Status object (status `pending`) · `409 document_not_failed`
  ("실패한 학습 문서만 다시 만들 수 있습니다.") otherwise · `403` · `404`.

## Frontend rules tied to this contract

- Code panel content comes from the existing `GET /tasks/{task_id}/code` (tasks-api.md).
- Poll `GET …/document/status` every 3 s while `pending` / `in_progress`
  (TanStack Query `refetchInterval`), stop on `completed` / `failed`, then
  fetch `GET …/document` once when `completed`.
- Generating state (CHK086 #3): ⏳ "학습 문서 생성 중..." /
  "AI가 코드를 분석하고 초보자용 설명을 작성하고 있습니다." / a progress
  indicator / "약 N분 남음" (`ceil(seconds/60)`; under 60 s → "1분 이내").
  The user may leave the page and come back (edge case: >3 minutes).
- Failed state: show `error.message` and a "다시 만들기" button that calls
  regenerate, then resumes polling.
- Document view (T105): two columns — code (Monaco, read-only, T099/T100) on
  the left, explanation (chapter navigation, T101) on the right; stacked on
  narrow screens. Chapter 4 items are linked to code lines: clicking an
  explanation highlights its lines in the code panel, and scrolling the code
  panel scrolls the explanation panel to the chapter-4 item covering the top
  visible line (T112).
- Chapters 1, 2, 4 have dedicated components (T102–T104); chapters 3, 5, 6, 7
  may use a simple shared renderer for now (chapter 3's Mermaid text may be
  shown as preformatted text).
- Monaco must be bundled locally (no CDN) and loaded lazily (`React.lazy` /
  dynamic import) so the main bundle does not grow.
