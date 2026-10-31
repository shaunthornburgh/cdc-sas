"""Test setup.

Uses a separate Postgres database (`<db>_test`), rebuilt from the Alembic migrations at the
start of each run (upgrade -> downgrade -> upgrade, so the downgrade is exercised too).
Each test runs inside a transaction that is rolled back. Redis is replaced by fakeredis.
"""

import os

from sqlalchemy.engine import make_url

_base_url = make_url(
    os.environ.get("DATABASE_URL", "postgresql+psycopg://cdc:cdc@localhost:5432/cdc")
)
TEST_DB_NAME = f"{_base_url.database}_test"
os.environ["DATABASE_URL"] = _base_url.set(database=TEST_DB_NAME).render_as_string(
    hide_password=False
)
os.environ["ENVIRONMENT"] = "test"

# Imports below must come after the env vars above are set.
from collections.abc import Callable, Generator, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from alembic import command  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
from app.db.session import engine, get_db  # noqa: E402
from app.main import app as main_app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import Cargo  # noqa: E402
from app.services.users import create_user  # noqa: E402

TEST_PASSWORD = "test-password-123"
BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    admin = create_engine(_base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin.dispose()

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture
def db() -> Iterator[Session]:
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def make_client(
    db: Session, redis: fakeredis.FakeRedis
) -> Iterator[Callable[[FastAPI], TestClient]]:
    """Build a TestClient for any app, wired to the test DB session and fake Redis."""
    apps: list[FastAPI] = []

    def _make(app: FastAPI) -> TestClient:
        def _get_db() -> Generator[Session, None, None]:
            yield db

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_redis] = lambda: redis
        apps.append(app)
        return TestClient(app)

    yield _make
    for app in apps:
        app.dependency_overrides.clear()


@pytest.fixture
def client(make_client: Callable[[FastAPI], TestClient]) -> TestClient:
    return make_client(main_app)


@pytest.fixture
def make_user(db: Session) -> Callable[..., User]:
    counter = 0

    def _make(cargo: Cargo = Cargo.ASESOR, **kwargs) -> User:
        nonlocal counter
        counter += 1
        kwargs.setdefault("email", f"user{counter}@example.com")
        kwargs.setdefault("full_name", f"User {counter}")
        kwargs.setdefault("password", TEST_PASSWORD)
        return create_user(db, cargo=cargo, **kwargs)

    return _make


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
