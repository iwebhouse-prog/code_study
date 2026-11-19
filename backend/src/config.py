import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENTS = ("development", "test", "production")
# Browsers send Origin as scheme://host[:port] with no path or trailing slash.
ORIGIN_PATTERN = re.compile(r"https?://[^/\s]+")
TRUE_VALUES = ("true", "1")
FALSE_VALUES = ("false", "0")


def load_env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    """Returns `env` as given, or the process environment merged with .env."""
    if env is not None:
        return env
    # Real environment variables win over the repository-root .env file.
    load_dotenv(REPO_ROOT / ".env", override=False)
    return os.environ


@dataclass(frozen=True)
class AppConfig:
    environment: str = "development"
    debug: bool = False
    allowed_origins: tuple[str, ...] = ()
    upload_dir: Path = REPO_ROOT / "storage" / "uploads"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        env = load_env(env)

        environment = env.get("ENVIRONMENT", cls.environment)
        if environment not in ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT must be one of {', '.join(ENVIRONMENTS)}, "
                f"got {environment!r}"
            )

        debug = _flag(env, "DEBUG", cls.debug)
        if debug and environment == "production":
            raise ValueError("DEBUG must be false when ENVIRONMENT is production")

        origins = tuple(
            origin.strip()
            for origin in env.get("ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        )
        for origin in origins:
            _check_origin(origin, environment)

        return cls(
            environment=environment,
            debug=debug,
            allowed_origins=origins,
            upload_dir=_upload_dir(env),
        )


def _upload_dir(env: Mapping[str, str]) -> Path:
    raw = env.get("UPLOAD_DIR", "").strip()
    if not raw:
        return AppConfig.upload_dir
    # A relative path means relative to the repository, not to wherever the
    # server happens to be started from.
    return REPO_ROOT / raw


def _flag(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        return default
    if raw.lower() in TRUE_VALUES:
        return True
    if raw.lower() in FALSE_VALUES:
        return False
    raise ValueError(f"{key} must be true or false, got {raw!r}")


def _check_origin(origin: str, environment: str) -> None:
    if origin == "*":
        raise ValueError(
            "ALLOWED_ORIGINS must list exact origins, not '*': "
            "browsers refuse cookies for wildcard origins"
        )
    if not ORIGIN_PATTERN.fullmatch(origin):
        raise ValueError(
            "ALLOWED_ORIGINS entries must look like http://localhost:5173 "
            f"(no path or trailing slash), got {origin!r}"
        )
    if environment == "production" and not origin.startswith("https://"):
        raise ValueError(
            f"ALLOWED_ORIGINS must use https in production, got {origin!r}"
        )
