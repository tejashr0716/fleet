"""Trip segmentation model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.vehicle import Base


class Trip(Base):
    """Segmented movement interval for a vehicle."""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_speed_kmh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_speed_kmh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
