"""
Development settings.

Inherits everything from base and applies developer-friendly overrides:
  - DEBUG on
  - Permissive CORS / ALLOWED_HOSTS
  - BrowsableAPIRenderer enabled
  - Mock adapters allowed
"""

from .base import *  # noqa: F401, F403
from decouple import config, Csv

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = True

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-me')

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# ---------------------------------------------------------------------------
# CORS — allow everything locally
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# Django REST Framework — add BrowsableAPIRenderer for local development
# ---------------------------------------------------------------------------
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [  # noqa: F405
    'core.renderers.EnvelopeJSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# ---------------------------------------------------------------------------
# Adapter guard flags (mock adapters are fine in development)
# ---------------------------------------------------------------------------
RC_MOCK_ADAPTER_FORBIDDEN = False
DL_MOCK_ADAPTER_FORBIDDEN = False

# ---------------------------------------------------------------------------
# OTP dev helpers — allow override via env even in dev
# ---------------------------------------------------------------------------
OTP_DEV_MODE = config('OTP_DEV_MODE', default=False, cast=bool)
OTP_DEV_FIXED_CODE = config('OTP_DEV_FIXED_CODE', default='000000')
