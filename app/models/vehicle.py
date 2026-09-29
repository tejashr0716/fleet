"""Vehicle declarative model and status/type enums."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Index, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy entities."""


class VehicleType(StrEnum):
    """Categorical vehicle types."""

    TRUCK = "truck"
    VAN = "van"
    BIKE = "bike"
    CAR = "car"


class VehicleStatus(StrEnum):
    """Operational status of a vehicle."""

    ACTIVE = "active"
    IDLE = "idle"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class Vehicle(Base):
    """Vehicle entity representing tracked assets in the fleet."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plate: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    vehicle_type: Mapped[VehicleType] = mapped_column(
        Enum(VehicleType, name="vehicle_type"),
        nullable=False,
        default=VehicleType.CAR,
    )
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus, name="vehicle_status"),
        nullable=False,
        default=VehicleStatus.OFFLINE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=UTC),
        onupdate=lambda: datetime.now(tz=UTC),
        nullable=False,
    )

    __table_args__ = (Index("ix_vehicles_status_type", "status", "vehicle_type"),)
