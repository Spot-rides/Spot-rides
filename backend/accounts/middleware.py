"""Request-ID middleware.

Implements PLAN-001 TASK-014 / ARCH-001 §Observability.

Reads inbound ``X-Request-ID``, or generates a UUID4 hex if absent, stores it
on ``request.request_id``, publishes it to the logging ``ContextVar`` for the
JSON formatter, and echoes the value back in the response header.
"""

from __future__ import annotations

import uuid

from .logging import reset_request_id, set_request_id


_HEADER = 'X-Request-ID'
_META_KEY = 'HTTP_X_REQUEST_ID'
_MAX_LEN = 40


class RequestIDMiddleware:
    """Populate + propagate ``X-Request-ID`` for correlation across log/DB."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get(_META_KEY, '') or ''
        # Reject overlong / suspicious ids and fall back to a fresh uuid4.
        if not incoming or len(incoming) > _MAX_LEN or not _is_safe_id(incoming):
            request_id = uuid.uuid4().hex
        else:
            request_id = incoming
        request.request_id = request_id

        token = set_request_id(request_id)
        try:
            response = self.get_response(request)
        finally:
            reset_request_id(token)
        response[_HEADER] = request_id
        return response


def _is_safe_id(value: str) -> bool:
    # Only accept URL-safe / hex-ish characters to avoid log-injection.
    return all(ch.isalnum() or ch in '-_' for ch in value)
