"""Alert model and classifications."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.vehicle import Base


class AlertKind(StrEnum):
    """Categorical alert trigger kinds."""

    SPEEDING = "speeding"
    IDLE = "idle"
    GEOFENCE_ENTER = "geofence_enter"
    GEOFENCE_EXIT = "geofence_exit"
    SIGNAL_LOST = "signal_lost"


class AlertSeverity(StrEnum):
    """Severity ratings for fleet operations."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(Base):
    """System-generated alert notification."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[AlertKind] = mapped_column(
        Enum(AlertKind, name="alert_kind"),
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_alerts_kind_sev_ack", "kind", "severity", "acknowledged"),
        Index("ix_alerts_vehicle_time", "vehicle_id", "time"),
    )
