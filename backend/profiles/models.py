"""Data models for the user onboarding flow (FEAT-002).

- ``UserProfile``: onboarding state machine, active role, and personal profile.
- ``DriverVerification``: DL submission state, encrypted DL number, and verification status.
"""

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """User profile holding onboarding state and personal details.

    The ``active_role`` field is the single source of truth for a user's current role.
    It can be freely switched after onboarding is complete via the role-switch endpoint.
    """

    # Role choices
    DRIVER = 'driver'
    PASSENGER = 'passenger'
    ROLE_CHOICES = [
        (DRIVER, 'Driver'),
        (PASSENGER, 'Passenger'),
    ]

    # Onboarding status choices
    NOT_STARTED = 'not_started'
    ROLE_SELECTED = 'role_selected'
    AWAITING_DL = 'awaiting_dl'
    PENDING_VERIFICATION = 'pending_verification'
    COMPLETE = 'complete'
    ONBOARDING_STATUS_CHOICES = [
        (NOT_STARTED, 'Not Started'),
        (ROLE_SELECTED, 'Role Selected'),
        (AWAITING_DL, 'Awaiting DL'),
        (PENDING_VERIFICATION, 'Pending Verification'),
        (COMPLETE, 'Complete'),
    ]

    # Gender choices
    MALE = 'male'
    FEMALE = 'female'
    OTHER = 'other'
    PREFER_NOT_TO_SAY = 'prefer_not_to_say'
    GENDER_CHOICES = [
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (OTHER, 'Other'),
        (PREFER_NOT_TO_SAY, 'Prefer not to say'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    active_role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        null=True,
        blank=True
    )
    first_name = models.CharField(max_length=50, null=True, blank=True)
    last_name = models.CharField(max_length=50, null=True, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        null=True,
        blank=True
    )
    onboarding_status = models.CharField(
        max_length=30,
        choices=ONBOARDING_STATUS_CHOICES,
        default=NOT_STARTED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'user profile'
        verbose_name_plural = 'user profiles'
        indexes = [
            models.Index(fields=['onboarding_status'], name='idx_profile_status'),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.onboarding_status}"


class DriverVerification(models.Model):
    """Driver licence verification state and encrypted DL number.

    The ``dl_number`` field stores the Fernet-encrypted ciphertext.
    The ``dl_number_display`` field stores the last 4 characters in plaintext for display/audit.
    """

    # DL verification status choices
    PENDING = 'pending'
    VERIFIED = 'verified'
    REJECTED = 'rejected'
    DL_VERIFICATION_STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (VERIFIED, 'Verified'),
        (REJECTED, 'Rejected'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='driver_verification'
    )
    dl_number = models.CharField(
        max_length=256,
        help_text='Fernet-encrypted ciphertext of normalized DL number'
    )
    dl_number_display = models.CharField(
        max_length=4,
        help_text='Last 4 characters of DL number in plaintext'
    )
    dl_verification_status = models.CharField(
        max_length=20,
        choices=DL_VERIFICATION_STATUS_CHOICES,
        null=True,
        blank=True
    )
    dl_verification_ref = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text='Provider-issued reference ID for async lookup'
    )
    dl_submitted_at = models.DateTimeField(null=True, blank=True)
    dl_verified_at = models.DateTimeField(null=True, blank=True)
    dl_rejection_reason = models.TextField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'driver verification'
        verbose_name_plural = 'driver verifications'
        indexes = [
            models.Index(fields=['dl_verification_status'], name='idx_dv_status'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['dl_verification_ref'],
                condition=models.Q(dl_verification_ref__isnull=False),
                name='uq_dl_verification_ref'
            ),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - DL {self.dl_verification_status}"
