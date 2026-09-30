from redis.asyncio import Redis


def make_redis(url: str) -> Redis:
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=3,
        health_check_interval=15,
    )
