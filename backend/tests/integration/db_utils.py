"""Helpers for integration tests that need a throwaway PostgreSQL database."""

import asyncio
import os
import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import asyncpg
from sqlalchemy.dialects import postgresql

BACKEND_DIR = Path(__file__).resolve().parents[2]
SERVER_DSN = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
TEST_DB = "codelearning_test"
TEST_DSN = f"postgresql://postgres:postgres@127.0.0.1:5432/{TEST_DB}"
TEST_DATABASE_URL = f"postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/{TEST_DB}"


def database_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=1):
            return True
    except OSError:
        return False


async def _recreate_test_database() -> None:
    conn = await asyncpg.connect(SERVER_DSN)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    finally:
        await conn.close()


async def _drop_test_database() -> None:
    conn = await asyncpg.connect(SERVER_DSN)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    finally:
        await conn.close()


def recreate_test_database() -> None:
    asyncio.run(_recreate_test_database())


def drop_test_database() -> None:
    asyncio.run(_drop_test_database())


def run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


async def _fetch(query: str, args: Sequence[Any]) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        return list(await conn.fetch(query, *args))
    finally:
        await conn.close()


def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    return asyncio.run(_fetch(query, args))


async def _execute_script(statements: Sequence[str]) -> None:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        async with conn.transaction():
            for statement in statements:
                await conn.execute(statement)
    finally:
        await conn.close()


def execute_script(*statements: str) -> None:
    """Runs statements in one transaction; raises asyncpg errors on violation."""
    asyncio.run(_execute_script(statements))


def schema_differences(model: Any, stricter: Sequence[str] = ()) -> list[str]:
    """Compares a model with its migrated table; an empty list means they match.

    `stricter` names columns the migration leaves nullable although their
    default always fills them, so the model may declare them NOT NULL.
    Call from a synchronous test: this runs its own event loop.
    """
    rows = fetch(
        "SELECT column_name, data_type, character_maximum_length, is_nullable "
        "FROM information_schema.columns WHERE table_name = $1",
        model.__tablename__,
    )
    db_columns = {row["column_name"]: row for row in rows}
    model_columns = model.__table__.c
    differences = [
        f"only one side has column {name}"
        for name in set(db_columns) ^ set(model_columns.keys())
    ]
    for name in set(db_columns) & set(model_columns.keys()):
        db_column, column = db_columns[name], model_columns[name]
        ddl_type = column.type.compile(dialect=postgresql.dialect()).split("(")[0]
        db_type = db_column["data_type"].upper()
        if ddl_type.replace("VARCHAR", "CHARACTER VARYING") != db_type:
            differences.append(f"{name}: type {ddl_type} vs {db_type}")
        db_length = db_column["character_maximum_length"]
        if getattr(column.type, "length", None) != db_length:
            differences.append(f"{name}: length differs from {db_length}")
        db_nullable = db_column["is_nullable"] == "YES"
        if name not in stricter and column.nullable != db_nullable:
            differences.append(f"{name}: nullable {column.nullable} vs {db_nullable}")
    return differences
