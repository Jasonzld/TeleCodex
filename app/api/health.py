"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from redis import Redis

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> dict[str, str]:
    try:
        r = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
        r.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception:
        return {"status": "degraded", "redis": "unreachable"}
