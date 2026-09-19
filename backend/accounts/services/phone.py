"""Phone-number normalization and country allowlist enforcement.

Implements PLAN-001 TASK-009 / ARCH-001 COMP-007.

- ``normalize_to_e164(raw, default_region="IN")``: parse a caller-provided
  phone string into canonical E.164, raising ``InvalidPhoneNumber`` on any
  parse/validation failure.
- ``country_allowed(e164)``: True when the parsed region is in
  ``settings.OTP_COUNTRY_ALLOWLIST`` (empty allowlist == no restriction).
"""

from __future__ import annotations

import logging

import phonenumbers
from django.conf import settings

from ..exceptions import CountryNotAllowed, InvalidPhoneNumber


logger = logging.getLogger('accounts')


def normalize_to_e164(raw: str, default_region: str = 'IN') -> str:
    """Parse ``raw`` and return the E.164 representation.

    Empty / non-string inputs and any ``phonenumbers`` failure raise
    :class:`InvalidPhoneNumber`.
    """
    if not raw or not isinstance(raw, str) or not raw.strip():
        raise InvalidPhoneNumber('Phone number is required.')
    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        raise InvalidPhoneNumber('Phone number could not be parsed.')
    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumber('Phone number is not a valid number.')
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def country_allowed(e164: str) -> bool:
    """Return True if the number's region is in the configured allowlist.

    Empty allowlist means no restriction. Raises :class:`InvalidPhoneNumber`
    if the input is not a parsable E.164 (should not normally happen since
    callers pass the output of :func:`normalize_to_e164`).
    """
    allowlist = [c.strip().upper() for c in (settings.OTP_COUNTRY_ALLOWLIST or []) if c.strip()]
    if not allowlist:
        if not settings.DEBUG:
            logger.warning('otp_country_allowlist_empty')
        return True
    try:
        parsed = phonenumbers.parse(e164, None)
    except phonenumbers.NumberParseException:
        raise InvalidPhoneNumber('Phone number could not be parsed.')
    region = phonenumbers.region_code_for_number(parsed)
    return bool(region) and region.upper() in allowlist


def ensure_allowed(e164: str) -> None:
    """Raise :class:`CountryNotAllowed` if ``e164`` is outside the allowlist."""
    if not country_allowed(e164):
        raise CountryNotAllowed()
