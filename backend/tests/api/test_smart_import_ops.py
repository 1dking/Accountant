"""Smart Import operations: AI-meter operator exemption + bulk delete.

- Operators/super-admins must never be blocked by the per-tenant AI credit
  meter (they pay the model bill directly); real tenants must still be capped.
- Bulk delete removes several import batches at once.
"""
import uuid

import pytest
from sqlalchemy import func, select

from app.auth.models import Role, User
from app.auth.utils import hash_password
from app.billing import ai_meter
from app.smart_import import service
from app.smart_import.models import SmartImport


async def _mk_user(db, email: str) -> User:
    u = User(
        id=uuid.uuid4(), email=email, hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0], role=Role.ADMIN, is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def test_exempt_operator_is_never_metered(db, monkeypatch):
    monkeypatch.setattr(ai_meter._settings, "ai_meter_exempt_emails", "op@ocidm.io")
    op = await _mk_user(db, "op@ocidm.io")
    # A charge that would blow past ANY plan limit still passes for an operator.
    cost = await ai_meter.consume(db, op, "smart_import", units=1000)
    assert cost > 0  # returned, not raised
    # And nothing was recorded against a tenant budget.
    from app.billing.models import AiUsage
    n = await db.scalar(select(func.count(AiUsage.tenant_key)))
    assert (n or 0) == 0


async def test_tenant_is_still_metered_and_blocked(db, monkeypatch):
    monkeypatch.setattr(ai_meter._settings, "ai_meter_exempt_emails", "op@ocidm.io")
    tenant = await _mk_user(db, "customer@example.com")
    with pytest.raises(ai_meter.AiCreditsExhausted):
        await ai_meter.consume(db, tenant, "smart_import", units=1000)


async def test_bulk_delete_imports(db):
    user = await _mk_user(db, "op2@ocidm.io")
    i1 = await service.create_import(db, user, filename="a.csv", storage_path="x",
                                     mime_type="text/csv", file_size=1)
    i2 = await service.create_import(db, user, filename="b.csv", storage_path="y",
                                     mime_type="text/csv", file_size=1)

    deleted = await service.bulk_delete_imports(db, [i1.id, i2.id], user.id)
    assert deleted == 2
    remaining = await db.scalar(
        select(func.count(SmartImport.id)).where(SmartImport.user_id == user.id)
    )
    assert remaining == 0


async def test_bulk_delete_skips_unknown_ids(db):
    user = await _mk_user(db, "op3@ocidm.io")
    i1 = await service.create_import(db, user, filename="a.csv", storage_path="x",
                                     mime_type="text/csv", file_size=1)
    # One real id + one that doesn't exist -> only the real one is deleted.
    deleted = await service.bulk_delete_imports(db, [i1.id, uuid.uuid4()], user.id)
    assert deleted == 1
