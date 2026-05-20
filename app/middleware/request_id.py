"""
Middleware that injects a unique request ID into every request and response.

The ID is taken from the incoming X-Request-ID header if provided by a
load balancer or API gateway, otherwise a new UUID is generated.
This ID is stored in request.state and in structlog's context vars so it
appears in every log line emitted during the request lifecycle.
"""

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings

logger = structlog.get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        header = get_settings().request_id_header
        request_id = request.headers.get(header) or str(uuid.uuid4())

        request.state.request_id = request_id

        # Bind to structlog context so all log lines in this request carry it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers[header] = request_id
        return response
