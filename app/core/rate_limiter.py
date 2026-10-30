import time
import asyncio
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class LoginRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_attempts=5, window_seconds=60):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.failed_attempts = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path.rstrip("/") != "/auth/login":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        async with self.lock:
            attempts = self.failed_attempts[client_ip]

            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()

            if len(attempts) >= self.max_attempts:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Too many failed login attempts. Please try again later."
                    },
                    headers={"Retry-After": str(max(
                        1,
                        int(self.window_seconds - (now - attempts[0]))
                    ))},
                )

        response = await call_next(request)

        if response.status_code in {400, 401}:
            async with self.lock:
                attempts = self.failed_attempts[client_ip]
                now = time.monotonic()

                while attempts and now - attempts[0] >= self.window_seconds:
                    attempts.popleft()

                attempts.append(now)

        return response