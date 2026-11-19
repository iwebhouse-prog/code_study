"""Auth endpoints (T028-T031); the contract is contracts/auth-api.md."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Cookie, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.api.dependencies import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    AppConfigDep,
    CurrentUser,
    JWTConfigDep,
    TokenServiceDep,
    UserServiceDep,
)
from src.api.exceptions import ErrorResponse, error_response
from src.models import User
from src.services.auth.token_service import SessionExpiredError, TokenPair
from src.utils.jwt import JWTConfig

# Must equal API_PREFIX + "/auth" (router.py): the refresh cookie travels only
# to the auth endpoints. Not imported from router.py, which imports this module.
AUTH_COOKIE_PATH = "/api/v1/auth"

# Starlette writes this value as given; the contract spells it "Strict".
SAME_SITE = cast(Literal["strict"], "Strict")

router = APIRouter()


class Credentials(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    """The User object of the contract; never carries the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    skill_level: str | None
    created_at: datetime
    last_login_at: datetime | None


def set_auth_cookies(
    response: Response, pair: TokenPair, config: JWTConfig, *, secure: bool
) -> None:
    """The one place that decides how auth cookies look (T201 adjusts flags here)."""
    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        pair.access_token,
        max_age=int(config.access_token_expire.total_seconds()),
        path="/",
        secure=secure,
        httponly=True,
        samesite=SAME_SITE,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        pair.refresh_token,
        max_age=int(config.refresh_token_expire.total_seconds()),
        path=AUTH_COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite=SAME_SITE,
    )


def clear_auth_cookies(response: Response, *, secure: bool) -> None:
    # A cookie is removed only by the name and path it was set with.
    for name, path in (
        (ACCESS_TOKEN_COOKIE, "/"),
        (REFRESH_TOKEN_COOKIE, AUTH_COOKIE_PATH),
    ):
        response.delete_cookie(
            name, path=path, secure=secure, httponly=True, samesite=SAME_SITE
        )


async def _sign_in(
    user: User,
    response: Response,
    token_service: TokenServiceDep,
    config: JWTConfigDep,
    app_config: AppConfigDep,
) -> UserResponse:
    pair = await token_service.issue_tokens(user.id)
    set_auth_cookies(response, pair, config, secure=app_config.is_production)
    return UserResponse.model_validate(user)


@router.post(
    "/register",
    status_code=201,
    summary="Create an account and sign in",
    responses={
        400: {"model": ErrorResponse, "description": "validation_error"},
        409: {"model": ErrorResponse, "description": "email_taken"},
    },
)
async def register(
    body: Credentials,
    response: Response,
    user_service: UserServiceDep,
    token_service: TokenServiceDep,
    config: JWTConfigDep,
    app_config: AppConfigDep,
) -> UserResponse:
    user = await user_service.register(body.email, body.password)
    return await _sign_in(user, response, token_service, config, app_config)


@router.post(
    "/login",
    summary="Sign in",
    responses={
        400: {"model": ErrorResponse, "description": "validation_error"},
        401: {"model": ErrorResponse, "description": "invalid_credentials"},
    },
)
async def login(
    body: Credentials,
    response: Response,
    user_service: UserServiceDep,
    token_service: TokenServiceDep,
    config: JWTConfigDep,
    app_config: AppConfigDep,
) -> UserResponse:
    user = await user_service.login(body.email, body.password)
    return await _sign_in(user, response, token_service, config, app_config)


@router.get(
    "/me",
    summary="Current user",
    responses={401: {"model": ErrorResponse, "description": "not signed in"}},
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=204, summary="Sign out; always succeeds")
async def logout(
    user_service: UserServiceDep,
    app_config: AppConfigDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)] = None,
) -> Response:
    if refresh_token:
        await user_service.logout(refresh_token)
    response = Response(status_code=204)
    clear_auth_cookies(response, secure=app_config.is_production)
    return response


@router.post(
    "/refresh",
    response_model=UserResponse,
    summary="Rotate the refresh token",
    responses={401: {"model": ErrorResponse, "description": "session_expired"}},
)
async def refresh(
    response: Response,
    user_service: UserServiceDep,
    token_service: TokenServiceDep,
    config: JWTConfigDep,
    app_config: AppConfigDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)] = None,
) -> UserResponse | JSONResponse:
    secure = app_config.is_production
    try:
        if not refresh_token:
            raise SessionExpiredError()
        pair = await token_service.rotate(refresh_token)
        user = await user_service.get_by_id(
            token_service.verify_access_token(pair.access_token)
        )
        if user is None:
            raise SessionExpiredError()
    except SessionExpiredError as error:
        # An exception would drop cookies set on `response`, so answer directly.
        failure = error_response(error.status_code, error.error, error.message)
        clear_auth_cookies(failure, secure=secure)
        return failure
    set_auth_cookies(response, pair, config, secure=secure)
    return UserResponse.model_validate(user)
