"""Development-only endpoint for trying the shared error responses (T016)."""

from typing import Literal

from fastapi import APIRouter, Query

from src.api.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError

ERRORS: dict[str, type[AppError]] = {
    "notfound": NotFoundError,
    "forbidden": ForbiddenError,
    "conflict": ConflictError,
}

router = APIRouter()


@router.get("/test-errors", tags=["dev"])
async def test_errors(
    error_type: Literal["notfound", "forbidden", "conflict"] | None = Query(
        default=None, alias="type"
    ),
) -> dict[str, str]:
    if error_type is not None:
        raise ERRORS[error_type]()
    return {"status": "ok", "message": "오류 없음"}
