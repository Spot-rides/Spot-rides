"""Vehicle RC verification with the flag ON (FEAT-002 FR-33..FR-50, FR-56, FR-57).

Covers all six mock modes, the attempt cap, row reuse on resubmission, the RC webhook
and the handling of the third-party owner name (never exposed, cleared on resolution).
"""

from django.test import override_settings

from profiles.adapters import RCAdapterError, RCVerificationAdapter, RCVerificationResult
from profiles.models import DriverVerification, UserProfile, Vehicle
from profiles.services.rc_verification import resolve_rc_review

from .helpers import (
    MOCK_RC_ADAPTER,
    TEST_WEBHOOK_SECRET,
    URL_STATUS,
    URL_VEHICLE,
    URL_VEHICLE_STATUS,
    VALID_REG,
    OnboardingTestCase,
)


class StubRCAdapter(RCVerificationAdapter):
    """Adapter whose next result is set by the test (class attributes)."""

    result = None
    raises = None
    calls = 0

    def __init__(self):
        super().__init__(timeout_seconds=1)

    @classmethod
    def from_settings(cls, settings):
        return cls()

    @classmethod
    def reset(cls):
        cls.result = None
        cls.raises = None
        cls.calls = 0

    def verify(self, registration_number, user_id):
        StubRCAdapter.calls += 1
        if StubRCAdapter.raises is not None:
            raise StubRCAdapter.raises
        return StubRCAdapter.result

    def validate_webhook(self, headers, body):
        return True

    def parse_webhook(self, body):
        raise RCAdapterError('not used')


STUB_RC = f'{__name__}.StubRCAdapter'

RC_ON = dict(
    RC_VERIFICATION_ENABLED=True,
    RC_MOCK_ADAPTER_FORBIDDEN=False,
    RC_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET,
)


class RCTestCase(OnboardingTestCase):
    def setUp(self):
        super().setUp()
        StubRCAdapter.reset()
        self.profile = self.driver_awaiting_vehicle()

    def register(self, registration_number=VALID_REG, vehicle_type='sedan'):
        return self.client.post(
            URL_VEHICLE,
            {'registration_number': registration_number, 'vehicle_type': vehicle_type},
            format='json',
        )

    def vehicle(self):
        return Vehicle.objects.get(user=self.user)


@override_settings(**RC_ON, RC_ADAPTER_CLASS=MOCK_RC_ADAPTER)
class MockRCAdapterModeTests(RCTestCase):
    """FR-49: every mock mode and the status / HTTP code it produces."""

    @override_settings(RC_ADAPTER_MOCK_RESULT='sync_verified')
    def test_sync_verified_completes_onboarding(self):
        data = self.assertSuccess(self.register(), 200)

        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertEqual(data['next_step'], 'none')
        self.assertEqual(data['rc_verification_status'], 'verified')
        self.assertIsNone(data['rejection_reason'])
        self.assertTrue(data['reference_id'].startswith('mock-rc-'))
        vehicle = self.vehicle()
        self.assertEqual(vehicle.rc_verification_status, Vehicle.RC_VERIFIED)
        self.assertEqual(vehicle.rc_name_match, Vehicle.NAME_MATCH)
        self.assertEqual(vehicle.rc_attempt_count, 1)
        self.assertIsNone(vehicle.rc_owner_name)
        self.assertIsNotNone(vehicle.rc_verified_at)

    @override_settings(RC_ADAPTER_MOCK_RESULT='sync_verified_name_mismatch')
    def test_name_mismatch_goes_to_review_without_saying_so(self):
        data = self.assertSuccess(self.register(), 202)

        self.assertEqual(data['onboarding_status'], 'pending_rc_verification')
        self.assertEqual(data['next_step'], 'awaiting_rc_verification')
        self.assertEqual(data['rc_verification_status'], 'pending')
        self.assertIsNone(data['rejection_reason'])
        vehicle = self.vehicle()
        self.assertEqual(vehicle.rc_verification_status, Vehicle.RC_PENDING)
        self.assertEqual(vehicle.rc_name_match, Vehicle.NAME_MISMATCH)
        # FR-38 / FR-47: the owner name is kept for staff review but never returned.
        self.assertEqual(vehicle.rc_owner_name, 'MOCK OTHER OWNER')

    @override_settings(RC_ADAPTER_MOCK_RESULT='sync_verified_name_mismatch')
    def test_owner_name_is_absent_from_every_driver_facing_response(self):
        register = self.register()
        status_response = self.client.get(URL_VEHICLE_STATUS)
        onboarding_response = self.client.get(URL_STATUS)

        for response in (register, status_response, onboarding_response):
            body = response.content.decode()
            self.assertNotIn('MOCK OTHER OWNER', body)
            self.assertNotIn('owner', body.lower())

    @override_settings(RC_ADAPTER_MOCK_RESULT='async_pending')
    def test_async_pending(self):
        data = self.assertSuccess(self.register(), 202)

        self.assertEqual(data['onboarding_status'], 'pending_rc_verification')
        self.assertEqual(data['rc_verification_status'], 'pending')
        self.assertTrue(data['reference_id'].startswith('mock-rc-'))
        self.assertEqual(self.vehicle().rc_attempt_count, 1)

    @override_settings(RC_ADAPTER_MOCK_RESULT='sync_rejected')
    def test_sync_rejected_is_422_with_the_recovery_data(self):
        response = self.register()

        error = self.assertApiError(
            response, 422, 'rc_verification_rejected',
            onboarding_status='awaiting_vehicle',
            next_step='vehicle_registration',
            rc_verification_status='rejected',
            rc_attempts_remaining=2,
        )
        self.assertEqual(error['detail'], 'Mock rejection for testing')
        vehicle = self.vehicle()
        self.assertEqual(vehicle.rc_verification_status, Vehicle.RC_REJECTED)
        self.assertEqual(vehicle.rc_attempt_count, 1)
        self.assertIsNone(vehicle.rc_owner_name)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)

    @override_settings(RC_ADAPTER_MOCK_RESULT='timeout')
    def test_timeout_is_treated_as_pending_and_consumes_an_attempt(self):
        data = self.assertSuccess(self.register(), 202)

        self.assertEqual(data['onboarding_status'], 'pending_rc_verification')
        self.assertEqual(data['rc_verification_status'], 'pending')
        self.assertIsNone(data['reference_id'])
        self.assertEqual(self.vehicle().rc_attempt_count, 1)

    @override_settings(RC_ADAPTER_MOCK_RESULT='provider_error')
    def test_provider_error_is_422_and_consumes_no_attempt(self):
        with self.assertLogs('profiles', level='ERROR'):
            response = self.register()

        self.assertApiError(response, 422, 'rc_verification_provider_error')
        self.assertFalse(Vehicle.objects.filter(user=self.user).exists())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)


@override_settings(**RC_ON, RC_ADAPTER_CLASS=STUB_RC)
class RCDecisionTests(RCTestCase):
    def test_verified_with_a_matching_owner_name_completes(self):
        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-1', owner_name='Priya Sharma',
        )

        data = self.assertSuccess(self.register(), 200)

        self.assertEqual(data['rc_verification_status'], 'verified')
        self.assertEqual(self.vehicle().rc_name_match, Vehicle.NAME_MATCH)

    def test_verified_with_a_masked_owner_name_goes_to_review(self):
        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-2', owner_name='PRIYA XXXXXX',
        )

        data = self.assertSuccess(self.register(), 202)

        self.assertEqual(data['rc_verification_status'], 'pending')
        self.assertEqual(self.vehicle().rc_name_match, Vehicle.NAME_NOT_CHECKED)

    def test_class_conflict_is_rejected(self):
        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-3', owner_name='Priya Sharma',
            vehicle_class='MOTOR CYCLE',
        )

        error = self.assertApiError(self.register(vehicle_type='sedan'), 422,
                                    'rc_verification_rejected')

        self.assertEqual(
            error['detail'],
            'The vehicle type does not match the registration certificate.',
        )
        self.assertEqual(self.vehicle().rc_verification_status, Vehicle.RC_REJECTED)

    def test_unknown_vehicle_class_does_not_reject(self):
        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-4', owner_name='Priya Sharma',
            vehicle_class='SOMETHING UNMAPPED',
        )

        data = self.assertSuccess(self.register(), 200)

        self.assertEqual(data['rc_verification_status'], 'verified')

    def test_informational_dates_are_stored_but_never_block(self):
        from datetime import date

        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-5', owner_name='Priya Sharma',
            fuel_type='PETROL',
            fitness_valid_upto=date(2000, 1, 1), insurance_valid_upto=date(2000, 1, 1),
        )

        data = self.assertSuccess(self.register(), 200)

        self.assertEqual(data['onboarding_status'], 'complete')
        vehicle = self.vehicle()
        self.assertEqual(vehicle.rc_fitness_valid_upto, date(2000, 1, 1))
        self.assertEqual(vehicle.rc_insurance_valid_upto, date(2000, 1, 1))
        self.assertEqual(vehicle.rc_fuel_type, 'PETROL')

    def test_rejection_reason_is_sanitised_and_truncated(self):
        StubRCAdapter.result = RCVerificationResult(
            status='rejected', reference_id='rc-6',
            rejection_reason='<script>x</script> ' + 'A' * 600,
        )

        error = self.assertApiError(self.register(), 422, 'rc_verification_rejected')

        self.assertNotIn('<script>', error['detail'])
        self.assertLessEqual(len(error['detail']), 500)

    def test_unrecognised_provider_status_is_a_provider_error(self):
        StubRCAdapter.result = RCVerificationResult(status='maybe', reference_id='rc-7')

        with self.assertLogs('profiles', level='ERROR'):
            response = self.register()

        self.assertApiError(response, 422, 'rc_verification_provider_error')
        self.assertFalse(Vehicle.objects.filter(user=self.user).exists())


@override_settings(**RC_ON, RC_ADAPTER_CLASS=STUB_RC)
class RCResubmissionAndAttemptCapTests(RCTestCase):
    def _reject_once(self, reason='first rejection'):
        StubRCAdapter.result = RCVerificationResult(
            status='rejected', reference_id=None, rejection_reason=reason,
        )
        return self.register()

    def test_resubmission_after_rejection_reuses_the_same_row(self):
        self._reject_once()
        vehicle_id = self.vehicle().pk

        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-ok', owner_name='Priya Sharma',
        )
        data = self.assertSuccess(self.register('MH01CD5678', 'car'), 200)

        self.assertEqual(Vehicle.objects.filter(user=self.user).count(), 1)
        vehicle = self.vehicle()
        self.assertEqual(vehicle.pk, vehicle_id)
        self.assertEqual(vehicle.registration_number, 'MH01CD5678')
        self.assertEqual(vehicle.vehicle_type, 'CAR')
        self.assertEqual(vehicle.rc_attempt_count, 2)
        self.assertEqual(data['rejection_reason'], None)
        self.assertIsNone(vehicle.rc_rejection_reason)

    @override_settings(RC_MAX_ATTEMPTS=1)
    def test_cap_of_one_refuses_the_second_submission(self):
        self._reject_once()

        with self.assertLogs('profiles', level='WARNING'):
            response = self.register()

        self.assertApiError(response, 429, 'max_rc_attempts_exceeded')
        self.assertEqual(self.vehicle().rc_attempt_count, 1)

    @override_settings(RC_MAX_ATTEMPTS=3)
    def test_cap_of_three_refuses_the_fourth_submission(self):
        Vehicle.objects.create(
            user=self.user, registration_number=VALID_REG, vehicle_type='SEDAN',
            is_active=True, rc_verification_status=Vehicle.RC_REJECTED, rc_attempt_count=3,
        )

        with self.assertLogs('profiles', level='WARNING'):
            response = self.register()

        self.assertApiError(response, 429, 'max_rc_attempts_exceeded')
        self.assertEqual(StubRCAdapter.calls, 0)

    @override_settings(RC_MAX_ATTEMPTS=3)
    def test_attempts_remaining_is_reported_on_rejection(self):
        self._reject_once()

        error = self.assertApiError(self._reject_once(), 422, 'rc_verification_rejected',
                                    rc_attempts_remaining=1)

        self.assertEqual(error['rc_attempts_remaining'], 1)

    def test_pending_rc_verification_blocks_a_new_submission(self):
        StubRCAdapter.result = RCVerificationResult(status='pending', reference_id='rc-p')
        self.assertSuccess(self.register(), 202)

        self.assertApiError(self.register(), 409, 'rc_verification_pending')

    def test_verified_vehicle_blocks_a_new_submission(self):
        StubRCAdapter.result = RCVerificationResult(
            status='verified', reference_id='rc-v', owner_name='Priya Sharma',
        )
        self.assertSuccess(self.register(), 200)

        self.assertApiError(self.register(), 409, 'rc_already_verified')

    def test_complete_driver_with_a_legacy_vehicle_gets_vehicle_already_registered(self):
        self.make_profile(
            active_role=UserProfile.DRIVER, onboarding_status=UserProfile.COMPLETE,
            first_name='Priya', last_name='Sharma', age=27, gender='female',
        )
        self.make_vehicle(rc_verification_status=None)

        self.assertApiError(self.register(), 409, 'vehicle_already_registered')


@override_settings(**RC_ON, RC_ADAPTER_CLASS=MOCK_RC_ADAPTER,
                   RC_ADAPTER_MOCK_RESULT='async_pending', RC_MAX_ATTEMPTS=3)
class RCVehicleStatusTests(RCTestCase):
    def test_pending_status_is_reported_with_attempts_remaining(self):
        self.assertSuccess(self.register(), 202)

        data = self.assertSuccess(self.client.get(URL_VEHICLE_STATUS), 200)

        self.assertEqual(data['onboarding_status'], 'pending_rc_verification')
        self.assertEqual(data['next_step'], 'awaiting_rc_verification')
        self.assertEqual(data['rc_verification_status'], 'pending')
        self.assertIsNone(data['rejection_reason'])
        self.assertEqual(data['registration_number'], VALID_REG)
        self.assertEqual(data['vehicle_type'], 'SEDAN')
        self.assertEqual(data['rc_attempts_remaining'], 2)

    @override_settings(RC_ADAPTER_MOCK_RESULT='sync_rejected')
    def test_rejected_status_exposes_the_sanitised_reason(self):
        self.assertApiError(self.register(), 422, 'rc_verification_rejected')

        data = self.assertSuccess(self.client.get(URL_VEHICLE_STATUS), 200)

        self.assertEqual(data['rc_verification_status'], 'rejected')
        self.assertEqual(data['rejection_reason'], 'Mock rejection for testing')
        self.assertEqual(data['onboarding_status'], 'awaiting_vehicle')

    def test_onboarding_status_endpoint_reports_the_rc_status(self):
        self.assertSuccess(self.register(), 202)

        data = self.assertSuccess(self.client.get(URL_STATUS), 200)

        self.assertEqual(data['onboarding_status'], 'pending_rc_verification')
        self.assertEqual(data['next_step'], 'awaiting_rc_verification')
        self.assertEqual(data['rc_verification_status'], 'pending')


@override_settings(**RC_ON, RC_ADAPTER_CLASS=MOCK_RC_ADAPTER)
class RCWebhookTests(RCTestCase):
    def setUp(self):
        super().setUp()
        self.profile.onboarding_status = UserProfile.PENDING_RC_VERIFICATION
        self.profile.save()
        self.vehicle_row = self.make_vehicle(
            rc_verification_status=Vehicle.RC_PENDING, rc_verification_ref='rc-ref-1',
            rc_attempt_count=1, rc_owner_name='MOCK OTHER OWNER',
            rc_name_match=Vehicle.NAME_MISMATCH,
        )

    def assertUnchanged(self):
        self.vehicle_row.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle_row.rc_verification_status, Vehicle.RC_PENDING)
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_RC_VERIFICATION)

    def test_valid_signature_verified_result_completes_the_driver(self):
        response = self.post_rc_webhook({'reference_id': 'rc-ref-1', 'status': 'verified',
                                         'owner_name': 'Priya Sharma'})

        self.assertSuccess(response, 200)
        self.vehicle_row.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle_row.rc_verification_status, Vehicle.RC_VERIFIED)
        self.assertEqual(self.profile.onboarding_status, UserProfile.COMPLETE)
        # F-07: the owner name is purged on every terminal transition.
        self.assertIsNone(self.vehicle_row.rc_owner_name)

    def test_valid_signature_rejected_result_returns_the_driver_to_the_vehicle_step(self):
        response = self.post_rc_webhook({
            'reference_id': 'rc-ref-1', 'status': 'rejected',
            'rejection_reason': '<b>Blacklisted</b> vehicle',
        })

        self.assertSuccess(response, 200)
        self.vehicle_row.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle_row.rc_verification_status, Vehicle.RC_REJECTED)
        self.assertEqual(self.vehicle_row.rc_rejection_reason, 'Blacklisted vehicle')
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)
        self.assertIsNone(self.vehicle_row.rc_owner_name)

    def test_missing_signature_is_403_and_changes_nothing(self):
        with self.assertLogs('profiles', level='WARNING'):
            response = self.post_rc_webhook(
                {'reference_id': 'rc-ref-1', 'status': 'verified'}, header_present=False,
            )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_wrong_key_signature_is_403_and_changes_nothing(self):
        with self.assertLogs('profiles', level='WARNING'):
            response = self.post_rc_webhook(
                {'reference_id': 'rc-ref-1', 'status': 'verified'}, secret='wrong',
            )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_signature_is_checked_before_the_payload_and_the_database(self):
        # Unknown reference and malformed body, unsigned: still a 403.
        with self.assertLogs('profiles', level='WARNING'):
            response = self.client.post(
                '/api/onboarding/driver/vehicle/rc/webhook/', data=b'{not json',
                content_type='application/json',
            )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    @override_settings(RC_WEBHOOK_SECRET='')
    def test_empty_secret_rejects_every_delivery(self):
        with self.assertLogs('profiles', level='WARNING'):
            response = self.post_rc_webhook(
                {'reference_id': 'rc-ref-1', 'status': 'verified'}, secret='',
            )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_unknown_reference_is_404_rc_reference_not_found(self):
        with self.assertLogs('profiles', level='WARNING'):
            response = self.post_rc_webhook({'reference_id': 'nope', 'status': 'verified'})

        self.assertApiError(response, 404, 'rc_reference_not_found')
        self.assertUnchanged()

    def test_duplicate_delivery_is_409_already_processed(self):
        self.post_rc_webhook({'reference_id': 'rc-ref-1', 'status': 'verified',
                              'owner_name': 'Priya Sharma'})

        with self.assertLogs('profiles', level='WARNING'):
            response = self.post_rc_webhook({'reference_id': 'rc-ref-1', 'status': 'rejected'})

        # FR-42: unlike the DL webhook, the RC webhook keeps 409 already_processed.
        self.assertApiError(response, 409, 'already_processed')
        self.vehicle_row.refresh_from_db()
        self.assertEqual(self.vehicle_row.rc_verification_status, Vehicle.RC_VERIFIED)

    def test_malformed_payload_is_400_invalid_webhook_payload(self):
        response = self.post_rc_webhook({'reference_id': 'rc-ref-1', 'status': 'maybe'})

        self.assertApiError(response, 400, 'invalid_webhook_payload')
        self.assertUnchanged()

    def test_blank_reference_is_400_invalid_webhook_payload(self):
        response = self.post_rc_webhook({'reference_id': '', 'status': 'verified'})

        self.assertApiError(response, 400, 'invalid_webhook_payload')
        self.assertUnchanged()


@override_settings(**RC_ON, RC_ADAPTER_CLASS=MOCK_RC_ADAPTER)
class RCStaffReviewTests(RCTestCase):
    """FR-44 / F-07 at the service level (the admin wiring is covered in test_admin)."""

    def setUp(self):
        super().setUp()
        self.profile.onboarding_status = UserProfile.PENDING_RC_VERIFICATION
        self.profile.save()
        self.staff = self.make_user()
        self.vehicle_row = self.make_vehicle(
            rc_verification_status=Vehicle.RC_PENDING, rc_owner_name='MOCK OTHER OWNER',
            rc_name_match=Vehicle.NAME_MISMATCH, rc_attempt_count=2,
        )

    def test_approve_completes_the_driver_and_clears_the_owner_name(self):
        resolve_rc_review(self.vehicle_row.pk, approve=True, reason=None, staff_user=self.staff)

        self.vehicle_row.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle_row.rc_verification_status, Vehicle.RC_VERIFIED)
        self.assertIsNone(self.vehicle_row.rc_owner_name)
        self.assertEqual(self.profile.onboarding_status, UserProfile.COMPLETE)

    def test_reject_returns_the_driver_to_the_vehicle_step_and_clears_the_owner_name(self):
        resolve_rc_review(
            self.vehicle_row.pk, approve=False, reason='Papers do not match',
            staff_user=self.staff,
        )

        self.vehicle_row.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle_row.rc_verification_status, Vehicle.RC_REJECTED)
        self.assertEqual(self.vehicle_row.rc_rejection_reason, 'Papers do not match')
        self.assertIsNone(self.vehicle_row.rc_owner_name)
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)

    def test_reject_redacts_the_owner_name_from_the_staff_reason(self):
        resolve_rc_review(
            self.vehicle_row.pk, approve=False,
            reason='Owner MOCK OTHER OWNER is not the driver', staff_user=self.staff,
        )

        self.vehicle_row.refresh_from_db()
        self.assertNotIn('MOCK OTHER OWNER', self.vehicle_row.rc_rejection_reason)
        self.assertIn('[redacted]', self.vehicle_row.rc_rejection_reason)
