"""``ApiResponse`` — the Response subclass views should return.

Views keep returning their plain payload; the envelope is assembled later by
:class:`core.renderers.EnvelopeJSONRenderer`. ``ApiResponse`` exists only so a
view can attach a human-readable ``message`` to that envelope.

A bare DRF ``Response`` is still fine — it simply renders with ``message: null``.
"""

from __future__ import annotations

from typing import Any, Optional

from rest_framework.response import Response


class ApiResponse(Response):
    """Carry an optional ``message`` through to the response envelope."""

    def __init__(self, data: Any = None, message: Optional[str] = None, **kwargs):
        super().__init__(data, **kwargs)
        self.api_message = message
