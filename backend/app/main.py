import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Configure app-level logging BEFORE anything else.
# uvicorn's default config installs handlers ONLY for the uvicorn.*
# namespace, so app-module `logger.info(...)` calls were being dropped
# silently. setup_logging() replaces any handlers already attached to the
# root by lazy imports.
#
# Read straight from the environment rather than Settings(): this runs at
# import time, before the app (and its settings) are constructed.
from app.core.logging_config import setup_logging

setup_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_logs=os.getenv("JSON_LOGS", "").lower() in ("1", "true", "yes"),
)

logger = logging.getLogger(__name__)

from typing import Annotated

from fastapi import Depends, FastAPI, Request, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings
from app.core.exceptions import register_exception_handlers
from app.dependencies import require_feature, get_current_user
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
import app.integrations.stripe_connect.models  # noqa: F401
import app.cards.models  # noqa: F401
import app.widget.models  # noqa: F401
import app.integrations.twilio.models  # noqa: F401
import app.estimates.models  # noqa: F401
import app.invoicing.reminder_models  # noqa: F401
import app.integrations.settings_models  # noqa: F401
import app.accounting.period_models  # noqa: F401
import app.invoicing.credit_models  # noqa: F401
import app.accounting.tax_models  # noqa: F401
import app.cashbook.models  # noqa: F401
import app.meetings.models  # noqa: F401
import app.office.models  # noqa: F401
import app.settings.models  # noqa: F401
import app.public.models  # noqa: F401
import app.proposals.models  # noqa: F401
import app.reconciliation.models  # noqa: F401
import app.inbox.models  # noqa: F401
import app.forms.models  # noqa: F401
import app.communication.models  # noqa: F401
import app.communication.identity_capture  # noqa: F401
import app.tasks.models  # noqa: F401
import app.workflows.models  # noqa: F401
import app.pages.models  # noqa: F401
import app.scheduling.models  # noqa: F401
import app.branding.models  # noqa: F401
import app.brain.models  # noqa: F401
import app.smart_import.models  # noqa: F401
import app.kyc.models  # noqa: F401
import app.integrations.google_calendar.models  # noqa: F401
import app.platform_admin.models  # noqa: F401
import app.coach.models  # noqa: F401
import app.news.models  # noqa: F401
import app.events.models  # noqa: F401
# contacts.models now includes ContactTag, ContactActivity, FileShare, etc.


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = application.state.settings

    # Ensure data directories exist before DB connection
    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    Path(settings.recordings_storage_path).mkdir(parents=True, exist_ok=True)
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

    # Seed starter page templates
    try:
        from app.pages.seed_templates import seed_starter_templates

        async with application.state.session_factory() as session:
            count = await seed_starter_templates(session)
            if count:
                logger.info("Seeded %d starter page templates", count)
    except Exception as e:
        logger.warning("Failed to seed templates: %s", e)

    # Seed platform admin defaults (feature flags, pricing settings)
    try:
        from app.platform_admin.service import seed_defaults

        async with application.state.session_factory() as session:
            count = await seed_defaults(session)
            if count:
                logger.info("Seeded %d platform admin defaults", count)
    except Exception as e:
        logger.warning("Failed to seed platform admin defaults: %s", e)

    yield

    shutdown_scheduler()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = Settings()
    settings.validate_secrets()

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
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    )

    # Correlation ID — one id per request, stamped on every log line that
    # request produces and echoed back as X-Request-ID so a user-reported
    # failure can be traced to its logs. Honours an inbound X-Request-ID so
    # the id survives a proxy hop.
    @fastapi_app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        from app.core.logging_config import correlation_id, new_correlation_id

        inbound = request.headers.get("X-Request-ID")
        if inbound:
            correlation_id.set(inbound[:64])
            cid = inbound[:64]
        else:
            cid = new_correlation_id()

        response = await call_next(request)
        response.headers["X-Request-ID"] = cid
        return response

    # Paths that are DESIGNED to be iframed on third-party sites: the
    # public booking page (the Calendar share hub hands out an <iframe>
    # embed snippet for it) and the email-capture widget frame. These
    # get frame-ancestors * instead of X-Frame-Options DENY — everything
    # else keeps the strict default.
    EMBEDDABLE_PATH_PREFIXES = ("/book/", "/embed/")

    # Security headers middleware — adds standard protective headers to all responses
    @fastapi_app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith(EMBEDDABLE_PATH_PREFIXES):
            response.headers["Content-Security-Policy"] = "frame-ancestors *"
        else:
            response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Rewrite *internal* redirect Location headers to be relative so they
    # work correctly behind a dev proxy (Vite) without cross-origin issues.
    # External redirects (e.g. to accounts.google.com) are left untouched.
    @fastapi_app.middleware("http")
    async def rewrite_redirect_to_relative(request: Request, call_next):
        response = await call_next(request)
        if response.status_code in (301, 302, 307, 308):
            location = response.headers.get("location", "")
            if location.startswith("http"):
                from urllib.parse import urlparse
                parsed = urlparse(location)
                request_host = request.headers.get("host", "")
                # Only rewrite if the redirect target is our own host
                if parsed.hostname and parsed.hostname in (request_host.split(":")[0], "localhost", "127.0.0.1"):
                    relative = parsed.path
                    if parsed.query:
                        relative += "?" + parsed.query
                    response.headers["location"] = relative
        return response

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
    from app.integrations.stripe_connect.router import router as stripe_connect_router
    from app.cards.router import router as cards_router
    from app.widget.router import router as widget_router
    from app.integrations.twilio.router import router as twilio_router
    from app.estimates.router import router as estimates_router
    from app.invoicing.reminder_router import router as reminder_router
    from app.integrations.settings_router import router as integration_settings_router
    from app.export.router import router as export_router
    from app.accounting.period_router import router as period_router
    from app.invoicing.credit_router import router as credit_notes_router
    from app.accounting.tax_router import router as tax_router
    from app.cashbook.router import router as cashbook_router
    from app.meetings.router import router as meetings_router
    from app.office.router import router as office_router
    from app.settings.router import router as settings_router
    from app.public.router import router as public_router
    from app.proposals.router import router as proposals_router
    from app.reconciliation.router import router as reconciliation_router
    from app.inbox.router import router as inbox_router
    from app.portal.router import router as portal_router
    from app.forms.router import router as forms_router
    from app.communication.router import router as communication_router
    from app.communication.automation_router import router as automation_router
    from app.tasks.router import router as tasks_router
    from app.workflows.router import router as workflows_router
    from app.pages.router import router as pages_router, analytics_router
    from app.scheduling.router import router as scheduling_router
    from app.branding.router import router as branding_router
    from app.brain.router import router as brain_router
    from app.smart_import.router import router as smart_import_router
    from app.kyc.router import router as kyc_router
    from app.integrations.google_calendar.router import router as google_calendar_router
    from app.platform_admin.router import router as platform_admin_router
    from app.coach.router import router as coach_router
    from app.news.router import router as news_router
    from app.events.router import router as events_router
    from app.wtp.router import router as wtp_router

    fastapi_app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    fastapi_app.include_router(documents_router, prefix="/api/documents", tags=["documents"], dependencies=[Depends(require_feature("drive"))])
    fastapi_app.include_router(collaboration_router, prefix="/api", tags=["collaboration"])
    fastapi_app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
    fastapi_app.include_router(calendar_router, prefix="/api/calendar", tags=["calendar"], dependencies=[Depends(require_feature("calendar"))])
    fastapi_app.include_router(ai_router, prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_feature("obrain_chat"))])
    fastapi_app.include_router(accounting_router, prefix="/api/accounting", tags=["accounting"], dependencies=[Depends(require_feature("expenses"))])
    fastapi_app.include_router(contacts_router, prefix="/api/contacts", tags=["contacts"], dependencies=[Depends(require_feature("contacts"))])
    fastapi_app.include_router(invoicing_router, prefix="/api/invoices", tags=["invoices"], dependencies=[Depends(require_feature("invoices"))])
    fastapi_app.include_router(reminder_router, prefix="/api/invoices", tags=["payment-reminders"], dependencies=[Depends(require_feature("invoices"))])
    fastapi_app.include_router(estimates_router, prefix="/api/estimates", tags=["estimates"], dependencies=[Depends(require_feature("estimates"))])
    fastapi_app.include_router(income_router, prefix="/api/income", tags=["income"])
    fastapi_app.include_router(recurring_router, prefix="/api/recurring", tags=["recurring"], dependencies=[Depends(require_feature("recurring"))])
    fastapi_app.include_router(budgets_router, prefix="/api/budgets", tags=["budgets"])
    fastapi_app.include_router(reports_router, prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_feature("reports"))])
    fastapi_app.include_router(email_router, prefix="/api/email", tags=["email"], dependencies=[Depends(require_feature("email_scanner"))])
    fastapi_app.include_router(gmail_router, prefix="/api/integrations/gmail", tags=["gmail"])
    fastapi_app.include_router(plaid_router, prefix="/api/integrations/plaid", tags=["plaid"])
    fastapi_app.include_router(categorization_rules_router, prefix="/api/integrations/plaid", tags=["categorization-rules"])
    fastapi_app.include_router(stripe_router, prefix="/api/integrations/stripe", tags=["stripe"])
    fastapi_app.include_router(stripe_connect_router, prefix="/api/integrations/stripe-connect", tags=["stripe-connect"])
    fastapi_app.include_router(cards_router, prefix="/api/cards", tags=["cards"], dependencies=[Depends(require_feature("cards"))])
    fastapi_app.include_router(widget_router, prefix="/api/widget", tags=["widget"], dependencies=[Depends(require_feature("forms"))])
    fastapi_app.include_router(twilio_router, prefix="/api/integrations/sms", tags=["sms"])
    fastapi_app.include_router(integration_settings_router, prefix="/api/integrations", tags=["integration-settings"])
    fastapi_app.include_router(export_router, prefix="/api/export", tags=["export"], dependencies=[Depends(require_feature("reports"))])
    fastapi_app.include_router(period_router, prefix="/api/accounting", tags=["accounting-periods"], dependencies=[Depends(require_feature("expenses"))])
    fastapi_app.include_router(credit_notes_router, prefix="/api/invoices", tags=["credit-notes"], dependencies=[Depends(require_feature("invoices"))])
    fastapi_app.include_router(tax_router, prefix="/api", tags=["sales-tax"], dependencies=[Depends(require_feature("tax"))])
    fastapi_app.include_router(cashbook_router, prefix="/api/cashbook", tags=["cashbook"], dependencies=[Depends(require_feature("cashbook"))])
    fastapi_app.include_router(meetings_router, prefix="/api/meetings", tags=["meetings"], dependencies=[Depends(require_feature("meeting_rooms"))])
    fastapi_app.include_router(office_router, prefix="/api/office", tags=["office"], dependencies=[Depends(require_feature("docs"))])
    fastapi_app.include_router(settings_router, prefix="/api/settings/company", tags=["settings"])
    fastapi_app.include_router(public_router, prefix="/api/public", tags=["public"])
    fastapi_app.include_router(proposals_router, prefix="/api/proposals", tags=["proposals"], dependencies=[Depends(require_feature("proposals"))])
    fastapi_app.include_router(reconciliation_router, prefix="/api/reconciliation", tags=["reconciliation"], dependencies=[Depends(require_feature("cashbook"))])
    fastapi_app.include_router(inbox_router, prefix="/api/inbox", tags=["inbox"], dependencies=[Depends(require_feature("inbox"))])
    fastapi_app.include_router(portal_router, prefix="/api/portal", tags=["portal"])
    fastapi_app.include_router(forms_router, prefix="/api/forms", tags=["forms"], dependencies=[Depends(require_feature("forms"))])
    fastapi_app.include_router(communication_router, prefix="/api/communication", tags=["communication"], dependencies=[Depends(require_feature("phone"))])
    fastapi_app.include_router(automation_router, prefix="/api/communication", tags=["automation"], dependencies=[Depends(require_feature("phone"))])
    fastapi_app.include_router(tasks_router, prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(require_feature("tasks"))])
    fastapi_app.include_router(workflows_router, prefix="/api/workflows", tags=["workflows"], dependencies=[Depends(require_feature("workflows"))])
    fastapi_app.include_router(pages_router, prefix="/api/pages", tags=["pages"], dependencies=[Depends(require_feature("pages"))])
    fastapi_app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
    fastapi_app.include_router(scheduling_router, prefix="/api/scheduling", tags=["scheduling"], dependencies=[Depends(require_feature("calendar"))])
    fastapi_app.include_router(branding_router, prefix="/api/branding", tags=["branding"])
    fastapi_app.include_router(brain_router, prefix="/api/brain", tags=["brain"], dependencies=[Depends(require_feature("obrain_chat"))])
    fastapi_app.include_router(smart_import_router, prefix="/api/smart-import", tags=["Smart Import"], dependencies=[Depends(require_feature("smart_import"))])
    fastapi_app.include_router(kyc_router, prefix="/api/kyc", tags=["KYC"])
    fastapi_app.include_router(google_calendar_router, prefix="/api/integrations/google-calendar", tags=["google-calendar"], dependencies=[Depends(require_feature("calendar"))])
    fastapi_app.include_router(platform_admin_router, prefix="/api/platform-admin", tags=["platform-admin"], dependencies=[Depends(require_feature("platform_admin"))])
    fastapi_app.include_router(events_router, prefix="/api/platform-admin/events", tags=["events"], dependencies=[Depends(require_feature("platform_admin"))])
    fastapi_app.include_router(wtp_router, prefix="/api/platform-admin/wtp", tags=["wtp"], dependencies=[Depends(require_feature("platform_admin"))])
    fastapi_app.include_router(coach_router, prefix="/api/coach", tags=["coach"], dependencies=[Depends(require_feature("obrain_coach"))])
    fastapi_app.include_router(news_router, prefix="/api/news", tags=["news"])

    # WebSocket endpoint — shared body, mounted at both /ws (legacy) and
    # /api/ws (preferred, routes through the same Apache proxy as /api/*).
    # The DH/Cloudflare path historically dropped Upgrade headers on /ws;
    # /api/ws goes through the proven /api/* proxy chain.
    async def _ws_handler(websocket: WebSocket, token: str):
        # Validate origin to prevent cross-site WebSocket hijacking
        origin = websocket.headers.get("origin", "")
        allowed_origins = settings.cors_origins
        if origin and not any(origin.startswith(o) for o in allowed_origins):
            await websocket.close(code=4003, reason="Origin not allowed")
            return

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

    @fastapi_app.websocket("/ws")
    async def websocket_endpoint_legacy(websocket: WebSocket, token: str = Query(...)):
        await _ws_handler(websocket, token)

    @fastapi_app.websocket("/api/ws")
    async def websocket_endpoint_api(websocket: WebSocket, token: str = Query(...)):
        await _ws_handler(websocket, token)

    # ---- Docs real-time collaboration (Hocuspocus) proxy ----
    # DreamHost's proxy only exposes port 8000 -- Hocuspocus (a separate Node
    # process on 127.0.0.1:1234) is unreachable from the browser directly.
    # This is a protocol-agnostic byte pipe under /api/* (the proven WS path,
    # see the comment above _ws_handler) so the collaboration server rides
    # through the same proxy chain as everything else. Hocuspocus's own
    # onAuthenticate hook validates the token against /api/auth/me -- this
    # proxy does no auth itself, it just forwards bytes both ways.
    @fastapi_app.websocket("/api/collaborate/{doc_id}")
    async def collaborate_proxy(websocket: WebSocket, doc_id: str):
        import asyncio

        import websockets as ws_client

        await websocket.accept()

        query = websocket.url.query
        upstream_url = f"ws://127.0.0.1:{settings.hocuspocus_port}/{doc_id}"
        if query:
            upstream_url += f"?{query}"

        try:
            async with ws_client.connect(upstream_url) as upstream:
                logger.info("collaborate_proxy: connected to upstream %s", upstream_url)

                async def pump_client_to_upstream():
                    while True:
                        message = await websocket.receive()
                        if message["type"] == "websocket.disconnect":
                            return
                        if message.get("bytes") is not None:
                            await upstream.send(message["bytes"])
                        elif message.get("text") is not None:
                            await upstream.send(message["text"])

                async def pump_upstream_to_client():
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)

                tasks = [
                    asyncio.create_task(pump_client_to_upstream()),
                    asyncio.create_task(pump_upstream_to_client()),
                ]
                try:
                    done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        exc = task.exception()
                        if exc is not None:
                            logger.warning("collaborate_proxy pump task failed: %r", exc)
                finally:
                    for task in tasks:
                        task.cancel()
        except WebSocketDisconnect:
            pass
        except (OSError, ws_client.exceptions.WebSocketException) as exc:
            # Hocuspocus process unreachable/down -- close so the client's
            # provider falls back to disconnected state (REST autosave still
            # covers editing; see DocEditorPage.tsx's connectionStatus).
            logger.warning("collaborate_proxy: upstream unavailable: %r", exc)
            try:
                await websocket.close(code=1011, reason="Collaboration server unavailable")
            except RuntimeError:
                pass
        logger.info("collaborate_proxy: connection for %s ended", doc_id)

    # System endpoints
    @fastapi_app.get("/api/system/health")
    async def health():
        return {"data": {"status": "healthy"}}

    @fastapi_app.get("/api/system/stats")
    async def stats(request: Request, _: Annotated["User", Depends(get_current_user)]):
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

    # ── .well-known routes (TWA / Digital Asset Links) ──────────────────
    @fastapi_app.get("/.well-known/assetlinks.json")
    async def assetlinks():
        """Digital Asset Links for future TWA (Trusted Web Activity) verification."""
        return []  # Empty array until Android APK package is configured

    # Serve frontend static files in production
    # The built frontend at ../frontend/dist/ is served at /
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        frontend_dist_resolved = frontend_dist.resolve()

        # Serve static asset directories
        if (frontend_dist / "assets").is_dir():
            fastapi_app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")
        if (frontend_dist / "icons").is_dir():
            fastapi_app.mount("/icons", StaticFiles(directory=frontend_dist / "icons"), name="icons")

        # SPA fallback via 404 exception handler.
        # Unlike a catch-all route, this fires AFTER normal routing
        # (including redirect_slashes), so /api/documents correctly
        # redirects to /api/documents/ instead of serving index.html.
        @fastapi_app.exception_handler(StarletteHTTPException)
        async def spa_or_http_error(request: Request, exc: StarletteHTTPException):
            if exc.status_code == 404:
                path = request.url.path
                if not path.startswith("/api/") and not path.startswith("/ws"):
                    # Try to serve a static file from frontend/dist
                    clean = path.lstrip("/")
                    if clean:
                        file_path = (frontend_dist / clean).resolve()
                        if file_path.is_file() and str(file_path).startswith(str(frontend_dist_resolved)):
                            return FileResponse(file_path)
                    # SPA fallback – return index.html for client-side routing
                    return FileResponse(frontend_dist / "index.html")
            # API 404s and all other HTTP errors → JSON envelope
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": {"code": "HTTP_ERROR", "message": exc.detail or "Error", "details": None}},
            )

    return fastapi_app


app = create_app()
