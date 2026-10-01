from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


@dataclass
class TraceSession:
    """Legacy gap-derived trace; distinct from an explicitly started trip."""

    vehicle_id: int
    started_at: datetime
    ended_at: datetime
    point_count: int
    distance_km: float


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'interrupted')", name="ck_trip_status"),
        CheckConstraint("duration_seconds BETWEEN 5 AND 600", name="ck_trip_duration"),
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_trip_time"),
        Index(
            "uq_active_trip_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_trip_vehicle_started", "vehicle_id", "started_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("fleet_v2.vehicles.id"))
    route_key: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")
    source: Mapped[str] = mapped_column(String(20), default="synthetic")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    include_speeding: Mapped[bool] = mapped_column(Boolean, default=True)
    end_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
