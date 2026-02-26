"""RQ Worker runner — entry point for `python -m app.worker.runner`."""

from __future__ import annotations

import logging

from redis import Redis
from rq import Worker

from app.config import settings

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    conn = Redis.from_url(settings.redis_url)
    worker = Worker([settings.queue_name], connection=conn)
    logger.info("worker_start queue=%s redis=%s", settings.queue_name, settings.redis_url)
    worker.work()


if __name__ == "__main__":
    main()
