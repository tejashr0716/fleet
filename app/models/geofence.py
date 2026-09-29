"""Geofence models and event tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ARRAY, BigInteger, DateTime, Enum, ForeignKey, Index, SmallInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.vehicle import Base


class GeofenceKind(StrEnum):
    """Geofence geometry kind."""

    POLYGON = "polygon"
    CIRCLE = "circle"


class GeofenceEventKind(StrEnum):
    """Transition events for geofence crossings."""

    ENTER = "enter"
    EXIT = "exit"


class Geofence(Base):
    """Geofence boundary defined as GeoJSON and pre-computed H3 cell sets."""

    __tablename__ = "geofences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    kind: Mapped[GeofenceKind] = mapped_column(
        Enum(GeofenceKind, name="geofence_kind"),
        nullable=False,
        default=GeofenceKind.POLYGON,
    )
    geojson: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    h3_resolution: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=8)
    h3_cells: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=UTC),
        nullable=False,
    )


class GeofenceEvent(Base):
    """Historical record of a vehicle entering or exiting a geofence."""

    __tablename__ = "geofence_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    geofence_id: Mapped[int] = mapped_column(
        ForeignKey("geofences.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[GeofenceEventKind] = mapped_column(
        Enum(GeofenceEventKind, name="geofence_event_kind"),
        nullable=False,
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_geofence_events_vehicle_time", "vehicle_id", "time"),)
