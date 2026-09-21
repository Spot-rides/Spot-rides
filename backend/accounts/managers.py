"""User manager for the phone-number-keyed custom user model.

See ARCH-001 §Data Model for identity semantics: phone_number is the
USERNAME_FIELD and regular users have no usable password. Superusers keep
a real password so Django admin login still works.
"""

from django.contrib.auth.base_user import BaseUserManager


class PhoneUserManager(BaseUserManager):
    """Manager for `accounts.User` (phone-number identifier, passwordless)."""

    use_in_migrations = True

    def _create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('phone_number is required')
        user = self.model(phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        # Regular users never have a usable password (passwordless OTP flow).
        return self._create_user(phone_number, password=None, **extra_fields)

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        if not password:
            raise ValueError('Superuser must have a password for admin login.')
        return self._create_user(phone_number, password=password, **extra_fields)
