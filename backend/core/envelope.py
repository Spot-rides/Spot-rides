"""The single response envelope used by every endpoint under ``/api/``.

Success::

    {"success": true, "message": ..., "data": ..., "error": null, "meta": {...}}

Failure::

    {"success": false, "message": ..., "data": null,
     "error": {"code": ..., "detail": ..., "fields": ..., "retry_after": ...},
     "meta": {...}}

``error`` may carry additional flat keys supplied through ``extra`` (e.g.
``next_step``); the four keys above are reserved and cannot be overridden.

``meta`` is attached by :class:`core.renderers.EnvelopeJSONRenderer` at render
time so the builders below stay free of request state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

ENVELOPE_KEYS = frozenset({'success', 'message', 'data', 'error', 'meta'})


def success_envelope(data: Any, message: Optional[str] = None) -> dict:
    return {
        'success': True,
        'message': message,
        'data': data,
        'error': None,
    }


RESERVED_ERROR_KEYS = frozenset({'code', 'detail', 'fields', 'retry_after'})


def check_error_extra(extra: Optional[dict]) -> None:
    """Reject ``extra`` keys that would overwrite the closed error keys."""
    clash = RESERVED_ERROR_KEYS.intersection(extra or ())
    if clash:
        raise ValueError(f"error extra may not use reserved keys: {sorted(clash)}")


def error_envelope(
    code: str,
    detail: str,
    *,
    message: Optional[str] = None,
    fields: Optional[dict] = None,
    retry_after: Optional[int] = None,
    extra: Optional[dict] = None,
) -> dict:
    check_error_extra(extra)
    error = {
        'code': code,
        'detail': detail,
        'fields': fields or None,
        'retry_after': int(retry_after) if retry_after is not None else None,
    }
    if extra:
        error.update(extra)
    return {
        'success': False,
        'message': message or detail,
        'data': None,
        'error': error,
    }


def is_enveloped(data: Any) -> bool:
    """True when ``data`` already carries the envelope's required keys."""
    return isinstance(data, dict) and ENVELOPE_KEYS.issuperset(data) and 'success' in data


def build_meta(request=None, pagination: Optional[dict] = None) -> dict:
    meta: dict[str, Any] = {
        'request_id': getattr(request, 'request_id', '') or None,
        'timestamp': datetime.now(tz=timezone.utc).isoformat().replace('+00:00', 'Z'),
    }
    if pagination is not None:
        meta['pagination'] = pagination
    return meta
