from __future__ import annotations

import httpx
from django.conf import settings

DEFAULT_TIMEOUT = httpx.Timeout(40.0, connect=15.0)


def client() -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": settings.HTTP_USER_AGENT, "Accept": "application/json"},
        follow_redirects=True,
    )
