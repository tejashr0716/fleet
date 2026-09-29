"""HTTP routers package."""

from __future__ import annotations

from app.routers.alerts import router as alerts_router
from app.routers.fleet import router as fleet_router
from app.routers.geofences import router as geofences_router
from app.routers.health import router as health_router
from app.routers.positions import router as positions_router
from app.routers.vehicles import router as vehicles_router

__all__ = [
    "alerts_router",
    "fleet_router",
    "geofences_router",
    "health_router",
    "positions_router",
    "vehicles_router",
]
