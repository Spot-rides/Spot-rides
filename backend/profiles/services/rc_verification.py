"""Vehicle RC verification service (flag-on path).

Imported lazily by ``onboarding.register_vehicle`` only when ``RC_VERIFICATION_ENABLED`` is on.
Lock order is always UserProfile then Vehicle. The provider call is made with no transaction
open. No owner name, raw provider payload, free-text reason or adapter message is ever logged.
"""

import logging
from typing import Optional, Tuple

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from profiles.adapters import RCVerificationResult, get_rc_adapter
from profiles.exceptions import (
    AlreadyProcessed,
    DLNotVerified,
    MaxRCAttemptsExceeded,
    NotADriver,
    RCAlreadyVerified,
    RCProviderError,
    RCReferenceNotFound,
    RCReviewStateError,
    RCVerificationPending,
    RCVerificationRejected,
    VehicleAlreadyRegistered,
)
from profiles.models import DriverVerification, UserProfile, Vehicle
from profiles.services.onboarding import compute_next_step, get_or_create_profile
from profiles.services.rc_matching import (
    NAME_NOT_CHECKED,
    OUTCOME_PENDING,
    OUTCOME_REJECTED,
    OUTCOME_VERIFIED,
    check_vehicle_class,
    classify_owner_match,
    decide_rc_outcome,
)
from profiles.services.sanitise import sanitise_reason

logger = logging.getLogger('profiles')

_LOG_FIELDS = frozenset({
    'user_id', 'vehicle_id', 'attempt_count', 'rc_status', 'outcome', 'cause', 'name_match',
    'onboarding_status', 'reference_id', 'adapter', 'error_type', 'duplicate_count',
    'staff_user_id', 'timed_out',
})
_ALLOWED_RESULT_STATUSES = ('verified', 'pending', 'rejected')


def _log_event(level: int, event: str, **fields) -> None:
    """Single logging entry point: fields outside the allow-list are dropped."""
    logger.log(level, event, extra={k: v for k, v in fields.items() if k in _LOG_FIELDS})


def _clear_owner_data(vehicle: Vehicle) -> None:
    """Single purge hook for the third-party owner name.

    Called on every terminal transition: sync/webhook verified or rejected and staff
    approve/reject. Only a vehicle still pending review keeps the name (staff need it to decide).
    """
    vehicle.rc_owner_name = None


def _lock_profile(user_id: int) -> Optional[UserProfile]:
    return UserProfile.objects.select_for_update().filter(user_id=user_id).first()


def _lock_active_vehicle(user_id: int) -> Optional[Vehicle]:
    return (
        Vehicle.objects.select_for_update()
        .filter(user_id=user_id, is_active=True)
        .order_by('-id')
        .first()
    )


def _attempts_remaining(vehicle: Optional[Vehicle]) -> int:
    used = vehicle.rc_attempt_count if vehicle else 0
    return max(0, settings.RC_MAX_ATTEMPTS - used)


def _assert_can_submit(user, profile: Optional[UserProfile], vehicle: Optional[Vehicle]) -> None:
    if profile is None or profile.active_role != UserProfile.DRIVER:
        raise NotADriver()

    status = profile.onboarding_status
    if status == UserProfile.PENDING_RC_VERIFICATION:
        raise RCVerificationPending()
    if status == UserProfile.COMPLETE:
        if vehicle is not None and vehicle.rc_verification_status == Vehicle.RC_VERIFIED:
            raise RCAlreadyVerified()
        raise VehicleAlreadyRegistered()
    if status != UserProfile.AWAITING_VEHICLE:
        raise DLNotVerified()

    dl_status = (
        DriverVerification.objects.filter(user_id=user.id)
        .values_list('dl_verification_status', flat=True)
        .first()
    )
    if dl_status != DriverVerification.VERIFIED:
        raise DLNotVerified()

    if vehicle is not None:
        if vehicle.rc_verification_status == Vehicle.RC_PENDING:
            raise RCVerificationPending()
        if vehicle.rc_verification_status == Vehicle.RC_VERIFIED:
            raise RCAlreadyVerified()
        # rejected or NULL: resubmission reuses the row

    if _attempts_remaining(vehicle) == 0:
        _log_event(
            logging.WARNING, 'onboarding.rc.attempts_exhausted',
            user_id=user.id, vehicle_id=vehicle.id if vehicle else None,
            attempt_count=vehicle.rc_attempt_count if vehicle else 0,
        )
        raise MaxRCAttemptsExceeded()


def _call_provider(user, registration_number: str) -> Tuple[RCVerificationResult, bool]:
    """Phase 2: no transaction is open. Returns (result, timed_out)."""
    adapter_name = str(settings.RC_ADAPTER_CLASS).rsplit('.', 1)[-1]
    try:
        result = get_rc_adapter().verify(registration_number, user.id)
    except TimeoutError:
        return RCVerificationResult(status='pending'), True
    except Exception as exc:  # any provider/adapter failure must become a 422, never a 500
        _log_event(
            logging.ERROR, 'onboarding.rc.provider_error',
            user_id=user.id, adapter=adapter_name, error_type=type(exc).__name__,
        )
        raise RCProviderError() from None

    reference_id = getattr(result, 'reference_id', None)
    valid = (
        isinstance(result, RCVerificationResult)
        and result.status in _ALLOWED_RESULT_STATUSES
        and (reference_id is None or (isinstance(reference_id, str) and len(reference_id) <= 100))
    )
    if not valid:
        _log_event(
            logging.ERROR, 'onboarding.rc.provider_error',
            user_id=user.id, adapter=adapter_name, error_type='InvalidResult',
        )
        raise RCProviderError()
    return result, False


def _clip(value: Optional[str], width: int) -> Optional[str]:
    return value[:width] if isinstance(value, str) else None


def _save_vehicle(vehicle: Vehicle, user_id: int) -> None:
    """Save, tolerating a provider that reuses a reference_id (unique constraint)."""
    try:
        with transaction.atomic():
            vehicle.save()
    except IntegrityError:
        if vehicle.rc_verification_ref is None:
            raise
        vehicle.rc_verification_ref = None
        vehicle.save()
        _log_event(logging.ERROR, 'onboarding.rc.ref_collision', user_id=user_id, vehicle_id=vehicle.pk)


def register_vehicle_with_rc(user, registration_number: str, vehicle_type: str):
    """Flag-on vehicle registration. Returns (profile, vehicle); raises RCVerificationRejected on rejection."""
    # Phase 1: guard (short transaction, nothing written)
    with transaction.atomic():
        profile = _lock_profile(user.id)
        vehicle = _lock_active_vehicle(user.id)
        _assert_can_submit(user, profile, vehicle)

    # Phase 2: provider call, no transaction open
    result, timed_out = _call_provider(user, registration_number)

    # Phase 3: decide and persist (re-lock and re-validate)
    rejected_reason = None
    with transaction.atomic():
        profile = _lock_profile(user.id)
        vehicle = _lock_active_vehicle(user.id)
        _assert_can_submit(user, profile, vehicle)

        name_match = classify_owner_match(profile.first_name, profile.last_name, result.owner_name)
        class_ok = check_vehicle_class(vehicle_type, result.vehicle_class)
        decision = decide_rc_outcome(result, name_match, class_ok)
        now = timezone.now()

        if vehicle is None:
            vehicle = Vehicle(user=user, is_active=True, rc_attempt_count=0)
        vehicle.registration_number = registration_number
        vehicle.vehicle_type = vehicle_type.upper()
        vehicle.rc_attempt_count += 1
        vehicle.rc_submitted_at = now
        vehicle.rc_verification_ref = result.reference_id
        vehicle.rc_vehicle_class = _clip(result.vehicle_class, 50)
        vehicle.rc_fuel_type = _clip(result.fuel_type, 30)
        vehicle.rc_fitness_valid_upto = result.fitness_valid_upto
        vehicle.rc_insurance_valid_upto = result.insurance_valid_upto
        vehicle.rc_name_match = name_match
        vehicle.rc_verified_at = None
        vehicle.rc_rejection_reason = None

        if decision.outcome == OUTCOME_VERIFIED:
            vehicle.rc_verification_status = Vehicle.RC_VERIFIED
            vehicle.rc_verified_at = now
            _clear_owner_data(vehicle)
            profile.onboarding_status = UserProfile.COMPLETE
        elif decision.outcome == OUTCOME_PENDING:
            vehicle.rc_verification_status = Vehicle.RC_PENDING
            if name_match != Vehicle.NAME_MATCH and result.owner_name:
                vehicle.rc_owner_name = _clip(result.owner_name, 100)
            else:
                _clear_owner_data(vehicle)
            profile.onboarding_status = UserProfile.PENDING_RC_VERIFICATION
        else:
            vehicle.rc_verification_status = Vehicle.RC_REJECTED
            rejected_reason = sanitise_reason(decision.reason, redact=[result.owner_name])
            vehicle.rc_rejection_reason = rejected_reason
            _clear_owner_data(vehicle)
            profile.onboarding_status = UserProfile.AWAITING_VEHICLE

        _save_vehicle(vehicle, user.id)
        profile.save(update_fields=['onboarding_status', 'updated_at'])

    # After commit
    _log_event(
        logging.INFO, 'onboarding.rc.submitted',
        user_id=user.id, vehicle_id=vehicle.pk, attempt_count=vehicle.rc_attempt_count,
    )
    if decision.outcome == OUTCOME_VERIFIED:
        _log_event(
            logging.INFO, 'onboarding.rc.verified',
            user_id=user.id, vehicle_id=vehicle.pk, name_match=name_match,
            reference_id=vehicle.rc_verification_ref,
        )
    elif decision.outcome == OUTCOME_PENDING:
        if timed_out:
            cause = 'timeout'
        elif result.status == 'pending':
            cause = 'provider_pending'
        else:
            cause = 'name_review'
        _log_event(
            logging.INFO, 'onboarding.rc.pending',
            user_id=user.id, vehicle_id=vehicle.pk, cause=cause, name_match=name_match,
        )
    else:
        _log_event(
            logging.INFO, 'onboarding.rc.rejected',
            user_id=user.id, vehicle_id=vehicle.pk,
            cause='provider' if result.status == 'rejected' else 'class_conflict',
        )

    duplicate_count = (
        Vehicle.objects.filter(registration_number=registration_number)
        .exclude(user_id=user.id)
        .values('user_id').distinct().count()
    )
    if duplicate_count:
        _log_event(
            logging.WARNING, 'onboarding.vehicle.duplicate_registration',
            user_id=user.id, duplicate_count=duplicate_count,
        )

    if decision.outcome == OUTCOME_REJECTED:
        # Raised only after the transaction committed so the rejection and attempt count persist.
        raise RCVerificationRejected(
            detail=rejected_reason or None,
            extra={
                'onboarding_status': profile.onboarding_status,
                'next_step': compute_next_step(profile),
                'rc_verification_status': Vehicle.RC_REJECTED,
                'rc_attempts_remaining': _attempts_remaining(vehicle),
            },
        )

    return profile, vehicle


def _apply_provider_fields(vehicle: Vehicle, result: RCVerificationResult) -> None:
    if result.vehicle_class:
        vehicle.rc_vehicle_class = _clip(result.vehicle_class, 50)
    if result.fuel_type:
        vehicle.rc_fuel_type = _clip(result.fuel_type, 30)
    if result.fitness_valid_upto:
        vehicle.rc_fitness_valid_upto = result.fitness_valid_upto
    if result.insurance_valid_upto:
        vehicle.rc_insurance_valid_upto = result.insurance_valid_upto


def _complete_if(profile: Optional[UserProfile], *from_statuses: str) -> None:
    """Move the profile to COMPLETE only from the given statuses (a passenger is never touched)."""
    if profile is not None and profile.onboarding_status in from_statuses:
        profile.onboarding_status = UserProfile.COMPLETE
        profile.save(update_fields=['onboarding_status', 'updated_at'])


def _reject_profile(profile: Optional[UserProfile]) -> None:
    if profile is not None and profile.onboarding_status == UserProfile.PENDING_RC_VERIFICATION:
        profile.onboarding_status = UserProfile.AWAITING_VEHICLE
        profile.save(update_fields=['onboarding_status', 'updated_at'])


def process_rc_webhook(result: RCVerificationResult) -> None:
    """Apply an asynchronous provider result. Idempotent: a terminal vehicle raises AlreadyProcessed."""
    reference_id = result.reference_id
    found = Vehicle.objects.filter(rc_verification_ref=reference_id).values('pk', 'user_id').first()
    if found is None:
        _log_event(logging.WARNING, 'onboarding.rc.webhook.unknown_reference', reference_id=reference_id)
        raise RCReferenceNotFound()

    with transaction.atomic():
        profile = _lock_profile(found['user_id'])
        vehicle = Vehicle.objects.select_for_update().filter(
            pk=found['pk'], rc_verification_ref=reference_id,
        ).first()
        if vehicle is None:
            raise RCReferenceNotFound()
        if vehicle.rc_verification_status in (Vehicle.RC_VERIFIED, Vehicle.RC_REJECTED):
            _log_event(logging.WARNING, 'onboarding.rc.webhook.duplicate', reference_id=reference_id)
            raise AlreadyProcessed()

        if result.status == 'rejected':
            outcome = OUTCOME_REJECTED
            reason = result.rejection_reason
        else:
            if profile is not None:
                name_match = classify_owner_match(profile.first_name, profile.last_name, result.owner_name)
            else:
                name_match = NAME_NOT_CHECKED
            class_ok = check_vehicle_class(
                vehicle.vehicle_type, result.vehicle_class or vehicle.rc_vehicle_class,
            )
            decision = decide_rc_outcome(result, name_match, class_ok)
            outcome, reason = decision.outcome, decision.reason
            if result.owner_name or vehicle.rc_name_match is None:
                vehicle.rc_name_match = name_match

        now = timezone.now()
        if outcome == OUTCOME_VERIFIED:
            _apply_provider_fields(vehicle, result)
            vehicle.rc_verification_status = Vehicle.RC_VERIFIED
            vehicle.rc_verified_at = now
            vehicle.rc_rejection_reason = None
            _clear_owner_data(vehicle)
            _complete_if(profile, UserProfile.PENDING_RC_VERIFICATION)
        elif outcome == OUTCOME_REJECTED:
            vehicle.rc_verification_status = Vehicle.RC_REJECTED
            vehicle.rc_rejection_reason = sanitise_reason(
                reason or None, redact=[result.owner_name, vehicle.rc_owner_name],
            ) or None
            _clear_owner_data(vehicle)
            _reject_profile(profile)
        else:
            _apply_provider_fields(vehicle, result)
            if result.owner_name and vehicle.rc_name_match != Vehicle.NAME_MATCH:
                vehicle.rc_owner_name = _clip(result.owner_name, 100)

        vehicle.save()
        vehicle_id = vehicle.pk

    _log_event(
        logging.INFO, 'onboarding.rc.webhook.processed',
        reference_id=reference_id, outcome=outcome, vehicle_id=vehicle_id,
    )


def _lock_for_review(vehicle_id: int) -> Tuple[Optional[UserProfile], Vehicle]:
    found = Vehicle.objects.filter(pk=vehicle_id).values('user_id').first()
    if found is None:
        raise RCReviewStateError(detail='Vehicle not found.')
    profile = _lock_profile(found['user_id'])
    vehicle = Vehicle.objects.select_for_update().filter(pk=vehicle_id).first()
    if vehicle is None:
        raise RCReviewStateError(detail='Vehicle not found.')
    return profile, vehicle


def resolve_rc_review(vehicle_id: int, *, approve: bool, reason: Optional[str], staff_user) -> Vehicle:
    """Staff approve (pending or rejected vehicle) or reject (pending vehicle, reason required).

    Works regardless of the flag so staff can recover drivers after a rollback.
    """
    with transaction.atomic():
        profile, vehicle = _lock_for_review(vehicle_id)
        current = vehicle.rc_verification_status

        if approve:
            if current not in (Vehicle.RC_PENDING, Vehicle.RC_REJECTED):
                raise RCReviewStateError()
            vehicle.rc_verification_status = Vehicle.RC_VERIFIED
            vehicle.rc_verified_at = timezone.now()
            vehicle.rc_rejection_reason = None
            _clear_owner_data(vehicle)
            _complete_if(profile, UserProfile.PENDING_RC_VERIFICATION, UserProfile.AWAITING_VEHICLE)
        else:
            if current != Vehicle.RC_PENDING:
                raise RCReviewStateError()
            clean = sanitise_reason(reason, redact=[vehicle.rc_owner_name])
            if not clean:
                raise RCReviewStateError(detail='A reason is required to reject.')
            vehicle.rc_verification_status = Vehicle.RC_REJECTED
            vehicle.rc_rejection_reason = clean
            _clear_owner_data(vehicle)
            _reject_profile(profile)

        vehicle.save()

    _log_event(
        logging.INFO,
        'onboarding.rc.review.approved' if approve else 'onboarding.rc.review.rejected',
        vehicle_id=vehicle.pk, staff_user_id=getattr(staff_user, 'id', None),
    )
    return vehicle


def reset_rc_attempts(vehicle_id: int, *, staff_user) -> Vehicle:
    with transaction.atomic():
        _, vehicle = _lock_for_review(vehicle_id)
        vehicle.rc_attempt_count = 0
        vehicle.save(update_fields=['rc_attempt_count', 'updated_at'])

    _log_event(
        logging.INFO, 'onboarding.rc.review.attempts_reset',
        vehicle_id=vehicle.pk, staff_user_id=getattr(staff_user, 'id', None),
    )
    return vehicle


def get_vehicle_status(user) -> dict:
    """Driver-facing vehicle/RC status. Never includes owner data or provider fields."""
    profile = get_or_create_profile(user)
    vehicle = user.vehicles.filter(is_active=True).order_by('-id').first()
    enabled = settings.RC_VERIFICATION_ENABLED

    rc_status = vehicle.rc_verification_status if (enabled and vehicle) else None
    return {
        'onboarding_status': profile.onboarding_status,
        'next_step': compute_next_step(profile),
        'rc_verification_status': rc_status,
        'rejection_reason': vehicle.rc_rejection_reason if rc_status == Vehicle.RC_REJECTED else None,
        'registration_number': vehicle.registration_number if vehicle else None,
        'vehicle_type': vehicle.vehicle_type if vehicle else None,
        'rc_attempts_remaining': _attempts_remaining(vehicle) if enabled else None,
    }


def derive_driver_status(profile: UserProfile, vehicle: Optional[Vehicle]) -> str:
    """Status for a driver with a verified DL, from the newest active vehicle (flag on).

    A driver with no vehicle row stays COMPLETE only if explicitly marked
    ``vehicle_step_exempt`` (grandfathered by migration 0004, FR-43); otherwise they must
    register a vehicle (AWAITING_VEHICLE). The marker is never set by application code.
    """
    if vehicle is None:
        if profile.vehicle_step_exempt:
            return UserProfile.COMPLETE
        return UserProfile.AWAITING_VEHICLE
    if vehicle.rc_verification_status in (None, Vehicle.RC_VERIFIED):
        return UserProfile.COMPLETE
    if vehicle.rc_verification_status == Vehicle.RC_PENDING:
        return UserProfile.PENDING_RC_VERIFICATION
    return UserProfile.AWAITING_VEHICLE
