"""Database models package."""

from __future__ import annotations

from app.models.alert import Alert, AlertKind, AlertSeverity
from app.models.geofence import Geofence, GeofenceEvent, GeofenceEventKind, GeofenceKind
from app.models.position import Position
from app.models.trip import Trip
from app.models.vehicle import Base, Vehicle, VehicleStatus, VehicleType

__all__ = [
    "Alert",
    "AlertKind",
    "AlertSeverity",
    "Base",
    "Geofence",
    "GeofenceEvent",
    "GeofenceEventKind",
    "GeofenceKind",
    "Position",
    "Trip",
    "Vehicle",
    "VehicleStatus",
    "VehicleType",
]
