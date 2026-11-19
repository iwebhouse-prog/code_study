import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeVar

from sqlalchemy.exc import SQLAlchemyError

from src.config import load_env
from src.db.session import Database, init_database

REQUIRED_DRIVER = "postgresql+asyncpg://"

# Startup retry policy from requirements-addendum CHK105.
CONNECT_ATTEMPTS = 3
CONNECT_RETRY_DELAY_SECONDS = 5


class DatabaseUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    """Connection and pool settings; defaults follow requirements-addendum CHK105."""

    url: str
    pool_size: int = 10
    max_overflow: int = 40  # pool_size + max_overflow = 50 connections at most
    pool_timeout: float = 30
    pool_recycle: int = 300
    command_timeout: float = 30

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "DatabaseConfig":
        env = load_env(env)

        url = env.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. Copy .env.example to .env in the "
                "repository root."
            )
        if not url.startswith(REQUIRED_DRIVER):
            raise ValueError(f"DATABASE_URL must start with {REQUIRED_DRIVER}")

        return cls(
            url=url,
            pool_size=_positive(env, "DB_POOL_SIZE", int, cls.pool_size),
            max_overflow=_positive(env, "DB_MAX_OVERFLOW", int, cls.max_overflow),
            pool_timeout=_positive(env, "DB_POOL_TIMEOUT", float, cls.pool_timeout),
            pool_recycle=_positive(env, "DB_POOL_RECYCLE", int, cls.pool_recycle),
            command_timeout=_positive(
                env, "DB_COMMAND_TIMEOUT", float, cls.command_timeout
            ),
        )

    def engine_options(self) -> dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "connect_args": {"command_timeout": self.command_timeout},
        }


Number = TypeVar("Number", int, float)


def _positive(
    env: Mapping[str, str], key: str, cast: Callable[[str], Number], default: Number
) -> Number:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        value = cast(raw)
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None
    if value <= 0:
        raise ValueError(f"{key} must be greater than 0, got {raw!r}")
    return value


async def connect_database(
    config: DatabaseConfig,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Database:
    """Creates the shared Database and waits until PostgreSQL answers."""
    database = init_database(config.url, **config.engine_options())
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            await database.ping()
            return database
        except (OSError, SQLAlchemyError) as error:
            if attempt == CONNECT_ATTEMPTS:
                await database.dispose()
                raise DatabaseUnavailableError(
                    f"Could not connect to the database after {attempt} attempts"
                ) from error
            await sleep(CONNECT_RETRY_DELAY_SECONDS)
    raise AssertionError("unreachable")  # pragma: no cover
