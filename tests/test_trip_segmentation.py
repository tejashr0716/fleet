"""Test suite for trip segmentation and trajectory distance analytics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.trips import TripSegmenter, haversine_km


def test_haversine_distance_calculation() -> None:
    """Verify haversine distance between two known Bengaluru landmarks."""
    # Vidhana Soudha: 12.9796, 77.5907
    # MG Road: 12.9756, 77.6066
    dist_km = haversine_km(12.9796, 77.5907, 12.9756, 77.6066)
    assert 1.5 < dist_km < 2.0


def test_trip_segmenter_continuity_and_stops() -> None:
    """Verify sequential telemetry creates, accumulates, and bounds trip distance and speed."""
    base_time = datetime(2026, 9, 30, 8, 0, 0, tzinfo=UTC)

    # 1. First movement packet starts trip
    trip = TripSegmenter.segment(
        prev_trip=None,
        vehicle_id=1,
        lat=12.9700,
        lon=77.5900,
        prev_lat=None,
        prev_lon=None,
        speed_kmh=40.0,
        timestamp=base_time,
    )
    assert trip is not None
    assert trip.position_count == 1
    assert trip.distance_km == 0.0

    # 2. Second movement packet accumulates distance
    trip = TripSegmenter.segment(
        prev_trip=trip,
        vehicle_id=1,
        lat=12.9750,
        lon=77.5950,
        prev_lat=12.9700,
        prev_lon=77.5900,
        speed_kmh=50.0,
        timestamp=base_time + timedelta(seconds=10),
    )
    assert trip.position_count == 2
    assert trip.distance_km > 0.5
    assert trip.max_speed_kmh == 50.0

    # 3. Stationary packet (idle) maintains previous trip without ending it
    trip = TripSegmenter.segment(
        prev_trip=trip,
        vehicle_id=1,
        lat=12.9750,
        lon=77.5950,
        prev_lat=12.9750,
        prev_lon=77.5950,
        speed_kmh=0.0,
        timestamp=base_time + timedelta(seconds=20),
    )
    assert trip.position_count == 2  # Not incremented on stationary point
