"""DL verification service layer.

Business logic for DL submission, validation, and webhook processing.
Integrates with the DL verification adapter for provider interactions.

Submission follows the same three-phase pattern as the RC service: guard under a row lock,
provider call with no transaction open, then decide and persist under the lock again. Lock
order is always UserProfile then DriverVerification. The adapter is built per call through
``profiles.adapters.get_dl_adapter()``; there is no module-level adapter. Nothing sensitive
(DL number, rejection reason, adapter message) is ever logged.
"""

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from profiles.adapters import DLVerificationResult, get_dl_adapter
from profiles.exceptions import DLProviderError, DLReferenceNotFound
from profiles.models import DriverVerification, UserProfile
from profiles.services.sanitise import sanitise_reason
from profiles.utils.crypto import encrypt_dl_number, get_dl_last_four, normalize_dl_number

User = get_user_model()

logger = logging.getLogger('profiles')

_LOG_FIELDS = frozenset({
    'user_id', 'attempt_count', 'dl_status', 'outcome', 'cause', 'onboarding_status',
    'reference_id', 'adapter', 'error_type', 'timed_out',
})
_ALLOWED_RESULT_STATUSES = ('verified', 'pending', 'rejected')


def _log_event(level: int, event: str, **fields) -> None:
    """Single logging entry point: fields outside the allow-list are dropped."""
    logger.log(level, event, extra={k: v for k, v in fields.items() if k in _LOG_FIELDS})


def _lock_profile(user_id: int) -> Optional[UserProfile]:
    return UserProfile.objects.select_for_update().filter(user_id=user_id).first()


def _lock_dl_record(user_id: int) -> Optional[DriverVerification]:
    return DriverVerification.objects.select_for_update().filter(user_id=user_id).first()


def _assert_can_submit(profile: Optional[UserProfile], dl_record: Optional[DriverVerification]) -> None:
    """Guard shared by phase 1 and phase 3. Must run while the rows are locked."""
    if profile is None or profile.active_role != UserProfile.DRIVER:
        raise ValueError("Not a driver")

    if profile.onboarding_status not in [
        UserProfile.AWAITING_DL,
        UserProfile.PENDING_VERIFICATION  # Allow resubmit
    ]:
        raise ValueError("Invalid state for DL submission")

    if dl_record is not None:
        if dl_record.dl_verification_status == 'verified':
            raise ValueError("DL already verified")
        if dl_record.attempt_count >= settings.DL_MAX_ATTEMPTS:
            _log_event(
                logging.WARNING, 'onboarding.dl.attempts_exhausted',
                user_id=profile.user_id, attempt_count=dl_record.attempt_count,
            )
            raise ValueError("Maximum DL submission attempts exceeded")


def _call_provider(user_id: int, normalized_dl: str) -> tuple:
    """Phase 2: no transaction is open. Returns (result, timed_out)."""
    adapter_name = str(getattr(settings, 'DL_ADAPTER_CLASS', '')).rsplit('.', 1)[-1]
    try:
        result = get_dl_adapter().submit(normalized_dl, user_id)
    except TimeoutError:
        # Timeout: treat as pending
        return DLVerificationResult(status='pending'), True
    except Exception as exc:  # any provider/adapter/config failure must become a 422, never a 500
        _log_event(
            logging.ERROR, 'onboarding.dl.provider_error',
            user_id=user_id, adapter=adapter_name, error_type=type(exc).__name__,
        )
        raise DLProviderError() from None

    reference_id = getattr(result, 'reference_id', None)
    valid = (
        isinstance(result, DLVerificationResult)
        and result.status in _ALLOWED_RESULT_STATUSES
        and (reference_id is None or (isinstance(reference_id, str) and len(reference_id) <= 100))
    )
    if not valid:
        _log_event(
            logging.ERROR, 'onboarding.dl.provider_error',
            user_id=user_id, adapter=adapter_name, error_type='InvalidResult',
        )
        raise DLProviderError()
    return result, False


def submit_dl_verification(user: User, dl_number: str) -> Dict[str, Any]:
    """Submit DL for verification.

    Args:
        user: Authenticated user
        dl_number: Raw DL number from user input

    Returns:
        Dict with status, dl_verification_status, onboarding_status, etc.

    Raises:
        ValueError: If user not in correct state or max attempts exceeded
        DLProviderError: If the provider call failed (no attempt is consumed)
    """
    # Phase 1: guard (short transaction, nothing written)
    with transaction.atomic():
        profile = _lock_profile(user.id)
        dl_record = _lock_dl_record(user.id)
        _assert_can_submit(profile, dl_record)

    # Normalize and encrypt (no DB, before the provider is called so a missing key fails early)
    normalized_dl = normalize_dl_number(dl_number)
    encrypted_dl = encrypt_dl_number(normalized_dl)
    last_four = get_dl_last_four(normalized_dl)

    # Phase 2: provider call, no transaction open
    result, timed_out = _call_provider(user.id, normalized_dl)
    rejection_reason = None
    if result.status == 'rejected':
        rejection_reason = sanitise_reason(result.rejection_reason) or None

    # Phase 3: re-lock, re-validate (attempts counted under the lock), decide and persist
    with transaction.atomic():
        profile = _lock_profile(user.id)
        dl_record = _lock_dl_record(user.id)
        _assert_can_submit(profile, dl_record)

        if dl_record is None:
            dl_record = DriverVerification(user=user)

        now = timezone.now()
        dl_record.dl_number = encrypted_dl
        dl_record.dl_number_display = last_four
        dl_record.dl_verification_status = result.status
        dl_record.dl_verification_ref = result.reference_id
        dl_record.dl_submitted_at = now
        dl_record.attempt_count += 1

        if result.status == 'verified':
            dl_record.dl_verified_at = now
            profile.onboarding_status = UserProfile.AWAITING_VEHICLE
        elif result.status == 'pending':
            profile.onboarding_status = UserProfile.PENDING_VERIFICATION
        elif result.status == 'rejected':
            dl_record.dl_rejection_reason = rejection_reason
            # Status remains AWAITING_DL or PENDING_VERIFICATION

        dl_record.save()
        profile.save(update_fields=['onboarding_status', 'updated_at'])

    _log_event(
        logging.INFO, 'onboarding.dl.submitted',
        user_id=user.id, attempt_count=dl_record.attempt_count, dl_status=result.status,
        onboarding_status=profile.onboarding_status, timed_out=timed_out,
    )

    return {
        'dl_verification_status': dl_record.dl_verification_status,
        'onboarding_status': profile.onboarding_status,
        'reference_id': result.reference_id,
        'rejection_reason': rejection_reason if result.status == 'rejected' else None,
    }


def process_webhook_result(reference_id: str, status: str, rejection_reason: str = None) -> bool:
    """Process webhook callback from DL provider (the signature is verified by the caller).

    Idempotent: a verification that is already verified or rejected is left untouched.

    Args:
        reference_id: Provider reference ID
        status: 'verified' or 'rejected'
        rejection_reason: Optional reason if rejected (sanitised before it is stored)

    Returns:
        True if processed successfully

    Raises:
        DLReferenceNotFound: If reference_id is not known (404 dl_reference_not_found)
    """
    found = (
        DriverVerification.objects.filter(dl_verification_ref=reference_id)
        .values('pk', 'user_id').first()
    )
    if found is None:
        _log_event(
            logging.WARNING, 'onboarding.dl.webhook.unknown_reference',
            reference_id=str(reference_id)[:100],
        )
        raise DLReferenceNotFound()

    with transaction.atomic():
        profile = _lock_profile(found['user_id'])
        dl_record = DriverVerification.objects.select_for_update().filter(
            pk=found['pk'], dl_verification_ref=reference_id,
        ).first()
        if dl_record is None:
            # The reference changed between the lookup and the lock (user resubmitted).
            raise DLReferenceNotFound()

        # Idempotency check
        if dl_record.dl_verification_status in ['verified', 'rejected']:
            outcome = 'duplicate'
        else:
            dl_record.dl_verification_status = status
            outcome = status

            if status == 'verified':
                dl_record.dl_verified_at = timezone.now()
                # Only advance a user who is waiting on this DL; a user who switched to passenger in the
                # meantime is complete and must not be gated out.
                if profile is not None and profile.onboarding_status == UserProfile.PENDING_VERIFICATION:
                    profile.onboarding_status = UserProfile.AWAITING_VEHICLE
                    profile.save(update_fields=['onboarding_status', 'updated_at'])
            elif status == 'rejected':
                dl_record.dl_rejection_reason = sanitise_reason(rejection_reason) or None
                # User remains in PENDING_VERIFICATION, can resubmit

            dl_record.save()

    _log_event(
        logging.INFO, 'onboarding.dl.webhook.processed',
        reference_id=str(reference_id)[:100], outcome=outcome,
    )
    return True
