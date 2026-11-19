# Auth API Contract (T028–T038)

Shared agreement between the backend (T028–T031) and frontend (T032–T038) so
both sides can be built at the same time. Change it only together.

Base URL: `http://localhost:8000/api/v1` (frontend `VITE_API_BASE_URL`).
Use `localhost`, never `127.0.0.1`, on both sides: cookies are tied to the host name.

## Cookies (set by the backend, never readable by JavaScript)

| Name | Value | Path | Max-Age | Flags |
|---|---|---|---|---|
| `access_token` | access JWT (15 min) | `/` | 900 | HttpOnly, SameSite=Strict, Secure in production only |
| `refresh_token` | refresh JWT (7 days) | `/api/v1/auth` | 604800 | HttpOnly, SameSite=Strict, Secure in production only |

`refresh_token` is sent only to `/api/v1/auth/*`, so ordinary API calls never carry it.
Clearing a cookie = `Set-Cookie` with the same name and path and `Max-Age=0`.

## User object (response body)

```json
{
  "id": "uuid",
  "email": "student@example.com",
  "skill_level": "Complete Beginner",
  "created_at": "2026-11-09T01:00:00+00:00",
  "last_login_at": "2026-11-09T01:00:00+00:00"
}
```
`last_login_at` may be `null`. Never include `password_hash`.
Frontend maps it to `AuthUser { id, email, skillLevel }` (stores/auth-store.ts).

## Endpoints

All errors use the shared body `{ "error": code, "message": 한국어, "details"?, "suggestion"? }` (T016).

### POST /auth/register
Body `{ "email": string, "password": string }`
- `201` → User object, **and signs the user in** (sets both cookies). Frontend then goes to the dashboard.
- `400 validation_error` → `details.fields[]` with `field` = `email` or `password` (UserService rules: 8+ chars, letters and digits, ≤72 UTF-8 bytes)
- `409 email_taken`

### POST /auth/login
Body `{ "email": string, "password": string }`
- `200` → User object, sets both cookies
- `400 validation_error` (missing/invalid body)
- `401 invalid_credentials` (same for unknown email and wrong password)

### GET /auth/me
Protected by `CurrentUser` (access cookie).
- `200` → User object
- `401 unauthorized` (no cookie) · `401 token_expired` (refresh then retry) · `401 session_expired` (sign in again)

### POST /auth/logout
No sign-in required; always succeeds.
- `204`, revokes the refresh token from the cookie if any, clears both cookies

### POST /auth/refresh
Reads the `refresh_token` cookie and rotates it (TokenService.rotate).
- `200` → User object, sets both new cookies
- `401 session_expired` (missing, expired, revoked, or reused token); also clears both cookies

## Frontend rules tied to this contract

- Every request uses `withCredentials` (api-client.ts already does).
- On `401 token_expired` **or `401 unauthorized`**, call `POST /auth/refresh` once and retry the original request once.
  `unauthorized` is included because the access cookie's Max-Age equals the token lifetime: after 15 minutes
  the browser drops the cookie, so the server sees no cookie (`unauthorized`) instead of an expired token,
  while the 7-day refresh cookie is still valid (bug found 2026-11-09). If that refresh fails after
  `unauthorized`, report the original `unauthorized`; a real session ending arrives as `session_expired`.
- **Only one refresh request may be in flight at a time** (single-flight), shared per API client even when the
  interceptor is installed more than once (React StrictMode does that in development). Reusing an already rotated
  refresh token is treated as theft and ends every session of the user (T026, confirmed by the user).
- On `401 session_expired` or a failed refresh: `clearUser()` and `queryClient.clear()`, then go to `/login`.
- On page load, `GET /auth/me` decides `authenticated` vs `anonymous` (auth-store starts as `unknown`).
