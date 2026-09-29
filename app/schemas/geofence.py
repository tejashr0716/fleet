"""Geofence request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.geofence import GeofenceEventKind, GeofenceKind


class GeofenceCreate(BaseModel):
    """Schema for registering a new geofence boundary."""

    name: str = Field(min_length=3, max_length=64)
    kind: GeofenceKind = GeofenceKind.POLYGON
    geojson: dict[str, Any]
    h3_resolution: int = Field(default=8, ge=6, le=10)


class GeofenceRead(BaseModel):
    """Serialized geofence record with polyfilled H3 cells."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: GeofenceKind
    geojson: dict[str, Any]
    h3_resolution: int
    h3_cells: list[int]
    created_at: datetime


class GeofenceEventRead(BaseModel):
    """Serialized geofence transition event."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    vehicle_id: int
    geofence_id: int
    event: GeofenceEventKind
    time: datetime
