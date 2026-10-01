from app.models.trip import TraceSession
from app.services.geofence import distance_m


def segment_trace(points, gap_seconds=300):
    """Group observed points by a five-minute silence gap; no map matching."""
    groups = []
    for point in sorted(points, key=lambda p: p.recorded_at):
        if (
            not groups
            or (point.recorded_at - groups[-1][-1].recorded_at).total_seconds() > gap_seconds
        ):
            groups.append([])
        groups[-1].append(point)
    return [
        TraceSession(
            g[0].vehicle_id,
            g[0].recorded_at,
            g[-1].recorded_at,
            len(g),
            sum(distance_m(a.lat, a.lon, b.lat, b.lon) for a, b in zip(g, g[1:], strict=False))
            / 1000,
        )
        for g in groups
    ]
