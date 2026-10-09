"""Onboarding service layer.

Business logic for user profile creation, role selection, profile details, and role switching.
All state-changing functions use database transactions.
"""

from typing import Optional
from django.contrib.auth import get_user_model
from django.db import transaction
from profiles.models import UserProfile

User = get_user_model()


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


@transaction.atomic
def switch_role(user: User, new_role: str) -> UserProfile:
    """Switch active role after onboarding complete.

    Args:
        user: Authenticated user
        new_role: 'driver' or 'passenger'

    Returns:
        Updated UserProfile

    Raises:
        ValueError: If onboarding not complete or switching to driver without DL
    """
    profile = get_or_create_profile(user)

    if profile.onboarding_status != UserProfile.COMPLETE:
        # Special case: allow switch if pending_verification (user can go back to passenger)
        if profile.onboarding_status != UserProfile.PENDING_VERIFICATION:
            raise ValueError("Onboarding not complete")

    if new_role == profile.active_role:
        # No-op, already in that role
        return profile

    # Switching to passenger: always allowed
    if new_role == UserProfile.PASSENGER:
        profile.active_role = new_role
        profile.save()
        return profile

    # Switching to driver: check DL status
    if new_role == UserProfile.DRIVER:
        if not hasattr(user, 'driver_verification'):
            raise ValueError("DL verification required")

        dl_status = user.driver_verification.dl_verification_status

        if dl_status == 'verified':
            profile.active_role = new_role
            profile.onboarding_status = UserProfile.COMPLETE
        elif dl_status == 'pending':
            profile.active_role = new_role
            profile.onboarding_status = UserProfile.PENDING_VERIFICATION
        else:  # None or rejected
            raise ValueError("DL verification required")

        profile.save()
        return profile

    raise ValueError("Invalid role")
