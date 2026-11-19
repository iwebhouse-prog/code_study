from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from src.db.session import Database


async def health_response(request: Request) -> JSONResponse:
    """200 when PostgreSQL answers, 503 otherwise.

    Served at /health for monitoring and at /api/v1/health for the frontend.
    """
    database: Database = request.app.state.database
    try:
        await database.ping()
    except (OSError, SQLAlchemyError):
        return JSONResponse(
            {"status": "unavailable", "database": "unavailable"}, status_code=503
        )
    return JSONResponse({"status": "ok", "database": "ok"})
