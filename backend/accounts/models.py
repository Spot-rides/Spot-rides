"""Data models for the OTP phone-authentication feature (FEAT-001).

- ``User``: custom AbstractBaseUser keyed on E.164 ``phone_number`` (COMP-002).
- ``OtpCode``: durable record of an issued OTP; only the HMAC-SHA256 hash of
  the code is stored (COMP-003, NFR-SEC-01).
"""

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import PhoneUserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Phone-number-first user (see ARCH-001 §Data Model / accounts_user).

    Identity: ``phone_number`` in E.164, unique and indexed. Regular users
    have an unusable password (passwordless OTP flow, FR-11); superusers
    retain a real password for admin login.
    """

    phone_number = models.CharField(max_length=16, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    objects = PhoneUserManager()

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'

    def __str__(self):
        return self.phone_number


class OtpCode(models.Model):
    """Persistent OTP record; the plaintext code is never stored.

    See ARCH-001 §Data Model / accounts_otpcode. ``code_hash`` is the
    HMAC-SHA256 hex digest computed with the server-side ``OTP_PEPPER``.
    """

    phone_number = models.CharField(max_length=16)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    invalidated = models.BooleanField(default=False)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=40, blank=True, default='')

    class Meta:
        indexes = [
            models.Index(
                fields=('phone_number', 'invalidated', 'consumed_at'),
                name='idx_otpcode_phone_active',
            ),
            models.Index(fields=('expires_at',), name='idx_otpcode_expires_at'),
        ]
        verbose_name = 'OTP code'
        verbose_name_plural = 'OTP codes'

    def __str__(self):
        return f'OtpCode(phone={self.phone_number}, id={self.pk})'
