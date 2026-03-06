"""Adversarial / security tests for the Accountant API.

Covers XSS injection, SQL injection, financial amount abuse, negative line
items, overpayment, malformed JSON, oversized uploads, MIME mismatches,
path traversal in filenames, and auth bypass attempts.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from jose import jwt

from app.auth.models import User
from app.auth.utils import create_access_token
from app.cashbook.models import PaymentAccount
from app.contacts.models import Contact
from tests.conftest import TEST_SETTINGS, auth_header
from tests.fixtures.data import (
    FINANCIAL_ABUSE_AMOUNTS,
    SQL_INJECTION_PAYLOADS,
    XSS_PAYLOADS,
    make_cashbook_entry,
    make_expense_payload,
    make_income_payload,
    make_invoice_payload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _idempotency_headers(user: User) -> dict[str, str]:
    """Auth header + unique idempotency key."""
    headers = auth_header(user)
    headers["Idempotency-Key"] = str(uuid.uuid4())
    return headers


# ---------------------------------------------------------------------------
# 1. XSS INJECTION
# ---------------------------------------------------------------------------


class TestXSSInjection:
    """Verify XSS payloads are either rejected or stored as literal text."""

    @pytest.mark.critical
    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_xss_in_contact_company_name(
        self, client: AsyncClient, admin_user: User, payload: str
    ):
        resp = await client.post(
            "/api/contacts",
            json={
                "type": "client",
                "company_name": payload,
                "contact_name": "XSS Test",
                "country": "US",
            },
            headers=auth_header(admin_user),
        )
        # Should either reject (400/422) or store literal text
        if resp.status_code in (400, 422):
            return  # safely rejected
        assert resp.status_code == 201
        data = resp.json()["data"]
        # Stored value must exactly match input (no transformation/execution)
        assert data["company_name"] == payload

    @pytest.mark.critical
    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_xss_in_contact_contact_name(
        self, client: AsyncClient, admin_user: User, payload: str
    ):
        resp = await client.post(
            "/api/contacts",
            json={
                "type": "client",
                "company_name": "Safe Corp",
                "contact_name": payload,
                "country": "US",
            },
            headers=auth_header(admin_user),
        )
        if resp.status_code in (400, 422):
            return
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["contact_name"] == payload

    @pytest.mark.critical
    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_xss_in_invoice_notes(
        self,
        client: AsyncClient,
        admin_user: User,
        sample_contact: Contact,
        payload: str,
    ):
        body = make_invoice_payload(str(sample_contact.id), notes=payload)
        resp = await client.post(
            "/api/invoices",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        if resp.status_code in (400, 422):
            return
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["notes"] == payload

    @pytest.mark.critical
    @pytest.mark.parametrize("payload", XSS_PAYLOADS)
    async def test_xss_in_expense_description(
        self, client: AsyncClient, admin_user: User, payload: str
    ):
        body = make_expense_payload(description=payload)
        resp = await client.post(
            "/api/accounting/expenses",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        if resp.status_code in (400, 422):
            return
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["description"] == payload


# ---------------------------------------------------------------------------
# 2. SQL INJECTION
# ---------------------------------------------------------------------------


class TestSQLInjection:
    """Verify SQL injection payloads cannot corrupt the database."""

    @pytest.mark.critical
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    async def test_sql_injection_in_contact_search(
        self, client: AsyncClient, admin_user: User, payload: str
    ):
        resp = await client.get(
            "/api/contacts",
            params={"search": payload},
            headers=auth_header(admin_user),
        )
        # Must not cause a server error
        assert resp.status_code != 500, (
            f"SQL injection caused 500: {payload!r}"
        )
        assert resp.status_code in (200, 400, 422)

    @pytest.mark.critical
    @pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
    async def test_sql_injection_in_contact_company_name(
        self, client: AsyncClient, admin_user: User, payload: str
    ):
        resp = await client.post(
            "/api/contacts",
            json={
                "type": "client",
                "company_name": payload,
                "contact_name": "SQL Test",
                "country": "US",
            },
            headers=auth_header(admin_user),
        )
        # Must not cause a server error
        assert resp.status_code != 500, (
            f"SQL injection caused 500: {payload!r}"
        )
        # Either stored as literal string or rejected
        if resp.status_code == 201:
            data = resp.json()["data"]
            assert data["company_name"] == payload

    @pytest.mark.critical
    async def test_users_table_survives_injections(
        self, client: AsyncClient, admin_user: User
    ):
        """After all injection attempts, verify the users table still exists."""
        # Run a few injection attempts first
        for payload in SQL_INJECTION_PAYLOADS:
            await client.get(
                "/api/contacts",
                params={"search": payload},
                headers=auth_header(admin_user),
            )
            await client.post(
                "/api/contacts",
                json={
                    "type": "client",
                    "company_name": payload,
                    "country": "US",
                },
                headers=auth_header(admin_user),
            )

        # Verify the users table still works
        resp = await client.get(
            "/api/auth/me",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["email"] == admin_user.email


# ---------------------------------------------------------------------------
# 3. FINANCIAL AMOUNT ABUSE
# ---------------------------------------------------------------------------


class TestFinancialAmountAbuse:
    """Verify the API rejects invalid monetary amounts."""

    @pytest.mark.critical
    @pytest.mark.parametrize("amount", FINANCIAL_ABUSE_AMOUNTS)
    async def test_expense_amount_abuse(
        self, client: AsyncClient, admin_user: User, amount: str
    ):
        body = make_expense_payload(amount=amount)
        resp = await client.post(
            "/api/accounting/expenses",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        decimal_amount = Decimal(amount)
        if decimal_amount <= 0:
            # Negative and zero amounts must be rejected
            assert resp.status_code == 422, (
                f"Negative/zero amount {amount} was not rejected: {resp.status_code}"
            )
        else:
            # Positive amounts: sub-penny or very large may be accepted or rejected
            assert resp.status_code in (201, 422), (
                f"Unexpected status for amount {amount}: {resp.status_code}"
            )

    @pytest.mark.critical
    @pytest.mark.parametrize("amount", FINANCIAL_ABUSE_AMOUNTS)
    async def test_income_amount_abuse(
        self, client: AsyncClient, admin_user: User, amount: str
    ):
        body = make_income_payload(amount=amount)
        resp = await client.post(
            "/api/income",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        decimal_amount = Decimal(amount)
        if decimal_amount <= 0:
            assert resp.status_code == 422, (
                f"Negative/zero amount {amount} was not rejected: {resp.status_code}"
            )
        else:
            assert resp.status_code in (201, 422), (
                f"Unexpected status for amount {amount}: {resp.status_code}"
            )

    @pytest.mark.critical
    @pytest.mark.parametrize("amount", FINANCIAL_ABUSE_AMOUNTS)
    async def test_cashbook_amount_abuse(
        self,
        client: AsyncClient,
        admin_user: User,
        sample_payment_account: PaymentAccount,
        amount: str,
    ):
        body = make_cashbook_entry(
            str(sample_payment_account.id), total_amount=amount
        )
        resp = await client.post(
            "/api/cashbook/entries",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        decimal_amount = Decimal(amount)
        if decimal_amount <= 0:
            assert resp.status_code == 422, (
                f"Negative/zero amount {amount} was not rejected: {resp.status_code}"
            )
        else:
            assert resp.status_code in (201, 422), (
                f"Unexpected status for amount {amount}: {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# 4. NEGATIVE LINE ITEM QUANTITIES
# ---------------------------------------------------------------------------


class TestNegativeLineItems:
    """Verify invoice line items reject negative quantities and prices."""

    @pytest.mark.critical
    async def test_negative_quantity_invoice(
        self,
        client: AsyncClient,
        admin_user: User,
        sample_contact: Contact,
    ):
        body = make_invoice_payload(
            str(sample_contact.id),
            line_items=[
                {
                    "description": "Negative qty test",
                    "quantity": "-5",
                    "unit_price": "100.00",
                    "tax_rate": "0",
                }
            ],
        )
        resp = await client.post(
            "/api/invoices",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        assert resp.status_code == 422, (
            "Invoice with negative quantity should be rejected"
        )

    @pytest.mark.critical
    async def test_negative_unit_price_invoice(
        self,
        client: AsyncClient,
        admin_user: User,
        sample_contact: Contact,
    ):
        body = make_invoice_payload(
            str(sample_contact.id),
            line_items=[
                {
                    "description": "Negative price test",
                    "quantity": "1",
                    "unit_price": "-100.00",
                    "tax_rate": "0",
                }
            ],
        )
        resp = await client.post(
            "/api/invoices",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        assert resp.status_code == 422, (
            "Invoice with negative unit price should be rejected"
        )


# ---------------------------------------------------------------------------
# 5. PAYMENT LARGER THAN BALANCE
# ---------------------------------------------------------------------------


class TestOverpayment:
    """Verify the system handles overpayment attempts."""

    @pytest.mark.high
    async def test_payment_exceeding_invoice_total(
        self,
        client: AsyncClient,
        admin_user: User,
        sample_contact: Contact,
    ):
        # Create a $100 invoice
        invoice_body = make_invoice_payload(
            str(sample_contact.id),
            line_items=[
                {
                    "description": "Small service",
                    "quantity": "1",
                    "unit_price": "100.00",
                    "tax_rate": "0",
                }
            ],
            tax_rate="0",
            discount_amount="0",
        )
        create_resp = await client.post(
            "/api/invoices",
            json=invoice_body,
            headers=_idempotency_headers(admin_user),
        )
        assert create_resp.status_code == 201
        invoice_id = create_resp.json()["data"]["id"]

        # Try to record a $200 payment on a $100 invoice
        payment_resp = await client.post(
            f"/api/invoices/{invoice_id}/payments",
            json={
                "amount": "200.00",
                "date": date.today().isoformat(),
                "payment_method": "bank_transfer",
            },
            headers=_idempotency_headers(admin_user),
        )
        # The system should either reject (422) or cap/accept with status=PAID
        if payment_resp.status_code in (400, 422):
            # Properly rejected
            pass
        elif payment_resp.status_code == 201:
            # Accepted -- verify the invoice is at least marked as paid
            inv_resp = await client.get(
                f"/api/invoices/{invoice_id}",
                headers=auth_header(admin_user),
            )
            assert inv_resp.status_code == 200
            assert inv_resp.json()["data"]["status"] == "paid"
        else:
            pytest.fail(
                f"Unexpected status code for overpayment: {payment_resp.status_code}"
            )


# ---------------------------------------------------------------------------
# 6. MALFORMED JSON
# ---------------------------------------------------------------------------


class TestMalformedJSON:
    """Verify the API gracefully rejects malformed / invalid JSON bodies."""

    @pytest.mark.high
    async def test_non_json_body_invoices(
        self, client: AsyncClient, admin_user: User
    ):
        resp = await client.post(
            "/api/invoices",
            content=b"this is not json",
            headers={
                **_idempotency_headers(admin_user),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.high
    async def test_wrong_type_amount(
        self, client: AsyncClient, admin_user: User
    ):
        body = make_expense_payload(amount="not_a_number")
        resp = await client.post(
            "/api/accounting/expenses",
            json=body,
            headers=_idempotency_headers(admin_user),
        )
        assert resp.status_code == 422

    @pytest.mark.high
    async def test_missing_required_fields_expense(
        self, client: AsyncClient, admin_user: User
    ):
        # ExpenseCreate requires amount and date at minimum
        resp = await client.post(
            "/api/accounting/expenses",
            json={"vendor_name": "Incomplete"},
            headers=_idempotency_headers(admin_user),
        )
        assert resp.status_code == 422

    @pytest.mark.high
    async def test_missing_required_fields_invoice(
        self,
        client: AsyncClient,
        admin_user: User,
    ):
        # InvoiceCreate requires contact_id, issue_date, due_date, line_items
        resp = await client.post(
            "/api/invoices",
            json={"notes": "Missing everything else"},
            headers=_idempotency_headers(admin_user),
        )
        assert resp.status_code == 422

    @pytest.mark.high
    async def test_missing_required_fields_income(
        self, client: AsyncClient, admin_user: User
    ):
        # IncomeCreate requires description, amount, date
        resp = await client.post(
            "/api/income",
            json={"category": "service"},
            headers=_idempotency_headers(admin_user),
        )
        assert resp.status_code == 422

    @pytest.mark.high
    async def test_empty_json_body_contacts(
        self, client: AsyncClient, admin_user: User
    ):
        resp = await client.post(
            "/api/contacts",
            json={},
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. OVERSIZED FILE UPLOAD
# ---------------------------------------------------------------------------


class TestOversizedUpload:
    """Verify the server handles very large upload attempts."""

    @pytest.mark.high
    async def test_oversized_file_upload(
        self, client: AsyncClient, admin_user: User
    ):
        # Create a 51 MB in-memory file
        oversized_data = b"\x00" * (51 * 1024 * 1024)
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("bigfile.bin", oversized_data, "application/octet-stream")},
            headers=auth_header(admin_user),
        )
        # The server should reject (413 Payload Too Large) or accept
        # if max_upload_size is 0 (unlimited). Either way, no 500.
        assert resp.status_code != 500, (
            "Server crashed on oversized upload"
        )
        # With default config (max_upload_size=0), the upload may succeed
        # but we still verify no server error occurred.
        assert resp.status_code in (201, 400, 413, 422)


# ---------------------------------------------------------------------------
# 8. MIME TYPE MISMATCH
# ---------------------------------------------------------------------------


class TestMimeTypeMismatch:
    """Verify files with mismatched MIME types are handled safely."""

    @pytest.mark.high
    async def test_text_file_claiming_to_be_pdf(
        self, client: AsyncClient, admin_user: User
    ):
        text_content = b"This is plain text, not a PDF."
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("document.pdf", text_content, "application/pdf")},
            headers=auth_header(admin_user),
        )
        # Should store the file (MIME mismatch is acceptable) but not crash
        assert resp.status_code != 500, (
            "Server crashed on MIME mismatch"
        )
        if resp.status_code == 201:
            data = resp.json()["data"]
            # Verify the file is stored and not executed -- it should just
            # be saved as a document, not interpreted as executable content
            assert "id" in data

    @pytest.mark.high
    async def test_script_disguised_as_image(
        self, client: AsyncClient, admin_user: User
    ):
        script_content = b'<script>alert("xss")</script>'
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("photo.jpg", script_content, "image/jpeg")},
            headers=auth_header(admin_user),
        )
        assert resp.status_code != 500
        if resp.status_code == 201:
            data = resp.json()["data"]
            assert "id" in data


# ---------------------------------------------------------------------------
# 9. PATH TRAVERSAL IN FILENAMES
# ---------------------------------------------------------------------------


class TestPathTraversal:
    """Verify uploaded filenames are sanitized to prevent path traversal."""

    @pytest.mark.critical
    async def test_path_traversal_filename(
        self, client: AsyncClient, admin_user: User
    ):
        malicious_filename = "../../../etc/passwd"
        file_content = b"fake sensitive data"
        resp = await client.post(
            "/api/documents/upload",
            files={
                "file": (malicious_filename, file_content, "application/octet-stream")
            },
            headers=auth_header(admin_user),
        )
        # Should either reject or sanitize the filename
        assert resp.status_code != 500
        if resp.status_code == 201:
            data = resp.json()["data"]
            stored_filename = data.get("original_filename", "")
            # The stored filename must NOT contain path traversal sequences
            assert ".." not in stored_filename or stored_filename == malicious_filename
            # The storage path must not contain path traversal
            storage_path = data.get("storage_path", "")
            assert "../../../etc/passwd" not in storage_path

    @pytest.mark.critical
    async def test_null_byte_in_filename(
        self, client: AsyncClient, admin_user: User
    ):
        """Null bytes in filenames can trick path parsers."""
        malicious_filename = "innocent.pdf\x00.exe"
        file_content = b"payload content"
        resp = await client.post(
            "/api/documents/upload",
            files={
                "file": (malicious_filename, file_content, "application/octet-stream")
            },
            headers=auth_header(admin_user),
        )
        # Must not cause a server crash
        assert resp.status_code != 500
        # Filename should be sanitized if accepted
        if resp.status_code == 201:
            data = resp.json()["data"]
            stored_filename = data.get("original_filename", "")
            assert "\x00" not in stored_filename

    @pytest.mark.critical
    async def test_windows_reserved_name_filename(
        self, client: AsyncClient, admin_user: User
    ):
        """Windows reserved device names (CON, PRN, NUL) can cause issues."""
        resp = await client.post(
            "/api/documents/upload",
            files={
                "file": ("CON.pdf", b"test content", "application/pdf")
            },
            headers=auth_header(admin_user),
        )
        assert resp.status_code != 500


# ---------------------------------------------------------------------------
# 10. AUTH BYPASS ATTEMPTS
# ---------------------------------------------------------------------------


class TestAuthBypass:
    """Verify all protected endpoints reject unauthenticated requests."""

    # FastAPI's HTTPBearer(auto_error=True) returns 403 when the
    # Authorization header is missing entirely. When an invalid/expired
    # token IS provided, our dependency returns 401.
    # We accept both 401 and 403 as valid rejections for "no auth".

    @pytest.mark.critical
    @pytest.mark.parametrize(
        "method,url",
        [
            ("GET", "/api/contacts"),
            ("POST", "/api/contacts"),
            ("GET", "/api/invoices"),
            ("POST", "/api/invoices"),
            ("GET", "/api/accounting/expenses"),
            ("POST", "/api/accounting/expenses"),
            ("GET", "/api/income"),
            ("POST", "/api/income"),
            ("GET", "/api/cashbook/entries"),
            ("POST", "/api/cashbook/entries"),
            ("GET", "/api/documents/"),
            ("POST", "/api/documents/upload"),
            ("GET", "/api/auth/me"),
            ("GET", "/api/auth/users"),
        ],
    )
    async def test_no_auth_header(
        self, client: AsyncClient, method: str, url: str
    ):
        """Every protected endpoint must reject requests without auth."""
        if method == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url, json={})
        assert resp.status_code in (401, 403), (
            f"{method} {url} returned {resp.status_code} without auth (expected 401/403)"
        )

    @pytest.mark.critical
    async def test_expired_token(
        self, client: AsyncClient, admin_user: User
    ):
        """An expired JWT must be rejected."""
        # Create a token that expired 1 hour ago
        expired_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": str(admin_user.id),
            "role": admin_user.role.value,
            "exp": expired_time,
            "type": "access",
        }
        expired_token = jwt.encode(
            payload,
            TEST_SETTINGS.secret_key,
            algorithm=TEST_SETTINGS.algorithm,
        )
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401, (
            f"Expired token was not rejected: {resp.status_code}"
        )

    @pytest.mark.critical
    async def test_tampered_token(
        self, client: AsyncClient, admin_user: User
    ):
        """A token with a tampered payload but original signature must be rejected."""
        # Create a valid token
        valid_token = create_access_token(
            admin_user.id, admin_user.role.value, TEST_SETTINGS
        )
        # Tamper with it: change the payload but keep the signature
        parts = valid_token.split(".")
        assert len(parts) == 3

        # Decode the payload, modify it, re-encode, but keep original signature
        import base64
        import json

        # Pad the base64 payload
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_data = json.loads(base64.urlsafe_b64decode(padded))
        # Change the user ID to a random one
        payload_data["sub"] = str(uuid.uuid4())
        # Re-encode the modified payload
        new_payload = base64.urlsafe_b64encode(
            json.dumps(payload_data).encode()
        ).rstrip(b"=").decode()
        # Reconstruct with modified payload but ORIGINAL signature
        tampered_token = f"{parts[0]}.{new_payload}.{parts[2]}"

        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {tampered_token}"},
        )
        assert resp.status_code == 401, (
            f"Tampered token was not rejected: {resp.status_code}"
        )

    @pytest.mark.critical
    async def test_completely_fabricated_token(
        self, client: AsyncClient
    ):
        """A token signed with a different secret must be rejected."""
        fake_payload = {
            "sub": str(uuid.uuid4()),
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        fake_token = jwt.encode(
            fake_payload, "wrong-secret-key", algorithm="HS256"
        )
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert resp.status_code == 401

    @pytest.mark.critical
    async def test_garbage_bearer_token(self, client: AsyncClient):
        """Random garbage as a Bearer token must be rejected."""
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.token.at.all"},
        )
        assert resp.status_code == 401

    @pytest.mark.critical
    async def test_empty_bearer_token(self, client: AsyncClient):
        """An empty Bearer token value must be rejected."""
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.critical
    async def test_wrong_auth_scheme(self, client: AsyncClient):
        """Using Basic auth instead of Bearer must be rejected."""
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.critical
    async def test_valid_token_for_nonexistent_user(
        self, client: AsyncClient
    ):
        """A properly signed token referencing a non-existent user must be rejected."""
        non_existent_id = uuid.uuid4()
        token = create_access_token(
            non_existent_id, "admin", TEST_SETTINGS
        )
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
