from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trip:
    """Derived trace session; not an inference of a real-world business trip."""

    vehicle_id: int
    started_at: datetime
    ended_at: datetime
    point_count: int
    distance_km: float
