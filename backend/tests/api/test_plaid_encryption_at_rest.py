"""At-rest encryption of Plaid consumer-financial data.

Most tests are synchronous (type-level + raw-SQL migration) so they exercise the
security-critical paths directly. One async test confirms the real ORM model
stores ciphertext.
"""
import uuid
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import app.core.encryption as enc_mod
from app.core.encrypted_types import EncryptedNumeric, EncryptedString
from app.core.encryption import init_encryption_service
from app.integrations.plaid.at_rest import (
    decrypt_existing,
    encrypt_existing,
    load_fernet_or_fail,
)
from tests.conftest import TEST_SETTINGS

# Ephemeral key for the type-level tests (same path the app uses).
init_encryption_service(TEST_SETTINGS.fernet_key)


# ---------------------------------------------------------------------------
# Type-level: encrypt-on-write, decrypt-on-read, fail-closed
# ---------------------------------------------------------------------------

def test_encrypted_string_roundtrip_and_ciphertext():
    col = EncryptedString()
    stored = col.process_bind_param("Starbucks", None)
    assert stored is not None and stored != "Starbucks"          # ciphertext at rest
    assert "Starbucks" not in stored                              # plaintext not present
    assert col.process_result_value(stored, None) == "Starbucks"  # decrypt-on-read


def test_encrypted_numeric_roundtrip():
    col = EncryptedNumeric()
    stored = col.process_bind_param(Decimal("12.34"), None)
    assert stored != "12.34"
    assert col.process_result_value(stored, None) == Decimal("12.34")


def test_none_passes_through():
    assert EncryptedString().process_bind_param(None, None) is None
    assert EncryptedString().process_result_value(None, None) is None
    assert EncryptedNumeric().process_result_value(None, None) is None


def test_legacy_plaintext_read_is_tolerant():
    # A value that isn't a Fernet token (un-migrated legacy row) is returned
    # as-is rather than crashing the read.
    assert EncryptedString().process_result_value("legacy-plaintext", None) == "legacy-plaintext"


def test_encrypted_type_fails_closed_without_service(monkeypatch):
    # No encryption service (i.e. FERNET_KEY unset → boot guard blocked startup):
    # both write and read must raise, never silently store/return plaintext.
    monkeypatch.setattr(enc_mod, "_service", None)
    with pytest.raises(RuntimeError):
        EncryptedString().process_bind_param("secret", None)
    with pytest.raises(RuntimeError):
        EncryptedString().process_result_value("anything", None)
    # Restore the service for the remaining tests (monkeypatch also restores it,
    # but be explicit since module state is shared).
    init_encryption_service(TEST_SETTINGS.fernet_key)


# ---------------------------------------------------------------------------
# Migration helper: fail-closed, encrypt-in-place, idempotent, dry-run, rollback
# ---------------------------------------------------------------------------

def test_load_fernet_fails_closed_when_key_unset(monkeypatch):
    monkeypatch.delenv("FERNET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_fernet_or_fail()


def _seed_db():
    """A temp SQLite DB with plaintext Plaid rows (as they existed pre-encryption)."""
    engine = create_engine("sqlite://", poolclass=StaticPool)
    conn = engine.connect()
    conn.execute(text(
        "CREATE TABLE plaid_transactions (id TEXT PRIMARY KEY, account_id TEXT, "
        "amount NUMERIC, name TEXT, merchant_name TEXT, category TEXT)"
    ))
    conn.execute(text(
        "CREATE TABLE plaid_connections (id TEXT PRIMARY KEY, institution_name TEXT, accounts_json TEXT)"
    ))
    conn.execute(text(
        "INSERT INTO plaid_transactions VALUES (:id,'acc-1',12.34,'Coffee','Starbucks','Food')"
    ), {"id": uuid.uuid4().hex})
    conn.execute(text(
        "INSERT INTO plaid_connections VALUES (:id,'Chase Bank','{\"mask\":\"1234\"}')"
    ), {"id": uuid.uuid4().hex})
    conn.commit()
    return engine, conn


def test_migration_encrypts_in_place_and_is_idempotent():
    fernet = Fernet(Fernet.generate_key())
    engine, conn = _seed_db()
    try:
        # Dry run writes nothing.
        dry = encrypt_existing(conn, fernet, dry_run=True)
        assert dry["plaid_transactions"]["rows_encrypted"] == 1
        assert conn.execute(text("SELECT name FROM plaid_transactions")).scalar() == "Coffee"

        # Apply.
        s1 = encrypt_existing(conn, fernet, dry_run=False)
        assert s1["plaid_transactions"]["rows_encrypted"] == 1
        assert s1["plaid_connections"]["rows_encrypted"] == 1

        row = conn.execute(text("SELECT account_id, amount, name, merchant_name, category FROM plaid_transactions")).mappings().one()
        assert row["name"] != "Coffee"
        assert fernet.decrypt(row["name"].encode()).decode() == "Coffee"
        assert fernet.decrypt(row["amount"].encode()).decode() == "12.34"
        assert fernet.decrypt(row["account_id"].encode()).decode() == "acc-1"
        conn_row = conn.execute(text("SELECT institution_name, accounts_json FROM plaid_connections")).mappings().one()
        assert fernet.decrypt(conn_row["institution_name"].encode()).decode() == "Chase Bank"
        assert '"mask": "1234"' in fernet.decrypt(conn_row["accounts_json"].encode()).decode() or \
               '"mask":"1234"' in fernet.decrypt(conn_row["accounts_json"].encode()).decode()

        # Idempotent: re-running encrypts nothing more.
        s2 = encrypt_existing(conn, fernet, dry_run=False)
        assert s2["plaid_transactions"]["rows_encrypted"] == 0
        assert s2["plaid_transactions"]["rows_already_done"] == 1
        assert s2["plaid_connections"]["rows_encrypted"] == 0
    finally:
        conn.close()
        engine.dispose()


def test_migration_downgrade_reverses():
    fernet = Fernet(Fernet.generate_key())
    engine, conn = _seed_db()
    try:
        encrypt_existing(conn, fernet, dry_run=False)
        assert conn.execute(text("SELECT name FROM plaid_transactions")).scalar() != "Coffee"
        decrypt_existing(conn, fernet)
        assert conn.execute(text("SELECT name FROM plaid_transactions")).scalar() == "Coffee"
        assert conn.execute(text("SELECT institution_name FROM plaid_connections")).scalar() == "Chase Bank"
    finally:
        conn.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# ORM integration (async — CI): the real model stores ciphertext at rest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_plaid_connection_encrypted_at_rest(db, admin_user):
    from app.integrations.plaid.models import PlaidConnection

    conn = PlaidConnection(
        user_id=admin_user.id,
        institution_name="Wells Fargo",
        institution_id="ins_1",
        encrypted_access_token="tok",
        item_id=f"item-{uuid.uuid4().hex[:8]}",
        accounts_json='{"mask":"9876"}',
    )
    db.add(conn)
    await db.commit()

    # Raw read (bypasses the EncryptedString type) shows ciphertext, not plaintext.
    raw = (await db.execute(
        text("SELECT institution_name, accounts_json FROM plaid_connections WHERE id = :id"),
        {"id": str(conn.id)},
    )).mappings().one()
    assert raw["institution_name"] != "Wells Fargo"
    assert "9876" not in raw["accounts_json"]

    # ORM read decrypts transparently.
    await db.refresh(conn)
    assert conn.institution_name == "Wells Fargo"
    assert conn.accounts_json == '{"mask":"9876"}'
