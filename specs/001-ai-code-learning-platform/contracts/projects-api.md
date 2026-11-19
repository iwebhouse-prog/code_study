# Projects API Contract (T046–T056)

Shared agreement between the backend (T046–T050) and frontend (T051–T056).
Change it only together. Base URL and cookies as in `auth-api.md`; every endpoint
requires sign-in (`CurrentUser`): `401 unauthorized | token_expired | session_expired`.

## Project object (response body)

```json
{
  "id": "uuid",
  "title": "My Todo App",
  "description": "할 일 앱 만들기",
  "created_at": "2026-11-10T01:00:00+00:00",
  "updated_at": "2026-11-10T01:00:00+00:00",
  "last_activity_at": "2026-11-10T01:00:00+00:00",
  "task_count": 0,
  "completed_task_count": 0
}
```
- `description` may be `null`.
- `task_count` / `completed_task_count` are always `0` until tasks exist (T061+); they are
  in the contract now so the dashboard (US4: "2/5 tasks completed") does not change shape later.
- Never include `user_id` or trash fields.

## Endpoints (backend uses only the `*_for_user` ProjectService methods for one project)

All errors use the shared body `{ "error", "message", "details"?, "suggestion"? }` (T016).

### GET /projects
- `200` → array of Project objects: the user's projects outside the trash, most recent activity first.

### POST /projects
Body `{ "title": string, "description"?: string | null }`
- `201` → Project object
- `400 validation_error` → `details.fields[]` with `field` = `title`
  ("프로젝트 제목은 최소 1자 이상이어야 합니다." / 255 characters at most)

### GET /projects/{project_id}
- `200` → Project object
- `403 forbidden` ("이 프로젝트에 접근할 권한이 없습니다.") · `404 not_found` (missing or in the trash)
- a `project_id` that is not a UUID → `400 validation_error` with `field` = `project_id`

### PATCH /projects/{project_id}
Body: any of `{ "title": string, "description": string | null }`
- A field left out stays as it is; `"description": null` or `""` clears it.
- `200` → updated Project object · `400 validation_error` · `403` · `404`

### DELETE /projects/{project_id}
Moves the project to the trash (30 days, T043).
- `204` · `403` · `404`

## Frontend rules tied to this contract (CHK085, CHK086)

- Empty dashboard: 📁 "아직 프로젝트가 없습니다" / "프로젝트를 만들어 AI 코드 학습을 시작하세요. 프로젝트는
  관련된 학습 태스크들을 모아둔 폴더입니다." / button "첫 프로젝트 만들기" / "예: '나의 Todo 앱', '계산기 프로그램'".
- After creating: toast "프로젝트가 생성되었습니다." and go to the project detail page.
- After deleting: toast "프로젝트가 휴지통으로 이동되었습니다." and go to the dashboard.
- Toasts: top-right, 3 seconds, announced to screen readers (ARIA live region).
- Confirm deletion inside the page (a dialog component), never `window.confirm`.
- Show `error.message` from the API; show `fieldErrors.title` next to the title input.
