"""Alert generation rules engine for speeding, idle, and signal lost events."""

from __future__ import annotations

from datetime import datetime

from app.models.alert import Alert, AlertKind, AlertSeverity


def evaluate_speeding(
    vehicle_id: int,
    speed_kmh: float,
    limit_kmh: float,
    ts: datetime,
) -> Alert | None:
    """Evaluate whether telemetry speed exceeds designated speed limit thresholds.

    Args:
        vehicle_id: Vehicle ID.
        speed_kmh: Observed speed in km/h.
        limit_kmh: Designated threshold speed limit.
        ts: Observation timestamp (UTC).

    Returns:
        Alert | None: Generated speeding alert if threshold is violated, else None.
    """
    if speed_kmh > limit_kmh:
        severity = AlertSeverity.CRITICAL if speed_kmh > limit_kmh + 30 else AlertSeverity.WARNING
        return Alert(
            vehicle_id=vehicle_id,
            kind=AlertKind.SPEEDING,
            severity=severity,
            payload={"speed_kmh": speed_kmh, "limit_kmh": limit_kmh},
            time=ts,
            acknowledged=False,
        )
    return None


def evaluate_idle(
    vehicle_id: int,
    idle_duration_seconds: float,
    threshold_seconds: float,
    ts: datetime,
) -> Alert | None:
    """Evaluate whether vehicle idle time exceeds allowable threshold.

    Args:
        vehicle_id: Vehicle ID.
        idle_duration_seconds: Cumulative idle seconds.
        threshold_seconds: Configured maximum idle timeout seconds.
        ts: Observation timestamp (UTC).

    Returns:
        Alert | None: Generated idle alert if exceeded, else None.
    """
    if idle_duration_seconds >= threshold_seconds:
        return Alert(
            vehicle_id=vehicle_id,
            kind=AlertKind.IDLE,
            severity=AlertSeverity.INFO,
            payload={
                "idle_duration_seconds": idle_duration_seconds,
                "threshold_seconds": threshold_seconds,
            },
            time=ts,
            acknowledged=False,
        )
    return None


def generate_signal_lost_alert(
    vehicle_id: int,
    silence_seconds: float,
    ts: datetime,
) -> Alert:
    """Generate signal lost alert when telemetry timeout triggers.

    Args:
        vehicle_id: Vehicle ID.
        silence_seconds: Elapsed seconds since last received packet.
        ts: Evaluation timestamp (UTC).

    Returns:
        Alert: Critical signal lost alert instance.
    """
    return Alert(
        vehicle_id=vehicle_id,
        kind=AlertKind.SIGNAL_LOST,
        severity=AlertSeverity.CRITICAL,
        payload={"silence_seconds": silence_seconds},
        time=ts,
        acknowledged=False,
    )
