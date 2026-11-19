# Tasks API Contract (T067–T083)

Shared agreement between the backend (T067–T075) and frontend (T076–T083).
Change it only together. Base URL, cookies and the error body are as in
`auth-api.md` / `projects-api.md`. Every endpoint requires sign-in
(`401 unauthorized | token_expired | session_expired`).

Ownership: a task belongs to the user who owns its project. Another user's
task or project → `403 forbidden`; a task or project that is missing or in the
trash → `404 not_found`. A non-UUID id → `400 validation_error` (field = the
path parameter name).

## Task object (response body)

```json
{
  "id": "uuid",
  "project_id": "uuid",
  "task_number": 1,
  "title": "할 일 추가 기능",
  "description": "버튼을 누르면 목록에 추가",
  "upload_method": "file",
  "created_at": "2026-11-16T01:00:00+00:00",
  "updated_at": "2026-11-16T01:00:00+00:00",
  "code": {
    "detected_language": "javascript",
    "complexity_level": "beginner",
    "total_lines": 42,
    "total_files": 2,
    "upload_size_bytes": 1830
  }
}
```
- `description` may be `null`. `upload_method` is `"file" | "folder" | "paste"`.
- `code` is never `null` for tasks created through this API (code is uploaded
  together with the task). `detected_language` / `complexity_level` may be
  `null` (the frontend shows "분석 중" for null).
- `detected_language` is one of: `python, javascript, typescript, html, css,
  java, c, cpp, markdown, text` (backend `SUPPORTED_LANGUAGES`, T065).
- `complexity_level` is one of `beginner, intermediate, advanced` (T066).
- Never include `user_id`, `storage_path` or trash fields.

## Upload result (POST response only)

Task object plus:
```json
{
  "files": [
    { "id": "uuid", "file_name": "App.jsx", "file_path": "src/App.jsx",
      "file_extension": ".jsx", "file_size_bytes": 1240, "language": "javascript" }
  ],
  "excluded_paths": ["node_modules/react/index.js", ".git/config"]
}
```
- `files` are ordered by `file_path`, then `file_name` (CodeFile ordering, T063).
- `file_path` is the relative path inside an uploaded folder, otherwise the file name.
- `excluded_paths` lists files dropped by FR-017 (`.git`, `node_modules`,
  `.DS_Store`, `__pycache__`); `[]` when nothing was dropped.

## Endpoints

### GET /projects/{project_id}/tasks
- `200` → array of Task objects: the project's tasks outside the trash,
  **task_number ascending** (FR-003). · `403` · `404`

### POST /projects/{project_id}/tasks  (multipart/form-data)
Form fields:

| field | when | rule |
|---|---|---|
| `title` | always | 5–255 characters after trimming |
| `description` | optional | at most 500 characters; empty → `null` |
| `upload_method` | always | `file`, `folder` or `paste` |
| `files` | `file`, `folder` | one part per file, repeated field name `files`. For folders the part's **filename is the relative path** (`webkitRelativePath`, e.g. `my-app/src/App.jsx`). |
| `code` | `paste` | the pasted text, not blank |
| `language` | `paste` | required; one of the 10 languages above (including `text`) |

- `201` → Upload result. The new task gets the project's next `task_number`
  (highest + 1, trashed tasks included; T061), and the project's
  `last_activity_at` is set to now.
- Paste uploads are stored as one file named `pasted<ext>` where `<ext>` is
  the language's first extension (`python → .py`, `javascript → .js`,
  `typescript → .ts`, `html → .html`, `css → .css`, `java → .java`, `c → .c`,
  `cpp → .cpp`, `markdown → .md`, `text → .txt`). For paste uploads the chosen
  `language` is stored as `detected_language` (no detection).
- Checks run in this order and stop at the first failure (T064 `validate_upload`):
  excluded paths are dropped → file count → total size → each file's path,
  extension, binary content and encoding.
- Errors (all use the shared error body):

| status | error | message (Korean, from `error_messages.py`) | details |
|---|---|---|---|
| 400 | `validation_error` | shared validation message | `fields[]` with `field` = `title` ("태스크 제목은 최소 5자 이상이어야 합니다." / "태스크 제목은 최대 255자까지 입력할 수 있습니다."), `description` ("태스크 설명은 최대 500자까지 입력할 수 있습니다."), `upload_method`, `code` ("붙여넣을 코드를 입력하세요."), `language` ("프로그래밍 언어를 선택하세요.") |
| 400 | `no_files` | 업로드할 파일이 없습니다. | — (also when every file was excluded) |
| 400 | `too_many_files` | 한 번에 최대 20개 파일까지 업로드할 수 있습니다. | `max_files`, `uploaded_files` |
| 413 | `file_too_large` | 파일 크기가 10MB를 초과합니다. | `max_size_mb`, `uploaded_size_mb` |
| 400 | `unsupported_file_type` | 지원하지 않는 파일 형식입니다. | `file_name`, `extension`, `supported_extensions` |
| 400 | `binary_file` | 소스 코드 텍스트 파일만 업로드할 수 있습니다. | `file_name` |
| 400 | `unsupported_encoding` | 파일의 문자 인코딩을 읽을 수 없습니다. | `file_name` (suggestion: UTF-8로 저장한 뒤 다시 업로드) |
| 400 | `invalid_file_path` | 파일 경로가 올바르지 않습니다. | `file_name` (absolute paths or `..` segments) |
| 403 / 404 | | project ownership as above | |

  Every error also carries `suggestion` (T064 `UPLOAD_SUGGESTIONS`).

### GET /tasks/{task_id}
- `200` → Task object · `403` · `404`

### PATCH /tasks/{task_id}
Body (JSON): any of `{ "title": string, "description": string | null }`.
- `task_number`, `upload_method` and the code cannot be changed (FR-004).
- A field left out stays; `"description": null` or `""` clears it.
- `200` → Task object · `400 validation_error` (same field messages) · `403` · `404`
- Updates the project's `last_activity_at`.

### DELETE /tasks/{task_id}
Moves the task to the trash (30 days, `SoftDeleteMixin`). Files stay on disk
until permanent deletion.
- `204` · `403` · `404` · updates the project's `last_activity_at`.

### GET /tasks/{task_id}/code
```json
{
  "task_id": "uuid",
  "detected_language": "javascript",
  "files": [
    { "id": "uuid", "file_name": "App.jsx", "file_path": "src/App.jsx",
      "file_extension": ".jsx", "file_size_bytes": 1240,
      "language": "javascript", "content": "export default function App() {...}\n" }
  ]
}
```
- Same file order as the upload result. `content` is UTF-8 text with LF line endings.
- `200` · `403` · `404` · `404 file_missing` ("코드 파일을 찾을 수 없습니다. 다시 업로드하세요.")
  when a stored file is gone from disk.

## Project object change

`task_count` in the Project object (projects-api.md) now counts the project's
tasks outside the trash. `completed_task_count` stays `0` until progress
tracking exists (US4).

## Backend rules tied to this contract

- Storage (T067): `{UPLOAD_DIR}/{user_id}/{task_id}/{uuid}{ext}`; `UPLOAD_DIR`
  from the environment (`.env.example`, default `./storage/uploads`). Stored
  content is the decoded text re-encoded as UTF-8 with LF line endings.
- Decoding: UTF-8 (BOM allowed), then CP949; neither → `unsupported_encoding`.
- Atomic upload (requirements-addendum): if the database work fails after files
  were written, delete the written files.
- Task numbers: lock the project row (`SELECT … FOR UPDATE`) before reading
  the next number, so concurrent creates cannot collide.
- Analysis (language T065, complexity T066) runs during the request in a worker
  thread (`asyncio.to_thread`) for the MVP. Moving it to Celery is deferred to the
  document-generation phase.
- API routes use only owner-checked service methods (`*_for_user`), like projects.

## Frontend rules tied to this contract

- Allowed extensions, 10MB total and 1–20 files are checked in the browser
  first (same lists as the backend), but the backend stays the authority:
  always show `error.message` (and `suggestion`) from the API.
- Folder upload (T077) drops FR-017 paths before sending and shows
  "제외된 폴더: .git, node_modules, __pycache__" (only the names that occurred).
- Paste (T078): the language selector is required; Korean labels
  (Python, JavaScript, TypeScript, HTML, CSS, Java, C, C++, Markdown, 일반 텍스트).
- Empty task list (CHK086): 📝 "아직 태스크가 없습니다" / "코드를 업로드하고 학습
  자료를 생성하려면 태스크를 추가하세요." / button "첫 태스크 추가" /
  "💡 팁: 작은 코드 단위로 나누어 학습하면 이해가 쉬워집니다."
- After creating (FR-019): the modal shows a confirmation listing every uploaded
  file (and excluded paths, if any) with a "태스크 보기" button that goes to the
  task page; toast "태스크가 생성되었습니다." (top-right, 3 s); the task list and
  the project (task_count) are refetched.
- After deleting a task: toast "태스크가 삭제되었습니다.".
- Task cards (T079) show "Task {task_number}", the title, the created date,
  the language (or "분석 중") and link to `/tasks/{id}`.
