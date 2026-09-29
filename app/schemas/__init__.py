"""Pydantic schemas package."""

from __future__ import annotations

from app.schemas.alert import AlertFilters, AlertRead
from app.schemas.common import ResponseEnvelope
from app.schemas.geofence import GeofenceCreate, GeofenceEventRead, GeofenceRead
from app.schemas.position import (
    DownsampleMode,
    PositionBatchIngestSchema,
    PositionHistoryFilter,
    PositionHistoryResponse,
    PositionIngestSchema,
    PositionReadSchema,
)
from app.schemas.trip import TripRead
from app.schemas.vehicle import VehicleFilters, VehicleRead

__all__ = [
    "AlertFilters",
    "AlertRead",
    "DownsampleMode",
    "GeofenceCreate",
    "GeofenceEventRead",
    "GeofenceRead",
    "PositionBatchIngestSchema",
    "PositionHistoryFilter",
    "PositionHistoryResponse",
    "PositionIngestSchema",
    "PositionReadSchema",
    "ResponseEnvelope",
    "TripRead",
    "VehicleFilters",
    "VehicleRead",
]
