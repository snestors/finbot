import secrets
import logging
import bcrypt
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = logging.getLogger(__name__)

# In-memory sessions: {token: True}
_sessions: dict[str, bool] = {}

PUBLIC_PATHS = {
    "/api/login", "/api/health", "/webhook/whatsapp", "/favicon.ico",
}
PUBLIC_PREFIXES = ("/api/login", "/assets/")


def is_public(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def verify_pin(pin: str) -> bool:
    if not settings.auth_pin_hash:
        return True  # No PIN configured = open access
    stored = settings.auth_pin_hash
    # Support bcrypt hashes (start with $2) and plain-text PINs
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(pin.encode(), stored.encode())
        except Exception:
            return False
    return pin == stored


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = True
    return token


def is_valid_session(token: str) -> bool:
    return token in _sessions


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths, WebSocket, and when no PIN configured
        if not settings.auth_pin_hash or is_public(path) or path == "/ws":
            return await call_next(request)

        # Check session cookie
        session_token = request.cookies.get("finbot_session")
        if session_token and is_valid_session(session_token):
            return await call_next(request)

        # API calls get 401 — React client handles redirect to /login
        if path.startswith("/api/"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        # All other routes (SPA pages): let through so React can load and handle auth
        return await call_next(request)
