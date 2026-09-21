"""Twilio SMS wrapper for OTP dispatch.

Implements PLAN-001 TASK-011 / ARCH-001 COMP-005.

Contract:
- ``send_otp_sms(phone_e164, code)`` — synchronous, 5s HTTP timeout.
- Any Twilio SDK exception is translated to :class:`SmsDispatchError`; the
  provider's error code is logged but never returned to the caller.
- Dev-mode short-circuit: when ``DEBUG=True AND OTP_DEV_MODE=True`` the send
  is a no-op that logs ``otp_dev_dispatch_skipped``. ``OTP_DEV_MODE`` with
  ``DEBUG=False`` is refused with ``RuntimeError`` (prod guard).
- Client is constructed lazily so a missing / unset Twilio credential does
  not break module import in dev.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from django.conf import settings

from ..exceptions import AuthUnavailable, InvalidPhoneNumber, SmsDispatchError


logger = logging.getLogger('accounts')

_MESSAGE_TEMPLATE = 'Your Spot Rides code is {code}. It expires in 5 minutes.'
_HTTP_TIMEOUT_SECONDS = 5

# Cached client for the life of the process; reset if creds change.
_client = None


def _dev_mode_active() -> bool:
    if getattr(settings, 'OTP_DEV_MODE', False) and not settings.DEBUG:
        raise RuntimeError(
            'OTP_DEV_MODE must not be enabled while DEBUG=False (production).'
        )
    return bool(settings.DEBUG and getattr(settings, 'OTP_DEV_MODE', False))


def _get_client():
    """Lazily construct a Twilio ``Client`` with a bounded HTTP timeout."""
    global _client
    if _client is not None:
        return _client
    sid = settings.TWILIO_ACCOUNT_SID
    token = settings.TWILIO_AUTH_TOKEN
    if not sid or not token:
        raise AuthUnavailable('SMS provider credentials are not configured.')

    # Imports are deferred so tests / dev environments without twilio's
    # transitive network stack imported still succeed at module import time.
    from twilio.rest import Client
    from twilio.http.http_client import TwilioHttpClient

    http_client = TwilioHttpClient(timeout=_HTTP_TIMEOUT_SECONDS)
    _client = Client(sid, token, http_client=http_client)
    return _client


def _dispatch_kwargs(phone_e164: str, body: str) -> dict:
    kwargs: dict = {'to': phone_e164, 'body': body}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        kwargs['messaging_service_sid'] = settings.TWILIO_MESSAGING_SERVICE_SID
    elif settings.TWILIO_FROM_NUMBER:
        kwargs['from_'] = settings.TWILIO_FROM_NUMBER
    else:
        raise AuthUnavailable('SMS sender is not configured.')
    return kwargs


def send_otp_sms(phone_e164: str, code: str, *, request_id: str = '') -> None:
    """Send the OTP to ``phone_e164``. Raises on any provider-side failure.

    The raw ``code`` MUST NOT be logged; only ``phone_e164`` (which the
    logging filter masks) and the provider error code are recorded.
    """
    if _dev_mode_active():
        logger.info(
            'otp_dev_dispatch_skipped',
            extra={'phone_number': phone_e164, 'request_id': request_id},
        )
        return

    body = _MESSAGE_TEMPLATE.format(code=code)
    started = time.monotonic()
    try:
        client = _get_client()
        client.messages.create(**_dispatch_kwargs(phone_e164, body))
    except AuthUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — deliberate broad catch, mapped below.
        duration_ms = int((time.monotonic() - started) * 1000)
        twilio_error_code = _extract_twilio_error_code(exc)
        logger.error(
            'otp.request.sms_failed',
            extra={
                'phone_number': phone_e164,
                'twilio_error_code': twilio_error_code,
                'duration_ms': duration_ms,
                'request_id': request_id,
            },
        )
        if _is_invalid_number_error(twilio_error_code):
            raise InvalidPhoneNumber('SMS provider rejected the phone number.')
        raise SmsDispatchError()

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        'otp.request.dispatched',
        extra={'phone_number': phone_e164, 'duration_ms': duration_ms, 'request_id': request_id},
    )


def _extract_twilio_error_code(exc) -> Optional[int]:
    code = getattr(exc, 'code', None)
    if code is None:
        code = getattr(exc, 'status', None)
    try:
        return int(code) if code is not None else None
    except (TypeError, ValueError):
        return None


def _is_invalid_number_error(code: Optional[int]) -> bool:
    # Twilio error codes 21211 (invalid To), 21614 (not a mobile number) etc.
    return code in {21211, 21214, 21217, 21421, 21610, 21611, 21612, 21614}


def reset_client_for_tests() -> None:
    """Test helper — clear the cached client so patched settings take effect."""
    global _client
    _client = None
