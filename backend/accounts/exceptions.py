"""Domain exceptions for the auth feature.

Implements PLAN-001 TASK-015. Each class maps an ARCH-001 §API Contracts error
code onto an HTTP status; the rendering of the response body is owned by
:func:`core.exceptions.envelope_exception_handler` (see DEC-011), so nothing
here builds a body itself.
Component ID: part of COMP-008 error surface.
"""

from __future__ import annotations

from typing import Optional

from rest_framework import status

from core.exceptions import ApiError


class AuthDomainError(ApiError):
    """Base class for all auth domain errors."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'auth_error'
    default_detail = 'Authentication error.'


class InvalidPhoneNumber(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_phone_number'
    default_detail = 'Phone number is not a valid E.164 number.'


class CountryNotAllowed(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'country_not_allowed'
    default_detail = 'Phone numbers from this country are not supported yet.'


class NoActiveOtp(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'no_active_otp'
    default_detail = 'No active OTP for this phone number.'


class OtpExpired(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'code_expired'
    default_detail = 'OTP has expired. Request a new one.'


class OtpInvalidated(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'code_invalidated'
    default_detail = 'OTP has been invalidated.'


class InvalidCode(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_code'
    default_detail = 'The code you entered is incorrect.'


class TooManyAttempts(AuthDomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = 'too_many_attempts'
    default_detail = 'Too many failed attempts. Request a new OTP.'


class RateLimited(AuthDomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = 'rate_limited'
    default_detail = 'Too many requests. Try again later.'

    def __init__(self, retry_after: int, detail: Optional[str] = None):
        super().__init__(detail=detail, retry_after=retry_after)


class SmsDispatchError(AuthDomainError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_code = 'sms_dispatch_failed'
    default_detail = 'Unable to send SMS at this time. Try again shortly.'


class AuthUnavailable(AuthDomainError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = 'auth_unavailable'
    default_detail = 'Authentication service is temporarily unavailable.'


class AccountDeactivated(AuthDomainError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = 'account_deactivated'
    default_detail = 'This account has been deactivated.'


class InvalidRefresh(AuthDomainError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_refresh'
    default_detail = 'Refresh token is invalid or already blacklisted.'
