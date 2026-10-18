"""Custom permissions for API-wide controls.

- ``ConditionalOnboardingGate`` — globally enforces onboarding completion
  when the feature flag ``ONBOARDING_GATE_ENABLED`` is True (FEAT-002).
"""

from rest_framework import permissions
from django.conf import settings


class ConditionalOnboardingGate(permissions.BasePermission):
    """
    Permission that conditionally requires onboarding completion.

    Only enforces if ONBOARDING_GATE_ENABLED is True.
    Views can explicitly opt out by overriding permission_classes.
    """

    def has_permission(self, request, view):
        # Feature flag check
        if not settings.ONBOARDING_GATE_ENABLED:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        # Import here to avoid circular dependency
        from profiles.exceptions import OnboardingIncomplete
        from profiles.models import UserProfile
        from profiles.services.onboarding import compute_next_step

        profile = getattr(request.user, 'profile', None)
        if profile is not None and profile.onboarding_status == UserProfile.COMPLETE:
            return True

        # No profile yet is reported as not_started.
        raise OnboardingIncomplete(extra={
            'onboarding_status': profile.onboarding_status if profile else UserProfile.NOT_STARTED,
            'next_step': compute_next_step(profile),
        })
