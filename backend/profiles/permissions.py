"""DRF permission classes for the user onboarding flow (FEAT-002).

- ``IsOnboardingComplete``: gate for all protected non-onboarding endpoints
- ``IsDriverRole``: gate for driver-specific endpoints
- ``IsDriverVerified``: gate for driver-facing actions (posting rides, etc)
"""

from rest_framework import permissions

from profiles.models import UserProfile


class IsOnboardingComplete(permissions.BasePermission):
    """Permission that requires user to have completed onboarding.

    Views that should be accessible pre-onboarding must explicitly
    override permission_classes to opt out.

    This permission is added to DEFAULT_PERMISSION_CLASSES in settings.py,
    making it a global gate for all authenticated endpoints.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has profile and onboarding is complete
        if hasattr(request.user, 'profile'):
            return request.user.profile.onboarding_status == UserProfile.COMPLETE

        # No profile yet = not complete
        return False


class IsDriverRole(permissions.BasePermission):
    """Permission that requires user to have active_role = DRIVER.

    This is used to gate driver-specific endpoints like DL submission.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if hasattr(request.user, 'profile'):
            return request.user.profile.active_role == UserProfile.DRIVER

        return False


class IsDriverVerified(permissions.BasePermission):
    """Permission that requires user to have verified DL.

    This is the gate for driver-facing actions (posting rides, etc).
    Requires BOTH active_role=DRIVER AND dl_verification_status=VERIFIED.

    This is a stronger check than IsDriverRole: having active_role=driver alone
    is not sufficient to perform driver actions.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Must be a driver
        if not hasattr(request.user, 'profile'):
            return False
        if request.user.profile.active_role != UserProfile.DRIVER:
            return False

        # Must have verified DL
        if not hasattr(request.user, 'driver_verification'):
            return False

        return request.user.driver_verification.dl_verification_status == 'verified'
