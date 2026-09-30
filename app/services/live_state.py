import json
from datetime import UTC, datetime

from redis.exceptions import RedisError

TOPIC = "fleet-v2:events"
GEO_KEY = "fleet-v2:geo"
# Comparing integer microseconds prevents late packets or concurrent workers moving a marker backward.
# Lua makes the freshness check, cache update and GEOADD one indivisible operation.
LATEST_LUA = """
local old = redis.call('GET', KEYS[1])
if old then
    local prev = cjson.decode(old)
    if tonumber(prev._version) >= tonumber(ARGV[1]) then return 0 end
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[6])
if math.abs(tonumber(ARGV[4])) <= 85.05112878 then
    redis.call('GEOADD', KEYS[2], ARGV[3], ARGV[4], ARGV[5])
else
    redis.call('ZREM', KEYS[2], ARGV[5])
end
return 1
"""


async def publish_event(redis, event, ttl):
    data = event["data"]
    if event["type"] == "position":
        stamp = datetime.fromisoformat(data["recorded_at"])
        # Always cache valid geographic coordinates; omit polar points from Redis GEO.
        payload = dict(data, _version=round(stamp.timestamp() * 1_000_000))
        await redis.eval(
            LATEST_LUA,
            2,
            f"fleet-v2:live:{data['vehicle_id']}",
            GEO_KEY,
            str(payload["_version"]),
            json.dumps(payload),
            str(data["lon"]),
            str(data["lat"]),
            str(data["vehicle_id"]),
            str(ttl),
        )
    # Pub/Sub is intentionally best effort, not durable WebSocket delivery.
    await redis.publish(TOPIC, json.dumps(event))


async def nearest_cached(redis, lat, lon, limit, ttl):
    if abs(lat) > 85.05112878:
        return None
    try:
        await redis.ping()
        rows = await redis.geosearch(
            GEO_KEY,
            longitude=lon,
            latitude=lat,
            radius=25000,
            unit="m",
            sort="ASC",
            count=1000,
            withdist=True,
        )
        if not rows:
            return None
        values = await redis.mget([f"fleet-v2:live:{row[0]}" for row in rows])
        now = datetime.now(UTC)
        result = []
        for row, raw in zip(rows, values, strict=False):
            if raw is None:
                continue
            data = json.loads(raw)
            age = (now - datetime.fromisoformat(data["recorded_at"])).total_seconds()
            if age > ttl:
                continue
            data.pop("_version", None)
            result.append(dict(data, distance_m=round(float(row[1]), 1)))
        # A cache miss/empty stale set falls back to PostgreSQL rather than lying about no vehicles.
        return result[:limit] if result else None
    except RedisError:
        return None
