"""Domain-error base class and the project-wide DRF exception handler.

Every failure — domain error, DRF validation, authentication, throttling or an
unhandled crash — leaves the API in the same envelope shape produced by
:func:`core.envelope.error_envelope`.

Feature apps declare their own errors by subclassing :class:`ApiError` and
setting ``status_code`` / ``error_code`` / ``default_detail``.
"""

from __future__ import annotations

import logging
from typing import Optional

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .envelope import error_envelope

logger = logging.getLogger('core')


class ApiError(APIException):
    """Base class for errors that map onto a stable machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'error'
    default_detail = 'Request could not be processed.'

    def __init__(self, detail: Optional[str] = None, retry_after: Optional[int] = None):
        super().__init__(detail or self.default_detail)
        self.retry_after = retry_after


def envelope_exception_handler(exc, context):
    """DRF ``EXCEPTION_HANDLER`` — renders all errors in the shared envelope."""

    if isinstance(exc, ApiError):
        response = Response(
            error_envelope(exc.error_code, str(exc.detail), retry_after=exc.retry_after),
            status=exc.status_code,
        )
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS and exc.retry_after is not None:
            response['Retry-After'] = str(int(exc.retry_after))
        return response

    # Let DRF resolve status codes and auth headers first, then re-wrap the body.
    response = drf_exception_handler(exc, context)
    if response is not None:
        response.data = error_envelope(
            _error_code(response.status_code),
            _detail(response.data),
            fields=_fields(response.data),
        )
        return response

    logger.exception('unhandled_exception', extra={'view': _view_name(context)})
    return Response(
        error_envelope('server_error', 'An unexpected error occurred.'),
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


_STATUS_CODES = {
    status.HTTP_401_UNAUTHORIZED: 'not_authenticated',
    status.HTTP_403_FORBIDDEN: 'permission_denied',
    status.HTTP_404_NOT_FOUND: 'not_found',
    status.HTTP_405_METHOD_NOT_ALLOWED: 'method_not_allowed',
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: 'unsupported_media_type',
    status.HTTP_429_TOO_MANY_REQUESTS: 'rate_limited',
}


def _error_code(status_code: int) -> str:
    if status_code in _STATUS_CODES:
        return _STATUS_CODES[status_code]
    return 'invalid_request' if 400 <= status_code < 500 else 'server_error'


def _detail(data) -> str:
    """Best-effort single human message out of DRF's default error body."""
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        for value in data.values():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
        return 'Invalid request.'
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data) if data is not None else 'Invalid request.'


def _fields(data) -> Optional[dict]:
    """Per-field messages from a DRF ``ValidationError`` body, if any."""
    if not isinstance(data, dict) or 'detail' in data:
        return None
    fields = {
        key: [str(item) for item in value] if isinstance(value, list) else [str(value)]
        for key, value in data.items()
    }
    return fields or None


def _view_name(context) -> str:
    view = context.get('view') if isinstance(context, dict) else None
    return '' if view is None else type(view).__name__
