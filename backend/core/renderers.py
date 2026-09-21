"""Renderer that wraps every DRF payload in the shared response envelope.

Doing this in the renderer rather than in each view keeps call sites free of
envelope boilerplate: a view returns ``Response(serializer.data)`` and the
client still receives the full ``{success, message, data, error, meta}`` shape.

Responses whose body was already built by
:func:`core.exceptions.envelope_exception_handler` are passed through untouched
apart from ``meta``.
"""

from __future__ import annotations

from rest_framework.renderers import JSONRenderer

from .envelope import build_meta, is_enveloped, success_envelope

# 204/205 must not carry a body, so there is nothing to envelope.
BODYLESS_STATUSES = frozenset({204, 205})


class EnvelopeJSONRenderer(JSONRenderer):
    """Apply the shared envelope to every JSON response."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        context = renderer_context or {}
        response = context.get('response')
        request = context.get('request')

        if response is None:
            return super().render(data, accepted_media_type, renderer_context)

        if response.status_code in BODYLESS_STATUSES:
            return b''

        if is_enveloped(data):
            body = dict(data)
        else:
            body = success_envelope(data, message=getattr(response, 'api_message', None))

        body['meta'] = build_meta(
            request=request,
            pagination=getattr(response, 'pagination_meta', None),
        )
        return super().render(body, accepted_media_type, renderer_context)
