import json
import secrets
import logging
import time
import bcrypt
from pathlib import Path
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.config import settings

logger = logging.getLogger(__name__)

# Persistent sessions file
_SESSIONS_FILE = Path("data/sessions.json")
_sessions: dict[str, float] = {}  # {token: created_timestamp}
_MAX_AGE = 86400 * 30  # 30 days

PUBLIC_PATHS = {
    "/api/login", "/api/health", "/webhook/whatsapp", "/favicon.ico",
}
PUBLIC_PREFIXES = ("/api/login", "/assets/")


def _load_sessions():
    """Load sessions from disk."""
    global _sessions
    if _SESSIONS_FILE.exists():
        try:
            data = json.loads(_SESSIONS_FILE.read_text())
            now = time.time()
            # Only keep non-expired sessions
            _sessions = {k: v for k, v in data.items()
                         if now - v < _MAX_AGE}
            return
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
    _sessions = {}


def _save_sessions():
    """Persist sessions to disk."""
    _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSIONS_FILE.write_text(json.dumps(_sessions))


# Load on import
_load_sessions()


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
    _sessions[token] = time.time()
    _save_sessions()
    return token


def is_valid_session(token: str) -> bool:
    created = _sessions.get(token)
    if created is None:
        return False
    if time.time() - created > _MAX_AGE:
        _sessions.pop(token, None)
        _save_sessions()
        return False
    return True


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
