"""Operator-only read of the willingness-to-pay interview cohort.

Same boundary as app/events/router.py, deliberately: require_platform_admin
at the endpoint plus require_feature("platform_admin") at the router mount
in main.py. This is a *different* data source (a manually-exported CSV, not
live product events) but the Pricing Lab treats both as operator-only
aggregate reads, so both sit behind the identical gate.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.models import User
from app.platform_admin.router import require_platform_admin
from app.wtp.service import get_wtp_responses

router = APIRouter()


@router.get("/responses")
async def wtp_responses(admin: Annotated[User, Depends(require_platform_admin)]):
    return {"data": get_wtp_responses()}
