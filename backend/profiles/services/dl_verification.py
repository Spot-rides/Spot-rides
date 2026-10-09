"""DL verification service layer.

Business logic for DL submission, validation, and webhook processing.
Integrates with the DL verification adapter for provider interactions.
"""

from typing import Dict, Any
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from profiles.models import DriverVerification, UserProfile
from profiles.utils.crypto import encrypt_dl_number, normalize_dl_number, get_dl_last_four
from profiles.adapters.base import DLVerificationAdapter
from profiles.adapters.mock import MockDLVerificationAdapter

User = get_user_model()

# Global adapter instance (mock for now)
_adapter: DLVerificationAdapter = MockDLVerificationAdapter(response_mode='sync_verified')


def set_adapter(adapter: DLVerificationAdapter):
    """Set the DL verification adapter (for testing or provider switching)."""
    global _adapter
    _adapter = adapter


@transaction.atomic
def submit_dl_verification(user: User, dl_number: str) -> Dict[str, Any]:
    """Submit DL for verification.

    Args:
        user: Authenticated user
        dl_number: Raw DL number from user input

    Returns:
        Dict with status, dl_verification_status, onboarding_status, etc.

    Raises:
        ValueError: If user not in correct state or max attempts exceeded
    """
    profile = user.profile

    if profile.active_role != UserProfile.DRIVER:
        raise ValueError("Not a driver")

    if profile.onboarding_status not in [
        UserProfile.AWAITING_DL,
        UserProfile.PENDING_VERIFICATION  # Allow resubmit
    ]:
        raise ValueError("Invalid state for DL submission")

    # Check attempt count
    if hasattr(user, 'driver_verification'):
        dl_record = user.driver_verification
        if dl_record.dl_verification_status == 'verified':
            raise ValueError("DL already verified")
        if dl_record.attempt_count >= 3:
            raise ValueError("Maximum DL submission attempts exceeded")
    else:
        dl_record = DriverVerification(user=user)

    # Normalize and encrypt
    normalized_dl = normalize_dl_number(dl_number)
    encrypted_dl = encrypt_dl_number(normalized_dl)
    last_four = get_dl_last_four(normalized_dl)

    # Call provider adapter
    try:
        result = _adapter.submit(normalized_dl, user.id)
    except TimeoutError:
        # Timeout: treat as pending
        result = type('Result', (), {
            'status': 'pending',
            'reference_id': None,
            'rejection_reason': None
        })()

    # Update DriverVerification record
    dl_record.dl_number = encrypted_dl
    dl_record.dl_number_display = last_four
    dl_record.dl_verification_status = result.status
    dl_record.dl_verification_ref = result.reference_id
    dl_record.dl_submitted_at = timezone.now()
    dl_record.attempt_count += 1

    if result.status == 'verified':
        dl_record.dl_verified_at = timezone.now()
        profile.onboarding_status = UserProfile.COMPLETE
    elif result.status == 'pending':
        profile.onboarding_status = UserProfile.PENDING_VERIFICATION
    elif result.status == 'rejected':
        dl_record.dl_rejection_reason = result.rejection_reason
        # Status remains AWAITING_DL or PENDING_VERIFICATION

    dl_record.save()
    profile.save()

    return {
        'dl_verification_status': dl_record.dl_verification_status,
        'onboarding_status': profile.onboarding_status,
        'reference_id': result.reference_id,
        'rejection_reason': result.rejection_reason if result.status == 'rejected' else None
    }


@transaction.atomic
def process_webhook_result(reference_id: str, status: str, rejection_reason: str = None) -> bool:
    """Process webhook callback from DL provider.

    Args:
        reference_id: Provider reference ID
        status: 'verified' or 'rejected'
        rejection_reason: Optional reason if rejected

    Returns:
        True if processed successfully

    Raises:
        DriverVerification.DoesNotExist: If reference_id not found
    """
    dl_record = DriverVerification.objects.select_related('user__profile').get(
        dl_verification_ref=reference_id
    )

    # Idempotency check
    if dl_record.dl_verification_status in ['verified', 'rejected']:
        return True  # Already processed

    dl_record.dl_verification_status = status

    if status == 'verified':
        dl_record.dl_verified_at = timezone.now()
        dl_record.user.profile.onboarding_status = UserProfile.COMPLETE
        dl_record.user.profile.save()
    elif status == 'rejected':
        dl_record.dl_rejection_reason = rejection_reason
        # User remains in PENDING_VERIFICATION, can resubmit

    dl_record.save()
    return True
