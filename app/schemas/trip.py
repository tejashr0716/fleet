from datetime import datetime

from app.schemas.common import Schema


class TripOut(Schema):
    vehicle_id: int
    started_at: datetime
    ended_at: datetime
    point_count: int
    distance_km: float
