"""Onboarding service layer.

Business logic for user profile creation, role selection, profile details, and role switching.
All state-changing functions use database transactions.
"""

from typing import Optional
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from profiles.models import UserProfile

User = get_user_model()

NEXT_STEP_BY_STATUS = {
    UserProfile.NOT_STARTED: 'role_selection',
    UserProfile.ROLE_SELECTED: 'profile',
    UserProfile.AWAITING_DL: 'dl_submission',
    UserProfile.PENDING_VERIFICATION: 'awaiting_verification',
    UserProfile.AWAITING_VEHICLE: 'vehicle_registration',
    UserProfile.PENDING_RC_VERIFICATION: 'awaiting_rc_verification',
    UserProfile.COMPLETE: 'none',
}


def next_step_for_status(onboarding_status: str) -> str:
    """Single source of truth for the client's next_step."""
    return NEXT_STEP_BY_STATUS.get(onboarding_status, 'none')


def compute_next_step(profile: Optional[UserProfile]) -> str:
    """next_step for a profile; a missing profile is reported as not_started."""
    if profile is None:
        return next_step_for_status(UserProfile.NOT_STARTED)
    return next_step_for_status(profile.onboarding_status)


def get_or_create_profile(user: User) -> UserProfile:
    """Lazy UserProfile creation.

    Args:
        user: Authenticated user

    Returns:
        UserProfile instance (existing or newly created)
    """
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'onboarding_status': UserProfile.NOT_STARTED}
    )
    return profile


@transaction.atomic
def set_role(user: User, role: str) -> UserProfile:
    """Set user's active role during onboarding.

    Args:
        user: Authenticated user
        role: 'driver' or 'passenger'

    Returns:
        Updated UserProfile

    Raises:
        ValueError: If role already set or invalid state
    """
    profile = get_or_create_profile(user)

    if profile.onboarding_status != UserProfile.NOT_STARTED:
        raise ValueError("Role already set")

    if role not in ['driver', 'passenger']:
        raise ValueError("Invalid role")

    profile.active_role = role
    profile.onboarding_status = UserProfile.ROLE_SELECTED
    profile.save()

    return profile


@transaction.atomic
def set_profile_details(
    user: User,
    first_name: str,
    last_name: str,
    age: int,
    gender: str
) -> UserProfile:
    """Set user profile details during onboarding.

    Args:
        user: Authenticated user
        first_name, last_name, age, gender: Profile fields

    Returns:
        Updated UserProfile

    Raises:
        ValueError: If profile already set or invalid state
    """
    profile = get_or_create_profile(user)

    if profile.onboarding_status != UserProfile.ROLE_SELECTED:
        raise ValueError("Must select role first")

    if profile.first_name is not None:
        raise ValueError("Profile already set")

    profile.first_name = first_name
    profile.last_name = last_name
    profile.age = age
    profile.gender = gender

    # Passenger: complete immediately
    if profile.active_role == UserProfile.PASSENGER:
        profile.onboarding_status = UserProfile.COMPLETE
    # Driver: await DL
    else:
        profile.onboarding_status = UserProfile.AWAITING_DL

    profile.save()
    return profile


def register_vehicle(user: User, registration_number: str, vehicle_type: str):
    """Register a vehicle during driver onboarding.

    With RC_VERIFICATION_ENABLED off (default) this is exactly the self-declared flow.
    The RC module is only imported when the flag is on.

    Returns:
        Tuple of (updated UserProfile, Vehicle)
    """
    if not settings.RC_VERIFICATION_ENABLED:
        return _register_vehicle_self_declared(user, registration_number, vehicle_type)

    from profiles.services import rc_verification
    return rc_verification.register_vehicle_with_rc(user, registration_number, vehicle_type)


@transaction.atomic
def _register_vehicle_self_declared(user: User, registration_number: str, vehicle_type: str):
    """Register a vehicle during driver onboarding.

    Only valid when onboarding_status is AWAITING_VEHICLE.
    Creates Vehicle record and completes onboarding.

    Args:
        user: Authenticated user (must be a driver with verified DL)
        registration_number: Normalized vehicle registration number
        vehicle_type: One of the VehicleType choices (lowercase accepted, stored uppercase)

    Returns:
        Tuple of (updated UserProfile, created Vehicle)

    Raises:
        ValueError: If user not in correct state, DL not verified, or vehicle already registered
    """
    from profiles.models import Vehicle

    profile = get_or_create_profile(user)

    if profile.onboarding_status != UserProfile.AWAITING_VEHICLE:
        raise ValueError("Must complete DL verification before registering a vehicle")

    # Check driver has verified DL
    if not hasattr(user, 'driver_verification') or user.driver_verification.dl_verification_status != 'verified':
        raise ValueError("DL must be verified before registering a vehicle")

    # v1: max 1 active vehicle per driver
    if user.vehicles.filter(is_active=True).exists():
        raise ValueError("Vehicle already registered")

    vehicle = Vehicle.objects.create(
        user=user,
        registration_number=registration_number,
        vehicle_type=vehicle_type.upper(),
        is_active=True
    )

    profile.onboarding_status = UserProfile.COMPLETE
    profile.save()

    return profile, vehicle


class OnboardingNotEligibleForSwitch(ValueError):
    """Role switch rejected because the user's onboarding state is not eligible."""

    def __init__(self, onboarding_status: str):
        super().__init__("Onboarding not complete")
        self.onboarding_status = onboarding_status


class VehicleStepIncomplete(ValueError):
    """Switch to driver rejected: the user is in awaiting_vehicle and must finish the vehicle step
    (or switch to passenger) first. Mapped to 400 invalid_onboarding_state (FR-55)."""


# States from which PATCH /api/profile/role/ is accepted. Every non-complete state is included so
# that a user who started driver setup can always get back to passenger (never locked out).
_SWITCH_ELIGIBLE_STATUSES = (
    UserProfile.COMPLETE,
    UserProfile.AWAITING_DL,
    UserProfile.PENDING_VERIFICATION,
    UserProfile.AWAITING_VEHICLE,
    UserProfile.PENDING_RC_VERIFICATION,
)


def _status_for_verified_driver(profile: UserProfile, vehicle) -> str:
    """Onboarding status for a user with a verified DL switching to driver.

    COMPLETE is only reachable with an active vehicle or the grandfathered
    ``vehicle_step_exempt`` marker (FR-43); otherwise the user must register a vehicle.
    Flag on: RC status of the vehicle decides. Flag off: an active vehicle is enough.
    """
    if settings.RC_VERIFICATION_ENABLED:
        from profiles.services.rc_verification import derive_driver_status
        return derive_driver_status(profile, vehicle)
    if vehicle is not None or profile.vehicle_step_exempt:
        return UserProfile.COMPLETE
    return UserProfile.AWAITING_VEHICLE


@transaction.atomic
def switch_role(user: User, new_role: str) -> UserProfile:
    """Switch active role (FR-22..FR-24, FR-43, FR-52, FR-55).

    Switching to passenger is always possible from any eligible state and completes the user;
    DriverVerification and Vehicle rows are kept.

    Switching to driver:
      - verified DL: status derived from the vehicle (never COMPLETE without a vehicle or the
        grandfathered exemption)
      - pending DL: PENDING_VERIFICATION
      - no DL, or rejected DL: starts driver setup (AWAITING_DL); the normal DL -> vehicle flow follows

    Args:
        user: Authenticated user
        new_role: 'driver' or 'passenger'

    Returns:
        Updated UserProfile

    Raises:
        OnboardingNotEligibleForSwitch: onboarding not started / mid-profile
        VehicleStepIncomplete: switch to driver while in awaiting_vehicle (flag on)
        ValueError: invalid role
    """
    from profiles.models import DriverVerification

    profile = UserProfile.objects.select_for_update().get(pk=get_or_create_profile(user).pk)

    if profile.onboarding_status not in _SWITCH_ELIGIBLE_STATUSES:
        raise OnboardingNotEligibleForSwitch(profile.onboarding_status)

    if new_role == UserProfile.PASSENGER:
        if (profile.active_role, profile.onboarding_status) != (UserProfile.PASSENGER, UserProfile.COMPLETE):
            profile.active_role = UserProfile.PASSENGER
            profile.onboarding_status = UserProfile.COMPLETE
            profile.save()
        return profile

    if new_role != UserProfile.DRIVER:
        raise ValueError("Invalid role")

    if profile.active_role == UserProfile.DRIVER:
        # No-op, already in that role
        return profile

    if profile.onboarding_status == UserProfile.AWAITING_VEHICLE:
        # Only reachable with inconsistent data (a passenger in awaiting_vehicle). Never derive
        # COMPLETE from here; the user finishes the vehicle step or switches to passenger first.
        if settings.RC_VERIFICATION_ENABLED:
            raise VehicleStepIncomplete()
        raise OnboardingNotEligibleForSwitch(profile.onboarding_status)

    dl_status = (
        DriverVerification.objects.filter(user=user)
        .values_list('dl_verification_status', flat=True)
        .first()
    )

    if dl_status == DriverVerification.VERIFIED:
        vehicle = user.vehicles.select_for_update().filter(is_active=True).order_by('-id').first()
        profile.onboarding_status = _status_for_verified_driver(profile, vehicle)
    elif dl_status == DriverVerification.PENDING:
        profile.onboarding_status = UserProfile.PENDING_VERIFICATION
    else:  # no DL row, or rejected: start (or restart) driver setup
        profile.onboarding_status = UserProfile.AWAITING_DL

    profile.active_role = UserProfile.DRIVER
    profile.save()
    return profile
