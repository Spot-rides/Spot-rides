"""Data models for the user onboarding flow (FEAT-002).

- ``UserProfile``: onboarding state machine, active role, and personal profile.
- ``DriverVerification``: DL submission state, encrypted DL number, and verification status.
- ``Vehicle``: driver vehicle, with optional RC verification columns (flag-gated).
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
    AWAITING_VEHICLE = 'awaiting_vehicle'
    PENDING_RC_VERIFICATION = 'pending_rc_verification'
    COMPLETE = 'complete'
    ONBOARDING_STATUS_CHOICES = [
        (NOT_STARTED, 'Not Started'),
        (ROLE_SELECTED, 'Role Selected'),
        (AWAITING_DL, 'Awaiting DL'),
        (PENDING_VERIFICATION, 'Pending Verification'),
        (AWAITING_VEHICLE, 'Awaiting Vehicle'),
        (PENDING_RC_VERIFICATION, 'Pending RC Verification'),
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
    vehicle_step_exempt = models.BooleanField(
        default=False,
        db_default=False,
        help_text=(
            'Driver grandfathered from before the vehicle step existed (FR-43). Set ONLY by the '
            'data migration; never set by application code or admin.'
        ),
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


class Vehicle(models.Model):
    """Vehicle registered by a driver during onboarding.

    Uses ForeignKey (not OneToOneField) to support future multi-vehicle.
    v1 enforces max 1 active vehicle per driver at the application layer.
    Registration numbers are stored plaintext (publicly visible on vehicles).
    """

    class VehicleType(models.TextChoices):
        CAR = 'CAR', 'Car'
        SUV = 'SUV', 'SUV'
        HATCHBACK = 'HATCHBACK', 'Hatchback'
        SEDAN = 'SEDAN', 'Sedan'
        AUTO_RICKSHAW = 'AUTO_RICKSHAW', 'Auto Rickshaw'
        BIKE = 'BIKE', 'Bike'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vehicles'
    )
    registration_number = models.CharField(max_length=15)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # RC verification (all NULL / 0 when RC_VERIFICATION_ENABLED is off)
    RC_PENDING = 'pending'
    RC_VERIFIED = 'verified'
    RC_REJECTED = 'rejected'
    RC_STATUS_CHOICES = [
        (RC_PENDING, 'Pending'),
        (RC_VERIFIED, 'Verified'),
        (RC_REJECTED, 'Rejected'),
    ]

    NAME_MATCH = 'match'
    NAME_PARTIAL = 'partial'
    NAME_MISMATCH = 'mismatch'
    NAME_NOT_CHECKED = 'not_checked'
    NAME_MATCH_CHOICES = [
        (NAME_MATCH, 'Match'),
        (NAME_PARTIAL, 'Partial'),
        (NAME_MISMATCH, 'Mismatch'),
        (NAME_NOT_CHECKED, 'Not checked'),
    ]

    rc_verification_status = models.CharField(
        max_length=20, choices=RC_STATUS_CHOICES, null=True, blank=True,
        help_text='NULL = legacy / self-declared (flag off)',
    )
    rc_verification_ref = models.CharField(max_length=100, null=True, blank=True)
    rc_submitted_at = models.DateTimeField(null=True, blank=True)
    rc_verified_at = models.DateTimeField(null=True, blank=True)
    rc_rejection_reason = models.TextField(null=True, blank=True)
    rc_attempt_count = models.PositiveSmallIntegerField(default=0, db_default=0)
    rc_owner_name = models.CharField(
        max_length=100, null=True, blank=True,
        help_text='Third-party PII. Staff review only; never expose to drivers or logs.',
    )
    rc_name_match = models.CharField(
        max_length=15, choices=NAME_MATCH_CHOICES, null=True, blank=True,
    )
    rc_vehicle_class = models.CharField(max_length=50, null=True, blank=True)
    rc_fuel_type = models.CharField(max_length=30, null=True, blank=True)
    rc_fitness_valid_upto = models.DateField(null=True, blank=True)
    rc_insurance_valid_upto = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'vehicle'
        verbose_name_plural = 'vehicles'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['registration_number'], name='idx_vehicle_regno'),
            models.Index(fields=['rc_verification_status'], name='idx_vehicle_rc_status'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['rc_verification_ref'],
                condition=models.Q(rc_verification_ref__isnull=False),
                name='uq_vehicle_rc_verification_ref',
            ),
        ]
        permissions = [
            ('review_rc', 'Can review and resolve RC verification'),
        ]

    def __str__(self):
        return f"{self.registration_number} ({self.get_vehicle_type_display()})"
