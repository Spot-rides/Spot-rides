"""Domain exceptions for the user onboarding flow (FEAT-002).

All exceptions inherit from ``core.exceptions.ApiError`` and map to stable
error codes defined in the API contract.
"""

from rest_framework import status
from core.exceptions import ApiError


class OnboardingIncomplete(ApiError):
    """User has not completed onboarding."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = 'onboarding_incomplete'
    default_detail = 'Onboarding must be completed before accessing this endpoint.'


class NotADriver(ApiError):
    """Endpoint requires driver role but user is a passenger."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = 'not_a_driver'
    default_detail = 'This endpoint is only accessible to drivers.'


class InvalidAge(ApiError):
    """Age is outside the allowed range (18-80)."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_age'
    default_detail = 'Age must be between 18 and 80.'


class InvalidGender(ApiError):
    """Gender value is not in the allowed set."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_gender'
    default_detail = 'Gender must be one of: male, female, other, prefer_not_to_say.'


class InvalidDLFormat(ApiError):
    """DL number does not match Indian DL format."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_dl_format'
    default_detail = 'Driving licence number format is invalid.'


class DLAlreadyVerified(ApiError):
    """Attempt to submit DL when already verified."""
    status_code = status.HTTP_409_CONFLICT
    error_code = 'dl_already_verified'
    default_detail = 'Driving licence is already verified.'


class DLProviderError(ApiError):
    """DL verification provider call failed."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = 'dl_verification_provider_error'
    default_detail = 'DL verification provider error. Please try again.'


class MaxDLAttemptsExceeded(ApiError):
    """Maximum DL submission attempts reached."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = 'max_dl_attempts_exceeded'
    default_detail = 'Maximum DL submission attempts exceeded. Manual review required.'


class RoleAlreadySet(ApiError):
    """Role was already set during onboarding."""
    status_code = status.HTTP_409_CONFLICT
    error_code = 'role_already_set'
    default_detail = 'Role has already been set for this account.'


class ProfileAlreadySet(ApiError):
    """Profile details were already submitted."""
    status_code = status.HTTP_409_CONFLICT
    error_code = 'profile_already_set'
    default_detail = 'Profile details have already been submitted.'


class DLRequired(ApiError):
    """Switching to driver role requires DL verification."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'dl_required'
    default_detail = 'Driving licence verification is required before acting as a driver.'


class AlreadyProcessed(ApiError):
    """Webhook result already applied (idempotent re-delivery)."""
    status_code = status.HTTP_409_CONFLICT
    error_code = 'already_processed'
    default_detail = 'This webhook result has already been processed.'


class InvalidWebhookSignature(ApiError):
    """Webhook signature validation failed."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = 'invalid_webhook_signature'
    default_detail = 'Webhook signature validation failed.'


class InvalidOnboardingState(ApiError):
    """User is not in the correct onboarding state for this operation."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = 'invalid_onboarding_state'
    default_detail = 'This operation is not allowed in your current onboarding state.'
