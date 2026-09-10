import asyncio
from app.config import settings
from app.jobs import worker_loop


if __name__ == "__main__":
    asyncio.run(worker_loop(settings().redis_url))
