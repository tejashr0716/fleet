"""H3 geospatial indexing and geofence evaluation service."""

from __future__ import annotations

import math
from typing import Any

import h3


def latlng_to_h3_int(lat: float, lon: float, resolution: int = 8) -> int:
    """Convert WGS84 coordinates to an H3 integer index.

    Supports both h3-py v4+ and v3 fallback.

    Args:
        lat: WGS84 Latitude.
        lon: WGS84 Longitude.
        resolution: H3 resolution level (default 8).

    Returns:
        int: 64-bit integer representation of the H3 cell.
    """
    if hasattr(h3, "latlng_to_cell"):
        cell_hex = h3.latlng_to_cell(lat, lon, resolution)
    else:  # v3 compatibility fallback
        cell_hex = h3.geo_to_h3(lat, lon, resolution)
    return int(cell_hex, 16)


def polyfill_geojson_to_h3(geojson: dict[str, Any], resolution: int = 8) -> list[int]:
    """Polyfill a GeoJSON Polygon or Circle geometry into an array of H3 cell integers.

    Converts point-in-polygon computational complexity at runtime into a simple
    O(1) set/array membership check per position.

    Args:
        geojson: GeoJSON geometry dictionary.
        resolution: Target H3 resolution (default 8).

    Returns:
        list[int]: Unique integer H3 cell IDs intersecting the geometry.
    """
    geom_type = geojson.get("type")

    if geom_type == "Polygon":
        coords = geojson.get("coordinates", [])
        if not coords or not coords[0]:
            return []

        # GeoJSON is [lon, lat]; h3-py v4 expects [lat, lon]
        outer_ring = [(pt[1], pt[0]) for pt in coords[0]]

        if hasattr(h3, "LatLngPoly") and hasattr(h3, "polygon_to_cells"):
            try:
                poly = h3.LatLngPoly(outer_ring)
                cells_hex = h3.polygon_to_cells(poly, res=resolution)
            except Exception:
                cells_hex = []
        elif hasattr(h3, "polygon_to_cells"):
            try:
                geo_polygon = {"outer": outer_ring, "holes": []}
                cells_hex = h3.polygon_to_cells(geo_polygon, res=resolution)
            except Exception:
                cells_hex = []
        else:  # v3 fallback
            geo_json_poly = {"type": "Polygon", "coordinates": coords}
            cells_hex = h3.polyfill(geo_json_poly, resolution, geo_json_conformant=True)

        return [int(cell, 16) for cell in cells_hex]

    if geom_type == "Circle" or "radius_m" in geojson:
        center = geojson.get("center") or geojson.get("coordinates")
        if not center:
            return []
        radius_m = float(geojson.get("radius_m", 500))
        lat, lon = center[1], center[0]

        if hasattr(h3, "latlng_to_cell"):
            center_cell = h3.latlng_to_cell(lat, lon, resolution)
        else:
            center_cell = h3.geo_to_h3(lat, lon, resolution)

        # Approximate edge radius in H3 k-ring steps
        if hasattr(h3, "get_hexagon_edge_length_avg"):
            edge_len_m = h3.get_hexagon_edge_length_avg(resolution, unit="m")
        else:
            edge_len_m = h3.edge_length(resolution, unit="m")

        k = max(1, math.ceil(radius_m / (edge_len_m * 1.732)))

        if hasattr(h3, "grid_disk"):
            cells_hex = h3.grid_disk(center_cell, k)
        else:
            cells_hex = h3.k_ring(center_cell, k)

        return [int(c, 16) for c in cells_hex]

    return []
