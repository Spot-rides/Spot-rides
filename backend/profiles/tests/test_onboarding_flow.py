"""Core onboarding flow: status, role, profile, the gate and /api/auth/me/.

Covers FR-01..FR-05, FR-16..FR-21, FR-14 (gate) and the deviations KD-05, KD-06,
KD-10, KD-11 and KD-13.
"""

from django.test import override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate
from rest_framework.views import APIView

from profiles.models import DriverVerification, UserProfile

from .helpers import (
    URL_PROFILE,
    URL_ROLE,
    URL_STATUS,
    EnvelopeAssertions,
    OnboardingTestCase,
)

PROFILE_PAYLOAD = {
    'first_name': 'Priya', 'last_name': 'Sharma', 'age': 27, 'gender': 'female',
}


class OnboardingStatusEndpointTests(OnboardingTestCase):
    def test_creates_the_profile_lazily_and_reports_not_started(self):
        # KD-10: no row is created at OTP verification; the status endpoint creates it.
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

        data = self.assertSuccess(self.client.get(URL_STATUS), 200)

        self.assertEqual(data, {
            'onboarding_status': 'not_started',
            'active_role': None,
            'next_step': 'role_selection',
            'profile_complete': False,
            'dl_verification_status': None,
            'rc_verification_status': None,
        })
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_reports_driver_progress(self):
        self.driver_awaiting_vehicle()

        data = self.assertSuccess(self.client.get(URL_STATUS), 200)

        self.assertEqual(data['onboarding_status'], 'awaiting_vehicle')
        self.assertEqual(data['active_role'], 'driver')
        self.assertEqual(data['next_step'], 'vehicle_registration')
        self.assertTrue(data['profile_complete'])
        self.assertEqual(data['dl_verification_status'], 'verified')

    def test_rc_status_is_null_while_the_flag_is_off(self):
        self.driver_complete_with_vehicle(rc_verification_status='pending')

        data = self.assertSuccess(self.client.get(URL_STATUS), 200)

        self.assertIsNone(data['rc_verification_status'])

    def test_resuming_on_another_device_returns_the_same_step(self):
        # FR-16: state is server-side, so a second client sees the same step.
        self.driver_awaiting_dl()
        other_client = self.client_class()
        other_client.force_authenticate(user=self.user)

        first = self.assertSuccess(self.client.get(URL_STATUS), 200)
        second = self.assertSuccess(other_client.get(URL_STATUS), 200)

        self.assertEqual(first['next_step'], 'dl_submission')
        self.assertEqual(first, second)

    def test_unauthenticated_is_401(self):
        self.client.force_authenticate(user=None)

        self.assertApiError(self.client.get(URL_STATUS), 401, 'not_authenticated')


class RoleSelectionEndpointTests(OnboardingTestCase):
    def test_passenger_role_selection(self):
        data = self.assertSuccess(
            self.client.post(URL_ROLE, {'role': 'passenger'}, format='json'), 200,
        )

        self.assertEqual(data, {
            'active_role': 'passenger',
            'onboarding_status': 'role_selected',
            'next_step': 'profile',
        })

    def test_driver_role_selection(self):
        data = self.assertSuccess(
            self.client.post(URL_ROLE, {'role': 'driver'}, format='json'), 200,
        )

        self.assertEqual(data['active_role'], 'driver')
        self.assertEqual(data['onboarding_status'], 'role_selected')

    def test_second_selection_is_409_role_already_set(self):
        self.client.post(URL_ROLE, {'role': 'passenger'}, format='json')

        response = self.client.post(URL_ROLE, {'role': 'driver'}, format='json')

        self.assertApiError(response, 409, 'role_already_set')
        self.assertEqual(
            UserProfile.objects.get(user=self.user).active_role, UserProfile.PASSENGER,
        )

    def test_unsupported_role_is_400_invalid_role(self):
        response = self.client.post(URL_ROLE, {'role': 'admin'}, format='json')

        error = self.assertApiError(response, 400, 'invalid_role')
        self.assertIn('role', error['fields'])

    def test_missing_role_is_400_invalid_request(self):
        # KD-05: only an unsupported value maps to invalid_role.
        response = self.client.post(URL_ROLE, {}, format='json')

        self.assertApiError(response, 400, 'invalid_request')

    def test_selection_after_onboarding_is_409(self):
        self.passenger_complete()

        self.assertApiError(
            self.client.post(URL_ROLE, {'role': 'driver'}, format='json'),
            409, 'role_already_set',
        )


class ProfileSubmissionEndpointTests(OnboardingTestCase):
    def _role_selected(self, role='passenger'):
        return self.make_profile(
            active_role=role, onboarding_status=UserProfile.ROLE_SELECTED,
        )

    def submit(self, **overrides):
        return self.client.post(URL_PROFILE, {**PROFILE_PAYLOAD, **overrides}, format='json')

    def test_passenger_completes_onboarding(self):
        self._role_selected('passenger')

        data = self.assertSuccess(self.submit(), 200)

        self.assertEqual(data, {'onboarding_status': 'complete', 'next_step': 'none'})
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.first_name, 'Priya')
        self.assertEqual(profile.age, 27)
        self.assertEqual(profile.gender, 'female')

    def test_driver_advances_to_dl_submission(self):
        self._role_selected('driver')

        data = self.assertSuccess(self.submit(), 200)

        self.assertEqual(data, {
            'onboarding_status': 'awaiting_dl', 'next_step': 'dl_submission',
        })

    def test_before_role_selection_is_400_invalid_onboarding_state(self):
        # KD-06: any status other than role_selected gives invalid_onboarding_state.
        self.make_profile(onboarding_status=UserProfile.NOT_STARTED)

        self.assertApiError(self.submit(), 400, 'invalid_onboarding_state')

    def test_second_submission_is_400_invalid_onboarding_state_not_409(self):
        # KD-06: the contract says 409 profile_already_set; that branch is unreachable.
        self._role_selected('passenger')
        self.submit()

        self.assertApiError(self.submit(), 400, 'invalid_onboarding_state')

    def test_age_boundaries_are_accepted(self):
        for age in (18, 80):
            with self.subTest(age=age):
                user = self.make_user()
                self.make_profile(
                    user, active_role=UserProfile.PASSENGER,
                    onboarding_status=UserProfile.ROLE_SELECTED,
                )
                self.client.force_authenticate(user=user)

                self.assertSuccess(self.submit(age=age), 200)

    def test_age_out_of_range_is_400_invalid_request(self):
        # KD-05: the contract says invalid_age.
        self._role_selected()

        for age in (17, 81, 0, -1):
            with self.subTest(age=age):
                error = self.assertApiError(self.submit(age=age), 400, 'invalid_request')
                self.assertIn('age', error['fields'])

    def test_non_integer_age_is_400(self):
        self._role_selected()

        self.assertApiError(self.submit(age='twenty'), 400, 'invalid_request')

    def test_invalid_gender_is_400_invalid_request(self):
        # KD-05: the contract says invalid_gender.
        self._role_selected()

        error = self.assertApiError(self.submit(gender='unknown'), 400, 'invalid_request')
        self.assertIn('gender', error['fields'])

    def test_all_genders_are_accepted(self):
        for gender in ('male', 'female', 'other', 'prefer_not_to_say'):
            with self.subTest(gender=gender):
                user = self.make_user()
                self.make_profile(
                    user, active_role=UserProfile.PASSENGER,
                    onboarding_status=UserProfile.ROLE_SELECTED,
                )
                self.client.force_authenticate(user=user)

                self.assertSuccess(self.submit(gender=gender), 200)

    def test_blank_and_whitespace_names_are_rejected(self):
        self._role_selected()

        for value in ('', '   '):
            with self.subTest(value=repr(value)):
                error = self.assertApiError(
                    self.submit(first_name=value), 400, 'invalid_request',
                )
                self.assertIn('first_name', error['fields'])

    def test_over_long_name_is_rejected(self):
        self._role_selected()

        error = self.assertApiError(self.submit(last_name='X' * 51), 400, 'invalid_request')
        self.assertIn('last_name', error['fields'])

    def test_disallowed_characters_are_rejected(self):
        self._role_selected()

        error = self.assertApiError(self.submit(first_name='Priya@home'), 400, 'invalid_request')
        self.assertIn('first_name', error['fields'])

    def test_names_with_hyphens_apostrophes_and_unicode_are_accepted(self):
        self._role_selected()

        self.assertSuccess(self.submit(first_name="Anne-Marie", last_name="O'Brien"), 200)

    def test_digits_and_underscores_are_accepted_by_the_name_check(self):
        # KD-11: the implemented pattern is ^[\w\s'-]+$, which admits digits and "_".
        self._role_selected()

        self.assertSuccess(self.submit(first_name='Priya_1'), 200)


class MeEndpointTests(OnboardingTestCase):
    url = '/api/auth/me/'

    def test_null_fields_before_a_profile_exists(self):
        # KD-10 / FR-21.
        data = self.assertSuccess(self.client.get(self.url), 200)

        self.assertIsNone(data['onboarding_status'])
        self.assertIsNone(data['active_role'])

    def test_reports_onboarding_state_once_a_profile_exists(self):
        self.driver_awaiting_dl()

        data = self.assertSuccess(self.client.get(self.url), 200)

        self.assertEqual(data['onboarding_status'], 'awaiting_dl')
        self.assertEqual(data['active_role'], 'driver')


class _GatedView(APIView):
    """A protected non-onboarding endpoint: it uses the project's default permissions."""

    def get(self, request):
        return Response({'ok': True})


class OnboardingGateTests(EnvelopeAssertions, APITestCase):
    """FR-14 / KD-13: the gate only applies while ONBOARDING_GATE_ENABLED is True."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(phone_number='+919811100001')
        self.factory = APIRequestFactory()

    def call(self):
        request = self.factory.get('/protected/')
        force_authenticate(request, user=self.user)
        return _GatedView.as_view()(request)

    @override_settings(ONBOARDING_GATE_ENABLED=False)
    def test_gate_off_lets_an_incomplete_user_through(self):
        UserProfile.objects.create(
            user=self.user, onboarding_status=UserProfile.AWAITING_DL,
            active_role=UserProfile.DRIVER,
        )

        response = self.call()

        self.assertEqual(response.status_code, 200)

    @override_settings(ONBOARDING_GATE_ENABLED=False)
    def test_gate_off_lets_a_user_without_a_profile_through(self):
        self.assertEqual(self.call().status_code, 200)

    @override_settings(ONBOARDING_GATE_ENABLED=True)
    def test_gate_on_allows_a_complete_user(self):
        UserProfile.objects.create(
            user=self.user, onboarding_status=UserProfile.COMPLETE,
            active_role=UserProfile.PASSENGER,
        )

        self.assertEqual(self.call().status_code, 200)

    @override_settings(ONBOARDING_GATE_ENABLED=True)
    def test_gate_on_blocks_each_incomplete_status_with_the_next_step(self):
        expected = {
            UserProfile.NOT_STARTED: 'role_selection',
            UserProfile.ROLE_SELECTED: 'profile',
            UserProfile.AWAITING_DL: 'dl_submission',
            UserProfile.PENDING_VERIFICATION: 'awaiting_verification',
            UserProfile.AWAITING_VEHICLE: 'vehicle_registration',
            UserProfile.PENDING_RC_VERIFICATION: 'awaiting_rc_verification',
        }
        profile = UserProfile.objects.create(
            user=self.user, onboarding_status=UserProfile.NOT_STARTED,
        )

        for status, next_step in expected.items():
            with self.subTest(status=status):
                profile.onboarding_status = status
                profile.save()
                self.user._state.fields_cache.clear()

                response = self.call()

                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.data['error']['code'], 'onboarding_incomplete')
                self.assertEqual(response.data['error']['onboarding_status'], status)
                self.assertEqual(response.data['error']['next_step'], next_step)

    @override_settings(ONBOARDING_GATE_ENABLED=True)
    def test_gate_on_reports_a_missing_profile_as_not_started(self):
        response = self.call()

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error']['code'], 'onboarding_incomplete')
        self.assertEqual(response.data['error']['onboarding_status'], 'not_started')
        self.assertEqual(response.data['error']['next_step'], 'role_selection')

    @override_settings(ONBOARDING_GATE_ENABLED=True)
    def test_unauthenticated_request_is_401_not_403(self):
        request = self.factory.get('/protected/')

        response = _GatedView.as_view()(request)

        self.assertEqual(response.status_code, 401)


@override_settings(ONBOARDING_GATE_ENABLED=True)
class OnboardingEndpointsStayReachableWithTheGateOnTests(OnboardingTestCase):
    def test_status_role_and_profile_are_not_gated(self):
        self.assertSuccess(self.client.get(URL_STATUS), 200)
        self.assertSuccess(self.client.post(URL_ROLE, {'role': 'driver'}, format='json'), 200)
        self.assertSuccess(self.client.post(URL_PROFILE, PROFILE_PAYLOAD, format='json'), 200)

    def test_dl_status_endpoint_is_not_gated(self):
        self.make_named_profile(
            active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.PENDING_VERIFICATION,
        )
        self.make_dl(status=DriverVerification.PENDING)

        data = self.assertSuccess(
            self.client.get('/api/onboarding/driver/dl/status/'), 200,
        )

        self.assertEqual(data['onboarding_status'], 'pending_verification')
