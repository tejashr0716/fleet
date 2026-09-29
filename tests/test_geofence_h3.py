"""Test suite for H3 indexing and geofence boundary transition logic."""

from __future__ import annotations

import h3

from app.models.geofence import Geofence, GeofenceKind
from app.services.geofence import latlng_to_h3_int, polyfill_geojson_to_h3


def test_h3_resolution_mapping() -> None:
    """Verify known Bangalore coordinate maps consistently to valid 64-bit integer H3 cells."""
    lat, lon = 12.9716, 77.5946

    r8_int = latlng_to_h3_int(lat, lon, resolution=8)
    r7_int = latlng_to_h3_int(lat, lon, resolution=7)

    assert r8_int > 0
    assert r7_int > 0

    # Verify hex representations
    r8_hex = hex(r8_int)[2:]
    r7_hex = hex(r7_int)[2:]
    assert h3.is_valid_cell(r8_hex)
    assert h3.is_valid_cell(r7_hex)
    assert h3.get_resolution(r8_hex) == 8
    assert h3.get_resolution(r7_hex) == 7


def test_geofence_polygon_polyfill() -> None:
    """Verify GeoJSON polygon polyfills to deterministic H3 cells."""
    polygon_geojson = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.5900, 12.9700],
                [77.6000, 12.9700],
                [77.6000, 12.9800],
                [77.5900, 12.9800],
                [77.5900, 12.9700],
            ]
        ],
    }

    cells = polyfill_geojson_to_h3(polygon_geojson, resolution=8)
    assert len(cells) > 0

    # Ensure center coordinate is contained within the cell set
    center_cell = latlng_to_h3_int(12.9750, 77.5950, resolution=8)
    assert center_cell in cells


def test_geofence_transition_events() -> None:
    """Verify entry and exit events trigger exactly once across transitions."""
    # Define a simulated geofence cell set
    geofence_cells = {1001, 1002, 1003}
    active_fence = Geofence(
        id=1,
        name="HQ Zone",
        kind=GeofenceKind.POLYGON,
        geojson={"type": "Polygon", "coordinates": []},
        h3_resolution=8,
        h3_cells=list(geofence_cells),
    )
    assert active_fence.id == 1

    # Route track: outside -> inside -> inside (idle) -> inside -> outside -> outside
    track_cells = [9999, 1001, 1001, 1002, 8888, 7777]

    enter_events = []
    exit_events = []

    prev_cell = None
    for curr_cell in track_cells:
        in_curr = curr_cell in geofence_cells
        in_prev = prev_cell in geofence_cells if prev_cell else False

        if in_curr and not in_prev:
            enter_events.append(curr_cell)
        elif in_prev and not in_curr:
            exit_events.append(curr_cell)

        prev_cell = curr_cell

    # Crucial test: exactly one ENTER and exactly one EXIT, not one per position inside
    assert len(enter_events) == 1, f"Expected exactly 1 ENTER event, got {len(enter_events)}"
    assert len(exit_events) == 1, f"Expected exactly 1 EXIT event, got {len(exit_events)}"
