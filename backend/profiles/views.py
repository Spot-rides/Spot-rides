"""DRF views for the user onboarding flow (FEAT-002).

Implements all 7 API endpoints:
- GET /api/onboarding/status/ (TASK-014)
- POST /api/onboarding/role/ (TASK-015)
- POST /api/onboarding/profile/ (TASK-016)
- POST /api/onboarding/driver/dl/ (TASK-017)
- GET /api/onboarding/driver/dl/status/ (TASK-018)
- POST /api/onboarding/driver/dl/webhook/ (TASK-019)
- PATCH /api/profile/role/ (TASK-020)

All success responses use ApiResponse; errors are raised as domain exceptions.
"""

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.response import ApiResponse
from profiles.models import UserProfile
from profiles.permissions import IsDriverRole
from profiles.serializers import (
    DLStatusSerializer,
    DLSubmissionResponseSerializer,
    DLSubmissionSerializer,
    OnboardingStatusSerializer,
    ProfileDetailsResponseSerializer,
    ProfileDetailsSerializer,
    RoleSelectionResponseSerializer,
    RoleSelectionSerializer,
    RoleSwitchResponseSerializer,
    RoleSwitchSerializer,
    WebhookPayloadSerializer,
)
from profiles.services.onboarding import (
    get_or_create_profile,
    set_profile_details,
    set_role,
    switch_role,
)
from profiles.services.dl_verification import (
    process_webhook_result,
    submit_dl_verification,
    _adapter,
)
from profiles.exceptions import (
    AlreadyProcessed,
    DLAlreadyVerified,
    DLProviderError,
    DLRequired,
    InvalidOnboardingState,
    InvalidWebhookSignature,
    MaxDLAttemptsExceeded,
    NotADriver,
    ProfileAlreadySet,
    RoleAlreadySet,
)


logger = logging.getLogger('profiles')


class OnboardingStatusView(APIView):
    """GET /api/onboarding/status/ — Get current onboarding state and next step.

    Public to authenticated users (explicitly opts out of IsOnboardingComplete).
    Creates profile lazily if it doesn't exist.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_create_profile(request.user)

        # Determine next_step based on state
        next_step_map = {
            UserProfile.NOT_STARTED: 'role_selection',
            UserProfile.ROLE_SELECTED: 'profile',
            UserProfile.AWAITING_DL: 'dl_submission',
            UserProfile.PENDING_VERIFICATION: 'awaiting_verification',
            UserProfile.COMPLETE: 'none'
        }

        # Get DL verification status if driver
        dl_status = None
        if hasattr(request.user, 'driver_verification'):
            dl_status = request.user.driver_verification.dl_verification_status

        data = {
            'onboarding_status': profile.onboarding_status,
            'active_role': profile.active_role,
            'next_step': next_step_map.get(profile.onboarding_status, 'none'),
            'profile_complete': profile.first_name is not None,
            'dl_verification_status': dl_status
        }

        serializer = OnboardingStatusSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RoleSelectView(APIView):
    """POST /api/onboarding/role/ — Set user's role during initial onboarding.

    Only valid when onboarding_status is NOT_STARTED.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RoleSelectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        role = serializer.validated_data['role']

        try:
            profile = set_role(request.user, role)
        except ValueError as e:
            error_msg = str(e).lower()
            if 'already set' in error_msg:
                raise RoleAlreadySet()
            elif 'invalid role' in error_msg:
                raise InvalidOnboardingState(detail='Invalid role. Must be "driver" or "passenger".')
            # Catch-all for other ValueError cases
            raise InvalidOnboardingState(detail=str(e))

        # Determine next step
        next_step = 'profile'

        response_data = {
            'active_role': profile.active_role,
            'onboarding_status': profile.onboarding_status,
            'next_step': next_step
        }

        response_serializer = RoleSelectionResponseSerializer(response_data)
        return ApiResponse(
            response_serializer.data,
            message='Role selected successfully.',
            status=status.HTTP_200_OK
        )


class ProfileSubmitView(APIView):
    """POST /api/onboarding/profile/ — Submit personal profile details.

    Only valid when onboarding_status is ROLE_SELECTED.
    Passenger → COMPLETE, Driver → AWAITING_DL.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProfileDetailsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = set_profile_details(
                request.user,
                first_name=serializer.validated_data['first_name'],
                last_name=serializer.validated_data['last_name'],
                age=serializer.validated_data['age'],
                gender=serializer.validated_data['gender']
            )
        except ValueError as e:
            error_msg = str(e).lower()
            if 'already set' in error_msg:
                raise ProfileAlreadySet()
            elif 'must select role first' in error_msg:
                raise InvalidOnboardingState(detail='You must select a role before submitting profile details.')
            # Catch-all for other ValueError cases
            raise InvalidOnboardingState(detail=str(e))

        # Determine next step based on new status
        next_step_map = {
            UserProfile.COMPLETE: 'none',
            UserProfile.AWAITING_DL: 'dl_submission'
        }

        response_data = {
            'onboarding_status': profile.onboarding_status,
            'next_step': next_step_map.get(profile.onboarding_status, 'none')
        }

        response_serializer = ProfileDetailsResponseSerializer(response_data)
        return ApiResponse(
            response_serializer.data,
            message='Profile details saved successfully.',
            status=status.HTTP_200_OK
        )


class DLSubmitView(APIView):
    """POST /api/onboarding/driver/dl/ — Submit DL for verification.

    Only accessible to drivers (active_role=DRIVER).
    Returns 200 for sync verified, 202 for pending.
    """

    permission_classes = [IsAuthenticated, IsDriverRole]

    def post(self, request):
        serializer = DLSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dl_number = serializer.validated_data['dl_number']

        try:
            result = submit_dl_verification(request.user, dl_number)
        except ValueError as e:
            error_msg = str(e).lower()
            if 'not a driver' in error_msg:
                raise NotADriver()
            elif 'already verified' in error_msg:
                raise DLAlreadyVerified()
            elif 'maximum' in error_msg or 'attempts' in error_msg:
                raise MaxDLAttemptsExceeded()
            elif 'provider' in error_msg:
                raise DLProviderError()
            elif 'invalid state' in error_msg:
                raise InvalidOnboardingState(detail=str(e))
            # Catch-all for other ValueError cases
            raise InvalidOnboardingState(detail=str(e))

        # Determine next step and HTTP status
        dl_status = result['dl_verification_status']
        onboarding_status = result['onboarding_status']

        next_step_map = {
            UserProfile.COMPLETE: 'none',
            UserProfile.PENDING_VERIFICATION: 'awaiting_verification',
            UserProfile.AWAITING_DL: 'dl_submission'
        }

        response_data = {
            'dl_verification_status': dl_status,
            'onboarding_status': onboarding_status,
            'next_step': next_step_map.get(onboarding_status, 'none'),
            'reference_id': result.get('reference_id')
        }

        response_serializer = DLSubmissionResponseSerializer(response_data)

        # 200 for verified, 202 for pending
        http_status = (
            status.HTTP_200_OK if dl_status == 'verified'
            else status.HTTP_202_ACCEPTED
        )

        return ApiResponse(
            response_serializer.data,
            message='DL verification submitted successfully.',
            status=http_status
        )


class DLStatusView(APIView):
    """GET /api/onboarding/driver/dl/status/ — Get current DL verification status.

    Only accessible to drivers. Allows polling for async verification results.
    """

    permission_classes = [IsAuthenticated, IsDriverRole]

    def get(self, request):
        if not hasattr(request.user, 'driver_verification'):
            raise NotADriver()

        dl_record = request.user.driver_verification
        profile = request.user.profile

        data = {
            'dl_verification_status': dl_record.dl_verification_status,
            'onboarding_status': profile.onboarding_status,
            'rejection_reason': dl_record.dl_rejection_reason,
            'dl_number_display': dl_record.dl_number_display
        }

        serializer = DLStatusSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DLWebhookView(APIView):
    """POST /api/onboarding/driver/dl/webhook/ — Receive DL verification result.

    No JWT authentication (uses signature validation instead).
    Validates signature before any DB operation.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # Validate signature FIRST, before any other processing
        headers = {key.lower(): value for key, value in request.headers.items()}

        if not _adapter.validate_webhook(headers, request.body):
            raise InvalidWebhookSignature()

        # Now parse and validate payload
        serializer = WebhookPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reference_id = serializer.validated_data['reference_id']
        result_status = serializer.validated_data['status']
        rejection_reason = serializer.validated_data.get('rejection_reason')

        try:
            success = process_webhook_result(reference_id, result_status, rejection_reason)
        except Exception as e:
            if 'already' in str(e).lower() or 'processed' in str(e).lower():
                raise AlreadyProcessed()
            logger.error(
                'webhook.processing.error',
                extra={
                    'reference_id': reference_id,
                    'status': result_status,
                    'error': str(e)
                }
            )
            raise

        logger.info(
            'webhook.processed',
            extra={
                'reference_id': reference_id,
                'status': result_status
            }
        )

        return Response({'detail': 'Webhook processed successfully.'}, status=status.HTTP_200_OK)


class RoleSwitchView(APIView):
    """PATCH /api/profile/role/ — Switch active role after onboarding complete.

    Requires onboarding_status=COMPLETE (or PENDING_VERIFICATION for edge cases).
    Switching to driver requires verified DL or pending DL.
    """

    permission_classes = [IsAuthenticated]  # Note: NOT IsOnboardingComplete to allow pending users

    def patch(self, request):
        serializer = RoleSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_role = serializer.validated_data['role']

        try:
            profile = switch_role(request.user, new_role)
        except ValueError as e:
            error_msg = str(e).lower()
            if 'dl' in error_msg or 'verification' in error_msg:
                raise DLRequired()
            elif 'not complete' in error_msg:
                raise InvalidOnboardingState(detail='Onboarding must be complete before switching roles.')
            elif 'invalid role' in error_msg:
                raise InvalidOnboardingState(detail='Invalid role. Must be "driver" or "passenger".')
            # Catch-all for other ValueError cases
            raise InvalidOnboardingState(detail=str(e))

        # Get DL status if switching to/from driver
        dl_status = None
        if hasattr(request.user, 'driver_verification'):
            dl_status = request.user.driver_verification.dl_verification_status

        response_data = {
            'active_role': profile.active_role,
            'onboarding_status': profile.onboarding_status,
            'dl_verification_status': dl_status
        }

        response_serializer = RoleSwitchResponseSerializer(response_data)

        # 200 for immediate switch, 202 for pending DL
        http_status = (
            status.HTTP_202_ACCEPTED
            if profile.onboarding_status == UserProfile.PENDING_VERIFICATION
            else status.HTTP_200_OK
        )

        return ApiResponse(
            response_serializer.data,
            message='Role switched successfully.',
            status=http_status
        )
