"""Abstract interface for DL verification providers.

This module defines the contract that all DL verification adapters must implement.
Provider-specific adapters (mock, real providers) inherit from DLVerificationAdapter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class DLVerificationResult:
    """Result from DL verification provider.

    Attributes:
        status: Verification status - 'verified', 'pending', or 'rejected'
        reference_id: Optional provider reference ID for async tracking
        rejection_reason: Optional reason if status is 'rejected'
    """
    status: str  # 'verified', 'pending', 'rejected'
    reference_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class DLVerificationAdapter(ABC):
    """Abstract interface for DL verification providers.

    All concrete DL verification providers must implement this interface.
    The service layer interacts only with this abstraction, making provider
    selection a configuration concern.
    """

    @abstractmethod
    def submit(self, dl_number: str, user_id: int) -> DLVerificationResult:
        """Submit DL for verification.

        Args:
            dl_number: Normalized DL number (uppercase, no spaces/hyphens)
            user_id: User ID for reference in provider systems

        Returns:
            DLVerificationResult with status and optional metadata

        Raises:
            TimeoutError: Provider didn't respond within timeout
            ValueError: Invalid DL format (though this should be pre-validated)
        """
        pass

    @abstractmethod
    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Validate webhook signature from provider.

        This method MUST be called before processing any webhook payload.
        It verifies the request authenticity using provider-specific signature
        validation (HMAC, IP allowlist, etc).

        Args:
            headers: HTTP headers dict (lowercase keys)
            body: Raw request body bytes (before JSON parsing)

        Returns:
            True if signature is valid, False otherwise
        """
        pass


@dataclass(frozen=True)
class RCVerificationResult:
    """Result from an RC verification provider. Every provider-derived field is optional.

    ``owner_name`` is third-party PII: ``repr=False`` keeps it out of logs that print the result.
    """
    status: str  # 'verified', 'pending', 'rejected'
    reference_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    owner_name: Optional[str] = field(default=None, repr=False)
    vehicle_class: Optional[str] = None
    fuel_type: Optional[str] = None
    fitness_valid_upto: Optional[date] = None
    insurance_valid_upto: Optional[date] = None


class RCAdapterError(Exception):
    """Any non-timeout provider failure. The message must not contain payloads or owner data."""


class RCVerificationAdapter(ABC):
    """Abstract interface for vehicle RC verification providers.

    Contract: provider outcomes "not found", "blacklisted" and "blocked" map to
    ``status='rejected'`` with a fixed, non-PII reason; ``timeout_seconds`` must be applied
    by the adapter to its own network calls and a timeout must surface as ``TimeoutError``.
    """

    def __init__(self, *, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds

    @classmethod
    @abstractmethod
    def from_settings(cls, settings) -> 'RCVerificationAdapter':
        """Build an instance from Django settings."""

    @abstractmethod
    def verify(self, registration_number: str, user_id: int) -> RCVerificationResult:
        """Look up a normalised registration number.

        Raises:
            TimeoutError: provider did not respond within ``timeout_seconds``
            RCAdapterError: any other provider failure
        """

    @abstractmethod
    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Verify the webhook signature. Header keys are lower-case. Must fail closed."""

    @abstractmethod
    def parse_webhook(self, body: bytes) -> RCVerificationResult:
        """Turn a webhook body into a result. Raises RCAdapterError if malformed."""
