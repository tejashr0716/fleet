import hmac
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, Field

bearer = HTTPBearer(auto_error=False)


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class Auth:
    def __init__(self, settings):
        self.settings = settings
        self.hasher = PasswordHash.recommended()
        self.password_hash = self.hasher.hash(settings.admin_password.get_secret_value())

    def issue(self):
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "sub": self.settings.admin_username,
                "iat": now,
                "exp": now + timedelta(minutes=self.settings.token_ttl_minutes),
                "iss": "fleet",
                "aud": "fleet-dashboard",
            },
            self.settings.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )

    def decode(self, token):
        try:
            return jwt.decode(
                token,
                self.settings.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                audience="fleet-dashboard",
                issuer="fleet",
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.InvalidTokenError as exc:
            raise HTTPException(401, "Invalid or expired access token") from exc

    def verify_password(self, username, password):
        # Always perform Argon2 verification, including an unknown username.
        password_ok = self.hasher.verify(password, self.password_hash)
        return hmac.compare_digest(username, self.settings.admin_username) and password_ok


async def require_user(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    if not credentials:
        raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    claims = request.app.state.auth.decode(credentials.credentials)
    if claims["sub"] != request.app.state.settings.admin_username:
        raise HTTPException(401, "Unknown account")
    return claims


async def require_ingest(
    request: Request,
    x_api_key: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
):
    expected = request.app.state.settings.device_api_key.get_secret_value()
    if x_api_key and hmac.compare_digest(x_api_key, expected):
        return
    if credentials:
        return await require_user(request, credentials)
    raise HTTPException(401, "Device API key or bearer token required")
