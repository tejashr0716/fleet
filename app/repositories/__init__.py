"""Data repositories package."""

from __future__ import annotations

from app.repositories.alert_repo import AlertRepository
from app.repositories.geofence_repo import GeofenceRepository
from app.repositories.position_repo import PositionRepository
from app.repositories.trip_repo import TripRepository
from app.repositories.vehicle_repo import VehicleRepository

__all__ = [
    "AlertRepository",
    "GeofenceRepository",
    "PositionRepository",
    "TripRepository",
    "VehicleRepository",
]
