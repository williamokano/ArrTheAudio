"""Request logging middleware."""

import json
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from arrtheaudio.utils.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming HTTP requests before validation."""

    async def dispatch(self, request: Request, call_next):
        """Log request before processing and response after."""
        # Only log webhook endpoints (exclude health checks)
        if not request.url.path.startswith("/webhook/"):
            return await call_next(request)

        # Log request BEFORE processing
        start_time = time.time()

        # Read body for logging (FastAPI will handle re-reading it)
        body = await request.body()

        # Try to parse and preview JSON body
        try:
            body_json = json.loads(body.decode())
            # Truncate large payloads for log readability
            body_preview = json.dumps(body_json, indent=2)[:500]
        except Exception:
            # If not JSON or decode fails, show raw bytes preview
            body_preview = body.decode()[:500] if body else "<empty>"

        # Log incoming request with sanitized headers
        logger.info(
            "Incoming webhook request",
            method=request.method,
            path=request.url.path,
            headers={
                k: v
                for k, v in request.headers.items()
                if k.lower() not in ("authorization", "x-webhook-signature")
            },
            body_preview=body_preview,
            content_length=len(body),
        )

        # Process request
        response = await call_next(request)

        # Log response
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            "Webhook request completed",
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
