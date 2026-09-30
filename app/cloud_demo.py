"""Render free-tier entrypoint. Normal Docker deployment does not use this module."""

import os
import subprocess
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.config import Settings


def prepare_environment(environ):
    env = dict(environ)
    env["ENVIRONMENT"] = "production"
    env["CLOUD_DEMO_ENABLED"] = "true"
    port = int(env.get("PORT", "10000"))
    if not 1 <= port <= 65535 or port in {18012, 18013, 19099}:
        raise ValueError("Unsupported HTTP port")
    env["PORT"] = str(port)
    parsed = urlsplit(env.get("DATABASE_URL", ""))
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"} or not parsed.hostname:
        raise ValueError("A PostgreSQL URL is required")
    redis = urlsplit(env.get("REDIS_URL", ""))
    if redis.scheme not in {"redis", "rediss"} or not redis.hostname:
        raise ValueError("A Redis URL is required")
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if "sslmode" in params:
        params.setdefault("ssl", params.pop("sslmode"))
    env["DATABASE_URL"] = urlunsplit(
        ("postgresql+asyncpg", parsed.netloc, parsed.path, urlencode(params), parsed.fragment)
    )
    return env


def main():
    try:
        env = prepare_environment(os.environ)
        os.environ.update(env)
        Settings(_env_file=None)
    except ValueError:
        print(
            "Cloud demo configuration rejected. Set PostgreSQL, Redis, explicit origins, "
            "a strong admin password and independently generated JWT/device secrets.",
            file=sys.stderr,
        )
        return 2
    for module, args in [("alembic", ["upgrade", "head"]), ("simulator.seed", [])]:
        try:
            subprocess.run([sys.executable, "-m", module, *args], check=True, env=env, timeout=180)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            print(f"Cloud demo startup step failed: {module}", file=sys.stderr)
            return 1
    os.execve(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            env["PORT"],
            "--workers",
            "1",
            "--no-access-log",
        ],
        env,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
