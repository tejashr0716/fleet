"""Alerts query and acknowledgment router."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.errors import NotFoundError
from app.repositories.alert_repo import AlertRepository
from app.schemas.alert import AlertFilters, AlertRead

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertRead])
async def list_alerts(
    filters: Annotated[AlertFilters, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AlertRead]:
    """Retrieve filtered alerts matching kind, severity, and acknowledgment state."""
    repo = AlertRepository(db)
    alerts = await repo.list_alerts(filters)
    return [AlertRead.model_validate(a) for a in alerts]


@router.patch("/{alert_id}", response_model=AlertRead)
async def acknowledge_alert(
    alert_id: int,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AlertRead:
    """Acknowledge an active alert by ID."""
    repo = AlertRepository(db)
    alert = await repo.acknowledge(alert_id)
    if not alert:
        raise NotFoundError("Alert", alert_id)
    return AlertRead.model_validate(alert)
