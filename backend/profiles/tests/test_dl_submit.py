"""DL submission endpoint and service (FEAT-002 FR-06..FR-13, FR-60, FR-61; SEC F-04).

Covers the attempt cap (including re-validation under the row lock), the provider
outcomes, and the documented deviations KD-01, KD-03, KD-04, KD-07 and KD-12.
"""

from django.test import override_settings

from profiles.adapters import DLVerificationAdapter, DLVerificationResult
from profiles.models import DriverVerification, UserProfile
from profiles.utils.crypto import decrypt_dl_number

from .helpers import (
    MOCK_DL_ADAPTER,
    URL_DL,
    URL_DL_STATUS,
    VALID_DL,
    OnboardingTestCase,
)


class _CountingAdapter(DLVerificationAdapter):
    """Base for stub adapters that record how often the provider was called."""

    calls = 0
    last_dl_number = None

    def __init__(self):
        pass

    @classmethod
    def from_settings(cls, settings):
        return cls()

    @classmethod
    def reset(cls):
        cls.calls = 0
        cls.last_dl_number = None

    def submit(self, dl_number, user_id):
        type(self).record(dl_number)
        return self.result(dl_number, user_id)

    @classmethod
    def record(cls, dl_number):
        _CountingAdapter.calls += 1
        _CountingAdapter.last_dl_number = dl_number

    def result(self, dl_number, user_id):
        raise NotImplementedError

    def validate_webhook(self, headers, body):
        return False


class VerifyingAdapter(_CountingAdapter):
    def result(self, dl_number, user_id):
        return DLVerificationResult(status='verified', reference_id=f'ref-verified-{user_id}')


class PendingAdapter(_CountingAdapter):
    def result(self, dl_number, user_id):
        return DLVerificationResult(status='pending', reference_id=f'ref-pending-{user_id}')


class RejectingAdapter(_CountingAdapter):
    def result(self, dl_number, user_id):
        return DLVerificationResult(
            status='rejected', reference_id=f'ref-rejected-{user_id}',
            rejection_reason='<i>Licence</i> not found',
        )


class TimingOutAdapter(_CountingAdapter):
    def result(self, dl_number, user_id):
        raise TimeoutError('provider did not answer')


class ExplodingAdapter(_CountingAdapter):
    def result(self, dl_number, user_id):
        raise RuntimeError('provider outage')


class BadResultAdapter(_CountingAdapter):
    def result(self, dl_number, user_id):
        return DLVerificationResult(status='maybe', reference_id='ref')


class FixedReferenceAdapter(_CountingAdapter):
    """Returns the same provider reference for every user (a misbehaving provider)."""

    def result(self, dl_number, user_id):
        return DLVerificationResult(status='pending', reference_id='SHARED-REF')


class RaceAdapter(_CountingAdapter):
    """Simulates a concurrent submission committing while the provider is called.

    The submit service releases its lock for the provider call (phase 2) and
    re-validates under the lock in phase 3; this adapter exhausts the attempt
    budget in between, deterministically exercising that re-validation.
    """

    def result(self, dl_number, user_id):
        DriverVerification.objects.filter(user_id=user_id).update(attempt_count=99)
        return DLVerificationResult(status='verified', reference_id='ref-race')


def path(cls):
    return f'{__name__}.{cls.__name__}'


class DLSubmitTestCase(OnboardingTestCase):
    def setUp(self):
        super().setUp()
        _CountingAdapter.reset()
        self.profile = self.make_named_profile(
            active_role=UserProfile.DRIVER, onboarding_status=UserProfile.AWAITING_DL,
        )

    def submit(self, dl_number=VALID_DL):
        return self.client.post(URL_DL, {'dl_number': dl_number}, format='json')

    def dl(self):
        return DriverVerification.objects.get(user=self.user)


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False)
class DLSubmitOutcomeTests(DLSubmitTestCase):
    @override_settings(DL_ADAPTER_CLASS=path(VerifyingAdapter))
    def test_synchronous_verified_result(self):
        response = self.submit()

        data = self.assertSuccess(response, 200)
        self.assertEqual(data['dl_verification_status'], 'verified')
        self.assertEqual(data['onboarding_status'], 'awaiting_vehicle')
        self.assertEqual(data['next_step'], 'vehicle_registration')
        self.assertEqual(data['reference_id'], f'ref-verified-{self.user.id}')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)
        record = self.dl()
        self.assertEqual(record.attempt_count, 1)
        self.assertIsNotNone(record.dl_verified_at)

    @override_settings(DL_ADAPTER_CLASS=path(VerifyingAdapter))
    def test_dl_number_is_stored_encrypted_with_a_plaintext_last_four(self):
        self.submit()

        record = self.dl()
        self.assertNotIn(VALID_DL, record.dl_number)
        self.assertEqual(decrypt_dl_number(record.dl_number), VALID_DL)
        self.assertEqual(record.dl_number_display, '2345')
        self.assertLessEqual(len(record.dl_number), 256)

    @override_settings(DL_ADAPTER_CLASS=path(VerifyingAdapter))
    def test_input_is_normalised_before_the_provider_is_called(self):
        # KD-12: lowercase input and separators in any position are accepted.
        response = self.submit('mh-01 2011 0012345')

        self.assertSuccess(response, 200)
        self.assertEqual(_CountingAdapter.last_dl_number, VALID_DL)
        self.assertEqual(decrypt_dl_number(self.dl().dl_number), VALID_DL)

    @override_settings(DL_ADAPTER_CLASS=path(PendingAdapter))
    def test_asynchronous_pending_result(self):
        response = self.submit()

        data = self.assertSuccess(response, 202)
        self.assertEqual(data['dl_verification_status'], 'pending')
        self.assertEqual(data['onboarding_status'], 'pending_verification')
        self.assertEqual(data['next_step'], 'awaiting_verification')
        self.assertEqual(data['reference_id'], f'ref-pending-{self.user.id}')
        self.assertEqual(self.dl().attempt_count, 1)

    @override_settings(DL_ADAPTER_CLASS=path(RejectingAdapter))
    def test_synchronously_rejected_result_returns_202(self):
        response = self.submit()

        # KD-04: a synchronous rejection is delivered as 202 with status "rejected";
        # the onboarding status does not move and the attempt is consumed.
        data = self.assertSuccess(response, 202)
        self.assertEqual(data['dl_verification_status'], 'rejected')
        self.assertEqual(data['onboarding_status'], 'awaiting_dl')
        self.assertEqual(data['next_step'], 'dl_submission')
        self.assertNotIn('rejection_reason', data)
        record = self.dl()
        self.assertEqual(record.attempt_count, 1)
        self.assertEqual(record.dl_rejection_reason, 'Licence not found')

    @override_settings(DL_ADAPTER_CLASS=path(RejectingAdapter))
    def test_rejection_from_pending_verification_keeps_that_status(self):
        self.profile.onboarding_status = UserProfile.PENDING_VERIFICATION
        self.profile.save()
        self.make_dl(status=DriverVerification.PENDING, dl_verification_ref='old-ref')

        data = self.assertSuccess(self.submit(), 202)

        self.assertEqual(data['onboarding_status'], 'pending_verification')
        self.assertEqual(data['next_step'], 'awaiting_verification')

    @override_settings(DL_ADAPTER_CLASS=path(TimingOutAdapter))
    def test_timeout_is_treated_as_pending_and_consumes_an_attempt(self):
        response = self.submit()

        data = self.assertSuccess(response, 202)
        self.assertEqual(data['dl_verification_status'], 'pending')
        self.assertEqual(data['onboarding_status'], 'pending_verification')
        self.assertIsNone(data['reference_id'])
        self.assertEqual(self.dl().attempt_count, 1)

    @override_settings(DL_ADAPTER_CLASS=path(ExplodingAdapter))
    def test_provider_error_is_422_and_consumes_no_attempt(self):
        existing = self.make_dl(status=DriverVerification.REJECTED, attempt_count=1)

        with self.assertLogs('profiles', level='ERROR'):
            response = self.submit()

        self.assertApiError(response, 422, 'dl_verification_provider_error')
        existing.refresh_from_db()
        self.assertEqual(existing.attempt_count, 1)
        self.assertEqual(existing.dl_verification_status, DriverVerification.REJECTED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_DL)

    @override_settings(DL_ADAPTER_CLASS=path(BadResultAdapter))
    def test_unrecognised_provider_status_is_422_and_consumes_no_attempt(self):
        with self.assertLogs('profiles', level='ERROR'):
            response = self.submit()

        self.assertApiError(response, 422, 'dl_verification_provider_error')
        self.assertFalse(DriverVerification.objects.filter(user=self.user).exists())

    @override_settings(DL_ADAPTER_CLASS=path(VerifyingAdapter))
    def test_resubmission_after_a_rejection_reuses_the_same_row(self):
        self.make_dl(status=DriverVerification.REJECTED, attempt_count=1,
                     dl_verification_ref='old-ref', dl_rejection_reason='typo')

        self.assertSuccess(self.submit(), 200)

        self.assertEqual(DriverVerification.objects.filter(user=self.user).count(), 1)
        record = self.dl()
        self.assertEqual(record.attempt_count, 2)
        self.assertEqual(record.dl_verification_status, DriverVerification.VERIFIED)

    @override_settings(DL_ADAPTER_CLASS=path(PendingAdapter))
    def test_resubmission_while_pending_is_accepted_and_replaces_the_submission(self):
        self.profile.onboarding_status = UserProfile.PENDING_VERIFICATION
        self.profile.save()
        self.make_dl(status=DriverVerification.PENDING, attempt_count=1,
                     dl_verification_ref='old-ref')

        self.assertSuccess(self.submit(), 202)

        record = self.dl()
        self.assertEqual(record.attempt_count, 2)
        self.assertEqual(record.dl_verification_ref, f'ref-pending-{self.user.id}')


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False, DL_ADAPTER_CLASS=path(FixedReferenceAdapter))
class DuplicateProviderReferenceTests(DLSubmitTestCase):
    """KNOWN BUG (asserted as-is, not fixed here).

    ``DriverVerification.dl_verification_ref`` is unique when set. If the provider
    returns a reference already held by another user's record, the insert in
    ``profiles/services/dl_verification.py:160`` raises ``IntegrityError`` and the client
    receives ``500 server_error`` — FR-60 requires a non-timeout provider problem to
    surface as ``422 dl_verification_provider_error`` and never a 500. The RC service
    guards against exactly this (``profiles/services/rc_verification.py:155-165``,
    ``_save_vehicle``); the DL service has no equivalent. The surrounding transaction
    rolls back, so no attempt is consumed and the onboarding status is unchanged.
    """

    def test_first_user_succeeds(self):
        self.assertSuccess(self.submit(), 202)

        self.assertEqual(self.dl().dl_verification_ref, 'SHARED-REF')

    def test_second_user_with_the_same_reference_gets_500_today(self):
        first = self.make_user()
        self.make_named_profile(
            first, active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.AWAITING_DL,
        )
        self.client.force_authenticate(user=first)
        self.assertSuccess(self.submit(), 202)
        self.client.force_authenticate(user=self.user)

        with self.assertLogs('core', level='ERROR'):
            response = self.submit()

        self.assertApiError(response, 500, 'server_error')
        # Nothing was persisted for the second user.
        self.assertFalse(DriverVerification.objects.filter(user=self.user).exists())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_DL)


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False, DL_ADAPTER_CLASS=path(VerifyingAdapter))
class DLSubmitAttemptCapTests(DLSubmitTestCase):
    """FR-13 / FR-61: the cap is on total submissions and is enforced under the lock."""

    @override_settings(DL_MAX_ATTEMPTS=1)
    def test_first_attempt_is_allowed_when_the_cap_is_one(self):
        self.assertSuccess(self.submit(), 200)

        self.assertEqual(self.dl().attempt_count, 1)
        self.assertEqual(_CountingAdapter.calls, 1)

    @override_settings(DL_MAX_ATTEMPTS=1)
    def test_second_attempt_is_refused_when_the_cap_is_one(self):
        self.make_dl(status=DriverVerification.REJECTED, attempt_count=1)

        with self.assertLogs('profiles', level='WARNING'):
            response = self.submit()

        self.assertApiError(response, 429, 'max_dl_attempts_exceeded')
        self.assertEqual(_CountingAdapter.calls, 0)
        self.assertEqual(self.dl().attempt_count, 1)

    @override_settings(DL_MAX_ATTEMPTS=3)
    def test_third_attempt_is_allowed_when_the_cap_is_three(self):
        self.make_dl(status=DriverVerification.REJECTED, attempt_count=2)

        self.assertSuccess(self.submit(), 200)

        self.assertEqual(self.dl().attempt_count, 3)

    @override_settings(DL_MAX_ATTEMPTS=3)
    def test_fourth_attempt_is_refused_without_calling_the_provider(self):
        self.make_dl(status=DriverVerification.REJECTED, attempt_count=3)

        with self.assertLogs('profiles', level='WARNING'):
            response = self.submit()

        self.assertApiError(response, 429, 'max_dl_attempts_exceeded')
        self.assertEqual(_CountingAdapter.calls, 0)
        record = self.dl()
        self.assertEqual(record.attempt_count, 3)
        self.assertEqual(record.dl_verification_status, DriverVerification.REJECTED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_DL)

    @override_settings(DL_MAX_ATTEMPTS=3, DL_ADAPTER_CLASS=path(RaceAdapter))
    def test_cap_is_re_checked_under_the_lock_after_the_provider_call(self):
        # A competing submission that lands while the provider is being called must not
        # be able to push the count past the cap: phase 3 re-validates under the lock.
        record = self.make_dl(status=DriverVerification.REJECTED, attempt_count=1)

        with self.assertLogs('profiles', level='WARNING'):
            response = self.submit()

        self.assertApiError(response, 429, 'max_dl_attempts_exceeded')
        record.refresh_from_db()
        self.assertEqual(record.attempt_count, 99)
        self.assertEqual(record.dl_verification_status, DriverVerification.REJECTED)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_DL)

    @override_settings(DL_MAX_ATTEMPTS=3)
    def test_attempt_cap_survives_a_role_round_trip(self):
        # FR-13 / v8 edge case: switching to passenger and back does not reset attempts.
        self.make_dl(status=DriverVerification.REJECTED, attempt_count=3)
        self.client.patch('/api/profile/role/', {'role': 'passenger'}, format='json')
        self.client.patch('/api/profile/role/', {'role': 'driver'}, format='json')

        with self.assertLogs('profiles', level='WARNING'):
            response = self.submit()

        self.assertApiError(response, 429, 'max_dl_attempts_exceeded')


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False, DL_ADAPTER_CLASS=path(VerifyingAdapter))
class DLSubmitValidationTests(DLSubmitTestCase):
    def test_malformed_dl_number_is_400_invalid_request(self):
        # KD-01: the contract says invalid_dl_format; the serializer error is rendered
        # by the shared handler as invalid_request with per-field messages.
        response = self.submit('ABCD1234')

        error = self.assertApiError(response, 400, 'invalid_request')
        self.assertIn('dl_number', error['fields'])
        self.assertIn('Invalid DL format', error['detail'])
        self.assertEqual(_CountingAdapter.calls, 0)
        self.assertFalse(DriverVerification.objects.filter(user=self.user).exists())

    def test_blank_dl_number_is_400_invalid_request(self):
        response = self.submit('')

        self.assertApiError(response, 400, 'invalid_request')
        self.assertEqual(_CountingAdapter.calls, 0)

    def test_missing_dl_number_is_400_invalid_request(self):
        response = self.client.post(URL_DL, {}, format='json')

        error = self.assertApiError(response, 400, 'invalid_request')
        self.assertIn('dl_number', error['fields'])

    def test_over_long_dl_number_is_400_invalid_request(self):
        response = self.submit('M' * 21)

        self.assertApiError(response, 400, 'invalid_request')
        self.assertEqual(_CountingAdapter.calls, 0)

    def test_too_short_and_too_long_digits_are_rejected(self):
        for bad in ['MH01201100123', 'MH012011001234567', '12345678901234']:
            with self.subTest(dl=bad):
                self.assertApiError(self.submit(bad), 400, 'invalid_request')


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False, DL_ADAPTER_CLASS=path(VerifyingAdapter))
class DLSubmitAccessTests(DLSubmitTestCase):
    def test_passenger_is_denied(self):
        self.make_named_profile(
            active_role=UserProfile.PASSENGER, onboarding_status=UserProfile.COMPLETE,
        )

        response = self.submit()

        # KD-03: IsDriverRole denies with DRF's generic code, not not_a_driver.
        self.assertApiError(response, 403, 'permission_denied')
        self.assertEqual(_CountingAdapter.calls, 0)

    def test_user_without_a_profile_is_denied(self):
        UserProfile.objects.filter(user=self.user).delete()

        self.assertApiError(self.submit(), 403, 'permission_denied')

    def test_unauthenticated_request_is_401(self):
        self.client.force_authenticate(user=None)

        self.assertApiError(self.submit(), 401, 'not_authenticated')

    def test_role_selected_driver_is_400_invalid_onboarding_state(self):
        self.profile.onboarding_status = UserProfile.ROLE_SELECTED
        self.profile.save()

        self.assertApiError(self.submit(), 400, 'invalid_onboarding_state')
        self.assertEqual(_CountingAdapter.calls, 0)

    def test_complete_driver_with_a_verified_dl_is_400_not_409(self):
        # KD-07: the status check runs before the dl-already-verified check.
        self.make_dl(status=DriverVerification.VERIFIED)
        self.profile.onboarding_status = UserProfile.COMPLETE
        self.profile.save()

        self.assertApiError(self.submit(), 400, 'invalid_onboarding_state')

    def test_verified_dl_in_awaiting_dl_is_409_dl_already_verified(self):
        # KD-07: the 409 is reachable only from awaiting_dl / pending_verification.
        self.make_dl(status=DriverVerification.VERIFIED)

        self.assertApiError(self.submit(), 409, 'dl_already_verified')
        self.assertEqual(_CountingAdapter.calls, 0)


class DLStatusEndpointTests(DLSubmitTestCase):
    def test_returns_status_reason_and_display_digits(self):
        self.profile.onboarding_status = UserProfile.PENDING_VERIFICATION
        self.profile.save()
        self.make_dl(status=DriverVerification.PENDING, dl_number_display='2345')

        data = self.assertSuccess(self.client.get(URL_DL_STATUS), 200)

        self.assertEqual(data, {
            'dl_verification_status': 'pending',
            'onboarding_status': 'pending_verification',
            'rejection_reason': None,
            'dl_number_display': '2345',
        })

    def test_rejection_reason_is_exposed_when_rejected(self):
        self.make_dl(status=DriverVerification.REJECTED, dl_rejection_reason='Licence not found')

        data = self.assertSuccess(self.client.get(URL_DL_STATUS), 200)

        self.assertEqual(data['dl_verification_status'], 'rejected')
        self.assertEqual(data['rejection_reason'], 'Licence not found')

    def test_never_exposes_the_dl_number(self):
        self.make_dl(status=DriverVerification.VERIFIED, dl_number='super-secret-ciphertext')

        response = self.client.get(URL_DL_STATUS)

        self.assertNotIn('super-secret-ciphertext', response.content.decode())
        self.assertNotIn('dl_number"', response.content.decode())

    def test_driver_without_a_dl_record_is_403_not_a_driver(self):
        # KD-03: on this endpoint a driver with no DL row gets not_a_driver.
        self.assertApiError(self.client.get(URL_DL_STATUS), 403, 'not_a_driver')

    def test_passenger_is_403_permission_denied(self):
        self.make_named_profile(
            active_role=UserProfile.PASSENGER, onboarding_status=UserProfile.COMPLETE,
        )

        self.assertApiError(self.client.get(URL_DL_STATUS), 403, 'permission_denied')


@override_settings(DL_MOCK_ADAPTER_FORBIDDEN=False, DL_ADAPTER_CLASS=MOCK_DL_ADAPTER)
class MockDLAdapterModeTests(DLSubmitTestCase):
    """FR-61: the shipped mock adapter's three modes."""

    @override_settings(DL_ADAPTER_MOCK_RESULT='sync_verified')
    def test_sync_verified(self):
        data = self.assertSuccess(self.submit(), 200)

        self.assertEqual(data['dl_verification_status'], 'verified')
        self.assertTrue(data['reference_id'].startswith('mock-'))

    @override_settings(DL_ADAPTER_MOCK_RESULT='async_pending')
    def test_async_pending(self):
        data = self.assertSuccess(self.submit(), 202)

        self.assertEqual(data['dl_verification_status'], 'pending')
        self.assertTrue(data['reference_id'].startswith('mock-'))

    @override_settings(DL_ADAPTER_MOCK_RESULT='sync_rejected')
    def test_sync_rejected(self):
        data = self.assertSuccess(self.submit(), 202)

        self.assertEqual(data['dl_verification_status'], 'rejected')
        self.assertEqual(self.dl().dl_rejection_reason, 'Mock rejection for testing')
