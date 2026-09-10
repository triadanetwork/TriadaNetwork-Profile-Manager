from datetime import datetime, timezone
from fastapi import HTTPException, Request
from redis.asyncio import Redis
from .observability import RATE_LIMIT_ERRORS


class RateLimiter:
    def __init__(self, redis: Redis, limit: int, window_seconds: int):
        self.redis = redis
        self.limit = limit
        self.window_seconds = window_seconds

    async def check(self, request: Request, bucket: str) -> None:
        if self.limit <= 0:
            return
        client = request.client.host if request.client else "unknown"
        minute = int(datetime.now(timezone.utc).timestamp()) // self.window_seconds
        key = f"triada:rl:{bucket}:{client}:{minute}"
        try:
            count = await self.redis.incr(key)
        except Exception:
            RATE_LIMIT_ERRORS.inc()
            raise
        if count == 1:
            await self.redis.expire(key, self.window_seconds + 1)
        if count > self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
