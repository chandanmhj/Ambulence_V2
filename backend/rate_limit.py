"""
Simple in-memory rate limiter for auth endpoints (login, signup, password
reset requests) - the endpoints most worth protecting against brute-force
and spam.

This is intentionally in-process (a plain dict), not backed by Redis. That's
a real limitation: it resets on every deploy/restart, and won't work
correctly if you ever scale to multiple backend instances (each instance
would track its own counts). For a single Railway instance, which is the
realistic scale here, this is a meaningful improvement over no rate limiting
at all. If you outgrow a single instance, swap this for `slowapi` + Redis.
"""

import time
from collections import defaultdict
from fastapi import HTTPException, Request, status

_attempts = defaultdict(list)  # key -> list of timestamps


def rate_limit(max_attempts: int, window_seconds: int):
    """
    Returns a FastAPI dependency that limits `max_attempts` calls per
    `window_seconds`, keyed by client IP + the endpoint path.
    """

    def dependency(request: Request):
        key = f"{request.client.host}:{request.url.path}"
        now = time.time()

        attempts = _attempts[key]
        # Drop attempts outside the window.
        attempts[:] = [t for t in attempts if now - t < window_seconds]

        if len(attempts) >= max_attempts:
            retry_after = int(window_seconds - (now - attempts[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many attempts. Try again in {max(retry_after, 1)}s.",
            )

        attempts.append(now)

    return dependency
