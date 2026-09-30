from fastapi import APIRouter, Depends, Request

from app.repositories.geofence_repo import create_fence, list_fences
from app.schemas.geofence import GeofenceCreate, GeofenceOut
from app.security import require_user

router = APIRouter(prefix="/geofences", tags=["Geofences"], dependencies=[Depends(require_user)])


@router.get("", response_model=list[GeofenceOut])
async def geofences(request: Request):
    async with request.app.state.db.sessions() as session:
        return await list_fences(session)


@router.post("", status_code=201, response_model=GeofenceOut)
async def create(body: GeofenceCreate, request: Request):
    async with request.app.state.db.sessions() as session:
        return await create_fence(session, body)
