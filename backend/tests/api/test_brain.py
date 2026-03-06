"""Comprehensive tests for the O-Brain module."""

import json
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.brain.models import (
    BrainConversation,
    BrainMessage,
    BrainEmbedding,
    EmbeddingSourceType,
    ProactiveAlert,
    AlertType,
    BrainAuditLog,
    AuditActionType,
)
from app.brain.embedding_service import chunk_text, embed_texts
from app.brain.transcription_service import (
    _extract_action_items,
    _extract_financial_commitments,
    _extract_speakers,
)
from app.brain.knowledge_service import (
    add_knowledge,
    list_knowledge,
    delete_knowledge,
    get_onboarding_questions,
    process_onboarding_answers,
)
from app.brain.proactive_service import (
    list_alerts,
    mark_alert_read,
    mark_all_alerts_read,
)

from tests.conftest import auth_header


# ── Embedding & Chunking Tests ────────────────────────────────────────


class TestChunking:
    def test_short_text_no_split(self):
        chunks = chunk_text("Hello world, this is a short text.")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world, this is a short text."

    def test_long_text_splits(self):
        text = "The quick brown fox. " * 200  # ~1000 words
        chunks = chunk_text(text)
        assert len(chunks) > 1

    def test_chunks_have_overlap(self):
        text = ". ".join([f"Sentence number {i}" for i in range(100)])
        chunks = chunk_text(text)
        if len(chunks) > 1:
            # Check that some content from end of chunk N appears in chunk N+1
            end_of_first = chunks[0][-50:]
            assert any(
                word in chunks[1] for word in end_of_first.split() if len(word) > 3
            )

    def test_empty_text(self):
        chunks = chunk_text("")
        assert len(chunks) == 0


class TestEmbedding:
    @pytest.mark.asyncio
    async def test_tfidf_fallback(self):
        """Without OpenAI key, should fall back to TF-IDF."""
        vectors = await embed_texts(["Hello world", "Goodbye world"])
        assert len(vectors) == 2
        assert len(vectors[0]) > 0  # Should have some dimensions


# ── Transcription Extraction Tests ────────────────────────────────────


class TestTranscriptionExtraction:
    def test_extract_action_items(self):
        text = "I'll send the contract tomorrow. We need to update the pricing page. Can you review the design?"
        items = _extract_action_items(text)
        assert len(items) > 0

    def test_extract_financial_commitments(self):
        text = "The budget is $50,000 per year. We quoted them $2,500 for the project."
        commitments = _extract_financial_commitments(text)
        assert len(commitments) >= 1
        assert any("$50,000" in c["amount_text"] or "$2,500" in c["amount_text"] for c in commitments)

    def test_extract_speakers(self):
        segments = [
            {"speaker": "Speaker A", "start": 0, "end": 10, "text": "Hello"},
            {"speaker": "Speaker B", "start": 10, "end": 20, "text": "Hi there"},
            {"speaker": "Speaker A", "start": 20, "end": 30, "text": "How are you"},
        ]
        speakers = _extract_speakers(segments)
        assert len(speakers) == 2
        a = next(s for s in speakers if s["name"] == "Speaker A")
        assert a["segments_count"] == 2

    def test_no_financial_commitments(self):
        text = "We had a great meeting about design principles."
        commitments = _extract_financial_commitments(text)
        assert len(commitments) == 0


# ── Knowledge Base Tests ──────────────────────────────────────────────


class TestKnowledgeBase:
    @pytest.mark.asyncio
    async def test_add_and_list_knowledge(self, db: AsyncSession, admin_user: User):
        result = await add_knowledge(
            db, admin_user.id, "Our refund policy is 30 days.", "Refund Policy", "policies",
        )
        assert "source_id" in result
        assert result["title"] == "Refund Policy"

        listing = await list_knowledge(db, admin_user.id)
        assert listing["total"] >= 1

    @pytest.mark.asyncio
    async def test_delete_knowledge(self, db: AsyncSession, admin_user: User):
        result = await add_knowledge(
            db, admin_user.id, "Test content to delete.", "Delete Me", "test",
        )
        source_id = result["source_id"]

        deleted = await delete_knowledge(db, admin_user.id, source_id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_onboarding_questions(self):
        questions = get_onboarding_questions()
        assert len(questions) > 0
        assert all("question" in q for q in questions)

    @pytest.mark.asyncio
    async def test_process_onboarding(self, db: AsyncSession, admin_user: User):
        answers = [
            {"question": "What does your business do?", "answer": "We build software."},
            {"question": "Who are your customers?", "answer": "Small businesses."},
        ]
        count = await process_onboarding_answers(db, admin_user.id, answers)
        assert count == 2


# ── Proactive Alerts Tests ────────────────────────────────────────────


class TestProactiveAlerts:
    @pytest.mark.asyncio
    async def test_create_and_list_alerts(self, db: AsyncSession, admin_user: User):
        alert = ProactiveAlert(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            alert_type=AlertType.OVERDUE_INVOICE,
            title="Test alert",
            message="You have overdue invoices.",
        )
        db.add(alert)
        await db.commit()

        alerts = await list_alerts(db, admin_user.id)
        assert len(alerts) >= 1

    @pytest.mark.asyncio
    async def test_mark_alert_read(self, db: AsyncSession, admin_user: User):
        alert = ProactiveAlert(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            alert_type=AlertType.REVENUE_MILESTONE,
            title="Revenue up!",
            message="Revenue increased 20%.",
        )
        db.add(alert)
        await db.commit()

        ok = await mark_alert_read(db, alert.id, admin_user.id)
        assert ok is True

        alerts = await list_alerts(db, admin_user.id, unread_only=True)
        assert all(a.id != alert.id for a in alerts)

    @pytest.mark.asyncio
    async def test_mark_all_read(self, db: AsyncSession, admin_user: User):
        for i in range(3):
            db.add(ProactiveAlert(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                alert_type=AlertType.FOLLOW_UP_NEEDED,
                title=f"Alert {i}",
                message=f"Follow up {i}",
            ))
        await db.commit()

        count = await mark_all_alerts_read(db, admin_user.id)
        assert count >= 3

    @pytest.mark.asyncio
    async def test_alert_isolation(self, db: AsyncSession, admin_user: User, accountant_user: User):
        alert = ProactiveAlert(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            alert_type=AlertType.EXPENSE_ANOMALY,
            title="Admin-only alert",
            message="Only for admin.",
        )
        db.add(alert)
        await db.commit()

        # Other user should not see it
        other_alerts = await list_alerts(db, accountant_user.id)
        assert all(a.id != alert.id for a in other_alerts)


# ── Conversation Tests ────────────────────────────────────────────────


class TestConversations:
    @pytest.mark.asyncio
    async def test_create_conversation(self, db: AsyncSession, admin_user: User):
        from app.brain.chat_service import get_or_create_conversation

        conv = await get_or_create_conversation(db, admin_user.id)
        assert conv.id is not None
        assert conv.user_id == admin_user.id
        assert conv.title == "New conversation"

    @pytest.mark.asyncio
    async def test_get_existing_conversation(self, db: AsyncSession, admin_user: User):
        from app.brain.chat_service import get_or_create_conversation

        conv1 = await get_or_create_conversation(db, admin_user.id)
        conv2 = await get_or_create_conversation(db, admin_user.id, str(conv1.id))
        assert conv1.id == conv2.id

    @pytest.mark.asyncio
    async def test_list_conversations(self, db: AsyncSession, admin_user: User):
        from app.brain.chat_service import get_or_create_conversation, list_conversations

        await get_or_create_conversation(db, admin_user.id)
        convs = await list_conversations(db, admin_user.id)
        assert len(convs) >= 1

    @pytest.mark.asyncio
    async def test_delete_conversation(self, db: AsyncSession, admin_user: User):
        from app.brain.chat_service import get_or_create_conversation, delete_conversation

        conv = await get_or_create_conversation(db, admin_user.id)
        deleted = await delete_conversation(db, admin_user.id, conv.id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_conversation_isolation(self, db: AsyncSession, admin_user: User, accountant_user: User):
        from app.brain.chat_service import get_or_create_conversation, delete_conversation

        conv = await get_or_create_conversation(db, admin_user.id)
        # Other user cannot delete it
        deleted = await delete_conversation(db, accountant_user.id, conv.id)
        assert deleted is False


# ── Rate Limiting Tests ───────────────────────────────────────────────


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_allows(self, db: AsyncSession, admin_user: User):
        from app.brain.chat_service import check_rate_limit

        allowed, minutes = await check_rate_limit(db, admin_user.id)
        assert allowed is True
        assert minutes == 0


# ── API Endpoint Tests ────────────────────────────────────────────────


class TestBrainAPI:
    @pytest.mark.asyncio
    async def test_conversations_list_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/brain/conversations")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_conversations_list(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/conversations",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    @pytest.mark.asyncio
    async def test_knowledge_add(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/brain/knowledge",
            headers=auth_header(admin_user),
            json={"content": "Our pricing starts at $500/month.", "title": "Pricing", "category": "sales"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "source_id" in data["data"]

    @pytest.mark.asyncio
    async def test_knowledge_list(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/knowledge",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_onboarding_questions(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/knowledge/onboarding",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_alerts_list(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/alerts",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_briefing(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/briefing",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "date" in data["data"]

    @pytest.mark.asyncio
    async def test_audit_logs(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/audit",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/brain/search",
            headers=auth_header(admin_user),
            json={"query": "invoices", "limit": 5},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_conversation_crud(self, client: AsyncClient, admin_user: User, db: AsyncSession):
        headers = auth_header(admin_user)

        # Create a conversation via direct DB (since chat endpoint needs Anthropic)
        conv = BrainConversation(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            title="Test conversation",
        )
        db.add(conv)
        msg = BrainMessage(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="user",
            content="Hello",
        )
        db.add(msg)
        await db.commit()

        # Get
        resp = await client.get(f"/api/brain/conversations/{conv.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "Test conversation"
        assert len(data["messages"]) == 1

        # Delete
        resp = await client.delete(f"/api/brain/conversations/{conv.id}", headers=headers)
        assert resp.status_code == 200

        # Verify deleted
        resp = await client.get(f"/api/brain/conversations/{conv.id}", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_alert_mark_read(self, client: AsyncClient, admin_user: User, db: AsyncSession):
        headers = auth_header(admin_user)

        alert = ProactiveAlert(
            id=uuid.uuid4(),
            user_id=admin_user.id,
            alert_type=AlertType.CASHFLOW_WARNING,
            title="Cash flow warning",
            message="Negative cash flow this month.",
        )
        db.add(alert)
        await db.commit()

        resp = await client.post(f"/api/brain/alerts/{alert.id}/read", headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_alert_mark_all_read(self, client: AsyncClient, admin_user: User, db: AsyncSession):
        headers = auth_header(admin_user)

        for i in range(2):
            db.add(ProactiveAlert(
                id=uuid.uuid4(),
                user_id=admin_user.id,
                alert_type=AlertType.FOLLOW_UP_NEEDED,
                title=f"Alert {i}",
                message=f"Follow up {i}",
            ))
        await db.commit()

        resp = await client.post("/api/brain/alerts/read-all", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["marked_read"] >= 2

    @pytest.mark.asyncio
    async def test_generate_briefing(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/brain/briefing/generate",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_onboarding_submit(self, client: AsyncClient, admin_user: User):
        resp = await client.post(
            "/api/brain/knowledge/onboarding",
            headers=auth_header(admin_user),
            json={"answers": [
                {"question": "What do you do?", "answer": "We sell software."},
            ]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["stored"] == 1

    @pytest.mark.asyncio
    async def test_knowledge_delete(self, client: AsyncClient, admin_user: User):
        headers = auth_header(admin_user)

        # Create knowledge
        resp = await client.post(
            "/api/brain/knowledge",
            headers=headers,
            json={"content": "To be deleted.", "title": "Delete me", "category": "test"},
        )
        source_id = resp.json()["data"]["source_id"]

        # Delete
        resp = await client.delete(f"/api/brain/knowledge/{source_id}", headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_transcription_queue(self, client: AsyncClient, admin_user: User):
        resp = await client.get(
            "/api/brain/transcription-queue",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
