import asyncio

from sqlalchemy.dialects.postgresql import insert

from app.config import Settings
from app.db import Database
from app.models import Geofence, Vehicle


async def seed(db, count=12):
    async with db.sessions() as session:
        for i in range(1, count + 1):
            await session.execute(
                insert(Vehicle)
                .values(
                    name=f"Fleet {i:02d}",
                    registration=f"DEMO-{i:03d}",
                    kind=["delivery", "cab", "bus"][(i - 1) % 3],
                )
                .on_conflict_do_nothing(index_elements=[Vehicle.name])
            )
        await session.execute(
            insert(Geofence)
            .values(name="Central Bengaluru demo zone", lat=12.9716, lon=77.5946, radius_m=1200)
            .on_conflict_do_nothing(index_elements=[Geofence.name])
        )
        await session.commit()


async def main():
    db = Database(Settings().database_url)
    try:
        await seed(db)
        print("Seeded 12 synthetic vehicles and one circular geofence (idempotent).")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
