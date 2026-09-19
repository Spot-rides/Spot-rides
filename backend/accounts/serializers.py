"""DRF serializers for the OTP phone-authentication endpoints.

Implements PLAN-001 TASK-016 (ARCH-001 §API Contracts).

- ``OtpRequestSerializer``  — validates + normalises the caller's phone
  number to E.164 and enforces the country allowlist (FR-01, FR-12, FR-13).
- ``OtpVerifySerializer``  — same phone normalisation plus a strict 6-digit
  code validator (FR-02).
- ``LogoutSerializer``    — accepts the refresh token to be blacklisted (FR-04).
- ``UserSerializer``      — read-only projection returned by ``/me/`` (FR-05).

The serializers raise domain exceptions from :mod:`accounts.exceptions`
directly so :func:`accounts.exceptions.auth_exception_handler` renders the
stable ARCH-001 error envelope for malformed input.
"""

from __future__ import annotations

import re

from rest_framework import serializers

from .models import User
from .services import phone as phone_service


_CODE_RE = re.compile(r'^\d{6}$')


class OtpRequestSerializer(serializers.Serializer):
    """POST /api/auth/otp/request/ payload."""

    phone_number = serializers.CharField(
        max_length=32,
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate_phone_number(self, value: str) -> str:
        # ``normalize_to_e164`` raises ``InvalidPhoneNumber`` (400).
        e164 = phone_service.normalize_to_e164(value)
        # ``ensure_allowed`` raises ``CountryNotAllowed`` (400) if outside allowlist.
        phone_service.ensure_allowed(e164)
        return e164

    @property
    def phone_e164(self) -> str:
        """Normalised E.164 phone extracted after ``is_valid()``."""
        return self.validated_data['phone_number']


class OtpVerifySerializer(serializers.Serializer):
    """POST /api/auth/otp/verify/ payload."""

    phone_number = serializers.CharField(
        max_length=32,
        allow_blank=False,
        trim_whitespace=True,
    )
    code = serializers.CharField(
        max_length=6,
        min_length=6,
        allow_blank=False,
        trim_whitespace=True,
    )

    def validate_phone_number(self, value: str) -> str:
        e164 = phone_service.normalize_to_e164(value)
        phone_service.ensure_allowed(e164)
        return e164

    def validate_code(self, value: str) -> str:
        if not _CODE_RE.match(value or ''):
            # DRF ValidationError → 400 invalid_request via the exception
            # handler. We keep this generic (not ``invalid_code``) because
            # this fires before any OTP lookup happens.
            raise serializers.ValidationError('Code must be exactly 6 digits.')
        return value

    @property
    def phone_e164(self) -> str:
        return self.validated_data['phone_number']


class LogoutSerializer(serializers.Serializer):
    """POST /api/auth/logout/ payload — refresh token to blacklist."""

    refresh = serializers.CharField(allow_blank=False, trim_whitespace=True)


class UserSerializer(serializers.ModelSerializer):
    """Read-only projection returned by ``/api/auth/me/`` and verify."""

    class Meta:
        model = User
        fields = ('id', 'phone_number', 'date_joined')
        read_only_fields = fields
