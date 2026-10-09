"""Unit tests for permission classes (FEAT-002 TASK-030)."""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model

from profiles.models import UserProfile, DriverVerification
from profiles.permissions import IsOnboardingComplete, IsDriverRole, IsDriverVerified

User = get_user_model()


class IsOnboardingCompleteTestCase(TestCase):
    """Test the IsOnboardingComplete permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsOnboardingComplete()
        self.user = User.objects.create_user(phone_number='+919876543210')

    def test_incomplete_user_denied(self):
        """User without complete onboarding should be denied."""
        profile = UserProfile.objects.create(
            user=self.user,
            onboarding_status=UserProfile.NOT_STARTED
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertFalse(result)

    def test_complete_user_allowed(self):
        """User with complete onboarding should be allowed."""
        profile = UserProfile.objects.create(
            user=self.user,
            onboarding_status=UserProfile.COMPLETE,
            active_role=UserProfile.PASSENGER
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertTrue(result)

    def test_no_profile_denied(self):
        """User without profile should be denied."""
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertFalse(result)


class IsDriverRoleTestCase(TestCase):
    """Test the IsDriverRole permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsDriverRole()
        self.user = User.objects.create_user(phone_number='+919876543210')

    def test_passenger_denied(self):
        """User with passenger role should be denied."""
        profile = UserProfile.objects.create(
            user=self.user,
            active_role=UserProfile.PASSENGER
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertFalse(result)

    def test_driver_allowed(self):
        """User with driver role should be allowed."""
        profile = UserProfile.objects.create(
            user=self.user,
            active_role=UserProfile.DRIVER
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertTrue(result)


class IsDriverVerifiedTestCase(TestCase):
    """Test the IsDriverVerified permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsDriverVerified()
        self.user = User.objects.create_user(phone_number='+919876543210')

    def test_unverified_driver_denied(self):
        """Driver without verified DL should be denied."""
        profile = UserProfile.objects.create(
            user=self.user,
            active_role=UserProfile.DRIVER
        )
        dv = DriverVerification.objects.create(
            user=self.user,
            dl_number='encrypted',
            dl_number_display='2345',
            dl_verification_status=DriverVerification.PENDING
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertFalse(result)

    def test_verified_driver_allowed(self):
        """Driver with verified DL should be allowed."""
        profile = UserProfile.objects.create(
            user=self.user,
            active_role=UserProfile.DRIVER
        )
        dv = DriverVerification.objects.create(
            user=self.user,
            dl_number='encrypted',
            dl_number_display='2345',
            dl_verification_status='verified'
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertTrue(result)

    def test_passenger_denied(self):
        """Passenger should be denied even with verified DL."""
        profile = UserProfile.objects.create(
            user=self.user,
            active_role=UserProfile.PASSENGER
        )
        dv = DriverVerification.objects.create(
            user=self.user,
            dl_number='encrypted',
            dl_number_display='2345',
            dl_verification_status='verified'
        )
        request = self.factory.get('/')
        request.user = self.user

        result = self.permission.has_permission(request, None)
        self.assertFalse(result)
