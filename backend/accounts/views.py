"""DRF views for the OTP phone-authentication endpoints.

Implements PLAN-001 TASK-017 (OtpRequestView), TASK-018 (OtpVerifyView),
TASK-019 (LogoutView) and TASK-020 (MeView). See ARCH-001 §API Contracts
for the canonical request/response shapes and error taxonomy.

All error responses flow through :func:`core.exceptions.envelope_exception_handler`
so this module never hand-rolls error envelopes — it raises domain
exceptions from :mod:`accounts.exceptions` instead. Success payloads are
wrapped by :class:`core.renderers.EnvelopeJSONRenderer`, so the views return
the bare ``data`` value and an optional human-readable ``message``.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import update_last_login
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.response import ApiResponse

from .exceptions import AccountDeactivated, InvalidRefresh, RateLimited
from .serializers import (
    LogoutSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    UserSerializer,
)
from .services import otp as otp_service
from .services import rate_limit
from .services import twilio_client


logger = logging.getLogger('accounts')

User = get_user_model()


def _client_ip(request) -> str:
    """Extract the client IP.

    ARCH-001 discusses ``X-Forwarded-Proto`` for HTTPS termination but does
    not designate a trusted proxy header for the client IP. To avoid trusting
    a spoofable header by default we use ``REMOTE_ADDR`` — a deployment
    concern (ALB / nginx) can layer in ``X-Forwarded-For`` handling later
    (via e.g. ``django-ipware`` or an explicit proxy setting) without
    touching this call site.
    """
    return request.META.get('REMOTE_ADDR', '') or '0.0.0.0'


class OtpRequestView(APIView):
    """POST /api/auth/otp/request/ — issue an OTP over SMS.

    Public endpoint. Flow (ARCH §OTP Lifecycle):
    1. Validate + normalise phone via ``OtpRequestSerializer``.
    2. Redis rate limit (per-phone 30s/1h/24h + per-IP 1h).
    3. Inside ``transaction.atomic``: supersede prior OTP, create hashed row,
       dispatch via Twilio. Any exception rolls back the DB write and
       compensates the Redis counters.
    4. On success, arm the 30s resend cooldown and respond with the ARCH
       shape ``{detail, expires_in, resend_available_in}``.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = OtpRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_e164 = serializer.phone_e164

        ip = _client_ip(request)
        phone_hash = rate_limit.hash_phone(phone_e164)

        ok, retry_after = rate_limit.check_otp_request(phone_hash, ip)
        if not ok:
            raise RateLimited(retry_after=int(retry_after or 0))

        request_id = getattr(request, 'request_id', '') or ''

        try:
            with transaction.atomic():
                otp_row, code = otp_service.create_for_phone(
                    phone_e164,
                    request_ip=ip,
                    request_id=request_id,
                )
                twilio_client.send_otp_sms(phone_e164, code, request_id=request_id)
        except Exception:
            # Roll back the rate-limit counters — the caller shouldn't be
            # penalised for provider-side failure (FR-15). Compensation is
            # best-effort; it swallows Redis errors internally.
            rate_limit.compensate_request(phone_hash, ip)
            raise

        rate_limit.record_success_cooldown(phone_hash)

        return ApiResponse(
            {
                'detail': 'otp_sent',
                'expires_in': int(settings.OTP_TTL_SECONDS),
                'resend_available_in': int(settings.OTP_RESEND_COOLDOWN_SECONDS),
            },
            message='OTP sent successfully.',
            status=status.HTTP_200_OK,
        )


class OtpVerifyView(APIView):
    """POST /api/auth/otp/verify/ — verify OTP and mint a JWT pair.

    Public endpoint. Flow:
    1. Validate payload.
    2. Per-IP verify rate limit (NFR-SEC-08).
    3. ``otp.verify`` inside its own atomic block — raises the appropriate
       domain exception on failure (invalid / expired / attempts).
    4. On success, ``get_or_create`` the user, update ``last_login``, and
       return ``{access, refresh, is_new_user, user}`` per ARCH.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_e164 = serializer.phone_e164
        code = serializer.validated_data['code']

        ip = _client_ip(request)
        phone_hash = rate_limit.hash_phone(phone_e164)

        ok, retry_after = rate_limit.check_otp_verify(phone_hash, ip)
        if not ok:
            raise RateLimited(retry_after=int(retry_after or 0))

        # A single atomic block covers both OTP consumption and user creation so
        # a crash between the two cannot leave the OTP consumed without a session.
        with transaction.atomic():
            otp_service.verify(phone_e164, code)
            user, is_new_user = User.objects.get_or_create(phone_number=phone_e164)

        if not user.is_active:
            raise AccountDeactivated()

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # SimpleJWT's UPDATE_LAST_LOGIN only fires via TokenObtain* serializers;
        # we mint tokens manually here, so update explicitly.
        update_last_login(None, user)

        logger.info(
            'otp.verify.success.view',
            extra={
                'user_id': user.id,
                'is_new_user': is_new_user,
                'phone_number': phone_e164,
                'request_id': getattr(request, 'request_id', '') or '',
            },
        )

        return ApiResponse(
            {
                'access': str(access),
                'refresh': str(refresh),
                'is_new_user': is_new_user,
                'user': UserSerializer(user).data,
            },
            message='Phone number verified.',
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the supplied refresh token.

    Per ARCH-001 §API Contracts, the refresh token in the request body is
    itself the credential for this endpoint, so we accept any authenticated
    session (access-bearer is sufficient) and rely on token validity for
    the actual state change.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refresh = serializer.validated_data['refresh']

        try:
            token = RefreshToken(refresh)
            if str(token['user_id']) != str(request.user.id):
                raise InvalidToken()
            token.blacklist()
        except InvalidToken:
            raise InvalidRefresh()
        except TokenError:
            raise InvalidRefresh()

        logger.info(
            'logout.success',
            extra={
                'user_id': getattr(request.user, 'id', None),
                'request_id': getattr(request, 'request_id', '') or '',
            },
        )
        # ARCH-001 specifies 205 Reset Content for logout success.
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    """GET /api/auth/me/ — return the authenticated user's minimal profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return ApiResponse(UserSerializer(request.user).data, status=status.HTTP_200_OK)
