from pydantic import Field, field_validator

from app.schemas.common import Schema


class VehicleCreate(Schema):
    name: str = Field(min_length=1, max_length=60, pattern=r"^[\w -]+$")
    registration: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9 -]+$")
    kind: str = Field(default="delivery", pattern=r"^(delivery|cab|bus)$")

    @field_validator("name", "registration", mode="before")
    @classmethod
    def normalize(cls, value, info):
        if isinstance(value, str):
            value = value.strip()
            return value.upper() if info.field_name == "registration" else value
        return value


class VehicleOut(VehicleCreate):
    id: int
    is_sample: bool = False
