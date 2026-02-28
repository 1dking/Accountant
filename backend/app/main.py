from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from app.config import Settings
from app.core.exceptions import register_exception_handlers
from app.core.websocket import websocket_manager
from app.database import Base, build_engine, build_session_factory

# Import all models so Base.metadata knows about them
import app.auth.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.collaboration.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.calendar.models  # noqa: F401
import app.accounting.models  # noqa: F401
import app.contacts.models  # noqa: F401
import app.invoicing.models  # noqa: F401
import app.income.models  # noqa: F401
import app.recurring.models  # noqa: F401
import app.budgets.models  # noqa: F401
import app.email.models  # noqa: F401
import app.integrations.gmail.models  # noqa: F401
import app.integrations.plaid.models  # noqa: F401
import app.integrations.plaid.categorization_models  # noqa: F401
import app.integrations.stripe.models  # noqa: F401
import app.integrations.twilio.models  # noqa: F401
import app.estimates.models  # noqa: F401
import app.invoicing.reminder_models  # noqa: F401
import app.integrations.settings_models  # noqa: F401
import app.accounting.period_models  # noqa: F401
import app.invoicing.credit_models  # noqa: F401
import app.accounting.tax_models  # noqa: F401
import app.cashbook.models  # noqa: F401


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = application.state.settings

    # Ensure data directories exist before DB connection
    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    if settings.is_sqlite:
        db_path = settings.database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Initialize encryption service
    from app.core.encryption import init_encryption_service

    init_encryption_service(settings.fernet_key)

    engine = build_engine(settings.database_url)

    # Auto-create tables for SQLite in development
    if settings.is_sqlite:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    application.state.engine = engine
    application.state.session_factory = build_session_factory(engine)

    # Start background scheduler
    from app.core.scheduler import setup_scheduler, shutdown_scheduler

    setup_scheduler(application.state.session_factory, settings)

    # Load saved integration configs (Twilio, Stripe, Plaid) from DB
    from app.integrations.settings_router import load_integration_configs

    await load_integration_configs(application.state.session_factory, settings)

    yield

    shutdown_scheduler()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = Settings()

    fastapi_app = FastAPI(
        title="Accountant",
        description="Document vault & accounting suite",
        version="0.1.0",
        lifespan=lifespan,
    )
    fastapi_app.state.settings = settings

    # CORS
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from app.auth.router import router as auth_router
    from app.documents.router import router as documents_router
    from app.collaboration.router import router as collaboration_router
    from app.notifications.router import router as notifications_router
    from app.calendar.router import router as calendar_router
    from app.ai.router import router as ai_router
    from app.accounting.router import router as accounting_router
    from app.contacts.router import router as contacts_router
    from app.invoicing.router import router as invoicing_router
    from app.income.router import router as income_router
    from app.recurring.router import router as recurring_router
    from app.budgets.router import router as budgets_router
    from app.reports.router import router as reports_router
    from app.email.router import router as email_router
    from app.integrations.gmail.router import router as gmail_router
    from app.integrations.plaid.router import router as plaid_router
    from app.integrations.plaid.categorization_router import router as categorization_rules_router
    from app.integrations.stripe.router import router as stripe_router
    from app.integrations.twilio.router import router as twilio_router
    from app.estimates.router import router as estimates_router
    from app.invoicing.reminder_router import router as reminder_router
    from app.integrations.settings_router import router as integration_settings_router
    from app.export.router import router as export_router
    from app.accounting.period_router import router as period_router
    from app.invoicing.credit_router import router as credit_notes_router
    from app.accounting.tax_router import router as tax_router
    from app.cashbook.router import router as cashbook_router

    fastapi_app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    fastapi_app.include_router(documents_router, prefix="/api/documents", tags=["documents"])
    fastapi_app.include_router(collaboration_router, prefix="/api", tags=["collaboration"])
    fastapi_app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
    fastapi_app.include_router(calendar_router, prefix="/api/calendar", tags=["calendar"])
    fastapi_app.include_router(ai_router, prefix="/api/ai", tags=["ai"])
    fastapi_app.include_router(accounting_router, prefix="/api/accounting", tags=["accounting"])
    fastapi_app.include_router(contacts_router, prefix="/api/contacts", tags=["contacts"])
    fastapi_app.include_router(invoicing_router, prefix="/api/invoices", tags=["invoices"])
    fastapi_app.include_router(reminder_router, prefix="/api/invoices", tags=["payment-reminders"])
    fastapi_app.include_router(estimates_router, prefix="/api/estimates", tags=["estimates"])
    fastapi_app.include_router(income_router, prefix="/api/income", tags=["income"])
    fastapi_app.include_router(recurring_router, prefix="/api/recurring", tags=["recurring"])
    fastapi_app.include_router(budgets_router, prefix="/api/budgets", tags=["budgets"])
    fastapi_app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
    fastapi_app.include_router(email_router, prefix="/api/email", tags=["email"])
    fastapi_app.include_router(gmail_router, prefix="/api/integrations/gmail", tags=["gmail"])
    fastapi_app.include_router(plaid_router, prefix="/api/integrations/plaid", tags=["plaid"])
    fastapi_app.include_router(categorization_rules_router, prefix="/api/integrations/plaid", tags=["categorization-rules"])
    fastapi_app.include_router(stripe_router, prefix="/api/integrations/stripe", tags=["stripe"])
    fastapi_app.include_router(twilio_router, prefix="/api/integrations/sms", tags=["sms"])
    fastapi_app.include_router(integration_settings_router, prefix="/api/integrations", tags=["integration-settings"])
    fastapi_app.include_router(export_router, prefix="/api/export", tags=["export"])
    fastapi_app.include_router(period_router, prefix="/api/accounting", tags=["accounting-periods"])
    fastapi_app.include_router(credit_notes_router, prefix="/api/invoices", tags=["credit-notes"])
    fastapi_app.include_router(tax_router, prefix="/api", tags=["sales-tax"])
    fastapi_app.include_router(cashbook_router, prefix="/api/cashbook", tags=["cashbook"])

    # WebSocket endpoint
    @fastapi_app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
        from app.auth.utils import decode_token

        token_data = decode_token(token, settings)
        if token_data is None:
            await websocket.close(code=4001, reason="Invalid token")
            return

        user_id = str(token_data.sub)
        await websocket_manager.connect(user_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            websocket_manager.disconnect(user_id, websocket)

    # System endpoints
    @fastapi_app.get("/api/system/health")
    async def health():
        return {"data": {"status": "healthy"}}

    @fastapi_app.get("/api/system/stats")
    async def stats(request: Request):
        from app.auth.models import User
        from app.documents.models import Document
        from app.collaboration.models import ApprovalWorkflow, ApprovalStatus
        from app.accounting.models import Expense

        async with request.app.state.session_factory() as db:
            doc_count = (await db.execute(select(func.count(Document.id)))).scalar() or 0
            storage_used = (await db.execute(select(func.coalesce(func.sum(Document.file_size), 0)))).scalar() or 0
            user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
            pending_approvals = (await db.execute(
                select(func.count(ApprovalWorkflow.id)).where(
                    ApprovalWorkflow.status == ApprovalStatus.PENDING
                )
            )).scalar() or 0
            expense_count = (await db.execute(select(func.count(Expense.id)))).scalar() or 0
            total_expenses = (await db.execute(
                select(func.coalesce(func.sum(Expense.amount), 0))
            )).scalar() or 0

        return {
            "data": {
                "document_count": doc_count,
                "storage_used": storage_used,
                "user_count": user_count,
                "pending_approvals": pending_approvals,
                "expense_count": expense_count,
                "total_expenses": total_expenses,
            }
        }

    # Register exception handlers
    register_exception_handlers(fastapi_app)

    # Serve frontend static files in production
    # The built frontend at ../frontend/dist/ is served at /
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        # Serve static assets (JS, CSS, images)
        fastapi_app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        # Catch-all: serve index.html for SPA client-side routing
        @fastapi_app.get("/{path:path}")
        async def spa_fallback(path: str):
            # If the file exists in dist/, serve it (e.g. favicon, manifest, icons)
            file_path = frontend_dist / path
            if path and file_path.is_file():
                return FileResponse(file_path)
            # Otherwise return index.html for client-side routing
            return FileResponse(frontend_dist / "index.html")

    return fastapi_app


app = create_app()
