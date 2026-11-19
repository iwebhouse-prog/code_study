"""User-facing error messages (requirements-addendum CHK084).

Keep every message here so the same error reads the same everywhere.
Messages say what happened and what to do next, in plain Korean.
"""

ERROR_MESSAGES: dict[str, str] = {
    "bad_request": "요청을 처리할 수 없습니다. 입력 내용을 확인한 뒤 다시 시도하세요.",
    "validation_error": (
        "입력값이 올바르지 않습니다. 표시된 항목을 확인한 뒤 다시 시도하세요."
    ),
    "unauthorized": "로그인이 필요합니다. 로그인한 뒤 다시 시도하세요.",
    "forbidden": "이 작업을 할 권한이 없습니다.",
    "not_found": "요청한 페이지를 찾을 수 없습니다.",
    "method_not_allowed": "지원하지 않는 요청 방식입니다.",
    "conflict": "다른 곳에서 먼저 수정되었습니다. 새로고침한 뒤 다시 시도하세요.",
    "email_taken": "이미 가입된 이메일입니다. 로그인하거나 다른 이메일을 사용하세요.",
    "invalid_credentials": (
        "이메일 또는 비밀번호가 올바르지 않습니다. 다시 확인한 뒤 시도하세요."
    ),
    "session_expired": "세션이 만료되었습니다. 다시 로그인하세요.",
    "token_expired": "세션이 만료되었습니다. 잠시 후 다시 시도하세요.",
    "rate_limit_exceeded": "요청이 너무 많습니다. 잠시 후 다시 시도하세요.",
    "internal_error": (
        "서버 오류가 발생했습니다. 잠시 후 다시 시도하세요. "
        "문제가 계속되면 고객지원에 문의하세요."
    ),
    "service_unavailable": (
        "일시적으로 서비스를 이용할 수 없습니다. 잠시 후 다시 시도하세요."
    ),
}

RATE_LIMIT_WITH_WAIT = "요청이 너무 많습니다. {minutes}분 후 다시 시도하세요."

# Per-field messages for request validation, keyed by pydantic error type.
FIELD_MESSAGES: dict[str, str] = {
    "missing": "필수 입력 항목입니다.",
    "string_too_short": "최소 {min_length}자 이상 입력하세요.",
    "string_too_long": "최대 {max_length}자까지 입력할 수 있습니다.",
    "json_invalid": "요청 본문이 올바른 JSON 형식이 아닙니다.",
}
DEFAULT_FIELD_MESSAGE = "올바른 형식이 아닙니다."

# Sign-up rules checked by UserService.
SIGNUP_MESSAGES: dict[str, str] = {
    "invalid_email": "올바른 이메일 형식이 아닙니다.",
    "too_short": "비밀번호는 최소 8자 이상이어야 합니다.",
    "too_long": "비밀번호가 너무 깁니다. 더 짧게 입력하세요.",
    "needs_mix": "비밀번호에 문자와 숫자를 모두 포함하세요.",
}

# Upload rules checked by utils/file_validator.py. The size texts are CHK084's
# own example; the others follow the spec's edge cases (FR-015 to FR-018).
UPLOAD_MESSAGES: dict[str, str] = {
    "unsupported_file_type": "지원하지 않는 파일 형식입니다.",
    "binary_file": "소스 코드 텍스트 파일만 업로드할 수 있습니다.",
    "file_too_large": "파일 크기가 10MB를 초과합니다.",
    "too_many_files": "한 번에 최대 20개 파일까지 업로드할 수 있습니다.",
    "no_files": "업로드할 파일이 없습니다.",
    "unsupported_encoding": "파일의 문자 인코딩을 읽을 수 없습니다.",
    "invalid_file_path": "파일 경로가 올바르지 않습니다.",
}
UPLOAD_SUGGESTIONS: dict[str, str] = {
    "unsupported_file_type": (
        ".py, .js, .ts, .jsx, .tsx, .html, .css, .java, .cpp, .c, .txt, .md "
        "파일만 업로드할 수 있습니다."
    ),
    "binary_file": ".py, .js, .html 같은 텍스트 형식의 코드 파일을 업로드하세요.",
    "file_too_large": (
        "더 작은 파일을 선택하거나 코드를 여러 태스크로 나누어 업로드하세요."
    ),
    "too_many_files": "파일 수를 줄이거나 코드를 여러 태스크로 나누어 업로드하세요.",
    "no_files": "코드 파일을 1개 이상 선택하세요.",
    "unsupported_encoding": "UTF-8로 저장한 뒤 다시 업로드하세요.",
    "invalid_file_path": (
        "폴더 안의 상대 경로로 된 파일만 업로드할 수 있습니다. "
        "경로에 '..'나 절대 경로가 없는지 확인하세요."
    ),
}

# Project rules checked by ProjectService (texts from CHK084 where it gives them).
PROJECT_MESSAGES: dict[str, str] = {
    "title_required": "프로젝트 제목은 최소 1자 이상이어야 합니다.",
    "title_too_long": "프로젝트 제목은 최대 255자까지 입력할 수 있습니다.",
    "forbidden": "이 프로젝트에 접근할 권한이 없습니다.",
    "not_found": (
        "요청한 프로젝트를 찾을 수 없습니다. "
        "삭제되었거나 존재하지 않는 프로젝트입니다."
    ),
}

# Task rules checked by TaskService and the upload service (contracts/tasks-api.md).
TASK_MESSAGES: dict[str, str] = {
    "title_too_short": "태스크 제목은 최소 5자 이상이어야 합니다.",
    "title_too_long": "태스크 제목은 최대 255자까지 입력할 수 있습니다.",
    "description_too_long": "태스크 설명은 최대 500자까지 입력할 수 있습니다.",
    "upload_method_invalid": "업로드 방식을 선택하세요.",
    "code_required": "붙여넣을 코드를 입력하세요.",
    "language_required": "프로그래밍 언어를 선택하세요.",
    "forbidden": "이 태스크에 접근할 권한이 없습니다.",
    "not_found": (
        "요청한 태스크를 찾을 수 없습니다. 삭제되었거나 존재하지 않는 태스크입니다."
    ),
    "file_missing": "코드 파일을 찾을 수 없습니다. 다시 업로드하세요.",
}

# Learning document rules (contracts/documents-api.md). The first five are the
# texts for a failed run's reason; the API never shows the English detail.
DOCUMENT_MESSAGES: dict[str, str] = {
    "ai_unavailable": (
        "AI 서비스가 잠시 응답하지 않아 학습 문서를 만들지 못했습니다. "
        "잠시 후 다시 시도하세요."
    ),
    "ai_rejected": (
        "이 코드로는 학습 문서를 만들 수 없습니다. 코드를 확인한 뒤 다시 업로드하세요."
    ),
    "invalid_content": "학습 문서를 만드는 중 문제가 생겼습니다. 다시 시도하세요.",
    "timeout": "학습 문서를 만드는 데 시간이 너무 오래 걸렸습니다. 다시 시도하세요.",
    "internal_error": "학습 문서를 만드는 중 오류가 발생했습니다. 다시 시도하세요.",
    "document_not_found": "이 태스크의 학습 문서가 없습니다.",
    "document_not_ready": "학습 문서가 아직 준비되지 않았습니다.",
    "document_not_failed": "실패한 학습 문서만 다시 만들 수 있습니다.",
}
