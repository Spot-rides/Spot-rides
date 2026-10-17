"""Verification adapter interfaces and implementations.

Exports:
- DLVerificationAdapter / DLVerificationResult / MockDLVerificationAdapter (driving licence)
- RCVerificationAdapter / RCVerificationResult / RCAdapterError / MockRCVerificationAdapter (vehicle RC)
- get_rc_adapter: settings-driven factory for the RC adapter
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .base import (
    DLVerificationAdapter,
    DLVerificationResult,
    RCAdapterError,
    RCVerificationAdapter,
    RCVerificationResult,
)
from .mock import MockDLVerificationAdapter, MockRCVerificationAdapter


def get_rc_adapter() -> RCVerificationAdapter:
    """Build a new RC adapter from ``settings.RC_ADAPTER_CLASS`` (no module-level instance)."""
    cls = import_string(settings.RC_ADAPTER_CLASS)
    if settings.RC_MOCK_ADAPTER_FORBIDDEN and issubclass(cls, MockRCVerificationAdapter):
        raise ImproperlyConfigured(
            "Mock RC adapter is not allowed when RC verification is enabled with DEBUG=False"
        )
    return cls.from_settings(settings)


__all__ = [
    'DLVerificationAdapter',
    'DLVerificationResult',
    'MockDLVerificationAdapter',
    'RCAdapterError',
    'RCVerificationAdapter',
    'RCVerificationResult',
    'MockRCVerificationAdapter',
    'get_rc_adapter',
]
