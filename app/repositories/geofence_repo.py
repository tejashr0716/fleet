from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Geofence


async def list_fences(session):
    return list((await session.scalars(select(Geofence).order_by(Geofence.id))).all())


async def create_fence(session, body):
    fence = Geofence(**body.model_dump())
    session.add(fence)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Geofence name already exists") from exc
    return fence
