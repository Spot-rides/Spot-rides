"""DRF serializers for the user onboarding flow (FEAT-002).

All serializers are for request/response validation only (not model serializers).
They enforce the API contracts defined in FEAT-002 requirements.
"""

from rest_framework import serializers

from profiles.services.validators import validate_age, validate_name, validate_dl_format
from profiles.utils.crypto import normalize_dl_number


class OnboardingStatusSerializer(serializers.Serializer):
    """Response for GET /api/onboarding/status/"""
    onboarding_status = serializers.CharField()
    active_role = serializers.CharField(allow_null=True)
    next_step = serializers.CharField()
    profile_complete = serializers.BooleanField()
    dl_verification_status = serializers.CharField(allow_null=True)


class RoleSelectionSerializer(serializers.Serializer):
    """Request for POST /api/onboarding/role/"""
    role = serializers.ChoiceField(choices=['driver', 'passenger'])


class RoleSelectionResponseSerializer(serializers.Serializer):
    """Response for POST /api/onboarding/role/"""
    active_role = serializers.CharField()
    onboarding_status = serializers.CharField()
    next_step = serializers.CharField()


class ProfileDetailsSerializer(serializers.Serializer):
    """Request for POST /api/onboarding/profile/"""
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    age = serializers.IntegerField()
    gender = serializers.ChoiceField(choices=['male', 'female', 'other', 'prefer_not_to_say'])

    def validate_first_name(self, value):
        is_valid, error = validate_name(value, 'first_name')
        if not is_valid:
            raise serializers.ValidationError(error)
        return value

    def validate_last_name(self, value):
        is_valid, error = validate_name(value, 'last_name')
        if not is_valid:
            raise serializers.ValidationError(error)
        return value

    def validate_age(self, value):
        is_valid, error = validate_age(value)
        if not is_valid:
            raise serializers.ValidationError(error)
        return value


class ProfileDetailsResponseSerializer(serializers.Serializer):
    """Response for POST /api/onboarding/profile/"""
    onboarding_status = serializers.CharField()
    next_step = serializers.CharField()


class DLSubmissionSerializer(serializers.Serializer):
    """Request for POST /api/onboarding/driver/dl/"""
    dl_number = serializers.CharField(max_length=20)

    def validate_dl_number(self, value):
        # Normalize first
        normalized = normalize_dl_number(value)

        # Validate format
        is_valid, error = validate_dl_format(normalized)
        if not is_valid:
            raise serializers.ValidationError(error)

        return normalized


class DLSubmissionResponseSerializer(serializers.Serializer):
    """Response for POST /api/onboarding/driver/dl/ (sync verified or async pending)"""
    dl_verification_status = serializers.CharField()
    onboarding_status = serializers.CharField()
    next_step = serializers.CharField()
    reference_id = serializers.CharField(allow_null=True)


class DLStatusSerializer(serializers.Serializer):
    """Response for GET /api/onboarding/driver/dl/status/"""
    dl_verification_status = serializers.CharField()
    onboarding_status = serializers.CharField()
    rejection_reason = serializers.CharField(allow_null=True)
    dl_number_display = serializers.CharField()  # Last 4 digits


class RoleSwitchSerializer(serializers.Serializer):
    """Request for PATCH /api/profile/role/"""
    role = serializers.ChoiceField(choices=['driver', 'passenger'])


class RoleSwitchResponseSerializer(serializers.Serializer):
    """Response for PATCH /api/profile/role/"""
    active_role = serializers.CharField()
    onboarding_status = serializers.CharField()
    dl_verification_status = serializers.CharField(allow_null=True)


class WebhookPayloadSerializer(serializers.Serializer):
    """Request payload for POST /api/onboarding/driver/dl/webhook/"""
    reference_id = serializers.CharField()
    status = serializers.ChoiceField(choices=['verified', 'rejected'])
    rejection_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True)
