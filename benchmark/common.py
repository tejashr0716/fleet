import json
import math
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings


async def login(client):
    settings = Settings()
    response = await client.post(
        "/api/v1/auth/token",
        json={
            "username": settings.admin_username,
            "password": settings.admin_password.get_secret_value(),
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def save_report(name, values, elapsed, errors, context):
    ordered = sorted(values)

    def percentile(q):
        return (
            ordered[min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))]
            if ordered
            else None
        )

    result = {
        "probe": name,
        "scope": "synthetic single-client smoke probe, not maximum capacity",
        "run_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "samples": len(values),
        "errors": errors,
        "elapsed_seconds": elapsed,
        "rtt_ms": {"p50": percentile(0.5), "p95": percentile(0.95), "p99": percentile(0.99)},
        "raw_ms": values,
        **context,
    }
    directory = Path("reports")
    directory.mkdir(exist_ok=True)
    output = directory / f"{name}-{int(time.time())}.json"
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "raw_ms"}, indent=2))
    print(f"Saved raw observations: {output}")
    return result
