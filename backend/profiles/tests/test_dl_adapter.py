"""DL adapter factory and configuration guards (FEAT-002 FR-61, FR-60; SEC F-01, F-03).

The factory is the single place adapters are built, so overriding
``DL_ADAPTER_CLASS`` must reach both DL submission and the DL webhook.
"""

import os
import subprocess
import sys

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from profiles.adapters import (
    DLVerificationAdapter,
    DLVerificationResult,
    MockDLVerificationAdapter,
    get_dl_adapter,
    get_rc_adapter,
)
from profiles.models import DriverVerification, UserProfile

from .helpers import (
    MOCK_DL_ADAPTER,
    TEST_WEBHOOK_SECRET,
    VALID_DL,
    URL_DL,
    OnboardingTestCase,
)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class StubDLAdapter(DLVerificationAdapter):
    """Non-mock adapter used to prove the factory honours DL_ADAPTER_CLASS."""

    instances = 0

    def __init__(self):
        type(self).instances += 1

    @classmethod
    def from_settings(cls, settings):
        return cls()

    def submit(self, dl_number, user_id):
        return DLVerificationResult(status='rejected', reference_id='stub-ref', rejection_reason='stub')

    def validate_webhook(self, headers, body):
        # Deliberately permissive: a webhook that is processed without a valid HMAC
        # proves the webhook view resolved *this* class through the factory.
        return True


STUB_DL_ADAPTER = f'{__name__}.StubDLAdapter'


class GetDLAdapterTests(SimpleTestCase):
    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=False)
    def test_builds_the_configured_class(self):
        self.assertIsInstance(get_dl_adapter(), MockDLVerificationAdapter)

    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=False)
    def test_builds_a_new_instance_per_call(self):
        first, second = get_dl_adapter(), get_dl_adapter()

        self.assertIsNot(first, second)

    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=False,
                       DL_ADAPTER_MOCK_RESULT='async_pending')
    def test_mock_mode_is_read_from_settings_per_call(self):
        self.assertEqual(get_dl_adapter().response_mode, 'async_pending')

        with override_settings(DL_ADAPTER_MOCK_RESULT='sync_rejected'):
            self.assertEqual(get_dl_adapter().response_mode, 'sync_rejected')

    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=False,
                       DL_ADAPTER_MOCK_RESULT='no_such_mode')
    def test_unknown_mock_mode_is_a_configuration_error(self):
        with self.assertRaises(ImproperlyConfigured):
            get_dl_adapter()

    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=True)
    def test_mock_is_refused_when_mocks_are_forbidden(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            get_dl_adapter()

        self.assertIn('Mock DL adapter', str(ctx.exception))

    @override_settings(DL_ADAPTER_CLASS=STUB_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=True)
    def test_non_mock_adapter_is_allowed_when_mocks_are_forbidden(self):
        self.assertIsInstance(get_dl_adapter(), StubDLAdapter)

    @override_settings(DL_ADAPTER_CLASS='profiles.adapters.nope.Missing',
                       DL_MOCK_ADAPTER_FORBIDDEN=False)
    def test_unimportable_class_raises(self):
        with self.assertRaises(ImportError):
            get_dl_adapter()


class GetRCAdapterTests(SimpleTestCase):
    @override_settings(RC_MOCK_ADAPTER_FORBIDDEN=True)
    def test_mock_rc_adapter_is_refused_when_forbidden(self):
        with self.assertRaises(ImproperlyConfigured):
            get_rc_adapter()

    @override_settings(RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_builds_a_new_instance_per_call(self):
        self.assertIsNot(get_rc_adapter(), get_rc_adapter())


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False, DL_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET)
class FactoryReachesEveryCodePathTests(OnboardingTestCase):
    """FR-61: there is no module-level adapter, so a settings change reaches both paths."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_named_profile(
            active_role=UserProfile.DRIVER, onboarding_status=UserProfile.AWAITING_DL,
        )

    @override_settings(DL_ADAPTER_CLASS=STUB_DL_ADAPTER)
    def test_submit_uses_the_configured_adapter(self):
        response = self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json')

        # The stub rejects synchronously: 202 with status rejected (KD-04).
        data = self.assertSuccess(response, 202)
        self.assertEqual(data['dl_verification_status'], 'rejected')
        self.assertEqual(data['reference_id'], 'stub-ref')

    @override_settings(DL_ADAPTER_CLASS=STUB_DL_ADAPTER)
    def test_webhook_validation_uses_the_configured_adapter(self):
        self.profile.onboarding_status = UserProfile.PENDING_VERIFICATION
        self.profile.save()
        dl = self.make_dl(status=DriverVerification.PENDING, dl_verification_ref='stub-ref')

        # No signature at all: the stub's permissive validate_webhook lets it through,
        # which can only happen if the view built the adapter from settings.
        response = self.post_dl_webhook(
            {'reference_id': 'stub-ref', 'status': 'verified'}, header_present=False,
        )

        self.assertSuccess(response, 200)
        dl.refresh_from_db()
        self.assertEqual(dl.dl_verification_status, DriverVerification.VERIFIED)

    @override_settings(DL_ADAPTER_CLASS='profiles.adapters.nope.Missing')
    def test_unimportable_adapter_surfaces_as_provider_error_on_submit(self):
        with self.assertLogs('profiles', level='ERROR'):
            response = self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json')

        # FR-60: a configuration failure is a 422, never a 500, and consumes no attempt.
        self.assertApiError(response, 422, 'dl_verification_provider_error')
        self.assertFalse(DriverVerification.objects.filter(user=self.user).exists())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_DL)

    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_MOCK_ADAPTER_FORBIDDEN=True)
    def test_forbidden_mock_surfaces_as_provider_error_on_submit(self):
        with self.assertLogs('profiles', level='ERROR'):
            response = self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json')

        self.assertApiError(response, 422, 'dl_verification_provider_error')
        self.assertFalse(DriverVerification.objects.filter(user=self.user).exists())

    @override_settings(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER, DL_ADAPTER_MOCK_RESULT='bogus_mode')
    def test_unknown_mock_mode_surfaces_as_provider_error_on_submit(self):
        with self.assertLogs('profiles', level='ERROR'):
            response = self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json')

        self.assertApiError(response, 422, 'dl_verification_provider_error')
        self.assertFalse(DriverVerification.objects.filter(user=self.user).exists())


class ProductionStartupGuardTests(SimpleTestCase):
    """FR-61 import-time guards.

    ``override_settings`` cannot exercise a check that runs while the settings module
    is imported, so these run a child interpreter with an explicit environment (no
    reliance on a developer ``.env``).
    """

    base_env = {
        'DJANGO_ENV': 'production',
        'DJANGO_SETTINGS_MODULE': 'config.settings.production',
        'SECRET_KEY': 'test-secret-key-for-startup-guard',
        'JWT_SIGNING_KEY': 'test-jwt-signing-key',
        'OTP_PEPPER': 'test-pepper',
        'ALLOWED_HOSTS': 'example.com',
        'DB_NAME': 'unused',
        'DB_USER': 'unused',
        'DB_PASSWORD': 'unused',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
        'RC_VERIFICATION_ENABLED': 'False',
        'ONBOARDING_GATE_ENABLED': 'True',
        'PYTHONIOENCODING': 'utf-8',
    }

    def _setup_django(self, **overrides):
        env = {**os.environ, **self.base_env, **overrides}
        return subprocess.run(
            [sys.executable, '-c', 'import django; django.setup()'],
            cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
        )

    def test_real_adapter_starts_cleanly(self):
        result = self._setup_django(DL_ADAPTER_CLASS=STUB_DL_ADAPTER)

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mock_dl_adapter_is_refused_with_debug_off(self):
        result = self._setup_django(DL_ADAPTER_CLASS=MOCK_DL_ADAPTER)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('mock DL adapter is not allowed in production', result.stderr)

    def test_default_dl_adapter_is_a_mock_and_is_refused(self):
        result = self._setup_django()

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('mock DL adapter is not allowed in production', result.stderr)

    def test_dl_max_attempts_below_one_is_refused(self):
        result = self._setup_django(DL_ADAPTER_CLASS=STUB_DL_ADAPTER, DL_MAX_ATTEMPTS='0')

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn('DL_MAX_ATTEMPTS must be >= 1', result.stderr)
