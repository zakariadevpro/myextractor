import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.organization import Organization
from app.models.user import User


def _build_test_db_url(database_url: str) -> str:
    url = make_url(database_url)
    database_name = url.database or "winaity"
    if not database_name.endswith("_test"):
        database_name = f"{database_name}_test"
    return url.set(database=database_name).render_as_string(hide_password=False)


def _build_admin_db_url(database_url: str) -> str:
    url = make_url(database_url)
    admin_db = "template1" if url.database == "postgres" else "postgres"
    return url.set(database=admin_db).render_as_string(hide_password=False)


TEST_DB_URL = _build_test_db_url(settings.database_url)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def ensure_test_database_exists():
    admin_engine = create_async_engine(
        _build_admin_db_url(settings.database_url),
        isolation_level="AUTOCOMMIT",
    )
    test_db_name = make_url(TEST_DB_URL).database
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": test_db_name},
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{test_db_name}"'))
    await admin_engine.dispose()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def _get_test_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_test_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_org(db_session: AsyncSession) -> Organization:
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:6]}")
    db_session.add(org)
    await db_session.flush()
    return org


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession, test_org: Organization) -> User:
    user = User(
        organization_id=test_org.id,
        email=f"test-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=hash_password("testpassword"),
        first_name="Test",
        last_name="User",
        role="admin",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
def auth_headers(test_user: User) -> dict:
    token = create_access_token(
        {"sub": str(test_user.id), "org": str(test_user.organization_id), "role": test_user.role}
    )
    return {"Authorization": f"Bearer {token}"}
