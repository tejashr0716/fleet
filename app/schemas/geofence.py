from pydantic import Field

from app.schemas.common import Schema


class GeofenceCreate(Schema):
    name: str = Field(min_length=1, max_length=60, pattern=r"^[\w -]+$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(ge=100, le=20000)


class GeofenceOut(GeofenceCreate):
    id: int
