from pydantic import Field

from app.schemas.common import Schema


class VehicleCreate(Schema):
    name: str = Field(min_length=1, max_length=60, pattern=r"^[\w -]+$")
    registration: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9 -]+$")
    kind: str = Field(default="delivery", pattern=r"^(delivery|cab|bus)$")


class VehicleOut(VehicleCreate):
    id: int
