"""Abstract interface for DL verification providers.

This module defines the contract that all DL verification adapters must implement.
Provider-specific adapters (mock, real providers) inherit from DLVerificationAdapter.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
