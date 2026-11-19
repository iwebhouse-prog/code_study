from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.exceptions import UnauthorizedError
from src.config import AppConfig
from src.db.session import get_db_session
from src.models import User
from src.services.auth.token_service import SessionExpiredError, TokenService
from src.services.auth.user_service import UserService
from src.services.code_analysis.code_upload_service import CodeUploadService
from src.services.code_analysis.file_storage import FileStorage
from src.services.document.document_queue_service import DocumentQueueService
from src.services.project_service import ProjectService
from src.services.task_service import TaskService
from src.utils.jwt import JWTConfig

ACCESS_TOKEN_COOKIE = "access_token"  # noqa: S105 - a cookie name, not a secret
REFRESH_TOKEN_COOKIE = "refresh_token"  # noqa: S105 - a cookie name, not a secret

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_jwt_config(request: Request) -> JWTConfig:
    config: JWTConfig = request.app.state.jwt_config
    return config


def get_app_config(request: Request) -> AppConfig:
    config: AppConfig = request.app.state.app_config
    return config


def get_token_service(
    session: DbSession, config: Annotated[JWTConfig, Depends(get_jwt_config)]
) -> TokenService:
    return TokenService(session, config)


def get_user_service(session: DbSession) -> UserService:
    return UserService(session)


def get_project_service(session: DbSession) -> ProjectService:
    return ProjectService(session)


def get_task_service(session: DbSession) -> TaskService:
    return TaskService(session)


def get_file_storage(request: Request) -> FileStorage:
    return FileStorage(get_app_config(request).upload_dir)


FileStorageDep = Annotated[FileStorage, Depends(get_file_storage)]


def get_document_queue_service(session: DbSession) -> DocumentQueueService:
    return DocumentQueueService(session)


DocumentQueueServiceDep = Annotated[
    DocumentQueueService, Depends(get_document_queue_service)
]


def get_code_upload_service(
    session: DbSession, storage: FileStorageDep, queue: DocumentQueueServiceDep
) -> CodeUploadService:
    return CodeUploadService(session, storage, queue)


AppConfigDep = Annotated[AppConfig, Depends(get_app_config)]
JWTConfigDep = Annotated[JWTConfig, Depends(get_jwt_config)]
TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
CodeUploadServiceDep = Annotated[CodeUploadService, Depends(get_code_upload_service)]


async def get_current_user(
    token_service: TokenServiceDep,
    user_service: UserServiceDep,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_TOKEN_COOKIE)] = None,
) -> User:
    """Route protection: add `user: CurrentUser` to a route to require sign-in.

    Reads only the HTTPOnly cookie (research.md section 8). Loads the user as
    well, because a token stays valid for 15 minutes after an account is deleted.
    """
    if not access_token:
        raise UnauthorizedError()
    user_id = token_service.verify_access_token(access_token)
    user = await user_service.get_by_id(user_id)
    if user is None:
        raise SessionExpiredError()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
