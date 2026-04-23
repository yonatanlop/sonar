from __future__ import annotations

import redis

from app.shared.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
