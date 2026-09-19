"""Tests for the shared response envelope."""

import json

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from .exceptions import ApiError, envelope_exception_handler
from .renderers import EnvelopeJSONRenderer
from .response import ApiResponse


class Teapot(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = 'slow_down'
    default_detail = 'Too many requests.'


class _View(APIView):
    """Minimal view used to give the handler a realistic context."""


def _handle(exc):
    factory = APIRequestFactory()
    context = {'view': _View(), 'request': factory.get('/'), 'args': (), 'kwargs': {}}
    return envelope_exception_handler(exc, context)


class ExceptionHandlerTests(SimpleTestCase):
    def test_api_error_uses_its_own_code_and_sets_retry_after_header(self):
        response = _handle(Teapot(retry_after=30))

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '30')
        self.assertFalse(response.data['success'])
        self.assertIsNone(response.data['data'])
        self.assertEqual(response.data['error']['code'], 'slow_down')
        self.assertEqual(response.data['error']['retry_after'], 30)

    def test_validation_error_reports_per_field_messages(self):
        response = _handle(ValidationError({'phone_number': ['This field is required.']}))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'invalid_request')
        self.assertEqual(
            response.data['error']['fields'],
            {'phone_number': ['This field is required.']},
        )

    def test_drf_exception_maps_to_status_specific_code(self):
        response = _handle(NotFound())

        self.assertEqual(response.data['error']['code'], 'not_found')
        self.assertIsNone(response.data['error']['fields'])

    def test_unhandled_exception_is_redacted_as_server_error(self):
        with self.assertLogs('core', level='ERROR'):
            response = _handle(RuntimeError('DB password is hunter2'))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error']['code'], 'server_error')
        self.assertNotIn('hunter2', str(response.data))


class RendererTests(SimpleTestCase):
    def setUp(self):
        self.renderer = EnvelopeJSONRenderer()
        self.request = APIRequestFactory().get('/')
        self.request.request_id = 'abc123'

    def _render(self, response):
        response.accepted_renderer = self.renderer
        response.accepted_media_type = 'application/json'
        response.renderer_context = {'response': response, 'request': self.request}
        return self.renderer.render(
            response.data, 'application/json', response.renderer_context
        )

    def test_plain_payload_is_wrapped(self):
        body = json.loads(self._render(Response({'id': 42})))

        self.assertTrue(body['success'])
        self.assertIsNone(body['message'])
        self.assertEqual(body['data'], {'id': 42})
        self.assertIsNone(body['error'])
        self.assertEqual(body['meta']['request_id'], 'abc123')
        self.assertIn('timestamp', body['meta'])

    def test_api_response_message_reaches_the_envelope(self):
        body = json.loads(self._render(ApiResponse({'ok': True}, message='Done.')))

        self.assertEqual(body['message'], 'Done.')

    def test_error_envelope_is_not_wrapped_twice(self):
        body = json.loads(self._render(_handle(Teapot())))

        self.assertFalse(body['success'])
        self.assertEqual(body['error']['code'], 'slow_down')
        self.assertNotIn('success', body['data'] or {})

    def test_bodyless_status_renders_empty(self):
        self.assertEqual(
            self._render(Response(status=status.HTTP_205_RESET_CONTENT)), b''
        )
