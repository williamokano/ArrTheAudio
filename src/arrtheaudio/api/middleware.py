"""Request logging middleware."""

import json
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from arrtheaudio.utils.logger import get_logger, TRACE_LEVEL

logger = get_logger(__name__)
stdlib_logger = logging.getLogger(__name__)


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

        # Determine if we should log body (debug/trace level only)
        should_log_body = stdlib_logger.isEnabledFor(logging.DEBUG)

        # Prepare body preview for debug/trace logging
        body_preview = None
        if should_log_body:
            try:
                body_json = json.loads(body.decode())
                # Truncate large payloads for log readability
                body_preview = json.dumps(body_json, indent=2)[:500]
            except Exception:
                # If not JSON or decode fails, show raw bytes preview
                body_preview = body.decode()[:500] if body else "<empty>"

        # Log incoming request (with or without body based on log level)
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "content_length": len(body),
        }

        # Only include headers and body at debug level
        if should_log_body:
            log_data["headers"] = {
                k: v
                for k, v in request.headers.items()
                if k.lower() not in ("authorization", "x-webhook-signature")
            }
            log_data["body_preview"] = body_preview

        logger.info("Incoming webhook request", **log_data)

        # Process request
        response = await call_next(request)

        # Log response
        duration_ms = (time.time() - start_time) * 1000

        # For error responses (4xx, 5xx), always log body for debugging
        response_log_data = {
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }

        # Include body in error responses even at info level
        if response.status_code >= 400 and not should_log_body:
            try:
                body_json = json.loads(body.decode())
                response_log_data["request_body"] = json.dumps(body_json, indent=2)[:500]
            except Exception:
                response_log_data["request_body"] = body.decode()[:500] if body else "<empty>"

        logger.info("Webhook request completed", **response_log_data)

        return response
