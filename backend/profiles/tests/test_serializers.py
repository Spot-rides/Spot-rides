"""Unit tests for serializers (FEAT-002 TASK-013)."""

from django.test import TestCase
from profiles.serializers import (
    ProfileDetailsSerializer,
    DLSubmissionSerializer,
    RoleSelectionSerializer,
)


class ProfileDetailsSerializerTestCase(TestCase):
    """Test the ProfileDetailsSerializer."""

    def test_valid_data(self):
        """Valid profile data should pass validation."""
        data = {
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'age': 27,
            'gender': 'female'
        }
        serializer = ProfileDetailsSerializer(data=data)
        self.assertTrue(serializer.is_valid())

    def test_age_too_young(self):
        """Age below 18 should be rejected."""
        data = {
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'age': 17,
            'gender': 'female'
        }
        serializer = ProfileDetailsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('age', serializer.errors)

    def test_age_too_old(self):
        """Age above 80 should be rejected."""
        data = {
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'age': 81,
            'gender': 'female'
        }
        serializer = ProfileDetailsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('age', serializer.errors)

    def test_age_boundaries(self):
        """Age 18 and 80 should be accepted."""
        for age in [18, 80]:
            data = {
                'first_name': 'Priya',
                'last_name': 'Sharma',
                'age': age,
                'gender': 'female'
            }
            serializer = ProfileDetailsSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Age {age} should be valid")

    def test_invalid_gender(self):
        """Invalid gender should be rejected."""
        data = {
            'first_name': 'Priya',
            'last_name': 'Sharma',
            'age': 27,
            'gender': 'invalid'
        }
        serializer = ProfileDetailsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('gender', serializer.errors)

    def test_all_valid_genders(self):
        """All valid gender values should be accepted."""
        valid_genders = ['male', 'female', 'other', 'prefer_not_to_say']
        for gender in valid_genders:
            data = {
                'first_name': 'Priya',
                'last_name': 'Sharma',
                'age': 27,
                'gender': gender
            }
            serializer = ProfileDetailsSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Gender '{gender}' should be valid")

    def test_blank_name(self):
        """Blank names should be rejected."""
        data = {
            'first_name': '',
            'last_name': 'Sharma',
            'age': 27,
            'gender': 'female'
        }
        serializer = ProfileDetailsSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('first_name', serializer.errors)


class DLSubmissionSerializerTestCase(TestCase):
    """Test the DLSubmissionSerializer."""

    def test_valid_dl_with_space(self):
        """Valid DL with space should be accepted and normalized."""
        data = {'dl_number': 'MH01 20110012345'}
        serializer = DLSubmissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['dl_number'], 'MH0120110012345')

    def test_valid_dl_with_hyphen(self):
        """Valid DL with hyphen should be accepted and normalized."""
        data = {'dl_number': 'MH01-20110012345'}
        serializer = DLSubmissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['dl_number'], 'MH0120110012345')

    def test_valid_dl_no_separator(self):
        """Valid DL without separator should be accepted."""
        data = {'dl_number': 'MH0120110012345'}
        serializer = DLSubmissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['dl_number'], 'MH0120110012345')

    def test_lowercase_dl_normalized(self):
        """Lowercase DL should be normalized to uppercase."""
        data = {'dl_number': 'mh01 20110012345'}
        serializer = DLSubmissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['dl_number'], 'MH0120110012345')

    def test_invalid_dl_format(self):
        """Invalid DL format should be rejected."""
        invalid_dls = [
            'ABCD1234',  # Too short
            'MH01 201100123',  # Too short
            'MH01 2011001234567',  # Too long
            '',  # Empty
            '12345678901234',  # No letters
        ]
        for dl in invalid_dls:
            data = {'dl_number': dl}
            serializer = DLSubmissionSerializer(data=data)
            self.assertFalse(serializer.is_valid(), f"DL '{dl}' should be invalid")
            self.assertIn('dl_number', serializer.errors)


class RoleSelectionSerializerTestCase(TestCase):
    """Test the RoleSelectionSerializer."""

    def test_valid_roles(self):
        """Valid roles should be accepted."""
        for role in ['driver', 'passenger']:
            data = {'role': role}
            serializer = RoleSelectionSerializer(data=data)
            self.assertTrue(serializer.is_valid(), f"Role '{role}' should be valid")

    def test_invalid_role(self):
        """Invalid role should be rejected."""
        data = {'role': 'admin'}
        serializer = RoleSelectionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role', serializer.errors)
