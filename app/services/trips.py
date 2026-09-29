"""Trip segmentation and trajectory distance analytics."""

from __future__ import annotations

import math
from datetime import datetime

from app.models.trip import Trip


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two coordinates.

    Args:
        lat1: Latitude of point 1.
        lon1: Longitude of point 1.
        lat2: Latitude of point 2.
        lon2: Longitude of point 2.

    Returns:
        float: Distance in kilometers.
    """
    earth_radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return earth_radius_km * c


class TripSegmenter:
    """Detects trip intervals from sequential vehicle positions."""

    @staticmethod
    def segment(
        prev_trip: Trip | None,
        vehicle_id: int,
        lat: float,
        lon: float,
        prev_lat: float | None,
        prev_lon: float | None,
        speed_kmh: float,
        timestamp: datetime,
        idle_threshold_kmh: float = 2.0,
    ) -> Trip | None:
        """Update active trip or start a new trip segment.

        Args:
            prev_trip: Active ongoing trip or None.
            vehicle_id: Vehicle ID.
            lat: Current latitude.
            lon: Current longitude.
            prev_lat: Previous latitude if known.
            prev_lon: Previous longitude if known.
            speed_kmh: Current speed in km/h.
            timestamp: Observation timestamp (UTC).
            idle_threshold_kmh: Speed threshold below which vehicle is considered stationary.

        Returns:
            Trip | None: The active updated Trip instance.
        """
        if speed_kmh < idle_threshold_kmh:
            return prev_trip

        if prev_trip is None:
            return Trip(
                vehicle_id=vehicle_id,
                started_at=timestamp,
                ended_at=timestamp,
                distance_km=0.0,
                avg_speed_kmh=speed_kmh,
                max_speed_kmh=speed_kmh,
                position_count=1,
            )

        if prev_lat is not None and prev_lon is not None:
            delta_dist = haversine_km(prev_lat, prev_lon, lat, lon)
            prev_trip.distance_km += delta_dist

        prev_trip.position_count += 1
        prev_trip.ended_at = timestamp
        prev_trip.max_speed_kmh = max(prev_trip.max_speed_kmh, speed_kmh)
        prev_trip.avg_speed_kmh = (
            prev_trip.avg_speed_kmh * (prev_trip.position_count - 1) + speed_kmh
        ) / prev_trip.position_count
        return prev_trip
