"""Verification adapter interfaces and implementations.

Exports:
- DLVerificationAdapter / DLVerificationResult / MockDLVerificationAdapter (driving licence)
- RCVerificationAdapter / RCVerificationResult / RCAdapterError / MockRCVerificationAdapter (vehicle RC)
- get_dl_adapter / get_rc_adapter: settings-driven factories (no module-level adapter instances)
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


def get_dl_adapter() -> DLVerificationAdapter:
    """Build a new DL adapter from ``settings.DL_ADAPTER_CLASS`` (no module-level instance).

    Called per request by both the submit service and the webhook view, so a settings change
    (or ``override_settings`` in tests) reaches every code path. Refuses the mock adapter when
    ``settings.DL_MOCK_ADAPTER_FORBIDDEN`` is set (DEBUG off at startup).
    """
    cls = import_string(settings.DL_ADAPTER_CLASS)
    if settings.DL_MOCK_ADAPTER_FORBIDDEN and issubclass(cls, MockDLVerificationAdapter):
        raise ImproperlyConfigured("Mock DL adapter is not allowed when DEBUG is off")
    return cls.from_settings(settings)


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
    'get_dl_adapter',
    'get_rc_adapter',
]
