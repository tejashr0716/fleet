from datetime import datetime

from app.schemas.common import Schema


class AlertOut(Schema):
    id: int
    vehicle_id: int
    kind: str
    recorded_at: datetime
    details: dict
