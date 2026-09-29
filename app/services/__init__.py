"""Domain services package."""

from __future__ import annotations

from app.services.alerts import evaluate_idle, evaluate_speeding, generate_signal_lost_alert
from app.services.geofence import latlng_to_h3_int, polyfill_geojson_to_h3
from app.services.live_state import LiveStateManager
from app.services.trips import TripSegmenter, haversine_km

__all__ = [
    "LiveStateManager",
    "TripSegmenter",
    "evaluate_idle",
    "evaluate_speeding",
    "generate_signal_lost_alert",
    "haversine_km",
    "latlng_to_h3_int",
    "polyfill_geojson_to_h3",
]
