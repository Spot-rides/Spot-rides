"""DL webhook authentication and idempotency (FEAT-002 FR-58, FR-59, FR-11; SEC F-02).

These are the regression tests for the webhook signature control: the endpoint is
unauthenticated by user token and relies entirely on an HMAC-SHA256 signature of the
raw body, verified before the payload is parsed and before any database access.
"""

from django.test import override_settings

from profiles.models import DriverVerification, UserProfile

from .helpers import (
    MOCK_DL_ADAPTER,
    TEST_WEBHOOK_SECRET,
    OnboardingTestCase,
    hmac_hex,
    json_body,
)

REF = 'provider-ref-abc123'


@override_settings(DL_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET, DL_ADAPTER_CLASS=MOCK_DL_ADAPTER)
class DLWebhookSignatureTests(OnboardingTestCase):
    """A request is processed only with a correct hex HMAC of the exact raw body."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_named_profile(
            active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.PENDING_VERIFICATION,
        )
        self.dl = self.make_dl(
            status=DriverVerification.PENDING, dl_verification_ref=REF, attempt_count=1,
        )
        self.payload = {'reference_id': REF, 'status': 'verified'}

    def assertUnchanged(self):
        """No field of the DL record and no onboarding status may have moved."""
        self.dl.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.PENDING)
        self.assertIsNone(self.dl.dl_verified_at)
        self.assertIsNone(self.dl.dl_rejection_reason)
        self.assertEqual(self.dl.attempt_count, 1)
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_VERIFICATION)

    # ------------------------------------------------------------- accepted

    def test_valid_signature_is_processed(self):
        response = self.post_dl_webhook(self.payload)

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.VERIFIED)
        self.assertEqual(self.profile.onboarding_status, UserProfile.AWAITING_VEHICLE)

    def test_valid_signature_with_sha256_prefix_is_processed(self):
        response = self.post_dl_webhook(self.payload, prefix='sha256=')

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.VERIFIED)

    def test_signature_with_surrounding_whitespace_is_accepted(self):
        body = json_body(self.payload)
        response = self.client.post(
            '/api/onboarding/driver/dl/webhook/', data=body,
            content_type='application/json',
            headers={'X-DL-Signature': f'  {hmac_hex(body)}  '},
        )

        self.assertSuccess(response, 200)

    # ------------------------------------------------------------- rejected

    def test_missing_header_is_rejected(self):
        response = self.post_dl_webhook(self.payload, header_present=False)

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_empty_header_is_rejected(self):
        response = self.post_dl_webhook(self.payload, signature='')

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_bare_sha256_prefix_is_rejected(self):
        response = self.post_dl_webhook(self.payload, signature='sha256=')

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_signature_from_the_wrong_key_is_rejected(self):
        response = self.post_dl_webhook(self.payload, secret='the-wrong-secret')

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_tampered_body_with_a_valid_signature_for_other_bytes_is_rejected(self):
        signature = hmac_hex(json_body(self.payload))
        tampered = {'reference_id': REF, 'status': 'rejected'}

        response = self.post_dl_webhook(tampered, signature=signature)

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_retired_mock_signature_header_is_rejected(self):
        body = json_body(self.payload)
        response = self.client.post(
            '/api/onboarding/driver/dl/webhook/', data=body,
            content_type='application/json',
            headers={'X-Mock-Signature': 'mock-secret'},
        )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_non_hex_garbage_signature_is_rejected(self):
        response = self.post_dl_webhook(self.payload, signature='not-a-signature')

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_signature_is_checked_before_the_payload_is_parsed(self):
        # Malformed JSON with no signature must still be a 403, never a 400.
        response = self.client.post(
            '/api/onboarding/driver/dl/webhook/', data=b'{not json',
            content_type='application/json',
        )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    def test_signature_is_checked_before_any_database_access(self):
        # An unknown reference without a signature is a 403, not a 404.
        response = self.post_dl_webhook(
            {'reference_id': 'no-such-ref', 'status': 'verified'}, header_present=False,
        )

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()

    @override_settings(DL_ADAPTER_CLASS='profiles.adapters.nope.NoSuchAdapter')
    def test_unbuildable_adapter_fails_closed(self):
        # FR-58: an adapter that cannot be built rejects the webhook (it must never
        # fall through to processing).
        with self.assertLogs('profiles', level='ERROR'):
            response = self.post_dl_webhook(self.payload)

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.assertUnchanged()


@override_settings(DL_WEBHOOK_SECRET='', DL_ADAPTER_CLASS=MOCK_DL_ADAPTER)
class DLWebhookEmptySecretTests(OnboardingTestCase):
    """FR-58: an empty DL_WEBHOOK_SECRET rejects every delivery (fail closed)."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_named_profile(
            active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.PENDING_VERIFICATION,
        )
        self.dl = self.make_dl(status=DriverVerification.PENDING, dl_verification_ref=REF)
        self.payload = {'reference_id': REF, 'status': 'verified'}

    def test_signature_computed_with_an_empty_key_is_rejected(self):
        response = self.post_dl_webhook(self.payload, secret='')

        self.assertApiError(response, 403, 'invalid_webhook_signature')
        self.dl.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.PENDING)
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_VERIFICATION)

    def test_any_signature_is_rejected(self):
        response = self.post_dl_webhook(self.payload, secret='some-other-secret')

        self.assertApiError(response, 403, 'invalid_webhook_signature')

    def test_missing_header_is_rejected(self):
        response = self.post_dl_webhook(self.payload, header_present=False)

        self.assertApiError(response, 403, 'invalid_webhook_signature')


@override_settings(DL_WEBHOOK_SECRET=TEST_WEBHOOK_SECRET, DL_ADAPTER_CLASS=MOCK_DL_ADAPTER)
class DLWebhookProcessingTests(OnboardingTestCase):
    """FR-11 / FR-59: outcomes, idempotency and unknown references."""

    def setUp(self):
        super().setUp()
        self.profile = self.make_named_profile(
            active_role=UserProfile.DRIVER,
            onboarding_status=UserProfile.PENDING_VERIFICATION,
        )
        self.dl = self.make_dl(status=DriverVerification.PENDING, dl_verification_ref=REF)

    def test_rejected_result_keeps_the_user_in_pending_verification(self):
        response = self.post_dl_webhook(
            {'reference_id': REF, 'status': 'rejected', 'rejection_reason': 'DL not found'},
        )

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.REJECTED)
        self.assertEqual(self.dl.dl_rejection_reason, 'DL not found')
        # AC-10: the status deliberately stays pending_verification after a webhook rejection.
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_VERIFICATION)

    def test_rejection_reason_is_sanitised_before_storage(self):
        response = self.post_dl_webhook({
            'reference_id': REF, 'status': 'rejected',
            'rejection_reason': '<b>Bad</b>   licence\x07 record',
        })

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_rejection_reason, 'Bad licence record')

    def test_duplicate_delivery_returns_200_and_changes_nothing(self):
        self.post_dl_webhook({'reference_id': REF, 'status': 'verified'})
        self.dl.refresh_from_db()
        verified_at = self.dl.dl_verified_at

        response = self.post_dl_webhook({'reference_id': REF, 'status': 'verified'})

        # FR-59 (v9 decision): a re-delivery is 200, not 409 already_processed.
        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verified_at, verified_at)
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.VERIFIED)

    def test_late_contradictory_delivery_is_ignored(self):
        self.post_dl_webhook({'reference_id': REF, 'status': 'verified'})

        response = self.post_dl_webhook(
            {'reference_id': REF, 'status': 'rejected', 'rejection_reason': 'too late'},
        )

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.VERIFIED)
        self.assertIsNone(self.dl.dl_rejection_reason)

    def test_delivery_after_a_rejection_is_ignored(self):
        self.dl.dl_verification_status = DriverVerification.REJECTED
        self.dl.dl_rejection_reason = 'original reason'
        self.dl.save()

        response = self.post_dl_webhook({'reference_id': REF, 'status': 'verified'})

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.REJECTED)
        self.assertEqual(self.dl.dl_rejection_reason, 'original reason')
        self.assertEqual(self.profile.onboarding_status, UserProfile.PENDING_VERIFICATION)

    def test_unknown_reference_is_404(self):
        with self.assertLogs('profiles', level='WARNING'):
            response = self.post_dl_webhook(
                {'reference_id': 'no-such-ref', 'status': 'verified'},
            )

        self.assertApiError(response, 404, 'dl_reference_not_found')
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.PENDING)

    def test_verified_result_for_a_user_who_switched_to_passenger_keeps_them_complete(self):
        self.profile.active_role = UserProfile.PASSENGER
        self.profile.onboarding_status = UserProfile.COMPLETE
        self.profile.save()

        response = self.post_dl_webhook({'reference_id': REF, 'status': 'verified'})

        self.assertSuccess(response, 200)
        self.dl.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.VERIFIED)
        self.assertEqual(self.profile.onboarding_status, UserProfile.COMPLETE)

    # ------------------------------------------------------- malformed payloads

    def test_missing_reference_id_is_400_invalid_request(self):
        # KD-05: the webhook payload serializer is unmapped, so the shared handler
        # renders a malformed body as invalid_request with per-field messages.
        response = self.post_dl_webhook({'status': 'verified'})

        error = self.assertApiError(response, 400, 'invalid_request')
        self.assertIn('reference_id', error['fields'])
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.PENDING)

    def test_blank_reference_id_is_400(self):
        response = self.post_dl_webhook({'reference_id': '', 'status': 'verified'})

        self.assertApiError(response, 400, 'invalid_request')

    def test_unrecognised_status_is_400(self):
        response = self.post_dl_webhook({'reference_id': REF, 'status': 'maybe'})

        error = self.assertApiError(response, 400, 'invalid_request')
        self.assertIn('status', error['fields'])
        self.dl.refresh_from_db()
        self.assertEqual(self.dl.dl_verification_status, DriverVerification.PENDING)

    def test_pending_status_is_not_accepted_from_the_webhook(self):
        response = self.post_dl_webhook({'reference_id': REF, 'status': 'pending'})

        self.assertApiError(response, 400, 'invalid_request')
