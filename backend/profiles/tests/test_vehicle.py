"""Vehicle registration with RC verification OFF (FEAT-002 FR-27..FR-32, FR-51..FR-56).

The flag-off completion rule is the product's hard rule: vehicle registration must
finish onboarding, no RC adapter may be consulted, and no RC state may be written.
"""

from django.test import override_settings

from profiles.adapters import RCAdapterError, RCVerificationAdapter, RCVerificationResult
from profiles.models import DriverVerification, UserProfile, Vehicle

from .helpers import (
    MOCK_DL_ADAPTER,
    TEST_WEBHOOK_SECRET,
    URL_DL,
    URL_PROFILE,
    URL_ROLE,
    URL_STATUS,
    URL_VEHICLE,
    URL_VEHICLE_STATUS,
    VALID_DL,
    VALID_REG,
    OnboardingTestCase,
)


class _FlagOffTripwireAdapter(RCVerificationAdapter):
    """Any use of this adapter while the flag is off is a failure of FR-32."""

    used = False

    def __init__(self, **kwargs):
        super().__init__(timeout_seconds=1)

    @classmethod
    def from_settings(cls, settings):
        _FlagOffTripwireAdapter.used = True
        return cls()

    def verify(self, registration_number, user_id):
        _FlagOffTripwireAdapter.used = True
        raise RCAdapterError('the adapter must not be called while the flag is off')

    def validate_webhook(self, headers, body):
        _FlagOffTripwireAdapter.used = True
        return True

    def parse_webhook(self, body):
        _FlagOffTripwireAdapter.used = True
        return RCVerificationResult(status='verified', reference_id='tripwire')


class RejectingRCAdapter(_FlagOffTripwireAdapter):
    def verify(self, registration_number, user_id):
        _FlagOffTripwireAdapter.used = True
        return RCVerificationResult(
            status='rejected', reference_id='rc-ref', rejection_reason='nope',
        )


TRIPWIRE = f'{__name__}._FlagOffTripwireAdapter'
REJECTING = f'{__name__}.RejectingRCAdapter'


@override_settings(RC_VERIFICATION_ENABLED=False)
class VehicleRegistrationFlagOffTests(OnboardingTestCase):
    def setUp(self):
        super().setUp()
        _FlagOffTripwireAdapter.used = False
        self.profile = self.driver_awaiting_vehicle()

    def register(self, registration_number=VALID_REG, vehicle_type='sedan'):
        return self.client.post(
            URL_VEHICLE,
            {'registration_number': registration_number, 'vehicle_type': vehicle_type},
            format='json',
        )

    def test_registration_completes_onboarding(self):
        response = self.register()

        data = self.assertSuccess(response, 200)
        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertEqual(data['next_step'], 'none')
        self.assertEqual(data['vehicle'], {
            'registration_number': VALID_REG,
            'vehicle_type': 'SEDAN',  # FR-53: returned uppercase
        })
        self.assertIsNone(data['rc_verification_status'])
        self.assertIsNone(data['rejection_reason'])
        self.assertIsNone(data['reference_id'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.COMPLETE)

    def test_no_rc_state_is_written(self):
        self.register()

        vehicle = Vehicle.objects.get(user=self.user)
        self.assertIsNone(vehicle.rc_verification_status)
        self.assertIsNone(vehicle.rc_verification_ref)
        self.assertIsNone(vehicle.rc_name_match)
        self.assertIsNone(vehicle.rc_owner_name)
        self.assertEqual(vehicle.rc_attempt_count, 0)
        self.assertTrue(vehicle.is_active)

    @override_settings(RC_ADAPTER_CLASS=TRIPWIRE, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_a_raising_rc_adapter_cannot_affect_the_flag_off_flow(self):
        data = self.assertSuccess(self.register(), 200)

        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertEqual(data['next_step'], 'none')
        self.assertIsNone(data['rc_verification_status'])
        self.assertFalse(_FlagOffTripwireAdapter.used)

    @override_settings(RC_ADAPTER_CLASS=REJECTING, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_a_rejecting_rc_adapter_cannot_affect_the_flag_off_flow(self):
        data = self.assertSuccess(self.register(), 200)

        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertIsNone(data['rc_verification_status'])
        self.assertFalse(_FlagOffTripwireAdapter.used)

    def test_registration_number_is_normalised(self):
        data = self.assertSuccess(self.register('mh 01-ab 1234'), 200)

        self.assertEqual(data['vehicle']['registration_number'], VALID_REG)

    def test_every_vehicle_type_is_accepted_and_returned_uppercase(self):
        types = ['car', 'suv', 'hatchback', 'sedan', 'auto_rickshaw', 'bike']
        for index, vehicle_type in enumerate(types):
            with self.subTest(vehicle_type=vehicle_type):
                user = self.make_user()
                self.driver_awaiting_vehicle(user)
                self.client.force_authenticate(user=user)

                response = self.client.post(
                    URL_VEHICLE,
                    {'registration_number': f'MH01AB{1000 + index}',
                     'vehicle_type': vehicle_type},
                    format='json',
                )

                data = self.assertSuccess(response, 200)
                self.assertEqual(data['vehicle']['vehicle_type'], vehicle_type.upper())

    # ------------------------------------------------------------------ errors

    def test_invalid_registration_format(self):
        response = self.register('XX1')

        self.assertApiError(response, 400, 'invalid_registration_format')
        self.assertFalse(Vehicle.objects.filter(user=self.user).exists())

    def test_missing_registration_number_maps_to_the_format_error(self):
        response = self.client.post(URL_VEHICLE, {'vehicle_type': 'sedan'}, format='json')

        self.assertApiError(response, 400, 'invalid_registration_format')

    def test_invalid_vehicle_type(self):
        response = self.register(vehicle_type='spaceship')

        self.assertApiError(response, 400, 'invalid_vehicle_type')
        self.assertFalse(Vehicle.objects.filter(user=self.user).exists())

    def test_missing_vehicle_type(self):
        response = self.client.post(
            URL_VEHICLE, {'registration_number': VALID_REG}, format='json',
        )

        self.assertApiError(response, 400, 'invalid_vehicle_type')

    def test_passenger_is_403_not_a_driver(self):
        self.passenger_complete()

        self.assertApiError(self.register(), 403, 'not_a_driver')

    def test_driver_without_a_verified_dl_is_403_dl_not_verified(self):
        self.make_named_profile(
            active_role=UserProfile.DRIVER, onboarding_status=UserProfile.AWAITING_DL,
        )

        self.assertApiError(self.register(), 403, 'dl_not_verified')

    def test_driver_with_a_pending_dl_is_403_dl_not_verified(self):
        self.make_named_profile(
            active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.PENDING_VERIFICATION,
        )
        self.make_dl(status=DriverVerification.PENDING)

        self.assertApiError(self.register(), 403, 'dl_not_verified')

    def test_complete_driver_posting_again_is_409_vehicle_already_registered(self):
        self.register()

        response = self.register('MH01AB9999')

        self.assertApiError(response, 409, 'vehicle_already_registered')
        self.assertEqual(Vehicle.objects.filter(user=self.user).count(), 1)

    def test_awaiting_vehicle_driver_with_an_existing_active_vehicle_is_409(self):
        self.make_vehicle()

        self.assertApiError(self.register('MH01AB9999'), 409, 'vehicle_already_registered')

    def test_unauthenticated_is_401(self):
        self.client.force_authenticate(user=None)

        self.assertApiError(self.register(), 401, 'not_authenticated')

    def test_duplicate_registration_across_drivers_is_allowed(self):
        # FR-46: no uniqueness constraint in v1.
        other = self.make_user()
        self.driver_awaiting_vehicle(other)
        self.client.force_authenticate(user=other)
        self.assertSuccess(self.register(), 200)

        self.client.force_authenticate(user=self.user)
        self.assertSuccess(self.register(), 200)

        self.assertEqual(Vehicle.objects.filter(registration_number=VALID_REG).count(), 2)


@override_settings(RC_VERIFICATION_ENABLED=False)
class VehicleStatusFlagOffTests(OnboardingTestCase):
    def setUp(self):
        super().setUp()
        self.profile = self.driver_complete_with_vehicle()

    def test_rc_fields_are_null_with_the_flag_off(self):
        data = self.assertSuccess(self.client.get(URL_VEHICLE_STATUS), 200)

        self.assertEqual(data, {
            'onboarding_status': 'complete',
            'next_step': 'none',
            'rc_verification_status': None,
            'rejection_reason': None,
            'registration_number': VALID_REG,
            'vehicle_type': 'SEDAN',
            'rc_attempts_remaining': None,
        })

    def test_rc_state_left_from_a_flag_on_period_is_not_exposed(self):
        Vehicle.objects.filter(user=self.user).update(
            rc_verification_status=Vehicle.RC_REJECTED, rc_rejection_reason='old reason',
        )

        data = self.assertSuccess(self.client.get(URL_VEHICLE_STATUS), 200)

        self.assertIsNone(data['rc_verification_status'])
        self.assertIsNone(data['rejection_reason'])

    def test_driver_without_a_vehicle_gets_nulls(self):
        Vehicle.objects.filter(user=self.user).delete()

        data = self.assertSuccess(self.client.get(URL_VEHICLE_STATUS), 200)

        self.assertIsNone(data['registration_number'])
        self.assertIsNone(data['vehicle_type'])

    def test_passenger_is_403_not_a_driver(self):
        self.passenger_complete()

        self.assertApiError(self.client.get(URL_VEHICLE_STATUS), 403, 'not_a_driver')

    @override_settings(ONBOARDING_GATE_ENABLED=True)
    def test_not_blocked_by_the_onboarding_gate(self):
        self.driver_awaiting_vehicle()

        data = self.assertSuccess(self.client.get(URL_VEHICLE_STATUS), 200)

        self.assertEqual(data['onboarding_status'], 'awaiting_vehicle')


@override_settings(RC_VERIFICATION_ENABLED=False, RC_ADAPTER_CLASS=TRIPWIRE,
                   RC_MOCK_ADAPTER_FORBIDDEN=False, RC_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET)
class RCWebhookFlagOffTests(OnboardingTestCase):
    """FR-42 / FR-57: while the flag is off the RC webhook is a 404 and changes nothing."""

    def setUp(self):
        super().setUp()
        _FlagOffTripwireAdapter.used = False
        self.profile = self.make_named_profile(
            active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.PENDING_RC_VERIFICATION,
        )
        self.make_dl(status=DriverVerification.VERIFIED)
        self.vehicle = self.make_vehicle(
            rc_verification_status=Vehicle.RC_PENDING, rc_verification_ref='rc-ref-1',
        )

    def test_valid_signature_still_gets_404_not_found(self):
        response = self.post_rc_webhook({'reference_id': 'rc-ref-1', 'status': 'verified'})

        self.assertApiError(response, 404, 'not_found')
        self.vehicle.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle.rc_verification_status, Vehicle.RC_PENDING)
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_RC_VERIFICATION)
        self.assertFalse(_FlagOffTripwireAdapter.used)

    def test_unsigned_request_also_gets_404(self):
        response = self.post_rc_webhook(
            {'reference_id': 'rc-ref-1', 'status': 'verified'}, header_present=False,
        )

        self.assertApiError(response, 404, 'not_found')
        self.assertFalse(_FlagOffTripwireAdapter.used)


@override_settings(
    RC_VERIFICATION_ENABLED=False,
    DL_MOCK_ADAPTER_FORBIDDEN=False,
    DL_ADAPTER_CLASS=MOCK_DL_ADAPTER,
    DL_ADAPTER_MOCK_RESULT='sync_verified',
    RC_ADAPTER_CLASS=TRIPWIRE,
    RC_MOCK_ADAPTER_FORBIDDEN=False,
)
class FlagOffDriverFlowInvariantTests(OnboardingTestCase):
    """FR-32: role -> profile -> DL -> vehicle ends complete with every RC field null."""

    def setUp(self):
        super().setUp()
        _FlagOffTripwireAdapter.used = False

    def test_full_driver_flow_completes(self):
        self.assertSuccess(self.client.post(URL_ROLE, {'role': 'driver'}, format='json'), 200)
        self.assertSuccess(self.client.post(URL_PROFILE, {
            'first_name': 'Priya', 'last_name': 'Sharma', 'age': 27, 'gender': 'female',
        }, format='json'), 200)
        self.assertSuccess(self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json'), 200)

        response = self.client.post(
            URL_VEHICLE, {'registration_number': VALID_REG, 'vehicle_type': 'sedan'},
            format='json',
        )

        data = self.assertSuccess(response, 200)
        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertEqual(data['next_step'], 'none')
        self.assertIsNone(data['rc_verification_status'])
        self.assertIsNone(data['rejection_reason'])
        self.assertIsNone(data['reference_id'])
        self.assertFalse(_FlagOffTripwireAdapter.used)

        status_data = self.assertSuccess(self.client.get(URL_STATUS), 200)
        self.assertEqual(status_data['onboarding_status'], 'complete')
        self.assertEqual(status_data['next_step'], 'none')
        self.assertIsNone(status_data['rc_verification_status'])
        self.assertEqual(status_data['dl_verification_status'], 'verified')
