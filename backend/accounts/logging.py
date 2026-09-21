"""Structured logging: JSON formatter + PII redaction filter + request-id filter.

Implements PLAN-001 TASK-013 / ARCH-001 §Observability + §Security PII.

- :class:`JsonFormatter` emits one JSON object per record with a stable set of
  top-level fields plus any ``extra=`` keys the caller supplied.
- :class:`PhoneRedactionFilter` masks phone-number values (both from ``extra``
  and inside the message string) to the last 4 digits, and strips any 6-digit
  OTP-like token from log messages tagged with an OTP context key.
- :class:`RequestIdFilter` injects the current request id (populated by the
  ``X-Request-ID`` middleware) into every record.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import re
from datetime import datetime, timezone


_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='')


# ---------------------------------------------------------------------------
# Context helpers (used by the middleware)
# ---------------------------------------------------------------------------


def set_request_id(request_id: str) -> contextvars.Token:
    return _request_id_ctx.set(request_id or '')


def reset_request_id(token: contextvars.Token) -> None:
    try:
        _request_id_ctx.reset(token)
    except (ValueError, LookupError):
        pass


def get_request_id() -> str:
    return _request_id_ctx.get()


# ---------------------------------------------------------------------------
# PII helpers
# ---------------------------------------------------------------------------


_PHONE_RE = re.compile(r'\+\d{6,15}')
_SIX_DIGIT_RE = re.compile(r'(?<!\d)\d{6}(?!\d)')


def mask_phone(phone: str) -> str:
    """Mask an E.164 phone number keeping the leading ``+CC`` and last 4 digits.

    ``+919812345678`` -> ``+91******5678``. Non-E.164 inputs are best-effort.
    """
    if not phone or not isinstance(phone, str):
        return ''
    if phone.startswith('+') and len(phone) > 6:
        # Preserve the first 3 chars (`+` + country code chunk) and the last 4.
        head = phone[:3]
        tail = phone[-4:]
        middle = '*' * max(0, len(phone) - len(head) - len(tail))
        return f'{head}{middle}{tail}'
    if len(phone) > 4:
        return '*' * (len(phone) - 4) + phone[-4:]
    return '****'


def hash_phone_for_logs(phone: str) -> str:
    if not phone:
        return ''
    return hashlib.sha256(phone.encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


# Known "reserved" LogRecord attribute names — everything else on the record
# is treated as extra data and included in the JSON output.
_RESERVED_ATTRS = {
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'message', 'module',
    'msecs', 'msg', 'name', 'pathname', 'process', 'processName',
    'relativeCreated', 'stack_info', 'thread', 'threadName', 'taskName',
}


class PhoneRedactionFilter(logging.Filter):
    """Mask phones and strip 6-digit OTP-like tokens on ``accounts`` records.

    - If a record has a ``phone_number`` extra, it is removed and replaced by
      ``phone_masked`` and ``phone_hash`` fields.
    - Any ``+\\d{6,15}`` occurrence inside the message string is masked.
    - When the record's logger name / message hints at OTP context, any
      standalone 6-digit sequence in the message is replaced with ``******``.
    """

    _OTP_CONTEXT_HINTS = ('otp', 'code')

    def filter(self, record: logging.LogRecord) -> bool:
        # Extract and redact structured phone data.
        raw_phone = getattr(record, 'phone_number', None)
        if raw_phone:
            record.phone_masked = mask_phone(raw_phone)
            record.phone_hash = hash_phone_for_logs(raw_phone)
            try:
                delattr(record, 'phone_number')
            except AttributeError:
                pass

        # Redact anything in the formatted message string.
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 — logging must never raise.
            return True

        redacted = _PHONE_RE.sub(lambda m: mask_phone(m.group(0)), message)

        message_lc = message.lower()
        logger_lc = (record.name or '').lower()
        if any(h in message_lc or h in logger_lc for h in self._OTP_CONTEXT_HINTS):
            redacted = _SIX_DIGIT_RE.sub('******', redacted)

        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


class RequestIdFilter(logging.Filter):
    """Attach the current request id (from ``ContextVar``) to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, 'request_id', None):
            record.request_id = get_request_id()
        return True


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter: one dict per record, extras included verbatim."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            'ts': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        request_id = getattr(record, 'request_id', '') or get_request_id()
        if request_id:
            payload['request_id'] = request_id

        for attr, value in record.__dict__.items():
            if attr in _RESERVED_ATTRS or attr.startswith('_'):
                continue
            if attr in ('message', 'request_id'):
                continue
            payload[attr] = _jsonable(value)

        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        if record.stack_info:
            payload['stack_info'] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def _jsonable(value):
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)
