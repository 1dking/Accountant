"""Root conftest: test client, auth helpers, and database fixtures.

Database backend is chosen automatically:
  - If ``TEST_DATABASE_URL`` env var is set → use that (PostgreSQL via asyncpg).
  - Otherwise → fresh in-memory SQLite per test.

PostgreSQL gives true concurrent-write testing.  SQLite is the zero-config
default for local development.
"""

import asyncio
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import AsyncGenerator

# Set test secret BEFORE any Settings() instantiation so decode_token()
# (which creates its own Settings()) uses the same key as our test tokens.
os.environ["SECRET_KEY"] = "test-secret-key-for-deterministic-tokens"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.auth.models import Role, User
from app.auth.utils import create_access_token, hash_password
from app.config import Settings
from app.database import Base

# ---------------------------------------------------------------------------
# Database backend detection
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
USE_POSTGRES = TEST_DATABASE_URL.startswith("postgresql")

# Expose a flag so test files can conditionally skip.
USING_SQLITE = not USE_POSTGRES

# ---------------------------------------------------------------------------
# Settings override — deterministic secret, test storage paths
# ---------------------------------------------------------------------------

TEST_SETTINGS = Settings(
    database_url=TEST_DATABASE_URL if USE_POSTGRES else "sqlite+aiosqlite:///:memory:",
    secret_key="test-secret-key-for-deterministic-tokens",
    storage_path="./test_data/documents",
    recordings_storage_path="./test_data/recordings",
)


# ---------------------------------------------------------------------------
# Import all models so Base.metadata knows every table
# ---------------------------------------------------------------------------

def _import_all_models():
    import app.auth.models  # noqa
    import app.documents.models  # noqa
    import app.collaboration.models  # noqa
    import app.notifications.models  # noqa
    import app.calendar.models  # noqa
    import app.accounting.models  # noqa
    import app.contacts.models  # noqa
    import app.invoicing.models  # noqa
    import app.income.models  # noqa
    import app.recurring.models  # noqa
    import app.budgets.models  # noqa
    import app.email.models  # noqa
    import app.integrations.gmail.models  # noqa
    import app.integrations.plaid.models  # noqa
    import app.integrations.plaid.categorization_models  # noqa
    import app.integrations.stripe.models  # noqa
    import app.integrations.twilio.models  # noqa
    import app.estimates.models  # noqa
    import app.invoicing.reminder_models  # noqa
    import app.invoicing.credit_models  # noqa
    import app.integrations.settings_models  # noqa
    import app.accounting.period_models  # noqa
    import app.accounting.tax_models  # noqa
    import app.cashbook.models  # noqa
    import app.meetings.models  # noqa
    import app.office.models  # noqa
    import app.settings.models  # noqa
    import app.public.models  # noqa
    import app.proposals.models  # noqa
    import app.core.idempotency  # noqa


_import_all_models()


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Per-test engine + session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def engine():
    """Create a test engine.

    SQLite:      in-memory + StaticPool (single connection, complete isolation).
    PostgreSQL:  real connection pool; tables are created then dropped per test.
    """
    from app.database import _json_serializer

    if USE_POSTGRES:
        eng = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            json_serializer=_json_serializer,
            pool_size=10,
            max_overflow=20,
        )
    else:
        eng = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            json_serializer=_json_serializer,
        )

        @event.listens_for(eng.sync_engine, "connect")
        def _set_pragma(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Create all tables
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    # Tear down: drop all tables (PostgreSQL needs this for isolation)
    if USE_POSTGRES:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    await eng.dispose()


@pytest_asyncio.fixture()
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture()
async def db(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# App + client
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def app(engine, session_factory):
    from app.main import create_app

    application = create_app()
    application.state.settings = TEST_SETTINGS
    application.state.engine = engine
    application.state.session_factory = session_factory

    from app import dependencies as deps

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    application.dependency_overrides[deps.get_db] = _override_get_db
    return application


@pytest_asyncio.fixture()
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def admin_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test Admin",
        role=Role.ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture()
async def accountant_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="accountant@test.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test Accountant",
        role=Role.ACCOUNTANT,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture()
async def viewer_user(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="viewer@test.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test Viewer",
        role=Role.VIEWER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def auth_header(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role.value, TEST_SETTINGS)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Common data fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def sample_contact(db: AsyncSession, admin_user: User):
    from app.contacts.models import Contact, ContactType

    contact = Contact(
        id=uuid.uuid4(),
        type=ContactType.CLIENT,
        company_name="Acme Corp",
        contact_name="John Doe",
        email="john@acme.com",
        phone="+1-555-0100",
        country="US",
        created_by=admin_user.id,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@pytest_asyncio.fixture()
async def sample_vendor(db: AsyncSession, admin_user: User):
    from app.contacts.models import Contact, ContactType

    contact = Contact(
        id=uuid.uuid4(),
        type=ContactType.VENDOR,
        company_name="SupplyCo",
        contact_name="Jane Smith",
        email="jane@supplyco.com",
        country="US",
        created_by=admin_user.id,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@pytest_asyncio.fixture()
async def sample_invoice(db: AsyncSession, admin_user: User, sample_contact):
    from app.invoicing.models import Invoice, InvoiceLineItem, InvoiceStatus

    invoice = Invoice(
        id=uuid.uuid4(),
        invoice_number="INV-0001",
        contact_id=sample_contact.id,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status=InvoiceStatus.DRAFT,
        subtotal=Decimal("1500.00"),
        tax_rate=Decimal("10.00"),
        tax_amount=Decimal("150.00"),
        discount_amount=Decimal("0.00"),
        total=Decimal("1650.00"),
        currency="USD",
        created_by=admin_user.id,
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    item = InvoiceLineItem(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        description="Consulting Services",
        quantity=Decimal("10.0000"),
        unit_price=Decimal("150.00"),
        tax_rate=Decimal("10.00"),
        total=Decimal("1500.00"),
    )
    db.add(item)
    await db.commit()
    return invoice


@pytest_asyncio.fixture()
async def sample_payment_account(db: AsyncSession, admin_user: User):
    from app.cashbook.models import AccountType, PaymentAccount

    account = PaymentAccount(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        name="Business Checking",
        account_type=AccountType.BANK,
        opening_balance=Decimal("10000.00"),
        opening_balance_date=date.today() - timedelta(days=365),
        is_active=True,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


# ---------------------------------------------------------------------------
# Test severity markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line("markers", "critical: CRITICAL priority — blocks deployment")
    config.addinivalue_line("markers", "high: HIGH priority — blocks deployment")
    config.addinivalue_line("markers", "normal: NORMAL priority — warning only")
