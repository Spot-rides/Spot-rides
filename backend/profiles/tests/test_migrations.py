"""The grandfathering data migration, profiles.0004 (FEAT-002 FR-43; SEC F-10).

The marking rule is exercised as a function against seeded rows (the historical and
current model states are identical for the fields involved), which keeps the test fast
and deterministic.  A full migration-executor run is deliberately not attempted; see
the testing notes.
"""

from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase

from profiles.models import DriverVerification, UserProfile, Vehicle

User = get_user_model()

migration_module = import_module('profiles.migrations.0004_userprofile_vehicle_step_exempt')
mark_grandfathered_drivers = migration_module.mark_grandfathered_drivers
unmark = migration_module.unmark


class GrandfatheringRuleTests(TestCase):
    """Marked only when: onboarding complete AND a verified DL AND no active vehicle."""

    def make_user(self, suffix):
        return User.objects.create_user(phone_number=f'+9199000{suffix:05d}')

    def seed(self, suffix, *, onboarding_status, dl_status=None, vehicle=None,
             exempt=False):
        user = self.make_user(suffix)
        profile = UserProfile.objects.create(
            user=user, active_role=UserProfile.DRIVER,
            onboarding_status=onboarding_status, vehicle_step_exempt=exempt,
            first_name='Driver', last_name=f'Number{suffix}', age=30, gender='male',
        )
        if dl_status is not None:
            DriverVerification.objects.create(
                user=user, dl_number='ciphertext', dl_number_display='2345',
                dl_verification_status=dl_status,
            )
        if vehicle is not None:
            Vehicle.objects.create(
                user=user, registration_number=f'MH01AB{1000 + suffix}',
                vehicle_type='SEDAN', is_active=vehicle,
            )
        return profile

    def run_migration(self):
        mark_grandfathered_drivers(apps, None)

    def assertMarked(self, profile, expected):
        profile.refresh_from_db()
        self.assertEqual(profile.vehicle_step_exempt, expected)

    def test_complete_verified_dl_without_a_vehicle_is_marked(self):
        profile = self.seed(1, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.VERIFIED)

        self.run_migration()

        self.assertMarked(profile, True)

    def test_complete_verified_dl_with_only_an_inactive_vehicle_is_marked(self):
        profile = self.seed(2, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.VERIFIED, vehicle=False)

        self.run_migration()

        self.assertMarked(profile, True)

    def test_complete_verified_dl_with_an_active_vehicle_is_not_marked(self):
        profile = self.seed(3, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.VERIFIED, vehicle=True)

        self.run_migration()

        self.assertMarked(profile, False)

    def test_pending_dl_is_not_marked(self):
        profile = self.seed(4, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.PENDING)

        self.run_migration()

        self.assertMarked(profile, False)

    def test_rejected_dl_is_not_marked(self):
        profile = self.seed(5, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.REJECTED)

        self.run_migration()

        self.assertMarked(profile, False)

    def test_absent_dl_record_is_not_marked(self):
        profile = self.seed(6, onboarding_status=UserProfile.COMPLETE)

        self.run_migration()

        self.assertMarked(profile, False)

    def test_incomplete_onboarding_is_not_marked(self):
        for suffix, status in enumerate((
            UserProfile.NOT_STARTED, UserProfile.ROLE_SELECTED, UserProfile.AWAITING_DL,
            UserProfile.PENDING_VERIFICATION, UserProfile.AWAITING_VEHICLE,
            UserProfile.PENDING_RC_VERIFICATION,
        ), start=10):
            with self.subTest(status=status):
                profile = self.seed(suffix, onboarding_status=status,
                                    dl_status=DriverVerification.VERIFIED)

                self.run_migration()

                self.assertMarked(profile, False)

    def test_passenger_without_a_dl_is_not_marked(self):
        user = self.make_user(20)
        profile = UserProfile.objects.create(
            user=user, active_role=UserProfile.PASSENGER,
            onboarding_status=UserProfile.COMPLETE,
        )

        self.run_migration()

        self.assertMarked(profile, False)

    def test_rule_is_idempotent(self):
        marked = self.seed(21, onboarding_status=UserProfile.COMPLETE,
                           dl_status=DriverVerification.VERIFIED)
        untouched = self.seed(22, onboarding_status=UserProfile.COMPLETE,
                              dl_status=DriverVerification.VERIFIED, vehicle=True)

        self.run_migration()
        self.run_migration()
        self.run_migration()

        self.assertMarked(marked, True)
        self.assertMarked(untouched, False)
        self.assertEqual(UserProfile.objects.filter(vehicle_step_exempt=True).count(), 1)

    def test_already_marked_rows_are_left_alone(self):
        profile = self.seed(25, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.VERIFIED, vehicle=True, exempt=True)

        self.run_migration()

        # The rule never clears an existing marker, even for a driver with a vehicle.
        self.assertMarked(profile, True)

    def test_reverse_clears_the_marker(self):
        profile = self.seed(23, onboarding_status=UserProfile.COMPLETE,
                            dl_status=DriverVerification.VERIFIED)
        self.run_migration()
        self.assertMarked(profile, True)

        unmark(apps, None)

        self.assertMarked(profile, False)

    def test_marker_is_never_set_for_a_driver_who_simply_has_no_vehicle_yet(self):
        # A driver verified later and sitting in awaiting_vehicle must not be exempt.
        profile = self.seed(24, onboarding_status=UserProfile.AWAITING_VEHICLE,
                            dl_status=DriverVerification.VERIFIED)

        self.run_migration()

        self.assertMarked(profile, False)


class MigrationShapeTests(TestCase):
    def test_migration_is_reversible_and_defaults_to_false(self):
        operations = migration_module.Migration.operations

        add_field = next(o for o in operations if isinstance(o, migrations.AddField))
        run_python = next(o for o in operations if isinstance(o, migrations.RunPython))
        self.assertFalse(add_field.field.default)
        db_default = add_field.field.db_default
        self.assertIs(getattr(db_default, 'value', db_default), False)
        self.assertIsNotNone(run_python.reverse_code)

    def test_model_default_matches_the_migration(self):
        field = UserProfile._meta.get_field('vehicle_step_exempt')

        self.assertFalse(field.default)
