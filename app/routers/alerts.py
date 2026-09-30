from fastapi import APIRouter, Depends, Query, Request

from app.repositories.alert_repo import latest_alerts
from app.schemas.alert import AlertOut
from app.security import require_user

router = APIRouter(prefix="/alerts", tags=["Alerts"], dependencies=[Depends(require_user)])


@router.get("", response_model=list[AlertOut])
async def alerts(request: Request, limit: int = Query(30, ge=1, le=200)):
    async with request.app.state.db.sessions() as session:
        return await latest_alerts(session, limit)
