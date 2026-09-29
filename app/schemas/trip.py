"""Trip response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TripRead(BaseModel):
    """Serialized vehicle trip summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    started_at: datetime
    ended_at: datetime
    distance_km: float
    avg_speed_kmh: float
    max_speed_kmh: float
    position_count: int
