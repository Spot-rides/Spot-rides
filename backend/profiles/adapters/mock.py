"""Mock DL verification adapter for dev/test.

This adapter simulates DL verification without calling any external service.
Behavior is controlled via settings.DL_ADAPTER_MOCK_RESULT.
"""

import uuid
from typing import Optional
from .base import DLVerificationAdapter, DLVerificationResult


class MockDLVerificationAdapter(DLVerificationAdapter):
    """Mock adapter for dev/test. Returns configurable results without external calls.

    Supports three response modes:
    - 'sync_verified': Returns verified status immediately
    - 'async_pending': Returns pending status with reference ID (simulates async flow)
    - 'sync_rejected': Returns rejected status with mock reason

    The mode is controlled by the response_mode constructor parameter or via
    settings.DL_ADAPTER_MOCK_RESULT (defaults to 'verified' for backward compat).
    """

    def __init__(self, response_mode: str = 'sync_verified'):
        """Initialize mock adapter with specific response behavior.

        Args:
            response_mode: One of 'sync_verified', 'async_pending', 'sync_rejected'
                          Defaults to 'sync_verified' for simple dev/test scenarios
        """
        self.response_mode = response_mode

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
        else:
            # Default to verified if unknown mode
            return DLVerificationResult(
                status='verified',
                reference_id=f'mock-{uuid.uuid4().hex[:8]}'
            )

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Mock webhook validation.

        Checks for X-Mock-Signature header matching settings.DL_WEBHOOK_SECRET.
        In a real provider, this would validate HMAC-SHA256 or equivalent.

        Args:
            headers: HTTP headers dict (lowercase keys)
            body: Raw request body bytes (ignored in mock)

        Returns:
            True if X-Mock-Signature header matches expected value
        """
        # Import here to avoid circular dependency at module load time
        from django.conf import settings

        expected_signature = getattr(settings, 'DL_WEBHOOK_SECRET', 'mock-secret')
        actual_signature = headers.get('x-mock-signature', '')

        return actual_signature == expected_signature
