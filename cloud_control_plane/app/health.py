import time
from fastapi import APIRouter, Response
from sqlalchemy import text
from redis.asyncio import Redis
from .db import engine
from .config import settings
from .observability import HEALTH_CHECKS, READY

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness():
    return {"status": "alive", "service": "triada-cloud", "version": "1.2.0"}


@router.get("/health/ready")
async def readiness(response: Response):
    checks = {}
    started = time.perf_counter()
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        checks["postgres"] = "error"

    redis = Redis.from_url(settings().redis_url, decode_responses=True)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    finally:
        await redis.aclose()

    healthy = all(value == "ok" for value in checks.values())
    for name, status in checks.items():
        HEALTH_CHECKS.labels(name, status).inc()
    READY.set(1 if healthy else 0)
    response.status_code = 200 if healthy else 503
    return {
        "status": "ready" if healthy else "not_ready",
        "checks": checks,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }
