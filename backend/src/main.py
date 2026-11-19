"""FastAPI application factory.

Run with: uvicorn src.main:create_app --factory --reload --port 8000
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.exceptions import UnhandledErrorMiddleware, register_exception_handlers
from src.api.health import health_response
from src.api.middleware import SecurityHeadersMiddleware
from src.api.router import create_api_router
from src.config import AppConfig
from src.db.config import DatabaseConfig, connect_database
from src.db.session import Database, close_database
from src.utils.jwt import JWTConfig

CORS_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
CORS_HEADERS = ["Content-Type"]


def create_app(
    app_config: AppConfig | None = None,
    db_config: DatabaseConfig | None = None,
    jwt_config: JWTConfig | None = None,
    connect: Callable[[DatabaseConfig], Awaitable[Database]] = connect_database,
) -> FastAPI:
    # Read every setting now so a bad .env stops the server before it listens.
    app_config = app_config or AppConfig.from_env()
    db_config = db_config or DatabaseConfig.from_env()
    jwt_config = jwt_config or JWTConfig.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = await connect(db_config)
        try:
            yield
        finally:
            await close_database()

    docs_enabled = not app_config.is_production
    app = FastAPI(
        title="AI Code Learning Platform API",
        debug=app_config.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.app_config = app_config
    app.state.jwt_config = jwt_config
    register_exception_handlers(app)

    # Starlette runs the last-added middleware first; CORS goes outermost so
    # preflight requests are answered before anything else runs, and the
    # unhandled-error middleware goes innermost so its 500 gets every header.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, hsts=app_config.is_production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_config.allowed_origins),
        allow_credentials=True,  # access/refresh tokens travel in HTTPOnly cookies
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
    )

    # Monitoring endpoint, kept out of the API docs; /api/v1/health is the
    # documented twin the frontend calls.
    app.add_api_route("/health", health_response, include_in_schema=False)

    app.include_router(create_api_router(include_dev_routes=docs_enabled))
    return app
