from app.models.alert import Alert
from app.services.geofence import inside


def evaluate_alerts(point, previous, fences, speed_limit):
    # Late history is stored, but must not create false live-state transitions.
    if previous is not None and point.recorded_at <= previous.recorded_at:
        return []
    result = []
    if point.speed_kmh > speed_limit and (previous is None or previous.speed_kmh <= speed_limit):
        result.append(
            Alert(
                vehicle_id=point.vehicle_id,
                kind="speeding",
                recorded_at=point.recorded_at,
                details={"speed_kmh": point.speed_kmh, "limit_kmh": speed_limit},
            )
        )
    if previous is not None:
        for fence in fences:
            before, after = inside(previous, fence), inside(point, fence)
            if before != after:
                result.append(
                    Alert(
                        vehicle_id=point.vehicle_id,
                        kind="geofence_enter" if after else "geofence_exit",
                        recorded_at=point.recorded_at,
                        details={"geofence_id": fence.id, "geofence_name": fence.name},
                    )
                )
    return result
