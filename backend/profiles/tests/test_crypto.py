"""Unit tests for DL normalisation and Fernet encryption (FEAT-002 FR-20, F-tests).

The encryption key is read by ``profiles.utils.crypto`` through ``decouple.config``
rather than Django settings, so every test here patches that accessor instead of
touching the environment or a real ``.env``.
"""

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from profiles.models import DriverVerification
from profiles.utils.crypto import (
    decrypt_dl_number,
    encrypt_dl_number,
    get_dl_last_four,
    normalize_dl_number,
)

from .helpers import TEST_DL_ENCRYPTION_KEY, VALID_DL, patch_dl_key


class NormalizeDLNumberTests(SimpleTestCase):
    def test_uppercases_and_strips_separators_anywhere(self):
        # KD-12: separators are removed from any position, not just between
        # the RTO code and the year, and lowercase input is accepted.
        for raw in [
            'MH0120110012345',
            'mh01 20110012345',
            'MH01-20110012345',
            '  mh-01 2011-0012345  ',
            'M H 0 1 2 0 1 1 0 0 1 2 3 4 5',
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_dl_number(raw), VALID_DL)

    def test_other_whitespace_is_not_removed(self):
        # Only spaces and hyphens are stripped; a tab survives normalisation
        # (and therefore fails format validation).
        self.assertEqual(normalize_dl_number('MH01\t20110012345'), 'MH01\t20110012345')

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(normalize_dl_number(''), '')
        self.assertEqual(normalize_dl_number(None), '')


class DLLastFourTests(SimpleTestCase):
    def test_last_four_characters(self):
        self.assertEqual(get_dl_last_four(VALID_DL), '2345')

    def test_shorter_than_four_returns_whole_value(self):
        self.assertEqual(get_dl_last_four('12'), '12')

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(get_dl_last_four(''), '')

    def test_fits_the_display_column(self):
        max_length = DriverVerification._meta.get_field('dl_number_display').max_length
        self.assertLessEqual(len(get_dl_last_four(VALID_DL)), max_length)


class EncryptDecryptTests(SimpleTestCase):
    def setUp(self):
        patcher = patch_dl_key()
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_round_trip(self):
        ciphertext = encrypt_dl_number(VALID_DL)
        self.assertNotEqual(ciphertext, VALID_DL)
        self.assertNotIn(VALID_DL, ciphertext)
        self.assertEqual(decrypt_dl_number(ciphertext), VALID_DL)

    def test_same_input_gives_distinct_ciphertexts(self):
        first = encrypt_dl_number(VALID_DL)
        second = encrypt_dl_number(VALID_DL)
        self.assertNotEqual(first, second)
        self.assertEqual(decrypt_dl_number(first), decrypt_dl_number(second))

    def test_ciphertext_fits_the_model_column(self):
        max_length = DriverVerification._meta.get_field('dl_number').max_length
        self.assertEqual(max_length, 256)
        self.assertLessEqual(len(encrypt_dl_number(VALID_DL)), max_length)

    def test_empty_plaintext_rejected(self):
        with self.assertRaises(ValueError):
            encrypt_dl_number('')

    def test_empty_ciphertext_rejected(self):
        with self.assertRaises(ValueError):
            decrypt_dl_number('')

    def test_corrupt_ciphertext_raises_value_error(self):
        with self.assertRaises(ValueError):
            decrypt_dl_number('not-a-fernet-token')

    def test_wrong_key_cannot_decrypt(self):
        ciphertext = encrypt_dl_number(VALID_DL)
        other_key = 'b3RoZXItZmVhdDAwMi10ZXN0LWtleS0zMi1ieXRlcyE='
        self.assertNotEqual(other_key, TEST_DL_ENCRYPTION_KEY)
        with patch_dl_key(other_key):
            with self.assertRaises(ValueError):
                decrypt_dl_number(ciphertext)


class MissingOrMalformedKeyTests(SimpleTestCase):
    """KD-02 / KG-04: the key is validated lazily, at first encrypt, not at startup."""

    def test_unset_key_raises_at_first_encrypt(self):
        with patch_dl_key(None):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                encrypt_dl_number(VALID_DL)
        self.assertIn('DL_ENCRYPTION_KEY', str(ctx.exception))

    def test_empty_key_raises_at_first_encrypt(self):
        with patch_dl_key(''):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                encrypt_dl_number(VALID_DL)
        self.assertIn('empty', str(ctx.exception))

    def test_malformed_key_raises_at_first_encrypt(self):
        with patch_dl_key('too-short-not-base64'):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                encrypt_dl_number(VALID_DL)
        self.assertIn('invalid', str(ctx.exception).lower())

    def test_malformed_key_also_raises_on_decrypt(self):
        ciphertext = None
        with patch_dl_key():
            ciphertext = encrypt_dl_number(VALID_DL)
        with patch_dl_key('too-short-not-base64'):
            with self.assertRaises(ImproperlyConfigured):
                decrypt_dl_number(ciphertext)

    def test_improperly_configured_is_not_a_value_error(self):
        # Why the view cannot map it to a 4xx: the DL submit view only catches
        # ValueError, so a key problem surfaces as 500 server_error (KD-02).
        self.assertFalse(issubclass(ImproperlyConfigured, ValueError))
