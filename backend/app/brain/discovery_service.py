"""Discovery system — comprehensive business onboarding questionnaire."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.brain.knowledge_service import add_knowledge

logger = logging.getLogger(__name__)

# The 28-question discovery flow, organized into sections
DISCOVERY_QUESTIONS = [
    # Section 1: Business Basics
    {"id": "biz_name", "section": "Business Basics", "question": "What is your business name?", "placeholder": "e.g., Acme Corp", "order": 1},
    {"id": "biz_type", "section": "Business Basics", "question": "What type of business is this?", "placeholder": "e.g., LLC, Corporation, Sole Proprietorship", "order": 2},
    {"id": "biz_industry", "section": "Business Basics", "question": "What industry are you in?", "placeholder": "e.g., Technology, Consulting, Retail", "order": 3},
    {"id": "biz_years", "section": "Business Basics", "question": "How long has your business been operating?", "placeholder": "e.g., 3 years, Since 2020", "order": 4},
    {"id": "biz_location", "section": "Business Basics", "question": "Where is your business located?", "placeholder": "e.g., Toronto, ON, Canada", "order": 5},
    {"id": "biz_website", "section": "Business Basics", "question": "What is your website URL?", "placeholder": "e.g., https://acmecorp.com", "order": 6},

    # Section 2: Products & Services
    {"id": "products", "section": "Products & Services", "question": "What products or services do you offer?", "placeholder": "Describe your main offerings", "order": 7},
    {"id": "pricing", "section": "Products & Services", "question": "What is your pricing model?", "placeholder": "e.g., Hourly, Project-based, Subscription, Retail", "order": 8},
    {"id": "avg_deal", "section": "Products & Services", "question": "What is your average deal or transaction size?", "placeholder": "e.g., $500, $5,000-$10,000", "order": 9},
    {"id": "currency", "section": "Products & Services", "question": "What currency do you primarily operate in?", "placeholder": "e.g., CAD, USD, EUR", "order": 10},

    # Section 3: Clients & Market
    {"id": "target_market", "section": "Clients & Market", "question": "Who is your target market?", "placeholder": "e.g., Small businesses, Enterprise, Consumers", "order": 11},
    {"id": "client_count", "section": "Clients & Market", "question": "Approximately how many active clients do you have?", "placeholder": "e.g., 15, 50-100", "order": 12},
    {"id": "acquisition", "section": "Clients & Market", "question": "How do you typically acquire new clients?", "placeholder": "e.g., Referrals, Online marketing, Cold outreach", "order": 13},
    {"id": "competitors", "section": "Clients & Market", "question": "Who are your main competitors?", "placeholder": "e.g., Company X, Company Y", "order": 14},

    # Section 4: Financial
    {"id": "revenue_range", "section": "Financial", "question": "What is your approximate annual revenue?", "placeholder": "e.g., $100K-$500K", "order": 15},
    {"id": "fiscal_year", "section": "Financial", "question": "When does your fiscal year end?", "placeholder": "e.g., December 31, March 31", "order": 16},
    {"id": "tax_setup", "section": "Financial", "question": "What taxes do you collect? (e.g., HST, GST, Sales Tax)", "placeholder": "e.g., HST 13%, No tax collected", "order": 17},
    {"id": "bank_accounts", "section": "Financial", "question": "How many bank accounts does the business have?", "placeholder": "e.g., 2 (checking + savings)", "order": 18},
    {"id": "payment_methods", "section": "Financial", "question": "How do your clients typically pay?", "placeholder": "e.g., Bank transfer, Credit card, Check", "order": 19},

    # Section 5: Team & Operations
    {"id": "team_size", "section": "Team & Operations", "question": "How many people are on your team?", "placeholder": "e.g., Just me, 5, 20+", "order": 20},
    {"id": "roles", "section": "Team & Operations", "question": "What roles exist on your team?", "placeholder": "e.g., Owner, Accountant, Sales rep, Developer", "order": 21},
    {"id": "tools", "section": "Team & Operations", "question": "What other tools do you currently use?", "placeholder": "e.g., QuickBooks, Slack, Google Workspace", "order": 22},

    # Section 6: Goals & Pain Points
    {"id": "challenges", "section": "Goals & Pain Points", "question": "What are your biggest business challenges right now?", "placeholder": "e.g., Cash flow management, Client acquisition", "order": 23},
    {"id": "goals", "section": "Goals & Pain Points", "question": "What are your top business goals for this year?", "placeholder": "e.g., Grow revenue 30%, Hire 2 more people", "order": 24},
    {"id": "pain_points", "section": "Goals & Pain Points", "question": "What takes up too much of your time?", "placeholder": "e.g., Invoicing, Following up on payments, Data entry", "order": 25},
    {"id": "automation_wish", "section": "Goals & Pain Points", "question": "If you could automate one thing, what would it be?", "placeholder": "e.g., Invoice reminders, Expense tracking", "order": 26},

    # Section 7: Communication Preferences
    {"id": "comm_style", "section": "Communication Preferences", "question": "How would you describe your communication style with clients?", "placeholder": "e.g., Formal, Casual, Professional but friendly", "order": 27},
    {"id": "brand_voice", "section": "Communication Preferences", "question": "How should O-Brain speak to represent your brand?", "placeholder": "e.g., Professional, Warm and approachable, Direct and concise", "order": 28},
]


def get_discovery_questions() -> list[dict]:
    """Return all discovery questions."""
    return DISCOVERY_QUESTIONS


def get_discovery_sections() -> list[dict]:
    """Return questions grouped by section."""
    sections: dict[str, list[dict]] = {}
    for q in DISCOVERY_QUESTIONS:
        section = q["section"]
        if section not in sections:
            sections[section] = []
        sections[section].append(q)
    return [{"section": s, "questions": qs} for s, qs in sections.items()]


async def save_discovery_answers(
    db: AsyncSession,
    user_id: uuid.UUID,
    answers: list[dict],
) -> dict:
    """Save discovery answers and embed them into the brain knowledge base.

    Each answer is saved as a knowledge entry for O-Brain to reference.
    """
    saved_count = 0
    for answer in answers:
        question_id = answer.get("id", "")
        question_text = answer.get("question", "")
        answer_text = answer.get("answer", "").strip()

        if not answer_text:
            continue

        # Build knowledge content
        content = f"Business Discovery - {question_text}: {answer_text}"
        title = f"Discovery: {question_id}"

        try:
            await add_knowledge(
                db=db,
                user_id=user_id,
                content=content,
                title=title,
                category="discovery",
            )
            saved_count += 1
        except Exception:
            logger.warning("Failed to save discovery answer for %s", question_id, exc_info=True)

    return {"saved_count": saved_count, "total": len(answers)}
