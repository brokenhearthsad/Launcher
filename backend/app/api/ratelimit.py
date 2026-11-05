"""Minimal in-memory per-client rate limiter for the REST API."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

EXEMPT = ("/api/health",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, per_minute: int):
        super().__init__(app)
        self.per_minute = per_minute
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path in EXEMPT:
            return await call_next(request)
        key = request.client.host if request.client else "local"
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            retry = max(1, int(60 - (now - q[0])))
            return JSONResponse({"error": {"code": "rate_limited", "message": "too many requests"}},
                                status_code=429, headers={"Retry-After": str(retry)})
        q.append(now)
        return await call_next(request)
