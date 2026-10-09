# ADR: FEAT-002 User Onboarding — Architectural Decisions

**Date:** 2026-09-23
**Status:** accepted
**Feature:** FEAT-002 — User Onboarding Flow
**Author:** architect
**Applies to:** `backend/profiles/` (new app)

---

## Context

FEAT-002 introduces a structured onboarding flow that gates access to the main Spot Rides experience. Six non-obvious architectural choices were identified during design that have downstream implications for security, coupling, testability, and operational complexity. This ADR records those choices and the reasoning behind each.

---

## Decision 1 — DL number input normalisation (resolves OQ-03)

### Options considered

**A. Normalise lowercase input to uppercase before validation.**
Strip surrounding whitespace, convert to uppercase, then apply the regex. An input of `mh01 20110012345` is accepted as `MH01 20110012345`.

**B. Reject any input that is not already uppercase.**
Return `400 invalid_dl_format` if the raw input contains any lowercase letter.

### Decision: Option A — normalise to uppercase

**Rationale.** This project already normalises user input at the service boundary (phone numbers are normalised to E.164 before validation in `accounts/services/phone.py`). Consistent normalisation is a better user experience and reduces unnecessary support contacts caused by keyboard auto-lowercase on mobile devices. The risk of masking a data entry error is low because the DL format has strict structural constraints (state code + RTO + year + serial); any genuinely wrong DL that happens to be all-uppercase will fail provider verification. The normalised value is what gets stored.

**Implementation note.** The `profiles/services/dl_verification.py` service function `validate_dl_format(dl_number: str) -> str` strips whitespace, uppercases, applies the regex `^[A-Z]{2}[0-9]{2}[ -]?[0-9]{4}[0-9]{7}$`, and returns the normalised string on success or raises `InvalidDLFormat` on failure.

---

## Decision 2 — `UserProfile` creation timing (resolves OQ-05)

### Options considered

**A. Proactive creation via a Django post-save signal on `accounts.User`.**
When a `User` is created (or an OTP-verify response sets `is_new_user=True`), a post-save signal fires and inserts a `UserProfile` row with `onboarding_status=NOT_STARTED`.

Drawback: the signal lives in `accounts` (or a `profiles/apps.py` receiver), which requires either the `accounts` app to import `profiles` (circular-dependency risk), or a signal receiver in `profiles` that is connected at app-ready time. Signals are also harder to unit-test and can fire unexpectedly in test factories.

**B. Lazy creation on first access.**
`GET /api/onboarding/status/` (and any other onboarding endpoint that reads the profile) calls `UserProfile.objects.get_or_create(user=request.user)` in the service layer. The profile row is created if it does not exist.

### Decision: Option B — lazy creation via `get_or_create`

**Rationale.** Lazy creation eliminates any coupling between the `accounts` and `profiles` apps at the Python module level. The `accounts` app never needs to know that `profiles` exists. The edge case described in the requirements — a race between OTP-verify and the first status poll — is handled naturally: `get_or_create` is safe under concurrent requests due to PostgreSQL's unique constraint on `UserProfile.user` (the first writer wins; the second receives the existing row). The `GET /api/onboarding/status/` endpoint always succeeds with `200 not_started` for a brand-new user, satisfying the edge case requirement.

**Implementation note.** The shared `profiles/services/onboarding.py` function `get_or_create_profile(user)` wraps `UserProfile.objects.get_or_create(user=user, defaults={'onboarding_status': UserProfile.NOT_STARTED})`. All onboarding views call this before reading profile state.

---

## Decision 3 — DL number storage strategy (resolves OQ-10)

### Options considered

**A. Symmetric encryption at rest (Fernet / AES-128-CBC + HMAC-SHA256) + last-4 plaintext in a separate column.**

**B. One-way hash (HMAC-SHA256) for deduplication + last-4 plaintext display only. Full DL number is never stored.**

**C. Plaintext storage.**

### Decision: Option A — symmetric encryption at rest

**Rationale.**
- DL numbers are government-issued PII that can be used for identity theft. Plaintext storage (Option C) is unacceptable under reasonable data-at-rest protection requirements.
- A hash-only approach (Option B) makes the full DL irrecoverable. While re-submission creates a new DL, Indian compliance and legal discovery requirements may require the platform to produce the full DL number on a law-enforcement demand. Additionally, if a provider offers a "re-verify by stored reference" path it may still need the DL string. Encryption preserves optionality.
- Fernet (via `cryptography` library, already a transitive dependency) provides authenticated symmetric encryption with no additional infrastructure (no KMS, no HSM) appropriate for an early-stage platform.

**Implementation detail.**
- Field `dl_number` on `DriverVerification` stores the Fernet-encrypted ciphertext as a base64 string in a `CharField(256)` (ciphertext of a ~20-char DL is ~120 bytes encoded).
- Field `dl_number_display` stores the last 4 characters of the normalised plaintext DL as `CharField(4)`.
- Env var `DL_ENCRYPTION_KEY` holds the Fernet key (32-byte base64url; generated once with `Fernet.generate_key()`).
- A helper `profiles/crypto.py` exposes `encrypt_dl(plaintext) -> str` and `decrypt_dl(ciphertext) -> str`.
- The key is loaded via `python-decouple`: `DL_ENCRYPTION_KEY = config('DL_ENCRYPTION_KEY')`.
- Key rotation is out of scope for v1 but is enabled by storing a `dl_key_version` column (default `1`) for future migration use.

**Alternatives rejected.** Hash-only (Option B) rejected because full DL is irrecoverable. Plaintext (Option C) rejected on security grounds.

---

## Decision 4 — Onboarding gate enforcement mechanism (FR-14, FR-25)

### Options considered

**A. Django middleware (`process_response` or `process_request`).**
Intercepts every request, checks the path, and redirects or rejects if the user is not onboarded.

Drawback: middleware fires before DRF's auth layer resolves the user identity; the `request.user` may be `AnonymousUser` at that point. Middleware also applies to admin views, static file requests, and other non-API paths, requiring careful URL exemption lists. It violates the convention that auth is handled by DRF permission classes.

**B. DRF permission class `IsOnboardingComplete`.**
Added to `DEFAULT_PERMISSION_CLASSES` alongside `IsAuthenticated`. Checks `request.user.profile.onboarding_status == COMPLETE` and raises an `ApiError` with code `onboarding_incomplete` if not. Onboarding views (and the webhook) declare `permission_classes = [IsAuthenticated]` (without `IsOnboardingComplete`) to opt out.

### Decision: Option B — DRF permission class

**Rationale.** DRF permission classes run after authentication is resolved, keeping `request.user` populated. They integrate with the existing `core.exceptions.envelope_exception_handler` so the error response automatically follows the DEC-011 envelope. No URL exemption lists to maintain. Onboarding views self-declare their reduced permission set — this is explicit and grep-able.

**Implementation note.**
`profiles/permissions.py` defines:
- `IsOnboardingComplete` — for any authenticated endpoint outside the onboarding flow; returns `403 onboarding_incomplete` with `onboarding_status` and `next_step`.
- `IsDriverRole` — for driver-only endpoints (`POST /api/onboarding/driver/dl/`, `GET /api/onboarding/driver/dl/status/`); returns `403 not_a_driver` if `active_role != DRIVER`.
- `IsDriverVerified` — for driver-facing ride endpoints; checks `dl_verification_status == VERIFIED` in addition to `active_role == DRIVER` (enforces FR-25 independently of role field).

`settings.py` `DEFAULT_PERMISSION_CLASSES` becomes:
```python
[
    'rest_framework.permissions.IsAuthenticated',
    'profiles.permissions.IsOnboardingComplete',
]
```

---

## Decision 5 — `DriverVerification` model placement

### Options considered

**A. In the `profiles` app alongside `UserProfile`.**
Both models are OneToOneField extensions of `accounts.User`, both owned by the onboarding flow, and `DriverVerification` has no reason to be queried independently of a user's profile.

**B. In a separate `verification` app.**
Separates DL verification concerns into a dedicated app with its own migration history, admin, and service layer.

### Decision: Option A — place `DriverVerification` in the `profiles` app

**Rationale.** DL verification is a direct step in the onboarding state machine and has no consumers outside the onboarding flow in v1. Introducing a second app increases migration complexity (inter-app FK dependencies) and operational overhead (two migration histories, two app registrations) without any current benefit. The adapter layer inside `profiles/adapters/` gives sufficient separation of the I/O concern. Extraction to a standalone `verification` app remains possible later without a database schema change (just a migration with `app_label` renaming).

---

## Decision 6 — DL verification adapter interface

### Design

The adapter is a Python ABC in `profiles/adapters/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class DLVerificationResult:
    status: Literal["verified", "pending", "rejected"]
    provider_ref: Optional[str]       # provider-issued reference ID for async lookup
    rejection_reason: Optional[str]

class DLVerificationAdapter(ABC):
    @abstractmethod
    def submit(self, dl_number: str) -> DLVerificationResult:
        """Submit a DL number for verification.

        Returns a result immediately (synchronous provider) or a pending
        result with a provider_ref for later resolution via webhook
        (asynchronous provider). Must not raise; on provider error,
        raises DLProviderError so the service layer can treat it as pending.
        """
        ...

    @abstractmethod
    def validate_webhook(self, request_headers: dict, raw_body: bytes) -> bool:
        """Return True if the inbound webhook request has a valid signature."""
        ...
```

Concrete implementations:
- `profiles/adapters/mock.py` — `MockDLVerificationAdapter` used in tests and dev; configurable to return `verified`, `pending`, or `rejected` via a `settings.DL_ADAPTER_MOCK_RESULT`.
- Provider-specific adapters (e.g. `profiles/adapters/karza.py`, `profiles/adapters/idfy.py`) added when the provider is chosen (OQ-01).

The active adapter is loaded by name from settings:
```
DL_ADAPTER_CLASS = config('DL_ADAPTER_CLASS', default='profiles.adapters.mock.MockDLVerificationAdapter')
```

The service layer calls `get_dl_adapter()` (a factory in `profiles/adapters/__init__.py`) to obtain the configured adapter instance. Business logic in `profiles/services/dl_verification.py` is adapter-agnostic.

**Both sync and async paths are handled in the service layer, not in the adapter.** The adapter always returns a `DLVerificationResult`; it is the `status` field (`pending` vs `verified`/`rejected`) that drives which state transition the service applies.

---

## Decision 7 — `GET /api/auth/me/` amendment strategy

### Decision: extend `accounts/serializers.py::UserSerializer` with `SerializerMethodField` values

The `UserSerializer` adds `onboarding_status` and `active_role` via `SerializerMethodField` that access the reverse `profile` relation on `User`. If no profile exists (new user, profile not yet created), both fields return `null`. This approach:
- Does not import any symbol from `profiles` into `accounts` (no Python-level coupling).
- Works even if `profiles` is not yet installed (the `User` model has no FK to `profiles`; accessing `user.profile` raises `RelatedObjectDoesNotExist` which is caught and mapped to `null`).
- Requires no URL reconfiguration.

---

## Open questions that remain unresolved (require provider selection)

| ID | Question | Impact |
|----|----------|--------|
| OQ-01 | Which DL verification provider will be used? | Determines concrete adapter implementation, webhook header format, and available `rejection_reason` values. |
| OQ-02 | Does the provider support sync and/or async response mode? | Determines whether the `202 pending` path is always reachable or only a fallback. |
| OQ-04 | What webhook authentication mechanism does the provider supply? | `validate_webhook()` implementation in the concrete adapter. Placeholder is HMAC-SHA256 on `X-Signature` header; this must be replaced with the provider's actual mechanism. |
| OQ-06 | Minimum age for Passengers — 18 for both roles, or lower for Passengers? | Age validation range in `ProfileSubmitSerializer`. Currently both roles use 18–80. |
| OQ-07 | Vehicle registration number in v1 Driver onboarding? | If yes, expands scope to a new model and additional API steps. Currently deferred. |
