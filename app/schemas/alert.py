"""Alert request filter and serialization schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.alert import AlertKind, AlertSeverity


class AlertFilters(BaseModel):
    """Query parameter filter for alerts listing."""

    kind: AlertKind | None = None
    severity: AlertSeverity | None = None
    acknowledged: bool | None = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class AlertRead(BaseModel):
    """Serialized alert notification."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    kind: AlertKind
    severity: AlertSeverity
    payload: dict[str, Any]
    time: datetime
    acknowledged: bool
