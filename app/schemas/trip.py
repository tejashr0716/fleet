from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import Schema


class TripOut(Schema):
    """Compatibility schema for legacy gap-derived trace sessions."""

    vehicle_id: int
    started_at: datetime
    ended_at: datetime
    point_count: int
    distance_km: float


class StartTrip(Schema):
    route_key: Literal["central", "east", "west"] = "central"
    duration_seconds: int = Field(default=180, ge=5, le=600, strict=True)
    include_speeding: bool = Field(default=True, strict=True)


class ManagedTripOut(Schema):
    id: int
    vehicle_id: int
    route_key: str
    status: str
    source: str
    started_at: datetime
    expires_at: datetime
    ended_at: datetime | None
    duration_seconds: int
    include_speeding: bool
    end_reason: str | None
