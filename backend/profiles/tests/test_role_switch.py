"""Role switching, including passenger-to-driver setup (FEAT-002 FR-22..FR-26, FR-43, FR-52, FR-55).

Behaviour is covered with ``RC_VERIFICATION_ENABLED`` both off and on wherever the
two differ.  The RC-on cases use the mock adapter only indirectly: the switch itself
never calls a provider.
"""

from django.test import override_settings

from profiles.models import DriverVerification, UserProfile, Vehicle

from .helpers import (
    MOCK_DL_ADAPTER,
    URL_DL,
    URL_ROLE_SWITCH,
    URL_VEHICLE,
    VALID_DL,
    VALID_REG,
    OnboardingTestCase,
)


class RoleSwitchTestCase(OnboardingTestCase):
    def switch(self, role):
        return self.client.patch(URL_ROLE_SWITCH, {'role': role}, format='json')

    def assertSwitched(self, response, *, status_code, role, onboarding_status,
                       next_step, dl_status):
        data = self.assertSuccess(response, status_code)
        self.assertEqual(data['active_role'], role)
        self.assertEqual(data['onboarding_status'], onboarding_status)
        # KD-09: next_step is always present, including on `complete` responses.
        self.assertIn('next_step', data)
        self.assertEqual(data['next_step'], next_step)
        self.assertEqual(data['dl_verification_status'], dl_status)
        return data


@override_settings(RC_VERIFICATION_ENABLED=False)
class SwitchToDriverFlagOffTests(RoleSwitchTestCase):
    """FR-24: a complete passenger who switches to driver starts driver setup."""

    def test_no_dl_record_starts_driver_setup(self):
        self.passenger_complete()

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_dl', next_step='dl_submission', dl_status=None,
        )

    def test_rejected_dl_starts_driver_setup_without_resetting_attempts(self):
        self.passenger_complete()
        dl = self.make_dl(status=DriverVerification.REJECTED, attempt_count=2)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_dl', next_step='dl_submission', dl_status='rejected',
        )
        dl.refresh_from_db()
        self.assertEqual(dl.attempt_count, 2)

    def test_pending_dl_gives_202_pending_verification(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.PENDING)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=202, role='driver',
            onboarding_status='pending_verification', next_step='awaiting_verification',
            dl_status='pending',
        )

    def test_verified_dl_with_an_active_vehicle_is_complete(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle()

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )

    def test_verified_dl_without_a_vehicle_requires_the_vehicle_step(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
            dl_status='verified',
        )

    def test_grandfathered_profile_without_a_vehicle_stays_complete(self):
        self.make_named_profile(
            active_role=UserProfile.PASSENGER, onboarding_status=UserProfile.COMPLETE,
            vehicle_step_exempt=True,
        )
        self.make_dl(status=DriverVerification.VERIFIED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )

    def test_inactive_vehicle_alone_does_not_imply_exemption(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle(is_active=False)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
            dl_status='verified',
        )

    def test_rc_state_of_an_active_vehicle_is_not_evaluated_with_the_flag_off(self):
        # v8 edge case: a row left over from a flag-on period still completes the user.
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle(rc_verification_status=Vehicle.RC_REJECTED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )


@override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
class SwitchToDriverFlagOnTests(RoleSwitchTestCase):
    """FR-43 flag-on derivation from the newest active vehicle."""

    def test_no_dl_record_starts_driver_setup(self):
        self.passenger_complete()

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_dl', next_step='dl_submission', dl_status=None,
        )

    def test_pending_dl_gives_202_pending_verification(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.PENDING)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=202, role='driver',
            onboarding_status='pending_verification', next_step='awaiting_verification',
            dl_status='pending',
        )

    def test_verified_vehicle_is_complete(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle(rc_verification_status=Vehicle.RC_VERIFIED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )

    def test_legacy_vehicle_with_null_rc_status_is_complete(self):
        # FR-45: existing drivers are grandfathered by their null RC status.
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle(rc_verification_status=None)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )

    def test_pending_vehicle_gives_pending_rc_verification(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle(rc_verification_status=Vehicle.RC_PENDING)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='pending_rc_verification',
            next_step='awaiting_rc_verification', dl_status='verified',
        )

    def test_rejected_vehicle_returns_to_the_vehicle_step(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)
        self.make_vehicle(rc_verification_status=Vehicle.RC_REJECTED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
            dl_status='verified',
        )

    def test_no_vehicle_and_not_exempt_requires_the_vehicle_step(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.VERIFIED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
            dl_status='verified',
        )

    def test_grandfathered_profile_without_a_vehicle_stays_complete(self):
        self.make_named_profile(
            active_role=UserProfile.PASSENGER, onboarding_status=UserProfile.COMPLETE,
            vehicle_step_exempt=True,
        )
        self.make_dl(status=DriverVerification.VERIFIED)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=200, role='driver',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )


class NeverSubmittedVehicleBypassTests(RoleSwitchTestCase):
    """v6 regression: a round trip must not turn "no vehicle row" into an exemption."""

    def _round_trip(self):
        self.driver_awaiting_vehicle()

        to_passenger = self.switch('passenger')
        back_to_driver = self.switch('driver')
        return to_passenger, back_to_driver

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_round_trip_does_not_reach_complete_with_the_flag_off(self):
        to_passenger, back_to_driver = self._round_trip()

        self.assertSwitched(
            to_passenger, status_code=200, role='passenger',
            onboarding_status='complete', next_step='none', dl_status='verified',
        )
        self.assertSwitched(
            back_to_driver, status_code=200, role='driver',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
            dl_status='verified',
        )
        self.assertFalse(UserProfile.objects.get(user=self.user).vehicle_step_exempt)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_round_trip_does_not_reach_complete_with_the_flag_on(self):
        _, back_to_driver = self._round_trip()

        self.assertSwitched(
            back_to_driver, status_code=200, role='driver',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
            dl_status='verified',
        )


class SwitchToPassengerTests(RoleSwitchTestCase):
    """FR-52: a user in any in-progress driver state can always become a passenger."""

    def _driver_in(self, status):
        profile = self.make_named_profile(
            active_role=UserProfile.DRIVER, onboarding_status=status,
        )
        dl_status = {
            UserProfile.AWAITING_DL: DriverVerification.REJECTED,
            UserProfile.PENDING_VERIFICATION: DriverVerification.PENDING,
        }.get(status, DriverVerification.VERIFIED)
        dl = self.make_dl(status=dl_status, attempt_count=2)
        vehicle = None
        if status == UserProfile.PENDING_RC_VERIFICATION:
            vehicle = self.make_vehicle(
                rc_verification_status=Vehicle.RC_PENDING, rc_attempt_count=2,
            )
        return profile, dl, vehicle

    def _assert_switch_to_passenger(self, status):
        profile, dl, vehicle = self._driver_in(status)
        dl_before = DriverVerification.objects.filter(pk=dl.pk).values().first()
        vehicle_before = (
            Vehicle.objects.filter(pk=vehicle.pk).values().first() if vehicle else None
        )

        response = self.switch('passenger')

        data = self.assertSuccess(response, 200)
        self.assertEqual(data['active_role'], 'passenger')
        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertEqual(data['next_step'], 'none')
        # Records are preserved untouched, including the attempt counters.
        self.assertEqual(DriverVerification.objects.filter(pk=dl.pk).values().first(), dl_before)
        if vehicle is not None:
            self.assertEqual(
                Vehicle.objects.filter(pk=vehicle.pk).values().first(), vehicle_before,
            )

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_awaiting_dl_flag_off(self):
        self._assert_switch_to_passenger(UserProfile.AWAITING_DL)

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_pending_verification_flag_off(self):
        self._assert_switch_to_passenger(UserProfile.PENDING_VERIFICATION)

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_awaiting_vehicle_flag_off(self):
        self._assert_switch_to_passenger(UserProfile.AWAITING_VEHICLE)

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_pending_rc_verification_flag_off(self):
        self._assert_switch_to_passenger(UserProfile.PENDING_RC_VERIFICATION)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_from_awaiting_dl_flag_on(self):
        self._assert_switch_to_passenger(UserProfile.AWAITING_DL)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_from_pending_verification_flag_on(self):
        self._assert_switch_to_passenger(UserProfile.PENDING_VERIFICATION)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_from_awaiting_vehicle_flag_on(self):
        self._assert_switch_to_passenger(UserProfile.AWAITING_VEHICLE)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_from_pending_rc_verification_flag_on(self):
        self._assert_switch_to_passenger(UserProfile.PENDING_RC_VERIFICATION)

    @override_settings(ONBOARDING_GATE_ENABLED=True)
    def test_endpoint_is_not_blocked_by_the_onboarding_gate(self):
        self._assert_switch_to_passenger(UserProfile.AWAITING_DL)

    def test_switching_to_passenger_when_already_a_complete_passenger_is_a_no_op(self):
        profile = self.passenger_complete()

        response = self.switch('passenger')

        self.assertSwitched(
            response, status_code=200, role='passenger',
            onboarding_status='complete', next_step='none', dl_status=None,
        )
        self.assertEqual(self.refresh(profile).updated_at, profile.updated_at)


class SwitchToDriverIsIdempotentTests(RoleSwitchTestCase):
    """FR-55: a switch to driver by a user already in an in-progress driver state."""

    def _assert_noop(self, status, *, status_code, next_step, dl_status):
        profile = self.make_named_profile(
            active_role=UserProfile.DRIVER, onboarding_status=status,
        )
        if dl_status:
            self.make_dl(status=dl_status, attempt_count=1)

        response = self.switch('driver')

        self.assertSwitched(
            response, status_code=status_code, role='driver',
            onboarding_status=status, next_step=next_step, dl_status=dl_status,
        )
        self.assertEqual(self.refresh(profile).onboarding_status, status)

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_awaiting_dl_flag_off(self):
        self._assert_noop(UserProfile.AWAITING_DL, status_code=200,
                          next_step='dl_submission', dl_status=None)

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_pending_verification_flag_off(self):
        self._assert_noop(UserProfile.PENDING_VERIFICATION, status_code=202,
                          next_step='awaiting_verification',
                          dl_status=DriverVerification.PENDING)

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_from_awaiting_vehicle_flag_off_does_not_derive_complete(self):
        # The retired v7 rule returned 400 here; it is now a no-op and, importantly,
        # no vehicle-state derivation runs (which could have produced `complete`).
        self.make_vehicle()
        self._assert_noop(UserProfile.AWAITING_VEHICLE, status_code=200,
                          next_step='vehicle_registration',
                          dl_status=DriverVerification.VERIFIED)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_from_awaiting_vehicle_flag_on(self):
        self._assert_noop(UserProfile.AWAITING_VEHICLE, status_code=200,
                          next_step='vehicle_registration',
                          dl_status=DriverVerification.VERIFIED)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_from_pending_rc_verification_flag_on(self):
        self._assert_noop(UserProfile.PENDING_RC_VERIFICATION, status_code=200,
                          next_step='awaiting_rc_verification',
                          dl_status=DriverVerification.VERIFIED)


class SwitchEligibilityTests(RoleSwitchTestCase):
    """FR-22: mid-onboarding users are not eligible and get 403 onboarding_incomplete."""

    def test_not_started_is_403_with_status_and_next_step(self):
        self.make_profile(onboarding_status=UserProfile.NOT_STARTED)

        response = self.switch('driver')

        self.assertApiError(
            response, 403, 'onboarding_incomplete',
            onboarding_status='not_started', next_step='role_selection',
        )

    def test_role_selected_is_403_with_status_and_next_step(self):
        self.make_profile(
            active_role=UserProfile.DRIVER, onboarding_status=UserProfile.ROLE_SELECTED,
        )

        response = self.switch('passenger')

        self.assertApiError(
            response, 403, 'onboarding_incomplete',
            onboarding_status='role_selected', next_step='profile',
        )

    def test_user_without_a_profile_row_is_403(self):
        response = self.switch('driver')

        self.assertApiError(
            response, 403, 'onboarding_incomplete',
            onboarding_status='not_started', next_step='role_selection',
        )

    def test_invalid_role_is_400_invalid_role(self):
        self.passenger_complete()

        response = self.switch('admin')

        error = self.assertApiError(response, 400, 'invalid_role')
        self.assertIn('role', error['fields'])

    def test_missing_role_is_400_invalid_request(self):
        # KD-05: a missing or null role is not mapped to invalid_role.
        self.passenger_complete()

        response = self.client.patch(URL_ROLE_SWITCH, {}, format='json')

        self.assertApiError(response, 400, 'invalid_request')

    def test_null_role_is_400_invalid_request(self):
        self.passenger_complete()

        response = self.client.patch(URL_ROLE_SWITCH, {'role': None}, format='json')

        self.assertApiError(response, 400, 'invalid_request')

    def test_unauthenticated_is_401(self):
        self.client.force_authenticate(user=None)

        self.assertApiError(self.switch('driver'), 401, 'not_authenticated')


class InconsistentDataDefensiveBranchTests(RoleSwitchTestCase):
    """FR-55 (v9): a passenger stuck in awaiting_vehicle is not part of the contract.

    Recorded here so the defensive branch cannot change unnoticed.
    """

    def setUp(self):
        super().setUp()
        self.make_named_profile(
            active_role=UserProfile.PASSENGER, onboarding_status=UserProfile.AWAITING_VEHICLE,
        )
        self.make_dl(status=DriverVerification.VERIFIED)

    @override_settings(RC_VERIFICATION_ENABLED=True, RC_MOCK_ADAPTER_FORBIDDEN=False)
    def test_flag_on_is_400_invalid_onboarding_state(self):
        self.assertApiError(self.switch('driver'), 400, 'invalid_onboarding_state')

    @override_settings(RC_VERIFICATION_ENABLED=False)
    def test_flag_off_is_403_onboarding_incomplete(self):
        self.assertApiError(
            self.switch('driver'), 403, 'onboarding_incomplete',
            onboarding_status='awaiting_vehicle', next_step='vehicle_registration',
        )


@override_settings(
    RC_VERIFICATION_ENABLED=False,
    DL_MOCK_ADAPTER_FORBIDDEN=False,
    DL_ADAPTER_CLASS=MOCK_DL_ADAPTER,
    DL_ADAPTER_MOCK_RESULT='sync_verified',
)
class PassengerBecomesDriverEndToEndTests(RoleSwitchTestCase):
    """US-21: switch, submit a DL, register a vehicle, finish onboarding."""

    def test_full_journey(self):
        self.passenger_complete()

        switch = self.switch('driver')
        self.assertSwitched(
            switch, status_code=200, role='driver',
            onboarding_status='awaiting_dl', next_step='dl_submission', dl_status=None,
        )

        dl = self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json')
        dl_data = self.assertSuccess(dl, 200)
        self.assertEqual(dl_data['onboarding_status'], 'awaiting_vehicle')
        self.assertEqual(dl_data['next_step'], 'vehicle_registration')

        vehicle = self.client.post(
            URL_VEHICLE, {'registration_number': VALID_REG, 'vehicle_type': 'sedan'},
            format='json',
        )
        vehicle_data = self.assertSuccess(vehicle, 200)
        self.assertEqual(vehicle_data['onboarding_status'], 'complete')
        self.assertEqual(vehicle_data['next_step'], 'none')
        self.assertIsNone(vehicle_data['rc_verification_status'])

    def test_rejected_dl_holder_can_restart_driver_setup_and_finish(self):
        self.passenger_complete()
        self.make_dl(status=DriverVerification.REJECTED, attempt_count=1,
                     dl_rejection_reason='typo')

        self.assertSuccess(self.switch('driver'), 200)
        self.assertSuccess(self.client.post(URL_DL, {'dl_number': VALID_DL}, format='json'), 200)
        response = self.client.post(
            URL_VEHICLE, {'registration_number': VALID_REG, 'vehicle_type': 'car'},
            format='json',
        )

        data = self.assertSuccess(response, 200)
        self.assertEqual(data['onboarding_status'], 'complete')
        self.assertEqual(DriverVerification.objects.get(user=self.user).attempt_count, 2)
