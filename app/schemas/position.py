from datetime import UTC, datetime, timedelta

from pydantic import Field, field_validator

from app.schemas.common import Schema


class PositionIn(Schema):
    vehicle_id: int = Field(gt=0)
    recorded_at: datetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmh: float = Field(ge=0, le=250)
    heading: float = Field(default=0, ge=0, lt=360)

    @field_validator("recorded_at")
    @classmethod
    def valid_timestamp(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone is required; use an ISO-8601 UTC timestamp")
        value = value.astimezone(UTC)
        now = datetime.now(UTC)
        if value > now + timedelta(seconds=60):
            raise ValueError("Timestamp cannot be more than 60 seconds in the future")
        if value < now - timedelta(days=90):
            raise ValueError("Demo ingestion accepts only the last 90 days")
        return value


class PositionBatch(Schema):
    positions: list[PositionIn] = Field(min_length=1, max_length=100)
