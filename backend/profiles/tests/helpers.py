"""Shared test helpers for the FEAT-002 onboarding suite.

Everything here is deterministic: no sleeps, no network, no reliance on the real
``.env``.  DL encryption is pinned to a fixed test key by patching the
``decouple`` accessor inside :mod:`profiles.utils.crypto` (the module reads the key
directly, bypassing Django settings), so the suite behaves the same whether or not
``DL_ENCRYPTION_KEY`` is configured in the developer's environment.
"""

import hashlib
import hmac
import json
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from profiles.models import DriverVerification, UserProfile, Vehicle

User = get_user_model()

# A valid Fernet key (32 url-safe base64 bytes), fixed so tests are reproducible.
TEST_DL_ENCRYPTION_KEY = 'ZmVhdDAwMi10ZXN0LWtleS0zMi1ieXRlcy1sb25nISE='

# Secret used by the DL/RC webhook signature tests.
TEST_WEBHOOK_SECRET = 'feat-002-test-webhook-secret'

VALID_DL = 'MH0120110012345'
VALID_DL_SPACED = 'MH01 2011 0012345'
VALID_REG = 'MH01AB1234'

URL_STATUS = '/api/onboarding/status/'
URL_ROLE = '/api/onboarding/role/'
URL_PROFILE = '/api/onboarding/profile/'
URL_DL = '/api/onboarding/driver/dl/'
URL_DL_STATUS = '/api/onboarding/driver/dl/status/'
URL_DL_WEBHOOK = '/api/onboarding/driver/dl/webhook/'
URL_VEHICLE = '/api/onboarding/driver/vehicle/'
URL_VEHICLE_STATUS = '/api/onboarding/driver/vehicle/status/'
URL_RC_WEBHOOK = '/api/onboarding/driver/vehicle/rc/webhook/'
URL_ROLE_SWITCH = '/api/profile/role/'

MOCK_DL_ADAPTER = 'profiles.adapters.mock.MockDLVerificationAdapter'
MOCK_RC_ADAPTER = 'profiles.adapters.mock.MockRCVerificationAdapter'


def fake_crypto_config(name, *args, **kwargs):
    """Stand-in for ``decouple.config`` inside ``profiles.utils.crypto``."""
    if name == 'DL_ENCRYPTION_KEY':
        return TEST_DL_ENCRYPTION_KEY
    raise KeyError(name)


def patch_dl_key(value=TEST_DL_ENCRYPTION_KEY):
    """Patch the DL encryption key as seen by ``profiles.utils.crypto``.

    ``value`` may be a string (the key), ``None`` (key unset -> the accessor raises)
    or any other string to simulate a malformed key.
    """

    def _config(name, *args, **kwargs):
        if name != 'DL_ENCRYPTION_KEY':
            raise KeyError(name)
        if value is None:
            raise KeyError(name)
        return value

    return mock.patch('profiles.utils.crypto.config', _config)


def hmac_hex(body: bytes, secret: str = TEST_WEBHOOK_SECRET) -> str:
    """Hex HMAC-SHA256 of the raw body, as the webhook signature header expects."""
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


def json_body(payload: dict) -> bytes:
    """Serialise a payload the same way the test client will send it."""
    return json.dumps(payload).encode('utf-8')


class EnvelopeAssertions:
    """Assertions on the unified response envelope (DEC-011)."""

    def assertSuccess(self, response, status_code=200):
        body = response.json()
        self.assertEqual(
            response.status_code, status_code,
            f'expected {status_code}, got {response.status_code}: {body}',
        )
        self.assertTrue(body['success'], body)
        self.assertIsNone(body['error'], body)
        return body['data']

    def assertApiError(self, response, status_code, code, **extra):
        body = response.json()
        self.assertEqual(
            response.status_code, status_code,
            f'expected {status_code}, got {response.status_code}: {body}',
        )
        self.assertFalse(body['success'], body)
        self.assertIsNone(body['data'], body)
        self.assertEqual(body['error']['code'], code, body)
        for key, value in extra.items():
            self.assertEqual(body['error'].get(key), value, body)
        return body['error']


class CacheBustingAPIClient(APIClient):
    """``force_authenticate`` reuses one user instance across requests.

    A real request authenticates a freshly loaded user, so cached (or cached-as-missing)
    ``profile`` / ``driver_verification`` relations are dropped before each call to keep
    the test client faithful to production.
    """

    def request(self, **kwargs):
        user = getattr(self.handler, '_force_user', None)
        if user is not None:
            user._state.fields_cache.clear()
        return super().request(**kwargs)


class OnboardingTestCase(EnvelopeAssertions, APITestCase):
    """Base case: an authenticated user, a pinned DL key, and state factories."""

    client_class = CacheBustingAPIClient
    phone_seq = 0

    def setUp(self):
        super().setUp()
        patcher = patch_dl_key()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = self.make_user()
        self.client.force_authenticate(user=self.user)

    # ---------------------------------------------------------------- factories

    @classmethod
    def next_phone(cls):
        OnboardingTestCase.phone_seq += 1
        return f'+9198000{OnboardingTestCase.phone_seq:05d}'

    def make_user(self, phone=None, **kwargs):
        return User.objects.create_user(phone_number=phone or self.next_phone(), **kwargs)

    @staticmethod
    def bust_related_cache(user):
        """Drop cached ``profile`` / ``driver_verification`` relations.

        ``force_authenticate`` puts the very same user instance on the request, so a
        relation cached (or cached as missing) by a factory would otherwise be read by
        permissions and views instead of the current database row.
        """
        user._state.fields_cache.clear()

    def make_profile(self, user=None, **kwargs):
        user = user or self.user
        kwargs.setdefault('onboarding_status', UserProfile.NOT_STARTED)
        profile, _ = UserProfile.objects.update_or_create(user=user, defaults=kwargs)
        self.bust_related_cache(user)
        return profile

    def make_named_profile(self, user=None, **kwargs):
        """Profile with personal details filled in (as after POST /onboarding/profile/)."""
        kwargs.setdefault('first_name', 'Priya')
        kwargs.setdefault('last_name', 'Sharma')
        kwargs.setdefault('age', 27)
        kwargs.setdefault('gender', UserProfile.FEMALE)
        return self.make_profile(user, **kwargs)

    def make_dl(self, user=None, status=DriverVerification.VERIFIED, **kwargs):
        user = user or self.user
        kwargs.setdefault('dl_number', 'ciphertext-placeholder')
        kwargs.setdefault('dl_number_display', '2345')
        kwargs.setdefault('attempt_count', 1)
        kwargs['dl_verification_status'] = status
        record, _ = DriverVerification.objects.update_or_create(user=user, defaults=kwargs)
        self.bust_related_cache(user)
        return record

    def make_vehicle(self, user=None, **kwargs):
        user = user or self.user
        kwargs.setdefault('registration_number', VALID_REG)
        kwargs.setdefault('vehicle_type', Vehicle.VehicleType.SEDAN)
        kwargs.setdefault('is_active', True)
        vehicle = Vehicle.objects.create(user=user, **kwargs)
        self.bust_related_cache(user)
        return vehicle

    # ------------------------------------------------------------ state presets

    def passenger_complete(self, user=None):
        return self.make_named_profile(
            user, active_role=UserProfile.PASSENGER, onboarding_status=UserProfile.COMPLETE,
        )

    def driver_awaiting_dl(self, user=None):
        return self.make_named_profile(
            user, active_role=UserProfile.DRIVER, onboarding_status=UserProfile.AWAITING_DL,
        )

    def driver_awaiting_vehicle(self, user=None, dl=True):
        profile = self.make_named_profile(
            user, active_role=UserProfile.DRIVER, onboarding_status=UserProfile.AWAITING_VEHICLE,
        )
        if dl:
            self.make_dl(user, DriverVerification.VERIFIED)
        return profile

    def driver_complete_with_vehicle(self, user=None, **vehicle_kwargs):
        profile = self.make_named_profile(
            user, active_role=UserProfile.DRIVER, onboarding_status=UserProfile.COMPLETE,
        )
        self.make_dl(user, DriverVerification.VERIFIED)
        self.make_vehicle(user, **vehicle_kwargs)
        return profile

    # ----------------------------------------------------------------- requests

    def post_dl_webhook(self, payload, signature=None, secret=TEST_WEBHOOK_SECRET,
                        header_present=True, prefix=''):
        """POST the DL webhook with a signature over the exact bytes sent."""
        body = json_body(payload)
        headers = {}
        if header_present:
            if signature is None:
                signature = prefix + hmac_hex(body, secret)
            headers['X-DL-Signature'] = signature
        return self.client.post(
            URL_DL_WEBHOOK, data=body, content_type='application/json', headers=headers,
        )

    def post_rc_webhook(self, payload, signature=None, secret=TEST_WEBHOOK_SECRET,
                        header_present=True):
        body = json_body(payload)
        headers = {}
        if header_present:
            if signature is None:
                signature = hmac_hex(body, secret)
            headers['X-RC-Signature'] = signature
        return self.client.post(
            URL_RC_WEBHOOK, data=body, content_type='application/json', headers=headers,
        )

    def refresh(self, obj):
        obj.refresh_from_db()
        return obj
