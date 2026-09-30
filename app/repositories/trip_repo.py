from app.repositories.position_repo import history
from app.services.trips import segment_trace


async def trace_sessions(session, vehicle_id, from_time, to_time):
    points, truncated = await history(session, vehicle_id, from_time, to_time, 5000)
    return segment_trace(points), truncated
