from fastapi import APIRouter
from pydantic import BaseModel

from src.api import auth, documents, projects, tasks, test_errors
from src.api.health import health_response

API_PREFIX = "/api/v1"
API_NAME = "AI Code Learning Platform API"


class ApiInfo(BaseModel):
    name: str
    version: str


def create_api_router(include_dev_routes: bool = False) -> APIRouter:
    """Builds the /api/v1 router; feature routers are included here.

    A new router per call keeps apps created in tests independent.
    """
    router = APIRouter(prefix=API_PREFIX)

    @router.get("", tags=["meta"])
    async def api_info() -> ApiInfo:
        return ApiInfo(name=API_NAME, version="v1")

    router.add_api_route(
        "/health",
        health_response,
        tags=["meta"],
        summary="API and database health",
        responses={503: {"description": "Database unavailable"}},
    )

    if include_dev_routes:
        # Never in production: these endpoints exist only to try error responses.
        router.include_router(test_errors.router)

    router.include_router(auth.router, prefix="/auth", tags=["auth"])
    router.include_router(projects.router, prefix="/projects", tags=["projects"])
    # Task paths start with /projects/{id}/tasks and /tasks/{id}, so no prefix.
    router.include_router(tasks.router, tags=["tasks"])
    router.include_router(documents.router, tags=["documents"])
    # Further feature routers join here as they are built.
    return router
