from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Vehicle


async def get_vehicle(session, vehicle_id):
    value = await session.get(Vehicle, vehicle_id)
    if value is None:
        raise HTTPException(404, "Vehicle not found")
    return value


async def list_vehicles(session):
    return list((await session.scalars(select(Vehicle).order_by(Vehicle.id))).all())


async def create_vehicle(session, body):
    vehicle = Vehicle(**body.model_dump())
    session.add(vehicle)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Vehicle name or registration already exists") from exc
    return vehicle
