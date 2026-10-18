"""Django admin hardening for the onboarding models (FEAT-002 FR-44; SEC F-07, F-11).

Staff who are not superusers must not be able to hand-edit the onboarding state
machine, the encrypted DL number must never be rendered, DL rows cannot be added by
hand, and the third-party RC owner name is visible only with ``profiles.review_rc``.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from profiles.admin import DriverVerificationAdmin, UserProfileAdmin, VehicleAdmin
from profiles.models import DriverVerification, UserProfile, Vehicle

User = get_user_model()


class AdminTestCase(TestCase):
    """Staff and superuser clients plus one profile / DL / vehicle to look at."""

    @staticmethod
    def grant(user, *codenames):
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        return user

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(phone_number='+919820000001', is_staff=True)
        self.staff.set_password('staff-pass')
        self.staff.save()
        self.grant(
            self.staff,
            'view_userprofile', 'change_userprofile',
            'view_driververification', 'change_driververification', 'add_driververification',
            'view_vehicle', 'change_vehicle',
        )
        self.superuser = User.objects.create_superuser(
            phone_number='+919820000002', password='super-pass',
        )

        self.driver = User.objects.create_user(phone_number='+919820000003')
        self.profile = UserProfile.objects.create(
            user=self.driver, active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.AWAITING_DL,
            first_name='Priya', last_name='Sharma', age=27, gender='female',
        )
        self.dl = DriverVerification.objects.create(
            user=self.driver, dl_number='super-secret-ciphertext',
            dl_number_display='2345', dl_verification_status=DriverVerification.REJECTED,
            dl_verification_ref='ref-1', attempt_count=2, dl_rejection_reason='typo',
        )
        self.vehicle = Vehicle.objects.create(
            user=self.driver, registration_number='MH01AB1234', vehicle_type='SEDAN',
            is_active=True, rc_verification_status=Vehicle.RC_PENDING,
            rc_owner_name='SOME OTHER OWNER', rc_name_match=Vehicle.NAME_MISMATCH,
            rc_attempt_count=1,
        )

    def login_staff(self):
        self.client.force_login(self.staff)

    def login_superuser(self):
        self.client.force_login(self.superuser)

    def fake_request(self, user):
        request = type('Req', (), {})()
        request.user = user
        return request


class UserProfileAdminTests(AdminTestCase):
    admin = UserProfileAdmin(UserProfile, None)

    def test_state_fields_are_read_only_for_non_superusers(self):
        readonly = self.admin.get_readonly_fields(
            self.fake_request(self.staff), obj=self.profile,
        )

        for field in ('onboarding_status', 'active_role', 'vehicle_step_exempt', 'user'):
            self.assertIn(field, readonly)

    def test_superusers_may_edit_the_state_fields(self):
        readonly = self.admin.get_readonly_fields(
            self.fake_request(self.superuser), obj=self.profile,
        )

        self.assertNotIn('onboarding_status', readonly)
        self.assertNotIn('active_role', readonly)
        # The grandfathering marker stays read-only even for superusers (FR-43).
        self.assertIn('vehicle_step_exempt', readonly)

    def test_state_fields_are_not_rendered_as_inputs_for_staff(self):
        self.login_staff()
        url = reverse('admin:profiles_userprofile_change', args=[self.profile.pk])

        body = self.client.get(url).content.decode()

        self.assertNotIn('name="onboarding_status"', body)
        self.assertNotIn('name="active_role"', body)
        self.assertNotIn('name="vehicle_step_exempt"', body)

    def test_tampered_post_cannot_change_the_state_fields(self):
        self.login_staff()
        url = reverse('admin:profiles_userprofile_change', args=[self.profile.pk])

        response = self.client.post(url, {
            'first_name': 'Priya', 'last_name': 'Sharma', 'age': '27', 'gender': 'female',
            'onboarding_status': UserProfile.COMPLETE,
            'active_role': UserProfile.PASSENGER,
            'vehicle_step_exempt': 'on',
            'user': str(self.staff.pk),
        })

        self.assertIn(response.status_code, (200, 302))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_DL)
        self.assertEqual(self.profile.active_role, UserProfile.DRIVER)
        self.assertFalse(self.profile.vehicle_step_exempt)
        self.assertEqual(self.profile.user_id, self.driver.pk)

    def test_superuser_post_can_change_the_state_fields(self):
        self.login_superuser()
        url = reverse('admin:profiles_userprofile_change', args=[self.profile.pk])

        self.client.post(url, {
            'user': str(self.driver.pk),
            'first_name': 'Priya', 'last_name': 'Sharma', 'age': '27', 'gender': 'female',
            'onboarding_status': UserProfile.COMPLETE,
            'active_role': UserProfile.PASSENGER,
        })

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.onboarding_status, UserProfile.COMPLETE)


class DriverVerificationAdminTests(AdminTestCase):
    admin = DriverVerificationAdmin(DriverVerification, None)

    def test_adding_a_dl_record_is_disabled(self):
        self.assertFalse(self.admin.has_add_permission(self.fake_request(self.superuser)))

    def test_add_view_is_forbidden_even_with_the_add_permission(self):
        self.login_staff()

        response = self.client.get(reverse('admin:profiles_driververification_add'))

        self.assertEqual(response.status_code, 403)

    def test_state_fields_are_read_only_for_non_superusers(self):
        readonly = self.admin.get_readonly_fields(self.fake_request(self.staff), obj=self.dl)

        for field in ('dl_verification_status', 'dl_verification_ref', 'attempt_count',
                      'dl_rejection_reason', 'dl_number_display', 'user'):
            self.assertIn(field, readonly)

    def test_encrypted_dl_number_is_never_rendered(self):
        self.login_superuser()
        url = reverse('admin:profiles_driververification_change', args=[self.dl.pk])

        body = self.client.get(url).content.decode()

        self.assertNotIn('super-secret-ciphertext', body)
        self.assertNotIn('name="dl_number"', body)
        self.assertIn('2345', body)  # the display digits are fine

    def test_dl_number_is_excluded_from_the_admin_form(self):
        self.assertIn('dl_number', self.admin.exclude)

    def test_tampered_post_cannot_change_the_dl_state(self):
        self.login_staff()
        url = reverse('admin:profiles_driververification_change', args=[self.dl.pk])

        response = self.client.post(url, {
            'dl_verification_status': DriverVerification.VERIFIED,
            'attempt_count': '0',
            'dl_verification_ref': 'tampered-ref',
            'dl_rejection_reason': '',
            'dl_number': 'attacker-supplied',
            'user': str(self.staff.pk),
        })

        self.assertIn(response.status_code, (200, 302))
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.REJECTED)
        self.assertEqual(self.dl.attempt_count, 2)
        self.assertEqual(self.dl.dl_verification_ref, 'ref-1')
        self.assertEqual(self.dl.dl_number, 'super-secret-ciphertext')
        self.assertEqual(self.dl.user_id, self.driver.pk)


class VehicleAdminTests(AdminTestCase):
    admin = VehicleAdmin(Vehicle, None)

    def test_every_field_is_read_only(self):
        readonly = self.admin.get_readonly_fields(self.fake_request(self.superuser))

        self.assertEqual(set(readonly), {f.name for f in Vehicle._meta.fields})

    def test_add_and_delete_are_disabled(self):
        request = self.fake_request(self.superuser)

        self.assertFalse(self.admin.has_add_permission(request))
        self.assertFalse(self.admin.has_delete_permission(request))

    def test_owner_name_is_hidden_without_the_review_permission(self):
        self.login_staff()
        url = reverse('admin:profiles_vehicle_change', args=[self.vehicle.pk])

        body = self.client.get(url).content.decode()

        self.assertNotIn('SOME OTHER OWNER', body)
        self.assertIn('MH01AB1234', body)

    def test_owner_name_is_visible_with_the_review_permission(self):
        self.grant(self.staff, 'review_rc')
        self.login_staff()
        url = reverse('admin:profiles_vehicle_change', args=[self.vehicle.pk])

        body = self.client.get(url).content.decode()

        self.assertIn('SOME OTHER OWNER', body)

    def test_fieldsets_drop_the_owner_name_without_the_permission(self):
        request = self.fake_request(self.staff)
        request.user = self.staff

        fieldsets = self.admin.get_fieldsets(request, self.vehicle)

        fields = [field for _, options in fieldsets for field in options['fields']]
        self.assertNotIn('rc_owner_name', fields)
        self.assertIn('rc_vehicle_class', fields)

    def test_fieldsets_keep_the_owner_name_with_the_permission(self):
        self.grant(self.staff, 'review_rc')
        staff = User.objects.get(pk=self.staff.pk)  # reload so perms are not cached

        fieldsets = self.admin.get_fieldsets(self.fake_request(staff), self.vehicle)

        fields = [field for _, options in fieldsets for field in options['fields']]
        self.assertIn('rc_owner_name', fields)

    def test_duplicate_indicator_counts_other_drivers(self):
        other = User.objects.create_user(phone_number='+919820000004')
        Vehicle.objects.create(
            user=other, registration_number='MH01AB1234', vehicle_type='CAR', is_active=True,
        )

        row = self.admin.get_queryset(self.fake_request(self.superuser)).get(pk=self.vehicle.pk)

        self.assertEqual(self.admin.other_drivers_with_same_reg(row), 1)

    def test_duplicate_indicator_is_zero_for_a_unique_registration(self):
        row = self.admin.get_queryset(self.fake_request(self.superuser)).get(pk=self.vehicle.pk)

        self.assertEqual(self.admin.other_drivers_with_same_reg(row), 0)


class VehicleAdminReviewActionTests(AdminTestCase):
    """FR-44: the review actions move the driver and are audit-logged."""

    def setUp(self):
        super().setUp()
        self.profile.onboarding_status = UserProfile.PENDING_RC_VERIFICATION
        self.profile.save()
        self.grant(self.staff, 'review_rc')
        self.login_staff()
        self.url = reverse('admin:profiles_vehicle_changelist')

    def act(self, action, **extra):
        return self.client.post(self.url, {
            'action': action,
            '_selected_action': [str(self.vehicle.pk)],
            **extra,
        }, follow=True)

    def test_approve_completes_the_driver(self):
        self.act('approve_rc')

        self.vehicle.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle.rc_verification_status, Vehicle.RC_VERIFIED)
        self.assertIsNone(self.vehicle.rc_owner_name)
        self.assertEqual(self.profile.onboarding_status, UserProfile.COMPLETE)

    def test_reject_requires_a_reason_and_changes_nothing_without_one(self):
        self.act('reject_rc', rc_reject_reason='   ')

        self.vehicle.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle.rc_verification_status, Vehicle.RC_PENDING)
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_RC_VERIFICATION)

    def test_reject_with_a_reason_returns_the_driver_to_the_vehicle_step(self):
        self.act('reject_rc', rc_reject_reason='Registration does not match')

        self.vehicle.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.vehicle.rc_verification_status, Vehicle.RC_REJECTED)
        self.assertEqual(self.vehicle.rc_rejection_reason, 'Registration does not match')
        self.assertIsNone(self.vehicle.rc_owner_name)
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)

    def test_reset_attempts(self):
        self.act('reset_rc_attempts')

        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.rc_attempt_count, 0)

    def test_review_actions_are_unavailable_without_the_review_permission(self):
        staff = User.objects.create_user(phone_number='+919820000005', is_staff=True)
        self.grant(staff, 'view_vehicle', 'change_vehicle')
        self.client.force_login(staff)

        self.act('approve_rc')

        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.rc_verification_status, Vehicle.RC_PENDING)
