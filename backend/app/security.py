"""HTTP-level protections: security headers, request-size limit, per-client rate limiting,
sensitive-number detection and an allow-list for links in AI answers.

Threat model and the reasoning behind each control: see SECURITY.md in the project root.
"""
from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Only these domains may ever appear as links in answers (government + appointed PAN agencies).
OFFICIAL_DOMAINS = ("incometax.gov.in", "incometaxindia.gov.in", "proteantech.in", "protean-tinpan.com", "utiitsl.com",
                    "uidai.gov.in", "pib.gov.in", "egazette.gov.in", "indiapost.gov.in")

MAX_BODY_BYTES = 64 * 1024  # largest legitimate request (chat with history) is a few KB

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

# (requests, window seconds) per client IP and route group. Chat is the expensive one (LLM quota).
RATE_LIMITS = {
    "chat": [(10, 60), (200, 86400)],
    "api": [(120, 60)],
}

AADHAAR_RE = re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")
VID_RE = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")  # Aadhaar Virtual ID (16 digits)
URL_RE = re.compile(r"https?://[^\s)\]>\"'】]+", re.I)


def is_official_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in OFFICIAL_DOMAINS)


def strip_unofficial_links(text: str) -> tuple[str, int]:
    """Remove any URL that isn't an official domain - defence in depth against prompt injection
    (from users or from crawled pages) steering people to phishing sites."""
    removed = 0

    def repl(m: re.Match) -> str:
        nonlocal removed
        if is_official_url(m.group(0)):
            return m.group(0)
        removed += 1
        return "[link removed - not an official government site]"

    return URL_RE.sub(repl, text), removed


def contains_aadhaar(value: str) -> bool:
    return bool(AADHAAR_RE.search(value) or VID_RE.search(value))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        path = request.url.path
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"  # answers may echo personal details
        elif path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # file names are content-hashed
        else:
            response.headers["Cache-Control"] = "no-cache"  # always re-check index.html so updates show up
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                return JSONResponse({"detail": "Content-Length required"}, status_code=411)
            if int(length) > MAX_BODY_BYTES:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        return await call_next(request)


class RateLimiter:
    """In-memory sliding window per (client, group). Fine for a single process; use Redis when scaling out."""

    def __init__(self, limits: dict[str, list[tuple[int, int]]]):
        self.limits = limits
        self.hits: dict[tuple[str, str], deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, client: str, group: str) -> int | None:
        """Return None if allowed, else seconds to wait."""
        now = time.monotonic()
        rules = self.limits.get(group, [])
        if not rules:
            return None
        longest = max(w for _, w in rules)
        with self.lock:
            q = self.hits[(client, group)]
            while q and now - q[0] > longest:
                q.popleft()
            for limit, window in rules:
                in_window = sum(1 for t in q if now - t <= window)
                if in_window >= limit:
                    oldest = next(t for t in q if now - t <= window)
                    return max(1, int(window - (now - oldest)) + 1)
            q.append(now)
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter):
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and request.method == "POST":
            group = "chat" if path == "/api/chat" else "api"
            client = request.client.host if request.client else "unknown"
            wait = self.limiter.check(client, group)
            if wait:
                return JSONResponse({"detail": f"Too many requests - please wait {wait} seconds and try again."},
                                    status_code=429, headers={"Retry-After": str(wait)})
        return await call_next(request)
