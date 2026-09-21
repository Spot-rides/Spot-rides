"""OTP generation, hashing, verification, and lifecycle transitions.

Implements PLAN-001 TASK-010 / ARCH-001 COMP-004.

Design points (see ARCH-001 §OTP Lifecycle):
- Codes are 6 digits, generated with ``secrets.randbelow``.
- Only ``hmac.new(pepper, code, sha256).hexdigest()`` is persisted.
- Verify uses ``hmac.compare_digest`` (constant-time).
- Attempt counter is bounded by ``settings.OTP_MAX_ATTEMPTS``; the row is
  ``invalidated`` on cap.
- Dev-mode override honours ``DEBUG=True AND OTP_DEV_MODE=True`` only; the
  module refuses to run with ``OTP_DEV_MODE`` while ``DEBUG=False``.
- The raw code never enters a log record or exception message.
"""

from __future__ import annotations

import hmac
import logging
import secrets
from datetime import timedelta
from hashlib import sha256
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..exceptions import (
    InvalidCode,
    NoActiveOtp,
    OtpExpired,
    OtpInvalidated,
    TooManyAttempts,
)
from ..models import OtpCode


logger = logging.getLogger('accounts')


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def generate() -> str:
    """Return a cryptographically secure 6-digit code as a zero-padded string."""
    return f'{secrets.randbelow(10 ** settings.OTP_LENGTH):0{settings.OTP_LENGTH}d}'


def _pepper_bytes() -> bytes:
    pepper = settings.OTP_PEPPER
    if isinstance(pepper, str):
        return pepper.encode('utf-8')
    return pepper


def hash_code(code: str) -> str:
    """HMAC-SHA256(pepper, code) as lowercase hex."""
    return hmac.new(_pepper_bytes(), code.encode('utf-8'), sha256).hexdigest()


def _dev_mode_enabled() -> bool:
    """Return True if dev-mode is active. Refuse to enable in prod."""
    if getattr(settings, 'OTP_DEV_MODE', False) and not settings.DEBUG:
        raise RuntimeError(
            'OTP_DEV_MODE must not be enabled while DEBUG=False (production).'
        )
    return bool(settings.DEBUG and getattr(settings, 'OTP_DEV_MODE', False))


def dev_mode_accepts(code: str) -> bool:
    """Return True if dev-mode is active AND ``code`` matches the fixed override."""
    if not _dev_mode_enabled():
        return False
    fixed = getattr(settings, 'OTP_DEV_FIXED_CODE', '') or ''
    if not fixed:
        return False
    return hmac.compare_digest(code, fixed)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@transaction.atomic
def create_for_phone(
    phone_number: str,
    *,
    request_ip: Optional[str] = None,
    request_id: str = '',
) -> tuple[OtpCode, str]:
    """Create a fresh OTP for ``phone_number``, superseding any active one.

    Returns ``(otp_row, raw_code)``. The raw code is returned so the caller
    (view) can hand it to Twilio; it MUST NOT be logged or persisted.
    """
    # Supersede any prior active OTP for this phone (FR-10, race-safe).
    now = timezone.now()
    (
        OtpCode.objects
        .select_for_update()
        .filter(
            phone_number=phone_number,
            invalidated=False,
            consumed_at__isnull=True,
            expires_at__gt=now,
        )
        .update(invalidated=True)
    )

    code = generate()
    otp = OtpCode.objects.create(
        phone_number=phone_number,
        code_hash=hash_code(code),
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        request_ip=request_ip,
        request_id=request_id or '',
    )
    logger.info(
        'otp.request.created',
        extra={'otp_id': otp.id, 'phone_number': phone_number, 'request_id': request_id},
    )
    return otp, code


def verify(phone_number: str, submitted: str) -> OtpCode:
    """Verify ``submitted`` against the latest active OTP for ``phone_number``.

    Consume-once semantics; on success returns the consumed row. Raises the
    appropriate domain exception on failure (never leaks the code).
    """
    if not submitted or not submitted.isdigit() or len(submitted) != settings.OTP_LENGTH:
        raise InvalidCode()

    now = timezone.now()
    otp = (
        OtpCode.objects
        .select_for_update()
        .filter(phone_number=phone_number, consumed_at__isnull=True)
        .order_by('-created_at')
        .first()
    )
    if otp is None:
        raise NoActiveOtp()

    if otp.invalidated:
        # Preserve audit row; caller must request a new OTP.
        raise TooManyAttempts() if otp.attempts >= settings.OTP_MAX_ATTEMPTS else OtpInvalidated()

    if otp.expires_at <= now:
        raise OtpExpired()

    # Dev-mode short-circuit — still requires an active OTP to have been issued.
    if dev_mode_accepts(submitted):
        otp.consumed_at = now
        otp.save(update_fields=['consumed_at'])
        logger.info(
            'otp.verify.success',
            extra={
                'otp_id': otp.id,
                'phone_number': phone_number,
                'dev_mode': True,
                'request_id': otp.request_id,
            },
        )
        return otp

    expected = otp.code_hash
    submitted_hash = hash_code(submitted)
    if hmac.compare_digest(expected, submitted_hash):
        otp.consumed_at = now
        otp.save(update_fields=['consumed_at'])
        logger.info(
            'otp.verify.success',
            extra={'otp_id': otp.id, 'phone_number': phone_number, 'request_id': otp.request_id},
        )
        return otp

    # Wrong code — count the attempt, invalidate at cap.
    otp.attempts = (otp.attempts or 0) + 1
    if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        otp.invalidated = True
        otp.save(update_fields=['attempts', 'invalidated'])
        logger.info(
            'otp.verify.failure',
            extra={
                'otp_id': otp.id,
                'phone_number': phone_number,
                'reason': 'too_many_attempts',
                'attempts': otp.attempts,
                'request_id': otp.request_id,
            },
        )
        raise TooManyAttempts()

    otp.save(update_fields=['attempts'])
    logger.info(
        'otp.verify.failure',
        extra={
            'otp_id': otp.id,
            'phone_number': phone_number,
            'reason': 'invalid_code',
            'attempts': otp.attempts,
            'request_id': otp.request_id,
        },
    )
    raise InvalidCode()
