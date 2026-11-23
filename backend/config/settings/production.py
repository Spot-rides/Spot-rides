"""
Production settings.

Inherits everything from base and applies production hardening:
  - DEBUG off
  - Strict CORS / ALLOWED_HOSTS from env (required)
  - HTTPS / HSTS via ALB (ARCH-001 §Security)
  - Mock adapters forbidden
  - Real email backend expected via MAILERS override
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403
from decouple import config, Csv

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = False

SECRET_KEY = config('SECRET_KEY')  # Must be set; no insecure default

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

# ---------------------------------------------------------------------------
# CORS — explicit allow-list required in production
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())

# ---------------------------------------------------------------------------
# OTP — dev helpers are always off in production
# ---------------------------------------------------------------------------
OTP_DEV_MODE = False

# ---------------------------------------------------------------------------
# Adapter guard flags — mock adapters are forbidden in production
# ---------------------------------------------------------------------------
RC_MOCK_ADAPTER_FORBIDDEN = RC_VERIFICATION_ENABLED  # noqa: F405
DL_MOCK_ADAPTER_FORBIDDEN = True

# ---------------------------------------------------------------------------
# Production-only RC + DL validation
# ---------------------------------------------------------------------------
if RC_VERIFICATION_ENABLED:  # noqa: F405
    _rc_problems = []
    if 'mock' in RC_ADAPTER_CLASS.lower():  # noqa: F405
        _rc_problems.append('the mock RC adapter is not allowed in production')
    if not RC_WEBHOOK_SECRET or RC_WEBHOOK_SECRET.startswith('PLACEHOLDER'):  # noqa: F405
        _rc_problems.append('RC_WEBHOOK_SECRET must be set to a real secret in production')
    if not ONBOARDING_GATE_ENABLED:  # noqa: F405
        _rc_problems.append('ONBOARDING_GATE_ENABLED must be True in production')
    if _rc_problems:
        raise ImproperlyConfigured(
            'Invalid RC verification settings: ' + '; '.join(_rc_problems)
        )

_dl_problems = []
if 'mock' in DL_ADAPTER_CLASS.lower():  # noqa: F405
    _dl_problems.append('the mock DL adapter is not allowed in production')
if _dl_problems:
    raise ImproperlyConfigured(
        'Invalid DL verification settings: ' + '; '.join(_dl_problems)
    )

# ---------------------------------------------------------------------------
# HTTPS hardening — HTTPS is terminated at ALB (ARCH-001 §Security)
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
