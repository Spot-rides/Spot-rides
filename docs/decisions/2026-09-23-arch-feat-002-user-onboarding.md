# ADR: FEAT-002 User Onboarding — Architectural Decisions

**Date:** 2026-09-23
**Updated:** 2026-10-17 (v3: vehicle RC verification, Decisions 11-26; v4: Decision 27; v5: Decision 28, role switch fix)
**Status:** accepted
**Feature:** FEAT-002 — User Onboarding Flow
**Author:** architect
**Applies to:** `backend/profiles/` (new app)

---

## Context

FEAT-002 introduces a structured onboarding flow that gates access to the main Spot Rides experience. Several non-obvious architectural choices were identified during design that have downstream implications for security, coupling, testability, and operational complexity. This ADR records those choices and the reasoning behind each.

**Update (2026-10-10):** Requirements v3 added vehicle registration to Driver onboarding, introducing Decision 8 (Vehicle model relationship type) and Decision 9 (Vehicle model placement). OQ-01, OQ-02, OQ-04, OQ-06, and OQ-07 have been resolved.

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
- A helper `profiles/utils/crypto.py` exposes `encrypt_dl_number(plaintext) -> str` and related helpers.
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
- `IsDriverRole` — for driver-only endpoints (`POST /api/onboarding/driver/dl/`, `POST /api/onboarding/driver/vehicle/`, `GET /api/onboarding/driver/dl/status/`); returns `403 not_a_driver` if `active_role != DRIVER`.
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
- `profiles/adapters/mock.py` — `MockDLVerificationAdapter` used in tests and dev; configurable to return `verified`, `pending`, or `rejected`.
- `profiles/adapters/digilocker.py` — `DigiLockerDLVerificationAdapter` for production; uses DigiLocker Pull URI API with OAuth 2.0 authentication.

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

## Decision 8 — Vehicle model relationship type (NEW, resolves OQ-07 partially)

### Options considered

**A. `OneToOneField` to `accounts.User`.**
Enforces exactly one vehicle per user at the database level. Simple, no application-layer uniqueness check needed.

Drawback: when multi-vehicle support is added in the future, this requires a schema migration from OneToOneField to ForeignKey. This migration is disruptive: it drops and recreates the unique constraint, requires a data migration if the constraint already has data, and the rollback path is complex.

**B. `ForeignKey` to `accounts.User` with application-layer enforcement of max 1 active vehicle in v1.**
Allows multiple vehicle rows per user at the database level. The `is_active` boolean flag marks the active vehicle. The service layer checks `user.vehicles.filter(is_active=True).exists()` before creating a new vehicle and raises `VehicleAlreadyRegistered` if one exists.

### Decision: Option B — ForeignKey with application-layer enforcement

**Rationale.**
- The product roadmap explicitly mentions multi-vehicle support as a future feature. Using ForeignKey now avoids a disruptive schema migration later.
- The `is_active` field provides a natural mechanism for managing active/inactive vehicles when multi-vehicle is added.
- Application-layer enforcement of "max 1 active vehicle" is straightforward: a single `.exists()` query in `register_vehicle()` inside a `transaction.atomic` block.
- The trade-off is that the database does not independently enforce the single-vehicle invariant. A bug in the service layer could create multiple active vehicles. This risk is acceptable because: (a) the `register_vehicle()` function is the only write path for vehicles in v1, (b) the function runs in a transaction, and (c) the risk can be further mitigated with a periodic data integrity check if needed.

**Implementation note.**
- `Vehicle.user` is `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicles')`.
- Composite index on `(user, is_active)` supports the common query pattern.
- `register_vehicle()` calls `user.vehicles.filter(is_active=True).exists()` before creating. If true, raises `VehicleAlreadyRegistered`.

---

## Decision 9 — Vehicle model placement

### Options considered

**A. In the `profiles` app alongside `UserProfile` and `DriverVerification`.**
All onboarding-related models live in the same app.

**B. In a separate `vehicles` app.**
Separates vehicle management into its own domain.

### Decision: Option A — place `Vehicle` in the `profiles` app

**Rationale.** Same reasoning as Decision 5 (DriverVerification placement). Vehicle registration is a step in the onboarding state machine in v1 and has no consumers outside the onboarding flow. When multi-vehicle management, vehicle editing, or vehicle-to-ride assignment becomes a first-class domain, extraction to a standalone `vehicles` app can be done without a schema change (just a migration with `app_label` renaming). For now, co-location reduces migration complexity and app registration overhead.

---

## Decision 10 — Vehicle registration number storage (plaintext)

### Options considered

**A. Plaintext storage.**
Store the registration number as-is in a `CharField(15)`.

**B. Encrypted storage (Fernet, same as DL numbers).**
Encrypt the registration number at rest using the same Fernet scheme.

### Decision: Option A — plaintext storage

**Rationale.** Vehicle registration numbers are publicly visible on the physical vehicle (painted on license plates). They are not PII in the same category as DL numbers, Aadhaar numbers, or PAN numbers. Encrypting them adds complexity (key management, decrypt on every read) without meaningful security benefit. The requirements (FR-31) explicitly state plaintext storage. If a future compliance requirement changes this assessment, encryption can be added without API contract changes.

---

## Resolved open questions

| ID | Question | Resolution |
|----|----------|------------|
| OQ-01 | Which DL verification provider will be used? | **Resolved (v2).** DigiLocker Pull URI API. |
| OQ-02 | Does the provider support sync and/or async response mode? | **Resolved (v2).** DigiLocker is synchronous. Async/pending path retained as timeout fallback only. |
| OQ-03 | Should DL number validator normalise lowercase to uppercase? | **Resolved (Decision 1).** Normalise to uppercase. |
| OQ-04 | What webhook authentication mechanism does the provider supply? | **Resolved (v2).** HMAC-SHA256 if webhook ever activated. Webhook not used in primary DigiLocker flow. |
| OQ-05 | Should UserProfile be created proactively or lazily? | **Resolved (Decision 2).** Lazy creation via get_or_create. |
| OQ-06 | Minimum age for Passengers? | **Resolved (v2).** 18 for both roles. |
| OQ-07 | Vehicle registration in v1 Driver onboarding? | **Resolved (v3).** Yes, included. See FR-27 through FR-31, Decisions 8-10. |
| OQ-10 | DL number storage: encrypted or hashed? | **Resolved (Decision 3).** Fernet symmetric encryption. |

## Open questions that remain unresolved

| ID | Question | Impact |
|----|----------|--------|
| OQ-08 | How should Drivers in `pending_verification` state be notified when their DL result arrives? Push notifications are a non-goal; will the app poll on launch? | UX concern. Client currently polls on app open. May need push notifications in a future release. |
| OQ-09 | Auto-rejection of stale `PENDING_VERIFICATION` drivers after N hours — requires a Celery beat task and a product policy decision. | Operational concern. Drivers could be stuck indefinitely in pending state without this. Deferred to a follow-up. |

---

## Decisions added for requirements v4 (2026-10-15): vehicle RC verification

Context: FEAT-002 requirements v4 adds optional, feature-flagged RC verification (FR-27..FR-50). It ships OFF; only a mock adapter is built. Decisions 11-26 record the architecture choices; the full design is in ARCH-002 v3. These decisions supersede the v2 statements that no third-party verification of vehicle registration is performed and that duplicates may be flagged "in future" (see Decision 17 and ARCH-002 RISK-006).

### Decision 11 — Flag-off isolation: one early branch, legacy body untouched

**Options.** (A) Branch inside `register_vehicle()`; (B) separate URL or view per mode; (C) rewrite `register_vehicle()` as a unified flow with the flag as a sub-condition.

**Decision: A.** `register_vehicle()` becomes `if not settings.RC_VERIFICATION_ENABLED: return _register_vehicle_self_declared(...)` followed by a lazy import and call of `rc_verification.register_vehicle_with_rc(...)`. `_register_vehicle_self_declared` is the existing function body moved verbatim (same `@transaction.atomic`, same `ValueError` messages, same `(profile, vehicle)` return). The flag is read at call time.

**Rationale.** The constraint is that the flag-off launch cannot be broken by RC code. With one `if`, a lazy import and an unchanged body, review of the flag-off path is a one-screen diff, the RC module is not even imported, and no RC setting (other than the flag), adapter, query or column write is involved. The flag-on path returns the same tuple, so the view needs no mode branching; RC results ride on the `Vehicle` row (`NULL` when the flag is off). View/serializer edits are limited to additive nullable response fields and `compute_next_step(profile)`, which returns the identical `none` for `COMPLETE`.

### Decision 12 — RC adapter contract and settings-driven factory

**Decision.** `RCVerificationAdapter` ABC with `from_settings(cls, settings)`, `verify(registration_number, user_id)`, `validate_webhook(headers, body)` and `parse_webhook(body)`; `RCVerificationResult` frozen dataclass with every provider field optional and `owner_name` declared `repr=False`; `RCAdapterError` for non-timeout failures, builtin `TimeoutError` for timeouts. `get_rc_adapter()` loads `settings.RC_ADAPTER_CLASS` via `import_string` and calls `from_settings`; it builds a new instance per call and there is no module global and no private import in views. `timeout_seconds` is passed to the adapter, which applies it to its own HTTP calls.

**Rationale.** The DL module's hardcoded global (`_adapter`, imported by views) cannot be swapped by configuration and was the exact wiring gap PLAN-003 asked not to copy. `from_settings` lets each adapter read its own settings without `isinstance` checks in the factory. `parse_webhook` is on the adapter because provider payload shapes differ, and FR-42 requires a verified webhook to feed owner/class data into the same rules as a synchronous result. The service never cuts a call short itself (no threads/signals); timeouts are an adapter responsibility, which is the only reliable place to apply them. Adapters must map "not found / blacklisted / blocked" to `rejected` so the service needs no provider-specific vocabulary.

### Decision 13 — Mock adapter modes, webhook signature, and the production guard

**Decision.** `MockRCVerificationAdapter` implements the six FR-49 modes (`sync_verified` default, `sync_verified_name_mismatch`, `async_pending`, `sync_rejected`, `timeout`, `provider_error`), selected by `RC_ADAPTER_MOCK_RESULT`; unknown modes raise `ImproperlyConfigured`. In `sync_verified` the owner name equals the user's profile name and `vehicle_class` is `None`, so the class check is skipped and all six vehicle types are testable. The mock webhook verifies `HMAC-SHA256(RC_WEBHOOK_SECRET, raw_body)` against `x-rc-signature` with `hmac.compare_digest` and fails closed if the secret is empty.

**Production guard (concrete, three layers).** (1) `config/settings.py`, only when `RC_VERIFICATION_ENABLED`: raise `ImproperlyConfigured` if `not DEBUG` and `'mock' in RC_ADAPTER_CLASS.lower()` (and for an empty/placeholder `RC_WEBHOOK_SECRET`, `ONBOARDING_GATE_ENABLED` false, `RC_MAX_ATTEMPTS < 1`, `RC_PROVIDER_TIMEOUT_SECONDS <= 0`). (2) `RC_MOCK_ADAPTER_FORBIDDEN = RC_VERIFICATION_ENABLED and not DEBUG`, computed at import from the environment `DEBUG`; `get_rc_adapter()` refuses any `MockRCVerificationAdapter` subclass when it is true. (3) The mock's webhook fails closed without a secret.

**Rationale.** A Django system check does not run when gunicorn/WSGI starts, so only an import-time settings raise protects every entry point. Capturing `DEBUG` at import (rather than reading `settings.DEBUG` at call time) avoids false positives because Django's test runner forces `DEBUG=False`. The webhook is HMAC over the body rather than a static header (PLAN-003 D3) so the mock exercises the same mechanism as a real provider. Residual risk: running production with `DEBUG=True` bypasses the guard; that is already a critical misconfiguration.

### Decision 14 — Provider call outside the DB transaction (three phases)

**Decision.** `register_vehicle_with_rc` runs: (1) guard in a short `transaction.atomic` taking `select_for_update` on `UserProfile` then `Vehicle`; (2) the adapter call with no transaction open; (3) decision and persistence in a second short `atomic` that re-locks and re-validates. Lock order is always profile then vehicle, including webhook and admin paths. `RCVerificationRejected` is raised only after phase 3 has committed. `ATOMIC_REQUESTS` must remain False. A first-submission provider error writes no `Vehicle` row. The DL module, which calls its provider inside `@transaction.atomic`, is not changed.

**Rationale.** NFR-REL-03 forbids holding a write transaction across the provider call. The cost is one extra lock/validate cycle and, on a concurrent double-submit, one wasted provider call followed by a `409`. Raising a domain error inside `atomic` would roll back the persisted rejection and attempt count, hence raise-after-commit. A Redis per-user lock to prevent the duplicate call was considered and not adopted (extra dependency in the request path; not needed with the mock).

### Decision 15 — Domain exceptions, no substring mapping, for all new code

**Decision.** New code raises `ApiError` subclasses with stable codes (`RCVerificationPending`, `RCAlreadyVerified`, `RCProviderError`, `MaxRCAttemptsExceeded`, `RCVerificationRejected`, `RCReferenceNotFound`, `MalformedWebhookPayload`, `RCReviewStateError`; existing classes reused). `ApiError` is not a `ValueError`, so the legacy `except ValueError` blocks (vehicle, DL, role views) are never reached by RC errors and are left unchanged. `switch_role` adds no new `ValueError` messages. The webhook view stops using `except Exception` plus `'already' in str(e)` for RC; terminal state is signalled by `AlreadyProcessed`.

**Rationale.** FR constraint "no substring matching" and the concrete hazard that "verified"/"DL" in any new message would be routed to `DLNotVerified`. Leaving the legacy mapping untouched keeps the flag-off path byte-stable (Decision 11).

### Decision 16 — Rejection response stays `422 rc_verification_rejected`; envelope gains optional `extra` (resolves OQ-R12a)

**Options.** (A) `422` with `onboarding_status`, `next_step`, `rc_verification_status`, `rc_attempts_remaining` inside `error`, as the requirements specify; (B) `200` with `rc_verification_status = "rejected"` (PLAN-003/DL style); (C) `422` with the extra data under `data`.

**Decision: A, with a small additive extension of DEC-011.** Concrete conflict found: DEC-011's `error` object is `{code, detail, fields, retry_after}` and `ApiError` cannot carry other data, so (A) cannot be produced as specified; (C) violates "data is null on failure". The extension: `ApiError.__init__(detail, retry_after, extra=None)` and `error_envelope(..., extra=None)` merge `extra` keys flat into `error`; keys colliding with the four reserved ones are rejected at construction. It is optional and defaults to none, so every existing error is unchanged and existing clients ignore unknown keys. The same mechanism delivers `next_step` for `onboarding_incomplete`, which the requirements already specify (it was also specified for `dl_required`, which is no longer returned since Decision 28). This is recorded as an amendment to DEC-011 (no change to its other rules).

**Rationale.** Product explicitly chose an error code; a `200` would also hide a failed vehicle verification from generic client error handling. The DL sync-rejection path returns `202` today; that inconsistency is noted but not changed (Decision 26).

### Decision 17 — Owner-name matching, class decision and data minimisation live in the service layer

**Decision.** `classify_owner_match` (match/partial/mismatch/not_checked), `check_vehicle_class` and `decide_rc_outcome` are pure functions in `services/rc_matching.py`. Name match requires every profile token to match, at most one by initial, and at least one full-token match; masked owners (`*` or `XXX`) are `not_checked`; relation tails (S/O etc.) and honorifics are stripped; non-Latin profile names always go to review. Only `match` auto-verifies; any other classification on a provider-`verified` result sends the vehicle to review, never to rejection. A class conflict rejects even when the name does not match. `rc_owner_name` is stored only when the vehicle goes to name review; provider strings are clipped to column widths; the raw payload is never stored; any rejection reason is sanitised and has the owner name redacted. Duplicate registrations are allowed (no unique constraint, non-unique index, flag-on WARNING log, admin indicator).

**Rationale.** FR-38/39/47 and the constraint that RC business rules are identical across providers. Requiring one full-token match prevents "P SHARMA" style initial-only matches from auto-verifying. Storing the owner name only for review cases is the minimum the reviewer needs and reduces the DPDP surface while OQ-R7 (retention) is open; `_clear_owner_data` is the single hook for a purge policy.

### Decision 18 — `vehicle_type` to RC vehicle class mapping

**Decision.** RC class strings are normalised and mapped, first hit wins, to `NON_PASSENGER` (goods/truck/tractor/trailer/bus/HMV/HGV/LGV...), `THREE_WHEELER`, `TWO_WHEELER`, `FOUR_WHEELER`, else unknown. Compatibility: `car`/`suv`/`hatchback`/`sedan` -> `FOUR_WHEELER` only; `auto_rickshaw` -> `THREE_WHEELER` only; `bike` -> `TWO_WHEELER` only. Rejected on a known category outside the compatible one, including `NON_PASSENGER` for every type. Unknown/missing class never rejects. The four car-family types are not distinguished from each other. Exact keyword table: ARCH-002 v3.

**Rationale.** An RC class does not reliably encode sedan/hatchback/SUV, so finer distinctions would create false rejections. Keyword lists are constants covered by a table test because provider class strings are unverified (PLAN-003); unknown strings skip rather than reject, consistent with "reject only on a clear conflict".

### Decision 19 — One `next_step` map; gate returns `onboarding_incomplete` with data

**Decision.** `NEXT_STEP_BY_STATUS` and `compute_next_step(profile)` in `services/onboarding.py` replace the three duplicated view maps and the hard-coded literals (values for all existing statuses are identical). `ConditionalOnboardingGate` raises `OnboardingIncomplete(extra={'onboarding_status', 'next_step'})` instead of returning `False`.

**Rationale.** Adding `pending_rc_verification` would otherwise touch every copy. The gate currently yields a generic `permission_denied` without `next_step`, so FR-14 and AC-41 are not met today; the fix reuses the Decision 16 mechanism, is dormant while `ONBOARDING_GATE_ENABLED` is False, and does not touch the vehicle endpoints (they override `permission_classes`). The gate already lazy-imports `profiles`; moving it into `profiles.permissions` is the cleaner long-term home and is left for a later change.

### Decision 20 — `switch_role` derivation and grandfathered drivers (resolves OQ-R12b)

**Decision.** (Partly superseded by Decision 28: from v5 the derivation below applies in both flag modes, the switch to passenger is accepted from every non-initial status, and `next_step` is always returned.) Flag OFF: unchanged in v3 (see Decision 28 for the v5 change). Flag ON, switching to `driver` with a verified DL derives status from the newest active vehicle: `verified` or `NULL` -> `complete`; `pending` -> `pending_rc_verification`; `rejected` -> `awaiting_vehicle`; **no vehicle row and `vehicle_step_exempt` set -> `complete`** (grandfathered); no vehicle row and marker not set -> `awaiting_vehicle` (superseded by Decision 27: the original rule "no vehicle row while the current status is `COMPLETE` -> `complete`" was replaced by the explicit marker). `PENDING_RC_VERIFICATION` is allowed through the entry guard (flag ON), and switching to `passenger` from it sets `COMPLETE`. The response adds `next_step` only for `awaiting_vehicle` / `pending_rc_verification`, with HTTP `200` (v5: `next_step` is always returned, Decision 28).

**Rationale.** (Revised: the original argument that the grandfather rule needs no new column was wrong; see Decision 27.) The product preference (OQ-R12b) and PLAN-003 D5 are to keep pre-vehicle-step drivers `COMPLETE`; requirements v6 (FR-43/AC-48) now state this. Setting `COMPLETE` on a switch to passenger prevents a passenger being gated out of the app while a vehicle is pending, and keeps later webhook/admin resolutions from moving a passenger to `awaiting_vehicle`. The v3 note that the `PENDING_VERIFICATION` behaviour (status left unchanged on a switch to passenger) was not altered, and the open item that a toggled user with a rejected vehicle and exhausted attempts cannot return to passenger (ARCH-002 U3), are both superseded by Decision 28 (every non-initial status can switch to passenger and ends `complete`).

### Decision 27 — Explicit `vehicle_step_exempt` marker for grandfathered drivers (supersedes the no-new-column rule in Decision 20)

**Decision.** Add `UserProfile.vehicle_step_exempt` (`BooleanField`, `default=False`, `db_default=False`) in migration `0004_userprofile_vehicle_step_exempt`. `derive_driver_status` with no vehicle row returns `complete` if the marker is set, else `awaiting_vehicle` (`next_step = vehicle_registration`); rows that exist keep the Decision 20 derivation. The marker is set only by a data step (`RunPython`) in `0004`, which marks profiles that are `complete`, have a `DriverVerification` row, and have no `is_active` `Vehicle` row. The step is idempotent; nothing else ever sets the marker (not application code, not admin, where it is read-only). Reverse: the data step clears the marker, then the column is dropped.

**Rationale.** The Decision 20 rule (no row + currently `COMPLETE` => grandfathered) is bypassable through FR-52: a driver in `awaiting_vehicle` who never submitted a vehicle can switch to passenger (which sets `complete`) and back to driver, and would then be treated as grandfathered and become `COMPLETE` without a vehicle. A stored marker cannot be reached by that path. This reverses the earlier rejection of a marker (the "current status is `COMPLETE`" condition is not an invariant). It also removes the "staff deleted a vehicle row" edge that Decision 20 accepted.

**Accepted edge cases of the marking rule.** (1) A profile whose only vehicle is inactive (`is_active = False`) has no active row and is marked, so it is treated as grandfathered. (2) A `complete` profile with a pending or rejected `DriverVerification` record is marked; this is harmless because switching to driver still requires a verified DL, so the marker has no effect until a DL is verified. Passengers who never began the driver path have no `DriverVerification` row and are not marked.

### Decision 21 — RC webhook with the flag OFF returns `404`; verification and parsing order (resolves OQ-R12c)

**Decision.** `RCWebhookView.post`: (1) flag OFF -> DRF `NotFound` before the body is read, no state change; (2) `validate_webhook` -> `403 invalid_webhook_signature`; (3) `parse_webhook` -> `400 invalid_webhook_payload`; (4) `process_rc_webhook` -> `404 rc_reference_not_found` / `409 already_processed` / `200`. The route is always registered; the check is at runtime so tests and toggles behave without a URLconf reload.

**Rationale.** A 404 makes the endpoint indistinguishable from nonexistent while the feature is off and avoids an inert `200` that would tell a provider the delivery succeeded (so it would not retry). Both options change no state, per product. The flag check needs no I/O, so signature-before-DB-access (NFR-SEC-02/FR-42) still holds.

### Decision 22 — Migration `0003`, not squashed into the uncommitted `0002`; `db_default` for the counter

**Options.** (A) Fold RC columns into `0002_add_vehicle`; (B) new additive `0003`.

**Decision: B.** Commit `0002` unchanged, generate `0003_vehicle_rc_verification` (AlterField choices, 12 AddField, 2 indexes, partial unique constraint on `rc_verification_ref`, `review_rc` permission). `rc_attempt_count` uses `default=0, db_default=0`. Migration runs before the code deploy.

**Rationale.** 0002 was generated on 2026-10-10 and any developer database may already have applied it; editing it would leave those databases out of sync with no error until runtime. The saving from squashing is one file. `db_default` matters because `AddField(default=0)` drops the DB default after backfill, so a still-running v2 process inserting a `Vehicle` between migrate and deploy would violate `NOT NULL`.

### Decision 23 — Admin review queue (OQ-R13 remains an operations item)

**Decision.** `VehicleAdmin`: list of registration number, user, type, `rc_verification_status`, `rc_name_match`, `rc_attempt_count`, `rc_submitted_at` and an annotated other-drivers-with-same-registration count; filters on status, name match, needs-review, duplicates; search by registration number and phone; owner name only on the read-only detail view and never in list/filter/search; actions Approve, Reject (reason from an `ActionForm` field) and Reset attempts, guarded by a new `profiles.review_rc` permission, implemented by service functions, audited through `ModelAdmin.log_change` (Django `LogEntry`); add and delete disabled. Approve is allowed for `pending` and also for `rejected` (FR-40 manual recovery after the limit); reject only for `pending`. Admin actions work regardless of the flag.

**Rationale.** Reuses Django admin and its audit log (no new table). A dedicated permission lets operations be a reviewer group instead of all staff. Owner/SLA/queue monitoring are operations decisions (OQ-R13) and are not designed here. Recommended follow-up: make `UserProfile.onboarding_status` read-only for non-superusers.

### Decision 24 — Settings and environment variables

**Decision.** `RC_VERIFICATION_ENABLED` (False), `RC_ADAPTER_CLASS` (mock path), `RC_ADAPTER_MOCK_RESULT` (`sync_verified`), `RC_PROVIDER_TIMEOUT_SECONDS` (5), `RC_MAX_ATTEMPTS` (3), `RC_WEBHOOK_SECRET` (empty = fail closed), loaded with `python-decouple`; validated only when the flag is ON; no RC variable is required for `manage.py check` or for the flag-off launch. Placeholders go in `backend/.env.example` (existence unverified by this review; append or create).

**Rationale.** Flag-off startup must never depend on RC configuration (AC-51).

### Decision 25 — Logging allow-list; no PII

**Decision.** All RC logging goes through one helper that drops fields outside an allow-list (ids, counts, classifications, provider reference, adapter name, exception type, duplicate count, staff id). Never logged: owner name, raw payload or result object, free-text reasons, adapter exception messages, `exc_info` for adapter errors, registration number next to a user id. `owner_name` is `repr=False`.

**Rationale.** `JsonFormatter` writes every `extra` key verbatim and the `profiles` logger has no redaction handler, so prevention at the call site is the only control (FR-47, NFR-SEC-07, AC-52). Event names are listed in ARCH-002 v3.

### Decision 26 — What this change deliberately does NOT fix

**Not fixed (tracked separately):** the DL module's module-global adapter imported by views, the provider call inside `@transaction.atomic`, the missing `DL_*` settings and hardcoded attempt limit `3`, the missing DL `_sanitise_rejection_reason`, the DL mock's `==` comparison and default secret, the DL webhook's silent idempotency, `DLSubmitView` returning `202` for a synchronous DL rejection, and the absent/unverified `backend/.env.example`.

**Pre-existing flag-off vehicle-endpoint discrepancies, preserved so flag-off behaviour does not change:** serializer errors surface as `400 invalid_request` instead of `invalid_registration_format` / `invalid_vehicle_type`; a Passenger gets `403 permission_denied` from `IsDriverRole` instead of `not_a_driver`; a `COMPLETE` Driver posting a vehicle gets `403 dl_not_verified` instead of `409 vehicle_already_registered` (flag ON follows the specified `409`); `vehicle_type` is returned upper-case. These make AC-28 and AC-29 fail as written today. A "contract conformance" change would fix them but alters flag-off error bodies, so it needs explicit approval. New RC code is specified-conformant where it is new (`RequireDriverRole` on the status view, `onboarding_incomplete` from the gate).

**Rationale.** The user's instruction is that flag-off must behave exactly as today and that DL gaps are out of scope; mixing fixes into this change would widen the blast radius of the launch path.

### Decision 28 — Switching to driver without a verified DL starts driver setup; one `switch_role` for both flag modes (v5, 2026-10-17)

**Context.** `PATCH /api/profile/role/` to `driver` by an eligible user with no verified DL (no `DriverVerification` row, or a rejected one) returned `400 dl_required`. That created a dead end: `POST /api/onboarding/driver/dl/` requires `active_role = driver` and `onboarding_status` in `awaiting_dl` / `pending_verification`, and a `COMPLETE` passenger is neither, so the client had no route to DL submission. In practice only users who chose Driver during initial onboarding could ever become drivers. The same code area had related gaps: the passenger exit from `awaiting_vehicle` worked only with `RC_VERIFICATION_ENABLED` on, the RC-enabled `switch_role` was a separate implementation from the flag-OFF one, the flag-OFF variant took no row lock, and a verified-DL webhook advanced any profile to `awaiting_vehicle`, which would push a `COMPLETE` passenger with a pending DL behind the onboarding gate.

**Decision.**
1. Switch to `driver` with no verified DL (no row, or rejected): set `active_role = driver`, `onboarding_status = awaiting_dl`, return `200` with `next_step = dl_submission`. The DL -> vehicle -> (RC) flow then applies unchanged. The DL attempt limit still applies and toggling roles does not reset `attempt_count`. A pending DL keeps `pending_verification` (`202`).
2. Switch to `passenger` is allowed from `complete`, `awaiting_dl`, `pending_verification`, `awaiting_vehicle` and `pending_rc_verification` in both flag modes; the result is `complete`, and `DriverVerification` and `Vehicle` rows are kept.
3. Switch to `driver` with a verified DL: `complete` only if an active vehicle exists or `vehicle_step_exempt` is set, otherwise `awaiting_vehicle` with `next_step = vehicle_registration`, in both flag modes. Flag ON keeps the RC-status derivation (`derive_driver_status`) for existing vehicles; flag OFF ignores the RC columns.
4. `switch_role` is a single implementation for both flag modes (the separate RC-enabled variant was removed) and takes a `select_for_update` lock on the profile (vehicle locked after it) in both modes.
5. `process_webhook_result` advances to `awaiting_vehicle` on a verified DL webhook only when the profile is `pending_verification`.
6. `next_step` is always returned by the role-switch response. `400 invalid_onboarding_state` remains for the inconsistent legacy case of a passenger row in `awaiting_vehicle` asking for `driver` with the flag ON (`VehicleStepIncomplete`; recoverable by switching to passenger first; with the flag OFF the same case yields `403 onboarding_incomplete`). `DLRequired` is no longer raised anywhere; the class is left in `profiles/exceptions.py` unused.

**Alternatives considered.**
- *Let a `COMPLETE` passenger call the DL endpoint directly.* Rejected: it leaves the user in the passenger role mid-verification (role, status and DL state disagree), requires loosening `IsDriverRole` and the state guard on the DL endpoint, and forces the webhook to special-case passengers.
- *Keep `400 dl_required` and add a dedicated "start driver setup" endpoint.* Rejected: an extra endpoint and client call for something the role switch already expresses.
- *Keep two `switch_role` implementations (flag ON / flag OFF).* Rejected: the divergent edge cases and the missing lock in one variant were part of the bug class being fixed.
- *Reset `attempt_count` on role change.* Rejected: toggling would bypass the DL attempt limit.
- *Always advance to `awaiting_vehicle` on a verified DL webhook.* Rejected: it gates out a passenger who switched away while the DL was pending.

**Consequences.**
- No dead end: every non-initial status has an exit to passenger (closes ARCH-002 U3), and every passenger can start driver setup.
- Flag-OFF role-switch edge cases change deliberately: a verified-DL user with no active vehicle and no `vehicle_step_exempt` marker now becomes `awaiting_vehicle` instead of `complete`, and a switch to passenger from `awaiting_vehicle` or `pending_verification` now works and yields `complete`. Initial onboarding with the flag OFF and the vehicle endpoint are unchanged, so Decision 11's flag-off isolation (which concerns the vehicle endpoint) still holds; this is a narrow, intended exception for the role switch.
- Accepted side effect: while `ONBOARDING_GATE_ENABLED` is on, a passenger who starts driver setup is gated out of normal features (`403 onboarding_incomplete`) until they finish or switch back. Clients should confirm before switching and offer a visible way back.
- A user who exhausted the DL attempt limit can still toggle roles, lands in `awaiting_dl` and cannot submit (`max_dl_attempts_exceeded`); they can switch back to passenger, and staff action is needed for more attempts.
- Contract: `dl_required` disappears from this endpoint; clients should route on `next_step`. No schema change, no migration; rollback is a code revert.

---

## Resolved open questions (requirements v4)

| ID | Resolution |
|----|------------|
| OQ-R1, R2, R3, R4, R5, R6, R8, R9, R10, R11 | Resolved by product in requirements v4; architecture implications in Decisions 11-18, 22, 23. |
| OQ-R12 (a) | `422 rc_verification_rejected` retained; DEC-011 error object extended with optional `extra` (Decision 16). |
| OQ-R12 (b) | A grandfathered driver (explicit `vehicle_step_exempt` marker, Decision 27) with no vehicle row stays `COMPLETE` on a role round trip; any other driver with no row becomes `awaiting_vehicle`. FR-43/AC-48 amended in requirements v6. |
| OQ-R12 (c) | RC webhook with the flag OFF returns `404`, no state change (Decision 21). |
| OQ-R7 | Still open (legal): retention of `rc_owner_name`; hook `_clear_owner_data`. Must be answered before production enablement. |
| OQ-R13 | Still open (operations): review queue owner and SLA; admin tooling provided (Decision 23). |

## New open technical items

| ID | Item | Owner |
|----|------|-------|
| U1 | Closed: FR-43/AC-48 amended in requirements v6 for the grandfathered "no vehicle row" case (marker, Decision 27). | product-manager |
| U2 | Approve or decline the flag-off contract-conformance fixes (Decision 26). | product-manager |
| U3 | Closed (v5, Decision 28): every non-initial status can switch back to passenger in both flag modes. | product-manager |
| U4 | Exercising the mock in a `DEBUG=False` staging environment is refused by the guard; an explicit override would need security approval. | security-reviewer / product-manager |
