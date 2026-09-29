"""Vehicle filter and serialization schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.vehicle import VehicleStatus, VehicleType


class VehicleFilters(BaseModel):
    """Query parameters for vehicle list queries."""

    status: list[VehicleStatus] | None = None
    vehicle_type: list[VehicleType] | None = None
    q: str | None = Field(default=None, max_length=32)
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class VehicleRead(BaseModel):
    """Serialized vehicle asset record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    label: str
    vehicle_type: VehicleType
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime
