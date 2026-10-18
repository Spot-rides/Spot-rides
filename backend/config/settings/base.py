"""
Base settings — shared by all environments.

Do not reference DEBUG here; environment-specific files (development.py,
production.py) set DEBUG and import this module via `from .base import *`.
"""

from datetime import timedelta
from pathlib import Path

from decouple import config, Csv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# base.py lives at  backend/config/settings/base.py
# BASE_DIR should resolve to  backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Core security (values supplied per environment)
# ---------------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY')

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    # Local apps
    'accounts',
    'profiles.apps.ProfilesConfig',
]

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'accounts.middleware.RequestIDMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ---------------------------------------------------------------------------
# Structured logging (JSON) with PII redaction on the `accounts` namespace
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'request_id': {'()': 'accounts.logging.RequestIdFilter'},
        'phone_redaction': {'()': 'accounts.logging.PhoneRedactionFilter'},
    },
    'formatters': {
        'json': {'()': 'accounts.logging.JsonFormatter'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['request_id'],
        },
        'accounts_console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['phone_redaction', 'request_id'],
        },
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'accounts': {
            'handlers': ['accounts_console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Unhandled-exception tracebacks can quote request payloads, so `core`
        # shares the redacting handler.
        'core': {
            'handlers': ['accounts_console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
# Onboarding gate (default: False to avoid breaking existing clients)
ONBOARDING_GATE_ENABLED = config('ONBOARDING_GATE_ENABLED', default=False, cast=bool)

# Vehicle RC verification (FEAT-002 FR-32..FR-50).  Default OFF.
RC_VERIFICATION_ENABLED = config('RC_VERIFICATION_ENABLED', default=False, cast=bool)
RC_ADAPTER_CLASS = config(
    'RC_ADAPTER_CLASS',
    default='profiles.adapters.mock.MockRCVerificationAdapter',
)
RC_ADAPTER_MOCK_RESULT = config('RC_ADAPTER_MOCK_RESULT', default='sync_verified')
RC_PROVIDER_TIMEOUT_SECONDS = config('RC_PROVIDER_TIMEOUT_SECONDS', default=5, cast=float)
RC_MAX_ATTEMPTS = config('RC_MAX_ATTEMPTS', default=3, cast=int)
RC_WEBHOOK_SECRET = config('RC_WEBHOOK_SECRET', default='')

# Non-environment-specific RC validation (range checks only — mock/secret
# checks live in production.py where DEBUG is known to be False).
if RC_VERIFICATION_ENABLED:
    from django.core.exceptions import ImproperlyConfigured as _IC

    _rc_problems = []
    if RC_MAX_ATTEMPTS < 1:
        _rc_problems.append('RC_MAX_ATTEMPTS must be >= 1')
    if RC_PROVIDER_TIMEOUT_SECONDS <= 0:
        _rc_problems.append('RC_PROVIDER_TIMEOUT_SECONDS must be > 0')
    if _rc_problems:
        raise _IC('Invalid RC verification settings: ' + '; '.join(_rc_problems))

# Driving-licence (DL) verification (FEAT-002).
DL_ADAPTER_CLASS = config(
    'DL_ADAPTER_CLASS',
    default='profiles.adapters.mock.MockDLVerificationAdapter',
)
DL_ADAPTER_MOCK_RESULT = config('DL_ADAPTER_MOCK_RESULT', default='sync_verified')
DL_MAX_ATTEMPTS = config('DL_MAX_ATTEMPTS', default=3, cast=int)
# HMAC-SHA256 key for the DL webhook.  Empty = every webhook is rejected (fail closed).
DL_WEBHOOK_SECRET = config('DL_WEBHOOK_SECRET', default='')

# Non-environment-specific DL validation.
from django.core.exceptions import ImproperlyConfigured as _IC  # noqa: E402

_dl_problems = []
if DL_MAX_ATTEMPTS < 1:
    _dl_problems.append('DL_MAX_ATTEMPTS must be >= 1')
if _dl_problems:
    raise _IC('Invalid DL verification settings: ' + '; '.join(_dl_problems))

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
        'core.permissions.ConditionalOnboardingGate',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    # Every response — success or failure — is wrapped in the shared envelope
    # defined in `core.envelope` (DEC-011).
    'DEFAULT_RENDERER_CLASSES': [
        'core.renderers.EnvelopeJSONRenderer',
    ],
    'EXCEPTION_HANDLER': 'core.exceptions.envelope_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.EnvelopePageNumberPagination',
    'PAGE_SIZE': 20,
}

# ---------------------------------------------------------------------------
# SimpleJWT — 15 min access / 30 day refresh with rotation + blacklist
# (FR-17, NFR-SEC-06)
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': config('JWT_SIGNING_KEY'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# ---------------------------------------------------------------------------
# Redis cache (django-redis) — used for rate-limit counters
# ---------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# ---------------------------------------------------------------------------
# OTP + Twilio
# ---------------------------------------------------------------------------
OTP_PEPPER = config('OTP_PEPPER')
OTP_LENGTH = 6
OTP_TTL_SECONDS = 300
OTP_RESEND_COOLDOWN_SECONDS = 30
OTP_MAX_ATTEMPTS = 5
OTP_DEV_MODE = config('OTP_DEV_MODE', default=False, cast=bool)
OTP_DEV_FIXED_CODE = config('OTP_DEV_FIXED_CODE', default='000000')
OTP_COUNTRY_ALLOWLIST = config('OTP_COUNTRY_ALLOWLIST', default='IN', cast=Csv())

TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_NUMBER = config('TWILIO_FROM_NUMBER', default='')
TWILIO_MESSAGING_SERVICE_SID = config('TWILIO_MESSAGING_SERVICE_SID', default='')
TWILIO_SSL_VERIFY = config('TWILIO_SSL_VERIFY', default=True, cast=bool)

# ---------------------------------------------------------------------------
# URLs / WSGI / ASGI
# ---------------------------------------------------------------------------
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = 'static/'

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}
