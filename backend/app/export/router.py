
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.dependencies import get_current_user, get_db, require_role

from . import service
from .schemas import ExportRequest

router = APIRouter()


@router.post("/quickbooks")
async def export_quickbooks(
    data: ExportRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    if data.format == "iif":
        content = await service.export_to_iif(db, data.date_from, data.date_to, data.include)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=export.iif"},
        )
    else:
        content = await service.export_to_csv(db, data.date_from, data.date_to, data.include)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=export.csv"},
        )


@router.get("/chart-of-accounts")
async def export_chart_of_accounts(
    user: User = Depends(require_role([Role.ACCOUNTANT, Role.ADMIN])),
):
    content = await service.export_chart_of_accounts()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chart_of_accounts.csv"},
    )
