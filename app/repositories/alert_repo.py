from sqlalchemy import select

from app.models import Alert


async def latest_alerts(session, limit=50):
    return list(
        (
            await session.scalars(
                select(Alert).order_by(Alert.recorded_at.desc(), Alert.id.desc()).limit(limit)
            )
        ).all()
    )
