"""DL verification adapter interface and implementations.

Exports:
- DLVerificationAdapter: Abstract base class for all adapters
- DLVerificationResult: Dataclass returned by adapter.submit()
- MockDLVerificationAdapter: Concrete mock implementation for dev/test
"""

from .base import DLVerificationAdapter, DLVerificationResult
from .mock import MockDLVerificationAdapter

__all__ = ['DLVerificationAdapter', 'DLVerificationResult', 'MockDLVerificationAdapter']
