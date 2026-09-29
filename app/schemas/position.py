"""Position ingest and read schemas with strict validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DownsampleMode(StrEnum):
    """Supported downsampling levels for position history queries."""

    RAW = "raw"
    ONE_MIN = "1min"
    ONE_HOUR = "1hour"
    AUTO = "auto"


class PositionIngestSchema(BaseModel):
    """Single vehicle telemetry ingest payload."""

    model_config = ConfigDict(extra="forbid")

    vehicle_id: int = Field(gt=0, description="Vehicle ID foreign key")
    lat: float = Field(ge=-90.0, le=90.0, description="WGS84 Latitude")
    lon: float = Field(ge=-180.0, le=180.0, description="WGS84 Longitude")
    speed_kmh: float = Field(ge=0.0, le=300.0, description="Speed in km/h")
    heading: int = Field(ge=0, le=359, description="Compass heading 0-359 deg")
    accuracy_m: float = Field(ge=0.0, le=1000.0, description="Horizontal accuracy in meters")
    time: datetime = Field(description="Telemetry timestamp (UTC)")

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: datetime) -> datetime:
        """Reject timestamps beyond 24 hours in the future."""
        now = datetime.now(tz=UTC)
        target = v if v.tzinfo else v.replace(tzinfo=UTC)
        if target > now + timedelta(hours=24):
            raise ValueError("Timestamp cannot be more than 24 hours in the future")
        return target


class PositionBatchIngestSchema(BaseModel):
    """Batch ingest schema capped at 500 telemetry records per request."""

    model_config = ConfigDict(extra="forbid")

    positions: list[PositionIngestSchema] = Field(
        min_length=1,
        max_length=500,
        description="Batch of up to 500 telemetry records",
    )


class PositionReadSchema(BaseModel):
    """Schema for returning historical telemetry positions."""

    model_config = ConfigDict(from_attributes=True)

    vehicle_id: int
    time: datetime
    lat: float
    lon: float
    speed_kmh: float
    heading: int | None = None
    accuracy_m: float | None = None
    point_count: int | None = 1


class PositionHistoryFilter(BaseModel):
    """Query parameter filter for vehicle position history."""

    from_time: Annotated[datetime, Field(alias="from")]
    to_time: Annotated[datetime, Field(alias="to")]
    downsample: DownsampleMode = DownsampleMode.AUTO

    @model_validator(mode="after")
    def check_range(self) -> PositionHistoryFilter:
        """Validate date range order and 90-day maximum window."""
        if self.from_time > self.to_time:
            raise ValueError("'from' timestamp must be before 'to' timestamp")
        if self.to_time - self.from_time > timedelta(days=90):
            raise ValueError("Time range cannot exceed 90 days")
        return self


class PositionHistoryResponse(BaseModel):
    """Response envelope detailing the chosen data source and returned points."""

    source_used: str
    points: list[PositionReadSchema]
