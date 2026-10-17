"""Mock DL verification adapter for dev/test.

This adapter simulates DL verification without calling any external service.
Behavior is controlled via settings.DL_ADAPTER_MOCK_RESULT.
"""

import hashlib
import hmac
import json
import uuid
from datetime import date, timedelta
from typing import Optional

from django.core.exceptions import ImproperlyConfigured

from .base import (
    DLVerificationAdapter,
    DLVerificationResult,
    RCAdapterError,
    RCVerificationAdapter,
    RCVerificationResult,
)


class MockDLVerificationAdapter(DLVerificationAdapter):
    """Mock adapter for dev/test ONLY. It verifies anything and must never run in production.

    Supports three response modes:
    - 'sync_verified': Returns verified status immediately
    - 'async_pending': Returns pending status with reference ID (simulates async flow)
    - 'sync_rejected': Returns rejected status with mock reason

    The mode is controlled by the response_mode constructor parameter or via
    settings.DL_ADAPTER_MOCK_RESULT (default 'sync_verified'). An unknown mode raises
    ImproperlyConfigured rather than silently verifying.
    """

    MODES = ('sync_verified', 'async_pending', 'sync_rejected')

    def __init__(self, response_mode: str = 'sync_verified'):
        """Initialize mock adapter with specific response behavior.

        Args:
            response_mode: One of 'sync_verified', 'async_pending', 'sync_rejected'
                          Defaults to 'sync_verified' for simple dev/test scenarios
        """
        if response_mode not in self.MODES:
            raise ImproperlyConfigured(
                f"Unknown DL_ADAPTER_MOCK_RESULT {response_mode!r}; expected one of {self.MODES}"
            )
        self.response_mode = response_mode

    @classmethod
    def from_settings(cls, settings) -> 'MockDLVerificationAdapter':
        return cls(response_mode=getattr(settings, 'DL_ADAPTER_MOCK_RESULT', 'sync_verified'))

    def submit(self, dl_number: str, user_id: int) -> DLVerificationResult:
        """Always succeeds for dev/test; returns result based on response_mode.

        Args:
            dl_number: Normalized DL number (ignored in mock)
            user_id: User ID (ignored in mock)

        Returns:
            DLVerificationResult matching the configured response_mode
        """
        if self.response_mode == 'sync_verified':
            return DLVerificationResult(
                status='verified',
                reference_id=f'mock-{uuid.uuid4().hex[:8]}'
            )
        elif self.response_mode == 'async_pending':
            return DLVerificationResult(
                status='pending',
                reference_id=f'mock-{uuid.uuid4().hex[:8]}'
            )
        elif self.response_mode == 'sync_rejected':
            return DLVerificationResult(
                status='rejected',
                reference_id=f'mock-{uuid.uuid4().hex[:8]}',
                rejection_reason='Mock rejection for testing'
            )
        raise ImproperlyConfigured(f"Unknown mock DL response mode {self.response_mode!r}")

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """HMAC-SHA256 of the raw body (hex) in ``x-dl-signature``, optional ``sha256=`` prefix.

        The key is ``settings.DL_WEBHOOK_SECRET``. Fails closed on an empty secret or a missing
        header; compared in constant time.

        Args:
            headers: HTTP headers dict (lowercase keys)
            body: Raw request body bytes (before JSON parsing)
        """
        # Import here to avoid circular dependency at module load time
        from django.conf import settings

        secret = getattr(settings, 'DL_WEBHOOK_SECRET', '') or ''
        if not secret:
            return False
        provided = (headers.get('x-dl-signature') or '').strip()
        if provided.startswith('sha256='):
            provided = provided[len('sha256='):]
        if not provided:
            return False
        expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided.encode('utf-8'), expected.encode('utf-8'))


class MockRCVerificationAdapter(RCVerificationAdapter):
    """Mock RC adapter for dev/test ONLY. It verifies anything and must never run in production.

    Modes (``settings.RC_ADAPTER_MOCK_RESULT``): sync_verified, sync_verified_name_mismatch,
    async_pending, sync_rejected, timeout, provider_error. No network I/O.
    """

    MODES = (
        'sync_verified',
        'sync_verified_name_mismatch',
        'async_pending',
        'sync_rejected',
        'timeout',
        'provider_error',
    )

    def __init__(self, *, timeout_seconds: float, response_mode: str = 'sync_verified'):
        super().__init__(timeout_seconds=timeout_seconds)
        if response_mode not in self.MODES:
            raise ImproperlyConfigured(
                f"Unknown RC_ADAPTER_MOCK_RESULT {response_mode!r}; expected one of {self.MODES}"
            )
        self.response_mode = response_mode

    @classmethod
    def from_settings(cls, settings) -> 'MockRCVerificationAdapter':
        return cls(
            timeout_seconds=getattr(settings, 'RC_PROVIDER_TIMEOUT_SECONDS', 5),
            response_mode=getattr(settings, 'RC_ADAPTER_MOCK_RESULT', 'sync_verified'),
        )

    def verify(self, registration_number: str, user_id: int) -> RCVerificationResult:
        mode = self.response_mode
        if mode == 'timeout':
            raise TimeoutError('mock provider timeout')
        if mode == 'provider_error':
            raise RCAdapterError('mock provider error')

        reference_id = f'mock-rc-{uuid.uuid4().hex[:8]}'
        if mode == 'async_pending':
            return RCVerificationResult(status='pending', reference_id=reference_id)
        if mode == 'sync_rejected':
            return RCVerificationResult(
                status='rejected',
                reference_id=reference_id,
                rejection_reason='Mock rejection for testing',
            )

        if mode == 'sync_verified_name_mismatch':
            owner_name = 'MOCK OTHER OWNER'
        else:
            owner_name = self._profile_name(user_id)
        today = date.today()
        return RCVerificationResult(
            status='verified',
            reference_id=reference_id,
            owner_name=owner_name,
            vehicle_class=None,
            fuel_type='PETROL',
            fitness_valid_upto=today + timedelta(days=365),
            insurance_valid_upto=today + timedelta(days=365),
        )

    @staticmethod
    def _profile_name(user_id: int) -> Optional[str]:
        from profiles.models import UserProfile

        profile = UserProfile.objects.filter(user_id=user_id).only('first_name', 'last_name').first()
        if profile is None:
            return None
        name = ' '.join(p for p in (profile.first_name, profile.last_name) if p)
        return name or None

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """HMAC-SHA256 of the raw body (hex) in ``x-rc-signature``. Fails closed on an empty secret."""
        from django.conf import settings

        secret = getattr(settings, 'RC_WEBHOOK_SECRET', '') or ''
        if not secret:
            return False
        provided = (headers.get('x-rc-signature') or '').strip()
        if provided.startswith('sha256='):
            provided = provided[len('sha256='):]
        if not provided:
            return False
        expected = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(provided.encode('utf-8'), expected.encode('utf-8'))

    def parse_webhook(self, body: bytes) -> RCVerificationResult:
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            raise RCAdapterError('malformed webhook body')
        if not isinstance(payload, dict):
            raise RCAdapterError('malformed webhook body')

        reference_id = payload.get('reference_id')
        status = payload.get('status')
        if not isinstance(reference_id, str) or not reference_id or len(reference_id) > 100:
            raise RCAdapterError('invalid reference_id')
        if status not in ('verified', 'rejected'):
            raise RCAdapterError('invalid status')

        def optional_str(key):
            value = payload.get(key)
            if value is None:
                return None
            if not isinstance(value, str):
                raise RCAdapterError(f'invalid {key}')
            return value

        def optional_date(key):
            value = payload.get(key)
            if value is None:
                return None
            try:
                return date.fromisoformat(value)
            except (TypeError, ValueError):
                raise RCAdapterError(f'invalid {key}')

        return RCVerificationResult(
            status=status,
            reference_id=reference_id,
            rejection_reason=optional_str('rejection_reason'),
            owner_name=optional_str('owner_name'),
            vehicle_class=optional_str('vehicle_class'),
            fuel_type=optional_str('fuel_type'),
            fitness_valid_upto=optional_date('fitness_valid_upto'),
            insurance_valid_upto=optional_date('insurance_valid_upto'),
        )
