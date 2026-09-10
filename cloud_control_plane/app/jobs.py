import json
import logging
import time
from redis.asyncio import Redis

LOGGER = logging.getLogger("triada.jobs")
QUEUE_KEY = "triada:jobs"


async def enqueue(redis: Redis, job_type: str, payload: dict) -> str:
    job = {
        "id": f"job-{time.time_ns()}",
        "type": job_type,
        "payload": payload,
        "created_at": time.time(),
    }
    await redis.rpush(QUEUE_KEY, json.dumps(job, separators=(",", ":")))
    return job["id"]


async def worker_loop(redis_url: str) -> None:
    redis = Redis.from_url(redis_url, decode_responses=True)
    LOGGER.info("worker.started")
    try:
        while True:
            item = await redis.blpop(QUEUE_KEY, timeout=30)
            if not item:
                continue
            _, raw = item
            job = json.loads(raw)
            # v1.2 worker is infrastructure-only. Handlers are intentionally
            # idempotent extension points for sync/rebuild/maintenance jobs.
            LOGGER.info("worker.job", extra={"job_id": job.get("id"), "job_type": job.get("type")})
    finally:
        await redis.aclose()
