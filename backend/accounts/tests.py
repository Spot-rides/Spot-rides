"""Tests for the accounts serializers."""

from django.test import TestCase

from .serializers import OtpRequestSerializer, OtpVerifySerializer


class OtpRequestSerializerTests(TestCase):
    """Tests for OtpRequestSerializer."""

    def test_valid_phone_number(self):
        serializer = OtpRequestSerializer(data={'phone_number': '+917337264708'})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.phone_e164, '+917337264708')
        self.assertEqual(serializer.validated_data['phone_number'], '+917337264708')

    def test_missing_phone_number(self):
        serializer = OtpRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('phone_number', serializer.errors)


class OtpVerifySerializerTests(TestCase):
    """Tests for OtpVerifySerializer."""

    def test_valid_payload_includes_code_and_phone(self):
        serializer = OtpVerifySerializer(data={'phone_number': '+917337264708', 'code': '245138'})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['code'], '245138')
        self.assertEqual(serializer.validated_data['phone_number'], '+917337264708')
        self.assertEqual(serializer.phone_e164, '+917337264708')

    def test_missing_code(self):
        serializer = OtpVerifySerializer(data={'phone_number': '+917337264708'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)

    def test_invalid_code_format(self):
        serializer = OtpVerifySerializer(data={'phone_number': '+917337264708', 'code': 'abc'})
        self.assertFalse(serializer.is_valid())
        self.assertIn('code', serializer.errors)
