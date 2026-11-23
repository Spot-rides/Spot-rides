# Architecture: User Onboarding Flow

**ID:** ARCH-002
**Type:** architecture
**Feature:** FEAT-002
**Version:** 7
**Status:** ready
**Date:** 2026-10-17

---

## Context

FEAT-001 established a passwordless phone/OTP authentication layer that produces a `User` row keyed on E.164 phone number and issues a JWT pair. After successful OTP verification a user has only a phone number on record: no role, no name, no demographic data, and no mechanism to vet driving licences. The main Spot Rides experience cannot function without knowing whether the user intends to be a Passenger or a Driver ("Rider" in UI copy), and Driver accounts require a verified Indian driving licence before they can offer rides.

FEAT-002 adds the complete onboarding flow: role selection, personal profile collection, DL verification for Drivers, vehicle registration for Drivers, server-side progress persistence (resumable across devices), and a server-enforced gate that blocks any non-onboarding API call until onboarding is complete.

**v2 changes (2026-10-10):** Requirements v3 added a vehicle registration step to the Driver onboarding flow. Drivers must register a vehicle (registration number + type) after DL verification and before onboarding is complete. This introduces a new `AWAITING_VEHICLE` onboarding state, a new `Vehicle` model, a new API endpoint, and corresponding service/serializer/validator additions.

**v3 changes (2026-10-15):** Requirements v4 (FR-27..FR-50, AC-27..AC-52) adds optional vehicle RC (Registration Certificate) verification behind the feature flag `RC_VERIFICATION_ENABLED`, default OFF. This revision adds the `RCVerificationAdapter` seam (mock only; no real provider), the `pending_rc_verification` state, Vehicle RC columns, an RC status endpoint, an RC webhook, admin review tooling, a `switch_role` fix, and a single shared `next_step` map. It also resolves OQ-R12 (ADR Decisions 16, 20, 21). The v2 statements "no third-party verification of vehicle registration numbers" and "future enhancement could flag duplicates" are superseded by section "v3: Vehicle RC verification" below. The overriding constraint of this revision is that **with the flag OFF the vehicle endpoint behaves exactly as in v2** (ADR Decision 11).

**v4 changes (2026-10-17):** Requirements v6 (FR-43, AC-48, AC-54) replaces the inferred grandfather rule ("no vehicle row while currently `COMPLETE`") with an explicit marker, `UserProfile.vehicle_step_exempt`, added by migration `0004_userprofile_vehicle_step_exempt` (ADR Decision 27). The inferred rule was bypassable through FR-52 (a driver in `awaiting_vehicle` who never submitted a vehicle could switch to passenger, which sets `complete`, and back to driver and become `COMPLETE` without a vehicle). This is a documentation alignment with the implementation; sections changed: Data Model (`UserProfile`), `switch_role`, Admin, Migration / Rollout, Alternatives Considered and Open Decisions (U1).

**v5 changes (2026-10-17):** A gap in the role switch was fixed in code: a `COMPLETE` passenger with no verified DL could not become a driver. `PATCH /api/profile/role/` to `driver` returned `400 dl_required`, but the DL endpoint requires `active_role = driver` and a status of `awaiting_dl` / `pending_verification`, so the user had no way to reach DL submission (a dead end). `switch_role` now starts driver setup instead (`active_role = driver`, `onboarding_status = awaiting_dl`, `next_step = dl_submission`). The same change makes `switch_role` a single implementation for both flag modes (the separate RC-enabled variant was removed), allows the switch to passenger from every non-initial status in both modes, takes a row lock in both modes, and makes a verified-DL webhook advance only a profile that is `pending_verification`. This is a documentation alignment with the implementation (ADR Decision 28). It deliberately changes flag-OFF **role-switch** edge cases; initial onboarding and the vehicle endpoint with the flag OFF are unchanged, so the v3 constraint above still holds for the vehicle endpoint. Sections changed: Onboarding State Machine (role switch), Components (COMP-003, COMP-004), API Contracts (PATCH row, refinements 3 and 5), Service Layer (`switch_role`, `process_webhook_result`), Frontend / Backend Responsibilities, Failure Modes, Security, Migration / Rollout, Alternatives Considered, Risks (RISK-015) and Open Decisions (U3 closed).

**v6 changes (2026-10-17):** The FEAT-002 security review (SEC-002, `docs/reviews/FEAT-002-security-review.md`) findings F-01..F-04, F-07 and F-09..F-11 were fixed in code (commit `803e319` on `onboarding-BE`). This revision is a documentation alignment with the implementation (ADR Decision 29) and closes the "known DL gaps not fixed" notes of v3 (ADR Decision 26): the DL adapter is no longer a module global but is built per call by `get_dl_adapter()` from new `DL_*` settings, guarded by an import-time production check that is not conditional on any flag; the DL webhook authenticates with an HMAC-SHA256 signature over the raw body and fails closed; `submit_dl_verification` follows the RC three-phase pattern (rows locked, provider called with no transaction open) and reads its attempt limit from `DL_MAX_ATTEMPTS`; the RC owner name is cleared on every terminal transition and shown in admin only to `profiles.review_rc` holders; migration `0004` marks only drivers with a verified DL; the admin makes state fields read-only for non-superusers. Findings F-05 (throttling), F-06 (flag-transition semantics) and F-08 (identity binding) remain open (Risks, Open Decisions). Sections changed: Current State (v3 snapshot annotated), Proposed Solution (new "v6: DL security hardening"), Diagram, Module Layout, Components, Data Model, API Contracts, Service Layer, Admin, Frontend / Backend Responsibilities, Failure Modes, Security, Observability, Performance, Migration / Rollout, Alternatives Considered, Risks and Open Decisions.

**v7 changes (2026-10-17):** Documentation-only reconciliation of this document and the ADR with the code as committed (`803e319` on `onboarding-BE`, re-read from disk) and with `docs/api/openapi-profiles.yaml`. No code, requirements, plan or security review was edited. Where the code deviates from the intended contract, the deviation is recorded as a **KNOWN GAP** (new section "Known Gaps (v7)", KG-01..KG-06) with an open item; the intended contract was not rewritten to match a defect. Corrections: (1) the flag-off vehicle-endpoint discrepancies in Current State, ADR Decision 26 and RISK-012 are resolved in code (`VehicleRegisterView` uses `RequireDriverRole` and maps validation errors to `invalid_registration_format` / `invalid_vehicle_type`; a `COMPLETE` driver gets `409 vehicle_already_registered`) and are kept only as history, and the upper-case `vehicle_type` is the contract (requirements FR-53); (2) the onboarding gate is `core.permissions.ConditionalOnboardingGate` behind `ONBOARDING_GATE_ENABLED`, not `profiles.permissions.IsOnboardingComplete` (which exists but is not wired); (3) the log events `onboarding.profile.created`, `role.set`, `profile.submitted`, `vehicle.registered`, `vehicle.duplicate_attempt` and `role.switch` are PLANNED, not emitted, and there is no `profiles` logger in `LOGGING` (KG-05); (4) `DL_ENCRYPTION_KEY` is read lazily by `profiles/utils/crypto.py`, so a missing key is a request-time `500`, not a startup failure (KG-04, SEC-002 F-15); (5) the crypto helpers are `encrypt_dl_number` / `decrypt_dl_number` and the adapter result field is `reference_id` (not `provider_ref`); (6) the DL submit endpoint is valid in `awaiting_dl` and `pending_verification`; (7) malformed DL input returns `400 invalid_request`, not `400 invalid_dl_format` (KG-01), and the DL regex applied by the code is `DL_PATTERN = ^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$` after normalisation (KG-06); (8) a synchronous DL rejection returns `202` (KG-02) and the DL endpoints answer a passenger with `403 permission_denied` (KG-03); (9) a duplicate DL webhook delivery returns `200`, which is now the accepted resolution (U8 is kept as a tracking item). Sections changed: Current State, Proposed Solution, Diagram, Module Layout, Components, API Contracts, Service Layer (DL and vehicle validators), Frontend / Backend Responsibilities, Failure Modes, Security, Observability, Known Gaps (new), Risks, Open Decisions and Assumptions.

ADR decisions made during design are recorded in `docs/decisions/2026-09-23-arch-feat-002-user-onboarding.md` (Decisions 11-26 added for v3, Decision 27 for v4, Decision 28 for v5, Decision 29 for v6; v7 adds no decision and corrects Decisions 1, 3, 4, 6, 19 and 26 in place).

---

## Current State

- `backend/` contains two apps: `accounts` (custom `AUTH_USER_MODEL`, OTP/phone auth, JWT) and `core` (envelope, exceptions, renderers — no models).
- `accounts.User` has fields: `phone_number`, `is_active`, `is_staff`, `date_joined`. No role or profile data.
- `config/settings.py` `DEFAULT_PERMISSION_CLASSES` is `[IsAuthenticated]`.
- `config/urls.py` wires `api/auth/` to `accounts.urls` and `api/health/`.
- The `profiles` app has been partially implemented: `UserProfile`, `DriverVerification` models, onboarding service, DL verification service, validators, adapters, and views for all ten routes in `profiles/urls.py` exist (v7: the original snapshot said "the first 7 endpoints").
- (v2 note, superseded) The `Vehicle` model, vehicle registration endpoint and `AWAITING_VEHICLE` status are now implemented in the working tree; migration `0002_add_vehicle.py` is staged but uncommitted. (v7: resolved; migrations `0001` to `0004` are committed.)
- `accounts/serializers.py` `UserSerializer` exposes `id`, `phone_number`, `date_joined` only.
- `core.exceptions.ApiError` is the base for all domain errors; `core.exceptions.envelope_exception_handler` is the DRF exception handler.
- Redis is available (used by `accounts` for rate-limiting).
- `python-decouple` is used throughout for env var loading.
- `cryptography` is in `requirements.txt`.

### Verified code facts relevant to v3 (read 2026-10-15)

- **Vehicle step (flag-off path to preserve).** `services/onboarding.py::register_vehicle` requires `AWAITING_VEHICLE`, a verified DL and no active vehicle, creates the `Vehicle`, sets `COMPLETE`, and raises bare `ValueError`. `views.py::VehicleRegisterView` maps those errors by substring (`'dl'` / `'verified'` -> `DLNotVerified`) and hard-codes `next_step: 'none'`. Any new message containing "dl" or "verified" would be mis-mapped. (v7 re-check at `803e319`: the flag-off body and messages are unchanged, but the view now builds `next_step` with `compute_next_step(profile)`, maps serializer errors to domain codes and answers `409 vehicle_already_registered` for a `COMPLETE` profile before the substring branches; see the resolved note on flag-off discrepancies below.)
- **Duplicated `next_step` maps** exist in `OnboardingStatusView`, `ProfileSubmitView` and `DLSubmitView`; `RoleSelectView` and `VehicleRegisterView` hard-code a literal. There is no `compute_next_step` in code although v2 specified one. (v7: resolved in the v3 code; `NEXT_STEP_BY_STATUS`, `next_step_for_status` and `compute_next_step` exist in `services/onboarding.py` and the views use them.)
- **DL module wiring (v3 snapshot, fixed in v6).** When v3 was designed, `dl_verification.py` held a module-global `_adapter` that `views.py` imported directly, called the provider inside `@transaction.atomic`, hard-coded the attempt limit `3`, had no `DL_*` settings and no reason sanitiser, and `MockDLVerificationAdapter.validate_webhook` compared a static header with `==` against a guessable default secret. All of this was replaced in v6 (commit `803e319`, ADR Decision 29); see "v6: DL security hardening" below.
- **Gate (v7 corrected; the v3 snapshot said the gate returned `False`).** `DEFAULT_PERMISSION_CLASSES` is `[IsAuthenticated, core.permissions.ConditionalOnboardingGate]`. The gate is active only when `ONBOARDING_GATE_ENABLED` is True (default False). When active and the profile is missing or not `COMPLETE`, it raises `OnboardingIncomplete(extra={'onboarding_status', 'next_step'})`, which delivers FR-14's `403 onboarding_incomplete` through the `ApiError.extra` mechanism (COMP-024). `profiles.permissions.IsOnboardingComplete` still exists with unit tests but nothing references it (not settings, not a view). Views that must be reachable before onboarding override `permission_classes` (the onboarding, vehicle and role-switch views do; the webhooks use `AllowAny`).
- **Envelope.** `core.envelope.error_envelope` emits a closed `error` object `{code, detail, fields, retry_after}`; `core.exceptions.ApiError` cannot carry extra data; DEC-011 requires `data = null` on failure. (v7: the `extra` limitation was resolved by v3: `ApiError(detail, retry_after, extra, fields)` and `error_envelope(..., extra=...)` exist and are used by `OnboardingIncomplete` and `RCVerificationRejected`.)
- **Logging.** No `profiles` logger is registered in `LOGGING`; records fall through to the root `console` handler (JSON, request-id filter, no redaction). `accounts.logging.JsonFormatter` writes every `extra=` key verbatim, so anything passed as `extra` reaches the log. (v7: still true; see KG-05.)
- **Migrations.** (v7: resolved) `profiles/migrations/0001_initial.py` to `0004_userprofile_vehicle_step_exempt.py` are all committed. The v3 snapshot said `0002_add_vehicle.py` was staged but uncommitted.
- **`backend/.env.example`.** PLAN-003 states it does not exist. This session could not read or list it (access denied), so existence is unverified; the backend engineer must check and either append to it or create it. (v7: `git ls-files` lists no `.env.example` under `backend/`, so none is committed; whether an untracked local copy exists was not checked and no `.env` file was opened.)
- **Pre-existing flag-off contract discrepancies: RESOLVED in code (history kept; re-verified 2026-10-17 at `803e319`).** Recorded at v3 design time (preserved by v3, ADR Decision 26): serializer validation errors surfaced as `400 invalid_request` with `error.fields` instead of `invalid_registration_format` / `invalid_vehicle_type` (the exception classes existed but were unused); a Passenger got `403 permission_denied` from `IsDriverRole` instead of `not_a_driver`; a `COMPLETE` Driver posting a vehicle got `403 dl_not_verified` (substring match on "DL") instead of `409 vehicle_already_registered`; the response returned the stored upper-case `vehicle_type` ("SEDAN") whereas the contract example was lower-case. Now: `VehicleRegisterView` has `permission_classes = [IsAuthenticated, RequireDriverRole]` (`403 not_a_driver`), `_raise_vehicle_validation_error` maps serializer errors to `400 invalid_registration_format` / `400 invalid_vehicle_type`, and the `ValueError` branch answers `409 vehicle_already_registered` for a `COMPLETE` profile before the substring checks. The upper-case `vehicle_type` is unchanged and is now the contract (requirements FR-53, OpenAPI). The same `IsDriverRole`-versus-`RequireDriverRole` defect still exists on the DL endpoints (KG-03).

---

## Proposed Solution

Extend the existing **`profiles`** Django app to support vehicle registration as the final step in Driver onboarding. The existing `UserProfile`, `DriverVerification`, service layer, and adapter architecture remain unchanged. The additions are:

1. **New model `Vehicle`** in `profiles/models.py` — ForeignKey to `accounts.User` (not OneToOneField) to support future multi-vehicle, with v1 enforcing max 1 active vehicle at the application layer.
2. **New onboarding status `AWAITING_VEHICLE`** — added to `UserProfile.ONBOARDING_STATUS_CHOICES`, inserted between `PENDING_VERIFICATION`/`AWAITING_DL` and `COMPLETE` in the state machine.
3. **New service function `register_vehicle()`** in `profiles/services/onboarding.py` — validates state, normalizes registration number, creates `Vehicle`, transitions to `COMPLETE`.
4. **New validator `validate_registration_number()`** in `profiles/services/validators.py` — strips spaces/hyphens, uppercases, validates against Indian format `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$`.
5. **New serializers** `VehicleRegistrationSerializer` (request) and `VehicleRegistrationResponseSerializer` (response) in `profiles/serializers.py`.
6. **New view `VehicleRegisterView`** in `profiles/views.py` — `POST /api/onboarding/driver/vehicle/`.
7. **Updated URL routing** in `profiles/urls.py` — adds the vehicle endpoint.
8. **New exception classes** `InvalidRegistrationFormat`, `InvalidVehicleType`, `DLNotVerified`, `VehicleAlreadyRegistered` in `profiles/exceptions.py`.
9. **Updated state transitions** in `submit_dl_verification()` and `process_webhook_result()` — DL verified now transitions to `AWAITING_VEHICLE` instead of `COMPLETE`.
10. **Updated `next_step` mapping** — adds `vehicle_registration` for `AWAITING_VEHICLE` state.

Key design decisions (all detailed in the ADR):
1. **DL normalisation** — input is stripped and uppercased before regex validation.
2. **`UserProfile` creation** — lazy, via `get_or_create` in the onboarding service on first contact.
3. **DL storage** — Fernet symmetric encryption (`DL_ENCRYPTION_KEY` env var) for the full DL number; last-4 plaintext in `dl_number_display`.
4. **Onboarding gate** — DRF permission class `core.permissions.ConditionalOnboardingGate` in `DEFAULT_PERMISSION_CLASSES`, enforced only when `ONBOARDING_GATE_ENABLED` is True (default False); onboarding views opt out by declaring their own `permission_classes`. (v7 correction: the original design named `profiles.permissions.IsOnboardingComplete`; see ADR Decision 4.)
5. **`DriverVerification` placement** — inside `profiles` app.
6. **DL adapter interface** — abstract class `DLVerificationAdapter` (with a `from_settings` classmethod) and a concrete mock adapter for dev/test, obtained per call through `get_dl_adapter()` (v6, no module-level instance). The production adapter (`DigiLockerDLVerificationAdapter`, `profiles/adapters/digilocker.py`) is the design target but is not implemented yet; until a real adapter exists the mock is refused whenever `DEBUG` is off (v6).
7. **Vehicle model uses ForeignKey** (not OneToOneField) — allows future multi-vehicle support while v1 enforces max 1 active vehicle at the application layer.
8. **Vehicle registration numbers stored plaintext** — they are publicly visible on vehicles; no encryption needed.
9. **Vehicle registration number normalisation** — strip spaces/hyphens, uppercase before validation (same normalisation philosophy as DL numbers, see ADR Decision 1).

### v3: Vehicle RC verification

Add an optional, provider-agnostic RC verification step to the existing vehicle step. Everything RC-specific lives in new modules (`adapters` additions, `services/rc_verification.py`, `services/rc_matching.py`, `services/sanitise.py`); the existing modules gain only small, additive changes.

**Design rules**

1. **Flag-off isolation.** `register_vehicle()` in `services/onboarding.py` becomes a two-line dispatcher: if `settings.RC_VERIFICATION_ENABLED` is falsy, call `_register_vehicle_self_declared()` (the current function body, moved verbatim, same `@transaction.atomic`, same `ValueError` messages, same `(profile, vehicle)` return); otherwise lazily import and call `rc_verification.register_vehicle_with_rc()`. The RC module is not imported, no RC setting other than the flag is read, no adapter is built, and no RC column is written on the flag-off path. The flag is read at call time (never cached at import) so `override_settings` works and a restart-free toggle is not required in tests.
2. **Same return type, no view branching.** The flag-on path also returns `(profile, vehicle)`. RC results travel on the `Vehicle` row (`rc_verification_status`, `rc_rejection_reason`, `rc_verification_ref`), which are `NULL` on the flag-off path, so the view builds one response shape (the additive fields are `null` when the flag is off). The only flag-on exception is a rejection, raised as a domain error (rule 5).
3. **RC rules live in the service layer.** Name matching, class mapping and the verified/pending/rejected decision are pure functions in `rc_matching.py`, independent of any provider.
4. **Provider call outside the DB transaction.** The flag-on service uses three phases: guard (short transaction), provider call (no transaction open), decide-and-persist (short transaction). Views must not be wrapped in a transaction (`ATOMIC_REQUESTS` stays False).
5. **Domain exceptions only.** New code raises `ApiError` subclasses with stable codes. `ApiError` is not a `ValueError`, so the legacy `except ValueError` substring mapping in the vehicle view is never reached by RC errors and is left untouched.
6. **Adapter obtained from settings** via `get_rc_adapter()` (a factory), never from a module global.
7. **No PII in logs or responses.** Owner name is stored for staff review only; logging uses an allow-list of fields.
8. **Existing drivers untouched.** No backfill, no state change; `rc_verification_status = NULL` means legacy/self-declared and is treated as acceptable for `COMPLETE`.

Key v3 decisions are recorded in ADR Decisions 11-26.

### v6: DL security hardening

Context: the security review found that the DL path, unlike the RC path, was a hard-wired mock with no production guard (F-01), a webhook protected by a public constant (F-02), an adapter binding that a replacement hook could not reach (F-03), a submit service with no row lock and a provider call inside a transaction (F-04), an unhandled unknown-reference case and unsanitised reason (F-09), a migration marking rule that was too broad (F-10) and admin forms that could edit state (F-11), plus retention of the RC owner name (F-07). v6 applies to the DL path the same patterns the RC path already used. No new infrastructure and no schema change.

**Design rules**

1. **Adapter per call from settings.** `profiles.adapters.get_dl_adapter()` does `import_string(settings.DL_ADAPTER_CLASS)` and returns `cls.from_settings(settings)`; it refuses any `MockDLVerificationAdapter` subclass when `settings.DL_MOCK_ADAPTER_FORBIDDEN` is true. There is no module-level adapter and no `set_adapter` hook (the module-level `_adapter` and `set_adapter` of `dl_verification.py` were removed). The submit service (`_call_provider`) and `DLWebhookView` both obtain the adapter through the factory on every request, so the adapter that verifies a webhook is always the one in settings (F-03). Tests use `override_settings(DL_ADAPTER_CLASS=..., DL_ADAPTER_MOCK_RESULT=...)` or patch `profiles.services.dl_verification.get_dl_adapter`. `DLVerificationAdapter.from_settings()` (in `base.py`) is a concrete classmethod that returns `cls()`; adapters with configuration override it.
2. **Production guard, unconditional.** DL verification has no feature flag (it is always part of driver onboarding), so the guard in `config/settings.py` is evaluated on every import. See "DL configuration and startup checks" below.
3. **Webhook authenticated by HMAC.** The mock (and the contract for every adapter) validates a hex HMAC-SHA256 of the raw body, keyed with `DL_WEBHOOK_SECRET`, from the `X-DL-Signature` header (optional `sha256=` prefix), compared with `hmac.compare_digest`; an empty secret or a missing header returns `False` (fail closed). `DLWebhookView` checks it before the payload is parsed and before any database access. The old static `X-Mock-Signature: mock-secret` header is gone.
4. **Submit follows the RC three-phase pattern.** Guard under `select_for_update` (profile, then `DriverVerification`), provider call with no transaction open, re-lock, re-check and persist. The attempt cap is `settings.DL_MAX_ATTEMPTS`, evaluated under the lock in both phases (F-04). Lock order everywhere is `UserProfile` then `DriverVerification` (submit, webhook).
5. **Failure is a domain error, never a 500.** A provider exception of any kind (including an unimportable `DL_ADAPTER_CLASS`, an `ImproperlyConfigured` from a bad mock mode, or the guard refusing the mock), or a result that is not a `DLVerificationResult` with an allowed status and a `reference_id` of at most 100 characters, becomes `422 dl_verification_provider_error` with nothing written and no attempt consumed. A `TimeoutError` becomes `pending` and does consume an attempt.
6. **Webhook outcomes.** Unknown `reference_id` -> `404 dl_reference_not_found` (new `DLReferenceNotFound`); the webhook `rejection_reason` goes through `sanitise_reason` (the same helper RC uses) before storage; a duplicate delivery for a reference already `verified` or `rejected` returns `200` and changes nothing (idempotent; it no longer returns `409`).
7. **No sensitive data in logs.** DL logging goes through one allow-listed helper (`_log_event`) and uses `onboarding.dl.*` event names. The DL number, rejection reason and adapter exception messages are never logged.
8. **RC owner name purged.** `resolve_rc_review` calls `_clear_owner_data(vehicle)` on both approve and reject (the other terminal paths already did), so only a vehicle still pending review holds `rc_owner_name`. The admin shows the field only to users holding `profiles.review_rc` (F-07).
9. **Migration `0004` corrected in place.** It was unmerged, so it was edited rather than followed by a new migration: the data step now marks only profiles that are `complete`, have a `DriverVerification` with `dl_verification_status = 'verified'`, and no active vehicle (F-10).
10. **Admin cannot edit state.** `UserProfile.onboarding_status` and `active_role` are read-only for non-superusers, `vehicle_step_exempt` is read-only for everyone, `DriverVerificationAdmin` excludes `dl_number` and makes its state fields read-only for non-superusers, and adding a `DriverVerification` row in admin is disabled (F-11).

**DL configuration and startup checks (`config/settings.py`)**

| Setting / env var | Default | Notes |
|---|---|---|
| `DL_ADAPTER_CLASS` | `profiles.adapters.mock.MockDLVerificationAdapter` | dotted path, loaded with `import_string` on every call |
| `DL_ADAPTER_MOCK_RESULT` | `sync_verified` | `sync_verified`, `async_pending` or `sync_rejected`; an unknown value makes `MockDLVerificationAdapter` raise `ImproperlyConfigured` (no silent fallback to "verified") |
| `DL_MAX_ATTEMPTS` | `3` (int) | read at call time under the row lock; `< 1` refuses startup |
| `DL_WEBHOOK_SECRET` | `''` (empty = every webhook is rejected) | HMAC-SHA256 key for `X-DL-Signature`; never committed |
| `DL_MOCK_ADAPTER_FORBIDDEN` (derived, not an env var) | `not DEBUG` | computed once at import from the environment `DEBUG`, so Django's test runner forcing `DEBUG=False` cannot trip it |

`DL_ENCRYPTION_KEY` is not a Django setting: `profiles/utils/crypto.py` reads it through `python-decouple` when it is first needed. There is no `DL_PROVIDER_TIMEOUT_SECONDS` setting in the code; a real adapter owns its provider timeout (a `TimeoutError` from `submit` is treated as pending).

Startup validation, always executed (not conditional on any flag), collects problems and raises one `ImproperlyConfigured`:
1. `DL_MAX_ATTEMPTS < 1`.
2. `not DEBUG` and `'mock' in DL_ADAPTER_CLASS.lower()` (the mock is refused outside `DEBUG`).

The second layer is `get_dl_adapter()`, which refuses any `MockDLVerificationAdapter` subclass when `DL_MOCK_ADAPTER_FORBIDDEN` is true (it catches an alias or subclass whose dotted path does not contain "mock"). Unlike the RC guard there is no check for an empty `DL_WEBHOOK_SECRET` or for `ONBOARDING_GATE_ENABLED`: an empty secret simply makes the webhook reject everything, which is acceptable for a synchronous-only provider. Residual gap (same as RC): a production process run with `DEBUG=True` bypasses the guard. Consequence: **with `DEBUG` off, the process will not start with the default `DL_ADAPTER_CLASS`, and no real DL adapter exists yet, so non-`DEBUG` deployments are blocked until one is built and configured** (ADR Decision 29, Open Decision U9).

---

## Diagram

```mermaid
graph TD
    Client[Expo mobile client] -->|JWT Bearer| DRF[Django 6.1 + DRF]

    subgraph "accounts app (existing)"
        User[accounts.User]
        OtpVerifyView
        MeView
    end

    subgraph "profiles app (extended)"
        UP[UserProfile model]
        DV[DriverVerification model]
        VH[Vehicle model - NEW]
        OnboardingService[services/onboarding.py]
        DLService[services/dl_verification.py]
        Validators[services/validators.py]
        Adapter[adapters/DLVerificationAdapter ABC]
        DLFactory[adapters.get_dl_adapter - built per call from settings]
        MockAdapter[adapters/mock.py]
        DigiLockerAdapter[adapters/digilocker.py - PLANNED, not implemented]
        OnboardingGate["core.permissions.ConditionalOnboardingGate - flag ONBOARDING_GATE_ENABLED"]
        IsDriverRole[permissions.IsDriverRole]
        IsDriverVerified[permissions.IsDriverVerified]
        OnboardingViews[views - status, role, profile, dl, webhook, vehicle, role-switch]
    end

    DRF --> OnboardingGate
    DRF --> OnboardingViews
    OnboardingViews --> OnboardingService
    OnboardingViews --> DLService
    OnboardingViews --> Validators
    OnboardingService --> UP
    OnboardingService --> VH
    DLService --> DV
    DLService --> DLFactory
    OnboardingViews --> DLFactory
    DLFactory --> Adapter
    Adapter --> MockAdapter
    Adapter --> DigiLockerAdapter
    DigiLockerAdapter -->|HTTP| DigiLocker[DigiLocker Pull URI API]
    DigiLocker -->|Webhook POST fallback| DRF
    UP -->|OneToOneField| User
    DV -->|OneToOneField| User
    VH -->|ForeignKey| User
    MeView -->|profile reverse relation| UP
```

### Onboarding State Machine

**Passenger path (unchanged):**
```
NOT_STARTED → (role selected) → ROLE_SELECTED → (profile submitted) → COMPLETE
```

**Driver path (synchronous DL verification — primary flow with DigiLocker):**
```
NOT_STARTED
  → (role selected) →
ROLE_SELECTED
  → (profile submitted) →
AWAITING_DL
  → (DL verified synchronously) →
AWAITING_VEHICLE
  → (vehicle registered) →
COMPLETE
```

**Driver path (async/timeout fallback):**
```
AWAITING_DL
  → (DL submitted, provider timeout) →
PENDING_VERIFICATION
  → (DL verified via webhook or retry) →
AWAITING_VEHICLE
  → (vehicle registered) →
COMPLETE
```


### v3 state machine: vehicle step

New onboarding status `PENDING_RC_VERIFICATION` (`pending_rc_verification`, 24 chars, fits `CharField(30)`), `next_step = "awaiting_rc_verification"`. It is reachable only while the flag is ON. The Driver-path states before the vehicle step are unchanged.

**Flag OFF (identical to v2):**
```
AWAITING_VEHICLE --POST vehicle--> COMPLETE        (next_step = "none", rc_verification_status = NULL)
```

**Flag ON:**
```
AWAITING_VEHICLE --POST vehicle: provider verified + name match + class ok/unknown--> COMPLETE
AWAITING_VEHICLE --POST vehicle: provider pending | timeout | verified-but-name-not-match--> PENDING_RC_VERIFICATION
AWAITING_VEHICLE --POST vehicle: provider rejected | class conflict--> AWAITING_VEHICLE   (same Vehicle row reused on resubmit)
AWAITING_VEHICLE --POST vehicle: provider error--> AWAITING_VEHICLE   (no Vehicle row written, no attempt consumed)
PENDING_RC_VERIFICATION --webhook verified (name match, class ok) | admin approve--> COMPLETE
PENDING_RC_VERIFICATION --webhook rejected | class conflict | admin reject--> AWAITING_VEHICLE
AWAITING_VEHICLE (attempts exhausted) --admin reset attempts--> AWAITING_VEHICLE (resubmit allowed)
AWAITING_VEHICLE (attempts exhausted) --admin approve--> COMPLETE
```

**Resolution rule shared by webhook and admin.** A resolution changes `onboarding_status` only if the profile is currently `PENDING_RC_VERIFICATION` (or `AWAITING_VEHICLE` for an admin approve of a rejected vehicle). If the user has since switched to passenger and is `COMPLETE`, the vehicle status changes but `onboarding_status` is left alone, so a passenger is never moved into `awaiting_vehicle` by a driver-side resolution.

**Vehicle-level status (`Vehicle.rc_verification_status`):** `NULL` (legacy / flag off) | `pending` | `verified` | `rejected`. `NULL` is never produced by the flag-on path and is treated as acceptable-for-`COMPLETE` by `switch_role`.

### v5 state machine: role switch (`PATCH /api/profile/role/`)

Entry guard: the profile must be in one of `complete`, `awaiting_dl`, `pending_verification`, `awaiting_vehicle`, `pending_rc_verification` (`_SWITCH_ELIGIBLE_STATUSES`). `not_started` and `role_selected` get `403 onboarding_incomplete`. Every non-initial status is included so that a user who started driver setup can always get back to passenger. Behaviour is the same with `RC_VERIFICATION_ENABLED` ON or OFF except where stated.

**To passenger (both flag modes):**
```
{complete | awaiting_dl | pending_verification | awaiting_vehicle | pending_rc_verification}
  --PATCH role=passenger--> COMPLETE     (active_role = passenger; DriverVerification and Vehicle rows kept)
```

**To driver (from `active_role = passenger`):**
```
no DriverVerification row, or DL rejected  --> AWAITING_DL            (200, next_step = dl_submission)
DL pending                                 --> PENDING_VERIFICATION   (202, next_step = awaiting_verification)
DL verified, status derived from vehicle   --> COMPLETE | PENDING_RC_VERIFICATION | AWAITING_VEHICLE   (200)
```

After `AWAITING_DL` the normal driver path applies unchanged (`AWAITING_DL --DL submitted--> AWAITING_VEHICLE | PENDING_VERIFICATION`, then the vehicle and, flag ON, RC states above). The DL attempt limit still applies and toggling roles does not reset `DriverVerification.attempt_count`.

**Webhook interplay.** A verified DL webhook sets the `DriverVerification` row to verified and advances the profile to `AWAITING_VEHICLE` only if the profile is currently `PENDING_VERIFICATION`. A `COMPLETE` passenger who still has a pending DL stays `COMPLETE` (not pushed behind the onboarding gate); a later switch to driver then derives the status from the vehicle.

```mermaid
graph TD
    VV[VehicleRegisterView] --> OB[onboarding.register_vehicle]
    OB -->|flag OFF: early branch| SD[_register_vehicle_self_declared - unchanged body]
    OB -->|flag ON: lazy import| RCS[rc_verification.register_vehicle_with_rc]
    RCS --> F[adapters.get_rc_adapter - from settings]
    F --> MK[MockRCVerificationAdapter - only adapter in v1]
    RCS --> RM[rc_matching - name match, class check, decide]
    RCS --> VH[Vehicle rc_* columns]
    WH[RCWebhookView] -->|flag OFF: 404| X[no state change]
    WH -->|flag ON: signature first| AD[adapter.validate_webhook then parse_webhook]
    AD --> RCW[rc_verification.process_rc_webhook]
    ADM[VehicleAdmin actions] --> RCR[rc_verification.resolve_rc_review / reset_rc_attempts]
    RCW --> VH
    RCR --> VH
    SV[VehicleStatusView] --> VH
```

---

## Module Layout

```
backend/
  requirements.txt          # +cryptography (already added)
  config/
    settings.py             # modified: INSTALLED_APPS, DEFAULT_PERMISSION_CLASSES, DL_* env vars
    urls.py                 # modified: include('profiles.urls')
  accounts/
    serializers.py          # modified: UserSerializer gains onboarding_status, active_role fields
  profiles/                 # EXTENDED app
    __init__.py
    apps.py
    admin.py                # UserProfile (staff-only; state fields read-only for non-superusers), DriverVerification (staff-only; no dl_number; add disabled), Vehicle (staff-only)
    models.py               # UserProfile (modified: +AWAITING_VEHICLE), DriverVerification, Vehicle (NEW)
    serializers.py          # Existing serializers + VehicleRegistrationSerializer (NEW),
                            # VehicleRegistrationResponseSerializer (NEW)
    views.py                # Existing views + VehicleRegisterView (NEW)
    urls.py                 # existing routes + vehicle endpoint (NEW)
    permissions.py          # IsDriverRole, RequireDriverRole, IsDriverVerified; IsOnboardingComplete (defined and tested but NOT wired: the gate is core.permissions.ConditionalOnboardingGate)
    exceptions.py           # Existing exceptions + InvalidRegistrationFormat (NEW),
                            # InvalidVehicleType (NEW), DLNotVerified (NEW),
                            # VehicleAlreadyRegistered (NEW), DLReferenceNotFound (v6)
    services/
      __init__.py
      onboarding.py         # Existing functions + register_vehicle (NEW)
      dl_verification.py    # Modified: DL verified → AWAITING_VEHICLE (not COMPLETE); v6: three-phase submit, adapter from get_dl_adapter(), DL_MAX_ATTEMPTS, sanitised reasons
      validators.py         # Existing validators + validate_registration_number (NEW)
    adapters/
      __init__.py           # get_dl_adapter() factory (v6: per call from settings, refuses the mock when DL_MOCK_ADAPTER_FORBIDDEN)
      base.py               # DLVerificationAdapter ABC (v6: + from_settings()), DLVerificationResult dataclass
      mock.py               # MockDLVerificationAdapter (dev/test; v6: validated modes, HMAC webhook)
      digilocker.py         # DigiLockerDLVerificationAdapter (production; PLANNED, not implemented yet)
    utils/
      __init__.py
      crypto.py             # encrypt_dl_number(), decrypt_dl_number(), normalize_dl_number(), get_dl_last_four(); Fernet key read lazily from DL_ENCRYPTION_KEY
    migrations/
      0001_initial.py       # existing: UserProfile, DriverVerification
      0002_add_vehicle.py   # NEW: Vehicle model + AWAITING_VEHICLE status choice
```

### v3 additions to the module layout

```
backend/
  config/settings.py              # + RC_* settings, RC_MOCK_ADAPTER_FORBIDDEN, startup validation (flag ON only); v6: + DL_* settings, DL_MOCK_ADAPTER_FORBIDDEN, unconditional DL startup validation
  core/
    envelope.py                   # error_envelope(..., extra=None)  (additive, DEC-011 amendment)
    exceptions.py                 # ApiError(detail, retry_after, extra=None); handler passes extra through
    permissions.py                # ConditionalOnboardingGate raises OnboardingIncomplete with status + next_step
  profiles/
    models.py                     # Vehicle: +12 rc_* columns, indexes, constraint, permission; UserProfile: +PENDING_RC_VERIFICATION
    permissions.py                # + RequireDriverRole (raises NotADriver)
    exceptions.py                 # + RC domain errors (see "Exceptions")
    serializers.py                # extended response serializers, + VehicleStatusSerializer
    views.py                      # VehicleRegisterView (response fields, 202), + VehicleStatusView, + RCWebhookView; shared next_step
    urls.py                       # + vehicle/status/, + vehicle/rc/webhook/
    admin.py                      # VehicleAdmin review queue and actions
    adapters/
      __init__.py                 # + get_rc_adapter()
      base.py                     # + RCVerificationResult, RCVerificationAdapter, RCAdapterError
      mock.py                     # + MockRCVerificationAdapter
    services/
      onboarding.py               # register_vehicle dispatcher, _register_vehicle_self_declared, switch_role, NEXT_STEP_BY_STATUS, compute_next_step
      rc_verification.py          # NEW: submit, webhook, admin resolution, status, derive_driver_status
      rc_matching.py              # NEW: pure functions (owner-name match, class check, decision)
      sanitise.py                 # NEW: sanitise_reason()
    migrations/
      0003_vehicle_rc_verification.py   # NEW, generated by makemigrations (not squashed into 0002)
      0004_userprofile_vehicle_step_exempt.py   # NEW (v4): AddField + RunPython marking grandfathered drivers (v6: only those with a verified DL)
```

---

## Components

| ID | Name | Responsibility | Changes |
|----|------|----------------|---------|
| COMP-001 | `profiles.models.UserProfile` | Stores onboarding state machine status, active role, and personal profile fields for every user. OneToOneField on `accounts.User`. | Modified: add `AWAITING_VEHICLE` to `ONBOARDING_STATUS_CHOICES`; v4: add `vehicle_step_exempt` grandfather marker |
| COMP-002 | `profiles.models.DriverVerification` | Stores DL submission state, encrypted DL number, last-4 display, provider reference ID, attempt count, and verification timestamps. OneToOneField on `accounts.User`. | Unchanged |
| COMP-003 | `profiles.services.onboarding` | State machine transitions: get-or-create profile, set role, set profile details, register vehicle, switch role, derive next_step. No HTTP concerns. | Modified: add `register_vehicle()` function; v5: single `switch_role` for both flag modes (row lock, driver setup start, `_SWITCH_ELIGIBLE_STATUSES`) |
| COMP-004 | `profiles.services.dl_verification` | DL submission in three phases (guard under row lock, provider call with no transaction open, re-lock and persist), timeout handling, webhook processing (idempotent), attempt counting against `DL_MAX_ATTEMPTS`. No HTTP concerns. | Modified: DL verified transitions to `AWAITING_VEHICLE` instead of `COMPLETE`; v5: the webhook advances only a `PENDING_VERIFICATION` profile; v6: adapter from `get_dl_adapter()` (no module global), provider call outside the transaction, settings-driven attempt limit, `sanitise_reason`, `DLReferenceNotFound`, allow-listed `onboarding.dl.*` logging |
| COMP-005 | `profiles.adapters.base` | `DLVerificationAdapter` ABC + `DLVerificationResult` dataclass. Defines the contract the service uses; concrete providers implement this. | Modified (v6): `DLVerificationAdapter.from_settings()` classmethod; `submit(dl_number, user_id)`; `validate_webhook` must fail closed |
| COMP-006 | `profiles.adapters.mock` | `MockDLVerificationAdapter` returns a configurable result (`verified`, `pending`, `rejected`) without calling any external service. Used in dev and tests only. | Modified (v6): `from_settings`; an unknown `DL_ADAPTER_MOCK_RESULT` raises `ImproperlyConfigured`; webhook validated by HMAC-SHA256 (`X-DL-Signature`, `DL_WEBHOOK_SECRET`), fail closed |
| COMP-007 | `profiles.permissions` | `IsDriverRole` (driver-only endpoints; returns `False`, which DRF renders as a generic `403 permission_denied`), `RequireDriverRole` (same check but raises `NotADriver`, i.e. `403 not_a_driver`; used by the vehicle endpoints), `IsDriverVerified` (ride-offer endpoints). `IsOnboardingComplete` is defined and unit-tested but **not wired**: the onboarding gate is `core.permissions.ConditionalOnboardingGate` (COMP-024), behind `ONBOARDING_GATE_ENABLED`. | Unchanged in v2; v3 added `RequireDriverRole`; v7 corrected this row (it listed `IsOnboardingComplete` as the gate) |
| COMP-008 | `profiles.exceptions` | Domain error subclasses of `core.exceptions.ApiError`, covering every error code defined in the API contract. | Modified: add `InvalidRegistrationFormat`, `InvalidVehicleType`, `DLNotVerified`, `VehicleAlreadyRegistered`; v6: add `DLReferenceNotFound` (`404 dl_reference_not_found`) |
| COMP-009 | `profiles.utils.crypto` | `encrypt_dl_number(dl_number) -> str` and `decrypt_dl_number(encrypted_dl) -> str` using Fernet. The key is read from `DL_ENCRYPTION_KEY` (python-decouple) by `_get_fernet()` on every call, so a missing or malformed key fails at first use, not at startup (KG-04). Also `normalize_dl_number()` and `get_dl_last_four()`. `decrypt_dl_number` has no caller today. | Unchanged (v7: helper names and key loading corrected) |
| COMP-010 | `profiles.views` | Thin DRF `APIView` subclasses. Validate input with serializers, delegate business logic to service layer, return bare data for envelope rendering. | Modified: add `VehicleRegisterView` |
| COMP-011 | `profiles.urls` | URL routing for all onboarding and profile endpoints. | Modified: add `onboarding/driver/vehicle/` route |
| COMP-012 | `accounts.serializers.UserSerializer` | Extended with `onboarding_status` and `active_role` as nullable `SerializerMethodField` values reading the `profile` reverse relation. | Modified (from v1, unchanged in v2) |
| COMP-013 | `config.settings` | `INSTALLED_APPS` gains `profiles`. `DEFAULT_PERMISSION_CLASSES` gains `core.permissions.ConditionalOnboardingGate` (a no-op unless `ONBOARDING_GATE_ENABLED`; v7 correction, it was documented as `IsOnboardingComplete`). v6 adds the DL settings `DL_ADAPTER_CLASS`, `DL_ADAPTER_MOCK_RESULT`, `DL_MAX_ATTEMPTS`, `DL_WEBHOOK_SECRET`, the derived `DL_MOCK_ADAPTER_FORBIDDEN` and an unconditional import-time DL guard (`DL_ENCRYPTION_KEY` is read by `profiles.utils.crypto`, not by `settings.py`). | Modified (from v1, unchanged in v2; v6: DL settings and guard) |
| COMP-014 | `config.urls` | `include('profiles.urls')` added under `api/`. | Modified (from v1, unchanged in v2) |
| COMP-015 | `profiles.models.Vehicle` | Stores vehicle registration number (plaintext), vehicle type, and active status. ForeignKey on `accounts.User` (supports future multi-vehicle). | New |
| COMP-016 | `profiles.services.validators` | Input validation functions for DL format, age, name, and vehicle registration number. | Modified: add `validate_registration_number()` |
| COMP-017 | `profiles.adapters.base` (RC additions) | `RCVerificationResult` dataclass, `RCVerificationAdapter` ABC (`from_settings`, `verify`, `validate_webhook`, `parse_webhook`), `RCAdapterError`. | New |
| COMP-018 | `profiles.adapters.mock.MockRCVerificationAdapter` | Six configurable modes, HMAC-verified webhook, no network. Dev/test only. | New |
| COMP-019 | `profiles.adapters.get_rc_adapter` | Settings-driven factory (`RC_ADAPTER_CLASS` -> `from_settings`), refuses the mock when `RC_MOCK_ADAPTER_FORBIDDEN`. | New |
| COMP-020 | `profiles.services.rc_verification` | Flag-on vehicle submission (three phases), webhook processing, admin resolution/reset, status read, `derive_driver_status`. | New |
| COMP-021 | `profiles.services.rc_matching` | Pure functions: owner-name classification, vehicle-class check, outcome decision. | New |
| COMP-022 | `profiles.services.sanitise` | `sanitise_reason()`: strip markup/control chars, redact owner name, truncate to 500. | New |
| COMP-023 | `core.envelope` / `core.exceptions` | Optional `extra` data on `ApiError`, merged into the `error` object. | Modified (additive) |
| COMP-024 | `core.permissions.ConditionalOnboardingGate` | Raises `OnboardingIncomplete` carrying `onboarding_status` and `next_step` instead of returning `False`. | Modified |
| COMP-025 | `profiles.admin.VehicleAdmin` | RC review queue: filters, duplicate indicator, approve/reject/reset actions, audit via admin `LogEntry`. The `rc_owner_name` field is shown only to holders of `profiles.review_rc`. | Modified (v6: owner-name field gated) |
| COMP-026 | `profiles.adapters.get_dl_adapter` | Settings-driven DL factory (`DL_ADAPTER_CLASS` -> `from_settings`), builds a new instance per call, refuses the mock when `DL_MOCK_ADAPTER_FORBIDDEN`. Used by the submit service and `DLWebhookView`. | New (v6) |
| COMP-027 | `profiles.admin.UserProfileAdmin` / `DriverVerificationAdmin` | Staff views of onboarding state and DL records. `onboarding_status` / `active_role` read-only for non-superusers, `vehicle_step_exempt` read-only for all; `DriverVerificationAdmin` excludes the encrypted `dl_number`, makes state fields read-only for non-superusers and disables add. | Modified (v6) |

**v3 changes to existing components:** COMP-001 (`UserProfile`: +`PENDING_RC_VERIFICATION`), COMP-003 (`onboarding`: dispatcher, `switch_role`, shared `NEXT_STEP_BY_STATUS`/`compute_next_step`), COMP-008 (`exceptions`: RC errors), COMP-010/COMP-011 (`views`/`urls`: status and webhook endpoints, response fields), COMP-013 (`settings`: RC settings and startup validation), COMP-015 (`Vehicle`: RC columns). COMP-002, COMP-004, COMP-005, COMP-006, COMP-009 are untouched by v3 (the DL module's gaps were deferred, ADR Decision 26). v6 (ADR Decision 29) fixed them: it modifies COMP-004, COMP-005, COMP-006, COMP-008, COMP-013, COMP-025 and adds COMP-026 and COMP-027.

---

## Data Model

### `profiles.UserProfile`

```
Column               Type                              Notes
----------------------------------------------------------------------
id                   BigAutoField                      PK
user                 OneToOneField -> accounts.User    CASCADE, related_name="profile"
active_role          CharField(10, nullable)           choices: DRIVER | PASSENGER; null until step 1
first_name           CharField(50, nullable)           null until step 2; Unicode letters/space/hyphen/apostrophe
last_name            CharField(50, nullable)           null until step 2; same charset
age                  PositiveSmallIntegerField(null)   18-80 inclusive; null until step 2
gender               CharField(20, nullable)           choices: MALE | FEMALE | OTHER | PREFER_NOT_TO_SAY; null until step 2
onboarding_status    CharField(30)                     choices: NOT_STARTED | ROLE_SELECTED | AWAITING_DL |
                                                        PENDING_VERIFICATION | AWAITING_VEHICLE | COMPLETE
                                                        default: NOT_STARTED
vehicle_step_exempt  BooleanField                      default=False, db_default=False (v4, migration 0004);
                                                        grandfathered-driver marker, see below
created_at           DateTimeField(auto_now_add)
updated_at           DateTimeField(auto_now)
```

**v2 change:** `AWAITING_VEHICLE` added to `onboarding_status` choices between `PENDING_VERIFICATION` and `COMPLETE`.

**v4 change (`vehicle_step_exempt`).** Marks a driver who completed onboarding before the vehicle step existed (FR-43). It is set only by the data step in migration `0004` (profiles that are `complete`, have a `DriverVerification` row with `dl_verification_status = 'verified'` and have no `is_active` `Vehicle` row; the verified condition was added in v6, SEC-002 F-10); no application code path and no admin form sets it (read-only in `UserProfileAdmin`). It is read only by `derive_driver_status` when the driver has no active vehicle row. `db_default=False` keeps a still-running older process safe between migrate and deploy.

Constraints and indexes:
- `UNIQUE (user_id)` — enforced by `OneToOneField`; prevents duplicate profiles from concurrent requests
- Index on `onboarding_status` (`idx_profile_status`) for admin queries

### `profiles.DriverVerification`

```
Column                   Type                              Notes
----------------------------------------------------------------------
id                       BigAutoField                      PK
user                     OneToOneField -> accounts.User    CASCADE, related_name="driver_verification"
dl_number                CharField(256)                    Fernet-encrypted ciphertext of normalised DL;
                                                            length 256 accommodates base64-encoded Fernet token
dl_number_display        CharField(4)                      Last 4 chars of normalised plaintext DL; always plaintext
dl_verification_status   CharField(20)                     choices: PENDING | VERIFIED | REJECTED
dl_verification_ref      CharField(100, nullable)          Provider-issued reference ID (async path)
dl_submitted_at          DateTimeField                     Timestamp of most recent submission
dl_verified_at           DateTimeField(nullable)           Timestamp of verification confirmation
dl_rejection_reason      TextField(nullable)               Provider-supplied reason; passed through sanitise_reason() (markup stripped, 500 chars) on both the submit and webhook paths
attempt_count            PositiveSmallIntegerField         Default 0; incremented under the row lock when a submission is accepted (a provider
                                                            error does not consume an attempt); limit is settings.DL_MAX_ATTEMPTS (default 3)
created_at               DateTimeField(auto_now_add)
updated_at               DateTimeField(auto_now)
```

Constraints and indexes:
- `UNIQUE (user_id)` — enforced by `OneToOneField`
- `UNIQUE (dl_verification_ref)` where not null — prevents duplicate webhook processing; implemented as a partial unique index: `UniqueConstraint(fields=['dl_verification_ref'], condition=Q(dl_verification_ref__isnull=False), name='uq_dl_verification_ref')`

### `profiles.Vehicle` (NEW in v2)

```python
class Vehicle(models.Model):
    class VehicleType(models.TextChoices):
        CAR = 'CAR', 'Car'
        SUV = 'SUV', 'SUV'
        HATCHBACK = 'HATCHBACK', 'Hatchback'
        SEDAN = 'SEDAN', 'Sedan'
        AUTO_RICKSHAW = 'AUTO_RICKSHAW', 'Auto Rickshaw'
        BIKE = 'BIKE', 'Bike'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vehicles')
    registration_number = models.CharField(max_length=15)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'is_active'])]
```

```
Column               Type                              Notes
----------------------------------------------------------------------
id                   BigAutoField                      PK
user                 ForeignKey -> accounts.User       CASCADE, related_name="vehicles"
registration_number  CharField(15)                     Indian vehicle registration number; stored plaintext (FR-31)
vehicle_type         CharField(20)                     choices: CAR | SUV | HATCHBACK | SEDAN | AUTO_RICKSHAW | BIKE
is_active            BooleanField                      default True; for future multi-vehicle support
created_at           DateTimeField(auto_now_add)
updated_at           DateTimeField(auto_now)
```

Design notes:
- **ForeignKey (not OneToOneField)**: Allows future multi-vehicle support. In v1, max 1 active vehicle per user is enforced at the application layer (service function checks `user.vehicles.filter(is_active=True).exists()` before creating). See ADR Decision 8.
- **Plaintext storage**: Vehicle registration numbers are publicly visible on vehicles. No encryption needed (FR-31).
- **No uniqueness constraint on `registration_number`**: Two different Drivers may submit the same registration number. (v3: a non-unique index, a flag-on WARNING log and an admin duplicate indicator are added; see v3 data changes.)
- **Composite index on `(user, is_active)`**: Optimizes the common query pattern of "get active vehicles for a user".

### v3 data changes

**`UserProfile.onboarding_status`** gains `PENDING_RC_VERIFICATION = 'pending_rc_verification'` ("Pending RC Verification"). Choices change only; no data migration.

**`Vehicle` RC columns** (all nullable or defaulted; additive; supersedes the v2 note "no uniqueness constraint ... future enhancement could flag duplicates"):

```
Column                    Type                         Notes
----------------------------------------------------------------------------------------------
rc_verification_status    CharField(20, null)          pending | verified | rejected; NULL = legacy / flag off
rc_verification_ref       CharField(100, null)         provider reference; partial unique when not null
rc_submitted_at           DateTimeField(null)          most recent submission
rc_verified_at            DateTimeField(null)          provider or staff verification time
rc_rejection_reason       TextField(null)              sanitised, max 500 chars; driver-visible
rc_attempt_count          PositiveSmallIntegerField    default=0 AND db_default=0 (see migration notes)
rc_owner_name             CharField(100, null)         PII, staff-only; written only when needed for review
rc_name_match             CharField(15, null)          match | partial | mismatch | not_checked
rc_vehicle_class          CharField(50, null)          provider class string (clipped to 50)
rc_fuel_type              CharField(30, null)          clipped to 30
rc_fitness_valid_upto     DateField(null)              informational only (FR-48)
rc_insurance_valid_upto   DateField(null)              informational only (FR-48)
```

Constants on `Vehicle`: `RC_PENDING/RC_VERIFIED/RC_REJECTED`, `NAME_MATCH/NAME_PARTIAL/NAME_MISMATCH/NAME_NOT_CHECKED`, with `*_CHOICES` lists.

Meta additions:
- `Index(fields=['registration_number'], name='idx_vehicle_regno')` (non-unique, FR-46; also serves the admin duplicate count).
- `Index(fields=['rc_verification_status'], name='idx_vehicle_rc_status')` (review queue).
- `UniqueConstraint(fields=['rc_verification_ref'], condition=Q(rc_verification_ref__isnull=False), name='uq_vehicle_rc_verification_ref')` (mirrors `uq_dl_verification_ref`).
- `permissions = [('review_rc', 'Can review and resolve RC verification')]` (gates the admin actions to a reviewer group rather than all staff).
- Existing `Index(['user', 'is_active'])` retained.

**Data handling.** The raw provider payload is never stored. `rc_owner_name` is written only when the vehicle goes to name review (outcome `pending` with `rc_name_match != match`); for a `match` the name is redundant and is not stored; for a provider rejection no owner is stored. All provider strings are clipped to their column width before saving so an over-long value can never cause a 500. A provider `reference_id` longer than 100 characters is treated as a provider error (it cannot be stored faithfully for webhook lookup). Since v6 `rc_owner_name` is cleared through `_clear_owner_data(vehicle)` on every terminal transition (synchronous or webhook verified/rejected, staff approve and reject), so only a vehicle still pending review holds the name (SEC-002 F-07). What remains of OQ-R7 is the retention period while a vehicle is pending and in backups.

**Why `db_default`.** The migration runs before the new code is deployed. `AddField(default=0)` alone makes Django drop the DB default after back-filling, so a still-running v2 process inserting a `Vehicle` would hit a `NOT NULL` violation on `rc_attempt_count`. `db_default=0` keeps the default in PostgreSQL. All other new columns are nullable.

**Migration `0003_vehicle_rc_verification`** (generated with `makemigrations profiles`, depends on `0002_add_vehicle`): `AlterField(userprofile.onboarding_status)`, 12 `AddField`, 2 `AddIndex`, 1 `AddConstraint`, `AlterModelOptions(vehicle, permissions)`. No `RunPython`; legacy rows keep `NULL` / `0`. Reversible. **Decision: do not squash into 0002** (ADR Decision 22).

### `accounts.User` — no schema change

`onboarding_status` and `active_role` are derived from `UserProfile` at serialization time. No new columns on `accounts_user`.

---

## API Contracts

All contracts from the requirements document are adopted without change. The refinements and ambiguity resolutions below are the only delta.

| Method | Path | Auth | Permission | Notes |
|--------|------|------|------------|-------|
| GET | `/api/onboarding/status/` | JWT | `IsAuthenticated` only | Creates profile lazily if absent |
| POST | `/api/onboarding/role/` | JWT | `IsAuthenticated` only | Only valid in `NOT_STARTED` state |
| POST | `/api/onboarding/profile/` | JWT | `IsAuthenticated` only | Only valid in `ROLE_SELECTED` state |
| POST | `/api/onboarding/driver/dl/` | JWT | `IsAuthenticated`, `IsDriverRole` (KG-03: a passenger gets the generic `403 permission_denied`; the contract says `not_a_driver`) | Valid only while `onboarding_status` is `awaiting_dl` or `pending_verification` (a resubmission after a rejection or timeout happens in one of these states; `rejected` is a DL status, not an onboarding status); otherwise `400 invalid_onboarding_state`. Also `409 dl_already_verified`, `429 max_dl_attempts_exceeded`, `422 dl_verification_provider_error`. Format errors: contract `400 invalid_dl_format`, code `400 invalid_request` (KG-01). A synchronous rejection returns `202` (KG-02). |
| GET | `/api/onboarding/driver/dl/status/` | JWT | `IsAuthenticated`, `IsDriverRole` | KG-03: same permission behaviour as the submit endpoint; a driver with no `DriverVerification` row yet gets `403 not_a_driver`. |
| POST | `/api/onboarding/driver/dl/webhook/` | None (HMAC signature) | `AllowAny`, `authentication_classes = []` + in-view signature check | Not subject to the onboarding gate (`AllowAny`). v6: `X-DL-Signature` HMAC-SHA256 over the raw body, fail closed; `403 invalid_webhook_signature`, `400 invalid_request`, `404 dl_reference_not_found`, `200` (also for a duplicate delivery) |
| POST | `/api/onboarding/driver/vehicle/` | JWT | `IsAuthenticated`, `RequireDriverRole` (`403 not_a_driver` for a passenger; v7 correction, it was documented as `IsDriverRole`) | **NEW** — only valid in `AWAITING_VEHICLE` state |
| PATCH | `/api/profile/role/` | JWT | `IsAuthenticated` only (the view overrides `permission_classes`, so the global `ConditionalOnboardingGate` is deliberately not applied and users mid-driver-setup can switch back) | v5: callable from `complete`, `awaiting_dl`, `pending_verification`, `awaiting_vehicle`, `pending_rc_verification`; `403 onboarding_incomplete` from `not_started` / `role_selected`. Always returns `next_step`. See "`switch_role`" |
| GET | `/api/auth/me/` | JWT | `IsAuthenticated` only (existing endpoint) | Amended: adds `onboarding_status`, `active_role` |

### Contract refinements vs requirements doc

1. **`POST /api/onboarding/driver/dl/` on sync verified** — DL verified now transitions to `onboarding_status=AWAITING_VEHICLE` with `next_step="vehicle_registration"` (not `COMPLETE`). The Driver must still complete vehicle registration.

2. **`POST /api/onboarding/driver/dl/` on timeout** — A `TimeoutError` from the adapter is treated as a pending result: the service saves `dl_verification_status=PENDING` (no `dl_verification_ref`), `onboarding_status=PENDING_VERIFICATION`, consumes an attempt, and returns `202 Accepted` (same as the async path). No `500` reaches the client (NFR-REL-01, AC-19). The timeout value itself belongs to the adapter; `DL_PROVIDER_TIMEOUT_SECONDS`, which earlier revisions listed, is not a setting in the code (v6). A timed-out submission has no reference and so cannot be resolved by webhook (compare RISK-010 for RC).

3. **Webhook verified result** — `process_webhook_result()` on verified now sets `onboarding_status=AWAITING_VEHICLE` (not `COMPLETE`), but (v5) only when the profile is currently `PENDING_VERIFICATION`; a profile in any other status (for example a `COMPLETE` passenger who still had a pending DL) keeps its status while the `DriverVerification` row becomes verified. The Driver must still complete vehicle registration before onboarding is fully complete.

4. **Webhook `403` before any DB read (v6)** — `DLWebhookView.post()` resolves the adapter through `get_dl_adapter()` (per request; a failure to build it is logged by exception type and answered with the same `403`, fail closed), lower-cases the header names and calls `adapter.validate_webhook(headers, request.body)` as the first operation. If it returns `False` the view raises `403 invalid_webhook_signature` before the payload is parsed and before any query (NFR-SEC-02, AC-18). The signature is `X-DL-Signature`: hex `HMAC-SHA256(DL_WEBHOOK_SECRET, raw body)`, optional `sha256=` prefix, compared in constant time; an empty `DL_WEBHOOK_SECRET` or a missing header always fails.

5. **`PATCH /api/profile/role/` — no more `dl_required` (v5)** — Earlier revisions returned `400 dl_required` (`DLRequired`) when a user without a verified DL asked for `driver`. That was a dead end, because the DL endpoint requires the driver role and status `awaiting_dl` / `pending_verification`, which such a user could not reach. The endpoint now sets `active_role = driver`, `onboarding_status = awaiting_dl` and returns `200` with `next_step = dl_submission` (a pending DL keeps `pending_verification` and returns `202`). `DLRequired` is no longer raised anywhere (the class remains in `profiles/exceptions.py`, unused) and `dl_required` is no longer a response code. `next_step` is always present in this response. `400 invalid_onboarding_state` remains for one inconsistent legacy case (see `switch_role`). ADR Decision 28.

6. **`dl_rejection_reason` sanitisation (v6)** — Provider-supplied reasons are passed through `profiles/services/sanitise.py::sanitise_reason()` (strip markup and control characters, collapse whitespace, truncate to 500) before storage, on both the synchronous submit path and the webhook path. The earlier `_sanitise_rejection_reason()` name never existed in code.

7. **Duplicate DL webhook delivery is idempotent and returns `200` (v6)** — When a webhook arrives for a `reference_id` whose `DriverVerification` is already `verified` or `rejected`, `process_webhook_result()` changes nothing and the view responds `200`. Earlier revisions returned `409 already_processed`. `409` is no longer returned by the DL webhook (the RC webhook still returns it). Rationale: providers retry, and a `200` stops the retries without telling a caller whether a reference exists in a terminal state. **Accepted resolution (v7): `200`.** The requirements wording (NFR-REL-02 and the duplicate-delivery paragraph, which name `409 already_processed` for both webhooks) is being aligned to the code for the DL webhook; the RC webhook keeps `409 already_processed`. Open Decision U8 is kept only as a tracking item until the requirements edit lands. No code change is needed.

8. **`POST /api/onboarding/driver/vehicle/` validation** — Registration number is normalised (strip spaces/hyphens, uppercase) before regex validation. Invalid format returns `400 invalid_registration_format`. Invalid vehicle type returns `400 invalid_vehicle_type`. Driver without verified DL returns `403 dl_not_verified`. Already-registered vehicle returns `409 vehicle_already_registered`.
9. **`POST /api/onboarding/driver/dl/` provider failure (v6)** — If the provider call raises anything other than a timeout (including an unimportable `DL_ADAPTER_CLASS`, an unknown `DL_ADAPTER_MOCK_RESULT`, or the factory refusing the mock), or the adapter returns an invalid result, the response is `422 dl_verification_provider_error`; nothing is written and no attempt is consumed. The attempt limit is `DL_MAX_ATTEMPTS` (default 3), checked under the row lock (`429 max_dl_attempts_exceeded`).

10. **DL webhook errors (v6)** — An unknown `reference_id` returns `404 dl_reference_not_found` (`DLReferenceNotFound`), only after the signature check. A signed payload whose `status` is not `verified` or `rejected`, or that lacks `reference_id`, returns `400 invalid_request` from `WebhookPayloadSerializer`; no state changes.

11. **DL format errors (v7, KNOWN GAP KG-01)** — The intended contract (requirements FR-07 and AC-11, OpenAPI, ADR Decision 1) is `400 invalid_dl_format`. The code returns `400 invalid_request` with `error.fields.dl_number` (a DRF `ValidationError` from `DLSubmissionSerializer`, not the unused `InvalidDLFormat`). Trace and open item: "Known Gaps (v7)".

12. **Synchronous DL rejection (v7, KNOWN GAP KG-02)** — `DLSubmitView` answers `202` with `dl_verification_status = rejected`; the submit body carries no `rejection_reason` (read it from the DL status endpoint).

13. **Passenger on a DL endpoint (v7, KNOWN GAP KG-03)** — The contract is `403 not_a_driver`; `DLSubmitView` and `DLStatusView` use `IsDriverRole`, so a passenger gets the generic `403 permission_denied`. The vehicle endpoints use `RequireDriverRole` and conform.

### Vehicle endpoint detail

**`POST /api/onboarding/driver/vehicle/`**

Request:
```json
{
  "registration_number": "MH01AB1234",
  "vehicle_type": "sedan"
}
```

Response `200 OK`:
```json
{
  "onboarding_status": "complete",
  "next_step": "none",
  "vehicle": {
    "registration_number": "MH01AB1234",
    "vehicle_type": "SEDAN"
  }
}
```

(v7: the response returns the stored upper-case `vehicle_type`; requirements FR-53 and OpenAPI agree. The v2 example showed lower-case. The request still takes lower-case. The flag-OFF response also carries the additive `rc_verification_status`, `rejection_reason` and `reference_id` fields, all `null`; see "v3 API additions".)

Errors:
- `400 invalid_registration_format` — registration number does not match `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$`
- `400 invalid_vehicle_type` — value not in allowed set
- `403 not_a_driver` — endpoint called by a Passenger account
- `403 dl_not_verified` — Driver's DL is not in `verified` state
- `409 vehicle_already_registered` — Driver has already registered a vehicle during onboarding



### v3 API additions

| Method | Path | Auth | Permission | Notes |
|--------|------|------|------------|-------|
| POST | `/api/onboarding/driver/vehicle/` | JWT | `IsAuthenticated`, `RequireDriverRole` | Flag OFF: unchanged. Flag ON: RC flow, may return 202 / 422 / 429. Response gains nullable `rc_verification_status`, `rejection_reason`, `reference_id`. |
| GET | `/api/onboarding/driver/vehicle/status/` | JWT | `IsAuthenticated`, `RequireDriverRole` | New. Not blocked by the onboarding gate (explicit `permission_classes`). Flag OFF: `rc_verification_status` and `rc_attempts_remaining` are `null`. |
| POST | `/api/onboarding/driver/vehicle/rc/webhook/` | None (HMAC signature) | `AllowAny`, `authentication_classes = []` | New. Flag OFF: `404`, nothing read, nothing changed. Flag ON: signature checked before any DB access. |
| GET | `/api/onboarding/status/` | JWT | unchanged | Gains nullable `rc_verification_status` (always `null` when the flag is OFF; no vehicle query is made in that case). |
| PATCH | `/api/profile/role/` | JWT | unchanged | May return `onboarding_status` `awaiting_dl` / `pending_verification` / `awaiting_vehicle` / `pending_rc_verification` / `complete`; `next_step` is always returned (v5). Same behaviour in both flag modes except that `pending_rc_verification` is only derived with the flag ON. |

**Outcome mapping for `POST /api/onboarding/driver/vehicle/` with the flag ON** (the authoritative table for the backend and test engineers; field-level contract is in the requirements document):

| Situation | HTTP / code | `onboarding_status` after | `Vehicle.rc_verification_status` | Attempt consumed |
|-----------|-------------|---------------------------|----------------------------------|------------------|
| Provider `verified`, name `match`, class compatible or unknown | 200 | `complete` | `verified` | yes |
| Provider `verified`, name `partial` / `mismatch` / `not_checked`, class ok or unknown | 202 | `pending_rc_verification` | `pending` (`rc_name_match` set) | yes |
| Provider `pending` | 202 | `pending_rc_verification` | `pending` | yes |
| `TimeoutError` from adapter | 202 | `pending_rc_verification` | `pending`, no reference | yes |
| Provider `rejected` (not found, blacklisted, blocked) | 422 `rc_verification_rejected` | `awaiting_vehicle` | `rejected` | yes |
| Provider `verified` but class conflicts with `vehicle_type` | 422 `rc_verification_rejected` | `awaiting_vehicle` | `rejected` | yes |
| Adapter raised any other exception, or returned an unknown status | 422 `rc_verification_provider_error` | unchanged | unchanged (no row created for a first submission) | no |
| `rc_attempt_count >= RC_MAX_ATTEMPTS` (checked before the provider call) | 429 `max_rc_attempts_exceeded` | unchanged | unchanged | no |
| Profile is `pending_rc_verification` | 409 `rc_verification_pending` | unchanged | unchanged | no |
| Profile is `complete` and active vehicle is `verified` | 409 `rc_already_verified` | unchanged | unchanged | no |
| Profile is `complete` and vehicle is legacy (`NULL`) or absent | 409 `vehicle_already_registered` | unchanged | unchanged | no |
| Profile is `not_started` ... `pending_verification` (DL not verified) | 403 `dl_not_verified` | unchanged | unchanged | no |

The `202` body never states whether the cause is a provider delay or a name review (FR-38). The `422 rc_verification_rejected` body carries `rc_attempts_remaining = max(0, RC_MAX_ATTEMPTS - rc_attempt_count)`; `0` tells the client to show a contact-support message.

**Error `extra` payload (OQ-R12a, ADR Decision 16).** `422 rc_verification_rejected` stays a `422` with the exact `error` keys the requirements specify (`onboarding_status`, `next_step`, `rc_verification_status`, `rc_attempts_remaining`). Concrete conflict found: DEC-011's `error` object is closed (`code`, `detail`, `fields`, `retry_after`) and `ApiError` cannot carry additional data, so the specified body is not producible today. Resolution: a backward-compatible, optional extension of the envelope. `ApiError.__init__` gains `extra: dict | None`; `error_envelope(..., extra=...)` merges those keys flat into `error`; keys that collide with `code`, `detail`, `fields`, `retry_after` are rejected at construction. Existing errors are unaffected (`extra` defaults to `None`). The same mechanism delivers `next_step` for `onboarding_incomplete`, which the requirements already specify (it was also specified for `dl_required`, which is no longer returned since v5, ADR Decision 28). The alternative (a `200` with `rc_verification_status = "rejected"`, PLAN-003/DL style) is not adopted because product chose an error code and a `200` would hide a failure from generic client error handling. Note the existing `DLSubmitView` returns `202` for a synchronous DL rejection; that inconsistency is left as is (KNOWN GAP KG-02).

**Webhook behaviour.** Order of checks in `RCWebhookView.post`: (1) flag OFF -> `NotFound` (`404 not_found`), before reading the body; (2) `adapter.validate_webhook(headers, request.body)` -> `403 invalid_webhook_signature`; (3) `adapter.parse_webhook(request.body)` -> `400 invalid_webhook_payload` on malformed input; (4) `process_rc_webhook()` -> `404 rc_reference_not_found`, `409 already_processed` (reference already `verified` or `rejected`), else `200`. Because the provider payload shape is provider-specific, the adapter, not a fixed serializer, turns the body into an `RCVerificationResult` so a verified webhook can carry owner/class data for FR-38/FR-39. A verified webhook without owner data classifies as `not_checked` and the vehicle stays `pending` (admin review); the call still returns `200` and is idempotent.

---

## Service Layer

### `profiles/services/onboarding.py`

```
get_or_create_profile(user) -> UserProfile
    Wraps UserProfile.objects.get_or_create(user=user, defaults={onboarding_status: NOT_STARTED})

set_role(user, role: str) -> UserProfile
    Guards: status must be NOT_STARTED, raises RoleAlreadySet if ROLE_SELECTED or beyond.
    Sets active_role and onboarding_status = ROLE_SELECTED. Saves.

set_profile_details(user, first_name, last_name, age, gender) -> UserProfile
    Guards: status must be ROLE_SELECTED, raises ProfileAlreadySet otherwise.
    Validates age 18-80, gender choices, name charset/length.
    If active_role == PASSENGER: sets onboarding_status = COMPLETE.
    If active_role == DRIVER: sets onboarding_status = AWAITING_DL.
    Saves in a single atomic write.

register_vehicle(user, registration_number, vehicle_type) -> (UserProfile, Vehicle)      [NEW]
    Guards:
      - profile.active_role must be DRIVER, raises NotADriver otherwise.
      - profile.onboarding_status must be AWAITING_VEHICLE, raises InvalidOnboardingState otherwise.
      - user.vehicles.filter(is_active=True).exists() must be False, raises VehicleAlreadyRegistered otherwise.
    Normalises registration_number: strip whitespace, remove hyphens, uppercase.
    Validates via validate_registration_number().
    Creates Vehicle(user=user, registration_number=normalised, vehicle_type=vehicle_type.upper(), is_active=True).
    Sets profile.onboarding_status = COMPLETE.
    All writes in transaction.atomic.
    Returns (updated profile, created vehicle).

switch_role(user, new_role: str) -> UserProfile                                            [CHANGED v5]
    One implementation for both flag modes; @transaction.atomic; the UserProfile row is read with
    select_for_update (and the active vehicle is locked after it).
    Guards: status must be in _SWITCH_ELIGIBLE_STATUSES (COMPLETE, AWAITING_DL, PENDING_VERIFICATION,
            AWAITING_VEHICLE, PENDING_RC_VERIFICATION), else OnboardingNotEligibleForSwitch.
    PASSENGER -> active_role = PASSENGER, onboarding_status = COMPLETE (DriverVerification and Vehicle kept).
    DRIVER:
      - already DRIVER: no-op.
      - status AWAITING_VEHICLE (passenger row; inconsistent legacy data): flag ON raises
        VehicleStepIncomplete (-> 400 invalid_onboarding_state); flag OFF raises
        OnboardingNotEligibleForSwitch (-> 403 onboarding_incomplete). Recoverable via switch to passenger.
      - DL VERIFIED: onboarding_status = _status_for_verified_driver(profile, active vehicle).
      - DL PENDING: onboarding_status = PENDING_VERIFICATION.
      - no DriverVerification row, or REJECTED: onboarding_status = AWAITING_DL (starts driver setup).
      - active_role = DRIVER. (DLRequired is no longer raised.)

compute_next_step(profile: UserProfile | None) -> str
    Pure function: maps onboarding_status + active_role to next_step string.
    Updated mapping:
      NOT_STARTED         -> "role_selection"
      ROLE_SELECTED       -> "profile"
      AWAITING_DL         -> "dl_submission"
      PENDING_VERIFICATION -> "awaiting_verification"
      AWAITING_VEHICLE    -> "vehicle_registration"      [NEW]
      COMPLETE            -> "none"
```

### `profiles/services/dl_verification.py`   [CHANGED v6]

```
Format validation and normalisation happen before the service: DLSubmissionSerializer calls
normalize_dl_number() (profiles/utils/crypto.py) and validators.validate_dl_format(); the service receives
the normalised number and encrypts it (Fernet) and derives the last-4 itself. A format failure is a DRF ValidationError raised before the service is called (400 invalid_request, KG-01).

submit_dl_verification(user, dl_number) -> dict
    Phase 1 - guard (short transaction.atomic, nothing written):
      lock UserProfile (select_for_update), then the user's DriverVerification if any;
      _assert_can_submit(profile, dl_record) raises ValueError for: "Not a driver", "Invalid state for DL
      submission" (allowed statuses: AWAITING_DL, PENDING_VERIFICATION), "DL already verified", and
      "Maximum DL submission attempts exceeded" (attempt_count >= settings.DL_MAX_ATTEMPTS).
    Encrypt the DL number and take the last 4 characters (no DB access). A missing, empty or malformed DL_ENCRYPTION_KEY raises ImproperlyConfigured here (after the phase-1 guard, before the provider is called); it is not mapped to a domain error and surfaces as 500 server_error with nothing written (KG-04).
    Phase 2 - provider call, no transaction open (_call_provider):
      get_dl_adapter().submit(normalised_dl, user_id)
        TimeoutError            -> DLVerificationResult(status='pending'), timed_out = True
        any other Exception     -> log onboarding.dl.provider_error (exception type only), raise DLProviderError (422)
        result is not a DLVerificationResult, status not in {verified, pending, rejected}, or reference_id is not a
        str of <= 100 chars     -> log (error_type='InvalidResult'), raise DLProviderError (422)
      On a provider error nothing is written and no attempt is consumed.
      A rejection reason is passed through sanitise_reason().
    Phase 3 - decide and persist (short transaction.atomic):
      re-lock profile then DriverVerification and re-run _assert_can_submit (a concurrent submit that already
      advanced the state or used up the attempts is rejected here; the wasted provider call is accepted);
      create or update the record: dl_number (encrypted), dl_number_display, dl_verification_status = result.status,
      dl_verification_ref = result.reference_id, dl_submitted_at = now, attempt_count += 1;
        verified -> dl_verified_at = now; profile.onboarding_status = AWAITING_VEHICLE
        pending  -> profile.onboarding_status = PENDING_VERIFICATION
        rejected -> dl_rejection_reason = sanitised reason; the status stays AWAITING_DL / PENDING_VERIFICATION
    Log onboarding.dl.submitted. Return {dl_verification_status, onboarding_status, reference_id, rejection_reason}.
    DLSubmitView still maps the four ValueError messages above to domain errors by substring; DLProviderError is an
    ApiError and passes through unchanged as 422 dl_verification_provider_error.

process_webhook_result(reference_id, status, rejection_reason=None) -> True      (the signature was verified by the view)
    Unlocked lookup of (pk, user_id) by dl_verification_ref. None found -> log onboarding.dl.webhook.unknown_reference,
      raise DLReferenceNotFound (404 dl_reference_not_found).
    transaction.atomic: lock UserProfile, then the DriverVerification row (re-selected by pk AND reference; if the
      reference changed meanwhile because the user resubmitted -> DLReferenceNotFound).
    Already verified or rejected: nothing changes (outcome 'duplicate'); the view still answers 200.
    verified: dl_verification_status = verified, dl_verified_at = now; the profile moves to AWAITING_VEHICLE only if it is
      currently PENDING_VERIFICATION (a user who switched to passenger and is COMPLETE is left alone).
    rejected: dl_verification_status = rejected, dl_rejection_reason = sanitise_reason(rejection_reason); the profile stays
      PENDING_VERIFICATION and the user may resubmit.
    Log onboarding.dl.webhook.processed (reference_id, outcome).
    An unrecognised status never reaches the service: WebhookPayloadSerializer accepts only verified | rejected (400 otherwise).
```

### `profiles/services/validators.py`

```
validate_dl_format(dl_number: str) -> Tuple[bool, str]
    Validates the normalised DL number against DL_PATTERN = ^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$ (15 characters, no separators).
    Normalisation is separate: profiles/utils/crypto.py::normalize_dl_number() strips whitespace, uppercases and removes
    EVERY space and hyphen (KG-06). Failure returns (False, "Invalid DL format. Expected: XX00 0000 0000000 (13 digits
    after state code)"); the function does not raise (KG-01).

validate_age(age: int) -> Tuple[bool, str]
    Validates age range 18-80 inclusive.

validate_name(name: str, field_name: str) -> Tuple[bool, str]
    Validates name charset and length.

validate_registration_number(number: str) -> Tuple[bool, str]                              [NEW]
    Input must already be normalised: normalize_registration_number() (strip, remove whitespace and hyphens, uppercase)
    is called first by VehicleRegistrationSerializer.validate_registration_number, which returns the normalised value.
    Validates against ^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$.
    Returns (True, "") on success or (False, error_message) on failure.
```

Implementation detail for `validate_registration_number`:
```python
import re

VEHICLE_REG_PATTERN = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$')

def normalize_registration_number(number: str) -> str:
    """Normalize vehicle registration: strip whitespace, remove hyphens/spaces, uppercase."""
    return re.sub(r'[\s-]', '', number.strip().upper())

def validate_registration_number(number: str) -> Tuple[bool, str]:
    """Validate Indian vehicle registration number format (input already normalised)."""
    if not VEHICLE_REG_PATTERN.match(number):
        return False, "Invalid vehicle registration format. Expected: XX00XXX0000 (e.g. MH01AB1234)"
    return True, ""
```
(v7: the snippet above now matches `profiles/services/validators.py`; the earlier version normalised inside `validate_registration_number`.)


### v3 service layer: RC verification

#### Adapter contract (`profiles/adapters/base.py`)

```python
@dataclass(frozen=True)
class RCVerificationResult:
    status: str                                  # 'verified' | 'pending' | 'rejected'
    reference_id: Optional[str] = None
    rejection_reason: Optional[str] = None       # short, non-PII, provider-agnostic text
    owner_name: Optional[str] = field(default=None, repr=False)   # repr=False: never leaks via logging a result
    vehicle_class: Optional[str] = None
    fuel_type: Optional[str] = None
    fitness_valid_upto: Optional[date] = None
    insurance_valid_upto: Optional[date] = None

class RCAdapterError(Exception):
    """Any non-timeout provider failure. The message must not contain payloads or owner data."""

class RCVerificationAdapter(ABC):
    def __init__(self, *, timeout_seconds: float): self.timeout_seconds = timeout_seconds

    @classmethod
    @abstractmethod
    def from_settings(cls, settings) -> "RCVerificationAdapter": ...

    @abstractmethod
    def verify(self, registration_number: str, user_id: int) -> RCVerificationResult:
        """Raises TimeoutError on timeout, RCAdapterError on any other failure."""

    @abstractmethod
    def validate_webhook(self, headers: dict, body: bytes) -> bool: ...   # headers keys lower-case

    @abstractmethod
    def parse_webhook(self, body: bytes) -> RCVerificationResult: ...     # raises RCAdapterError if malformed
```

Contract rules for every adapter: (a) provider outcomes "not found", "blacklisted", "blocked" map to `status='rejected'` with a fixed human-readable reason (never free provider text containing owner data); (b) every provider-derived field is optional; (c) `timeout_seconds` must be applied to the adapter's own HTTP calls (the service does not use threads or signals to cut a call short) and a timeout must surface as `TimeoutError`; (d) the raw payload is not retained or logged by the adapter beyond what its own security review allows.

#### Factory (`profiles/adapters/__init__.py`)

```python
def get_rc_adapter() -> RCVerificationAdapter:
    cls = import_string(settings.RC_ADAPTER_CLASS)            # ImproperlyConfigured/ImportError -> surfaced as provider error
    if settings.RC_MOCK_ADAPTER_FORBIDDEN and issubclass(cls, MockRCVerificationAdapter):
        raise ImproperlyConfigured("Mock RC adapter is not allowed when RC verification is enabled with DEBUG=False")
    return cls.from_settings(settings)
```

A new instance is built per call (adapters are cheap and stateless; a real adapter may keep its own module-level HTTP session). No module global; no private `_adapter` imported by views. Tests use `override_settings(RC_ADAPTER_CLASS=..., RC_ADAPTER_MOCK_RESULT=...)` or patch `profiles.services.rc_verification.get_rc_adapter`. The DL equivalent, `get_dl_adapter()`, was added in v6 with the same shape plus a per-call build from `DL_ADAPTER_CLASS` (ADR Decision 29).

#### `MockRCVerificationAdapter` (`profiles/adapters/mock.py`)

`from_settings` reads `RC_ADAPTER_MOCK_RESULT`; an unknown mode raises `ImproperlyConfigured` (the DL mock's silent fallback is not copied). The mock does no network I/O and ignores `timeout_seconds`.

| Mode (`RC_ADAPTER_MOCK_RESULT`) | `verify()` behaviour | Resulting driver state |
|---|---|---|
| `sync_verified` (default) | `verified`, `reference_id = mock-rc-<8hex>`, `owner_name` = the user's profile `first_name last_name` (read from `UserProfile` via `user_id`), `vehicle_class = None` (so the class check is skipped and every declared type passes), `fuel_type = 'PETROL'`, fitness and insurance dates one year ahead | 200 `complete` |
| `sync_verified_name_mismatch` | `verified`, same as above but `owner_name = "MOCK OTHER OWNER"` | 202 `pending_rc_verification`, `rc_name_match = mismatch` |
| `async_pending` | `pending`, `reference_id = mock-rc-<8hex>`, no owner data | 202 `pending_rc_verification`; resolved by the webhook or admin |
| `sync_rejected` | `rejected`, `reference_id`, `rejection_reason = "Mock rejection for testing"` | 422 `rc_verification_rejected` |
| `timeout` | raises `TimeoutError` | 202 `pending_rc_verification`, no reference |
| `provider_error` | raises `RCAdapterError("mock provider error")` | 422 `rc_verification_provider_error` |

Note: the mock returns no vehicle class so every `vehicle_type` can be exercised in development. The class-conflict path (AC-45) is covered by unit tests of `check_vehicle_class` and by integration tests that patch the adapter result.

`validate_webhook`: fail closed. If `RC_WEBHOOK_SECRET` is empty return `False`. Otherwise compute `HMAC-SHA256(secret, raw_body)` hex and compare to the `x-rc-signature` header (optional `sha256=` prefix) with `hmac.compare_digest` on bytes. (PLAN-003 D3 proposed a static `X-Mock-Signature` header equal to the secret; replaced by a body HMAC so the mock exercises the same mechanism a real provider uses.) `parse_webhook`: `json.loads`; requires `reference_id` (str), `status` in `{verified, rejected}`; optional `rejection_reason`, `owner_name`, `vehicle_class`, `fuel_type`, `fitness_valid_upto`, `insurance_valid_upto` (ISO dates); anything else -> `RCAdapterError`.

#### Pure rules (`profiles/services/rc_matching.py`)

**Owner-name classification** `classify_owner_match(profile_first, profile_last, rc_owner) -> 'match'|'partial'|'mismatch'|'not_checked'`:
1. `not_checked` if `rc_owner` is empty/None, contains `*`, or contains a run of 3+ `X` characters (masked owner).
2. Normalise both sides: Unicode NFKC, casefold; cut a relation tail (`S/O`, `D/O`, `W/O`, `C/O`, `SON OF`, `DAUGHTER OF`, `WIFE OF`) and everything after it; replace non-letters with spaces; drop honorifics `MR MRS MS MISS SHRI SMT SRI SHREE KUMARI DR` (not `MD`, which is a common name prefix); split into tokens. Profile tokens are those of `first_name` and `last_name`.
3. A profile token matches an RC token if equal, or if one of them is a single letter and the other starts with it (initial). Each RC token can satisfy only one profile token.
4. `match`: every profile token is matched, at most one of them only by initial, and at least one match is a full-token match. `partial`: at least one profile token matched but not `match`. `mismatch`: none matched.
5. Profile names in a non-Latin script cannot match a Latin RC owner and therefore always go to review in v1 (transliteration is out of scope).

**Vehicle-class check** `check_vehicle_class(declared_vehicle_type, rc_vehicle_class) -> Optional[bool]` (`None` = skip). Normalise the RC class (upper-case, non-alphanumerics -> spaces) and assign the first matching category, top to bottom:

| Order | Category | Whole-word / phrase keywords (after normalisation) |
|---|---|---|
| 1 | `NON_PASSENGER` | `GOODS`, `TRUCK`, `LORRY`, `TRACTOR`, `TRAILER`, `TIPPER`, `BUS`, `OMNIBUS`, `HMV`, `HGV`, `LGV`, `EARTH MOVING`, `CONSTRUCTION EQUIPMENT` |
| 2 | `THREE_WHEELER` | `THREE WHEELER`, `3 WHEELER`, `3W`, `E RICKSHAW`, `ERICKSHAW`, `AUTO RICKSHAW`, `AUTORICKSHAW`, `RICKSHAW` |
| 3 | `TWO_WHEELER` | `M CYCLE`, `MCYCLE`, `MOTOR CYCLE`, `MOTORCYCLE`, `SCOOTER`, `MOPED`, `TWO WHEELER`, `2 WHEELER`, `2W` |
| 4 | `FOUR_WHEELER` | `MOTOR CAR`, `LMV`, `LIGHT MOTOR VEHICLE`, `MOTOR CAB`, `MAXI CAB`, `CAB`, `TAXI`, `JEEP`, `CAR` |
| - | no hit, or class empty | unknown -> skip (never rejects) |

Mapping from the declared `vehicle_type` (this is the exact mapping required by FR-39 / OQ-R8):

| `vehicle_type` | Compatible RC category | Clear conflict (rejects) | Unknown / missing class |
|---|---|---|---|
| `car`, `suv`, `hatchback`, `sedan` | `FOUR_WHEELER` | `TWO_WHEELER`, `THREE_WHEELER`, `NON_PASSENGER` | skip |
| `auto_rickshaw` | `THREE_WHEELER` | `TWO_WHEELER`, `FOUR_WHEELER`, `NON_PASSENGER` | skip |
| `bike` | `TWO_WHEELER` | `THREE_WHEELER`, `FOUR_WHEELER`, `NON_PASSENGER` | skip |

The four car-family types are deliberately not distinguished from each other: an RC class does not reliably encode sedan vs hatchback vs SUV, so declaring `sedan` for an RC that is a hatchback is never a conflict. Because the order is top-down, `Three Wheeler (Goods)` is `NON_PASSENGER` and conflicts with every type, including `auto_rickshaw`. The keyword lists are module constants, covered by a table test; provider class strings are unverified (PLAN-003), so unrecognised strings skip rather than reject, and the lists are extended as real provider data appears.

**Decision** `decide_rc_outcome(result, name_match, class_ok) -> Decision(outcome, reason)`, evaluated in this order:
1. `result.status == 'rejected'` -> `REJECTED` (reason: sanitised provider reason, else a fixed default).
2. `class_ok is False` -> `REJECTED` with the fixed reason "The vehicle type does not match the registration certificate." (an objective failure wins over name review).
3. `result.status == 'pending'` -> `PENDING`.
4. `result.status == 'verified'`: `name_match == 'match'` -> `VERIFIED`; otherwise `PENDING` (admin review).
Anything else is rejected earlier as a provider error.

#### `profiles/services/sanitise.py`

`sanitise_reason(text, *, redact=(), max_len=500) -> str`: strip HTML tags and control characters, collapse whitespace, replace case-insensitive occurrences of each `redact` string (the owner name) with `[redacted]`, truncate to `max_len`. Used for every provider-supplied or staff-supplied reason before it is stored or returned.

#### `profiles/services/rc_verification.py` (flag-on; imported lazily by `onboarding.py`)

```
register_vehicle_with_rc(user, registration_number, vehicle_type) -> (UserProfile, Vehicle)
process_rc_webhook(result: RCVerificationResult) -> None
resolve_rc_review(vehicle_id, *, approve: bool, reason: str | None, staff_user) -> Vehicle
reset_rc_attempts(vehicle_id, *, staff_user) -> Vehicle
get_vehicle_status(user) -> dict
derive_driver_status(profile, vehicle) -> str            # used by switch_role (flag ON)
```

**`register_vehicle_with_rc`** (inputs already normalised/validated by the existing serializer; `vehicle_type` is upper-cased for storage):

- **Phase 1, guard (short `transaction.atomic`).** Lock order is always `UserProfile` then `Vehicle`: `select_for_update` the profile, then the user's active vehicle (if any). `_assert_can_submit(user, profile, vehicle)` raises, in this order: `NotADriver` (role not driver); by status: `AWAITING_VEHICLE` -> continue, `PENDING_RC_VERIFICATION` -> `RCVerificationPending`, `COMPLETE` -> `RCAlreadyVerified` if the vehicle is `verified`, else `VehicleAlreadyRegistered`, any other status -> `DLNotVerified`; DL not `verified` -> `DLNotVerified`; if a vehicle exists in `AWAITING_VEHICLE`: `pending` -> `RCVerificationPending`, `verified` -> `RCAlreadyVerified` (defensive, inconsistent data), `rejected` or `NULL` -> resubmission allowed; `rc_attempt_count >= RC_MAX_ATTEMPTS` -> `MaxRCAttemptsExceeded`. Nothing is written in phase 1.
- **Phase 2, provider call (no transaction open).** `adapter = get_rc_adapter()` (any construction error -> `RCProviderError`); `result = adapter.verify(reg, user.id)`. `TimeoutError` -> `result = RCVerificationResult(status='pending')`, `timed_out = True`. Any other exception, or `result.status` outside the allowed set, or a `reference_id` longer than 100 chars -> log (exception type name only, no message, no `exc_info`) and raise `RCProviderError` (nothing written, attempt not consumed).
- **Phase 3, decide and persist (short `transaction.atomic`).** Re-lock profile then vehicle and re-run `_assert_can_submit` (a concurrent double-submit that already advanced the state therefore gets a 409 instead of creating a second row; the wasted provider call is accepted). Compute `name_match = classify_owner_match(profile.first_name, profile.last_name, result.owner_name)` and `class_ok = check_vehicle_class(vehicle_type, result.vehicle_class)`, then `decide_rc_outcome`. Create the `Vehicle` (first submission) or update the existing row in place (replacing `registration_number`, `vehicle_type`; `rc_attempt_count` preserved). Always: `rc_attempt_count += 1`, `rc_submitted_at = now`, `rc_vehicle_class`, `rc_fuel_type`, fitness/insurance dates, `rc_name_match`. By outcome: `VERIFIED` -> `rc_verification_status='verified'`, `rc_verified_at=now`, profile `COMPLETE`, owner name not stored; `PENDING` -> `'pending'`, profile `PENDING_RC_VERIFICATION`, `rc_owner_name` stored only if `name_match != 'match'`; `REJECTED` -> `'rejected'`, `rc_rejection_reason = sanitise_reason(reason, redact=[owner_name])`, profile stays/returns `AWAITING_VEHICLE`. `rc_verification_ref = result.reference_id`; a unique-constraint `IntegrityError` on the reference (a provider reusing a reference) is caught in a nested savepoint, the reference is saved as `NULL`, and `onboarding.rc.ref_collision` is logged at ERROR (the vehicle then resolves via admin).
- **After commit.** Emit log events; if another user already has this `registration_number`, log `onboarding.vehicle.duplicate_registration` at WARNING with `user_id` and `duplicate_count` only. For `REJECTED`, raise `RCVerificationRejected(extra={...})` *after* the transaction has committed (raising inside `atomic` would roll back the persisted rejection and attempt count). Otherwise return `(profile, vehicle)`.

**`process_rc_webhook(result)`:** look up the vehicle by `rc_verification_ref` without a lock to find the user (`RCReferenceNotFound` if absent), then in one transaction lock the profile, then the vehicle, and re-check the reference. If `rc_verification_status` is `verified` or `rejected` -> `AlreadyProcessed`. If `result.status == 'rejected'` -> reject (sanitised reason). If `'verified'` -> compute name match and class check from the webhook result (falling back to the stored `rc_vehicle_class`) and apply `decide_rc_outcome`: `VERIFIED` -> verified; `PENDING` (name not `match`) -> stays `pending` with `rc_name_match` and owner name recorded; `REJECTED` (class conflict) -> rejected. Profile transitions follow the resolution rule in the state machine section. Does not change `rc_attempt_count`.

**`resolve_rc_review(vehicle_id, approve, reason, staff_user)`:** lock profile then vehicle. Approve is valid for a `pending` vehicle and for a `rejected` vehicle (FR-40 manual approval after the attempt limit); reject is valid for a `pending` vehicle only; otherwise `RCReviewStateError` (`409 rc_review_invalid_state`). Approve sets `verified`, `rc_verified_at`, clears `rc_rejection_reason`, keeps `rc_name_match` as the audit trail, clears `rc_owner_name` via `_clear_owner_data` (v6), and moves a `PENDING_RC_VERIFICATION` or `AWAITING_VEHICLE` profile to `COMPLETE`. Reject requires a non-empty reason, stores it sanitised, sets `rejected`, clears `rc_owner_name` via `_clear_owner_data` (v6), and moves a `PENDING_RC_VERIFICATION` profile to `AWAITING_VEHICLE`. Logs `staff_user_id`; the admin layer additionally writes a `LogEntry`. **`reset_rc_attempts`** sets `rc_attempt_count = 0` only. These functions do not check the flag: staff must be able to recover stranded drivers after a rollback.

**`get_vehicle_status(user)`:** flag OFF -> `rc_verification_status = None`, `rc_attempts_remaining = None`, vehicle fields from the active vehicle if any. Flag ON -> `rc_attempts_remaining = max(0, RC_MAX_ATTEMPTS - rc_attempt_count)` (`RC_MAX_ATTEMPTS` when there is no vehicle); `rejection_reason` only when the vehicle is `rejected`. Owner name and all `rc_*` provider data other than status are never returned. Vehicle fields use the same representation as the existing `POST` response.

**`derive_driver_status(profile, vehicle)`** (flag ON, DL verified) is defined under "`switch_role`" below.

#### `profiles/services/onboarding.py` changes

```python
NEXT_STEP_BY_STATUS = {
    NOT_STARTED: 'role_selection', ROLE_SELECTED: 'profile', AWAITING_DL: 'dl_submission',
    PENDING_VERIFICATION: 'awaiting_verification', AWAITING_VEHICLE: 'vehicle_registration',
    PENDING_RC_VERIFICATION: 'awaiting_rc_verification', COMPLETE: 'none',
}
def compute_next_step(profile) -> str            # NEXT_STEP_BY_STATUS.get(profile.onboarding_status, 'none')

def register_vehicle(user, registration_number, vehicle_type):
    if not settings.RC_VERIFICATION_ENABLED:
        return _register_vehicle_self_declared(user, registration_number, vehicle_type)   # current body, verbatim
    from profiles.services import rc_verification
    return rc_verification.register_vehicle_with_rc(user, registration_number, vehicle_type)
```

The three duplicated view-local maps and the literals in `RoleSelectView`/`VehicleRegisterView` are replaced by `compute_next_step(profile)`; for every existing status the value is identical, so existing responses are unchanged. `ConditionalOnboardingGate` uses the same function when it builds the `onboarding_incomplete` error.

**`switch_role` (OQ-R12b, ADR Decisions 20, 27 and 28).** v5: one implementation for both flag modes (the former flag-ON variant was removed), `@transaction.atomic`, with `select_for_update` on the profile in both modes. State diagrams: "v5 state machine: role switch". Summary:
- Guard: `_SWITCH_ELIGIBLE_STATUSES` = `complete`, `awaiting_dl`, `pending_verification`, `awaiting_vehicle`, `pending_rc_verification`; otherwise `OnboardingNotEligibleForSwitch` (`403 onboarding_incomplete` with `onboarding_status` and `next_step`).
- Switching to `passenger` (both flag modes): `active_role = passenger`, `onboarding_status = COMPLETE`; `DriverVerification` and `Vehicle` rows are kept. A passenger needs no vehicle, and a passenger left in a non-complete status would stay gated out of the app. (Before v5 this exit worked from `awaiting_vehicle` only with the flag ON, and `pending_verification` was left unchanged.)
- Switching to `driver` when already `driver`: no-op.
- Switching to `driver` from `awaiting_vehicle` (only reachable with inconsistent legacy data, a passenger row in `awaiting_vehicle`): never derives `COMPLETE`. Flag ON: `VehicleStepIncomplete` -> `400 invalid_onboarding_state` ("Finish vehicle registration first, or switch to passenger"). Flag OFF: `OnboardingNotEligibleForSwitch` -> `403 onboarding_incomplete`. Either way the user recovers by switching to passenger first.
- Switching to `driver` with **no verified DL** (no `DriverVerification` row, or a rejected one): `active_role = driver`, `onboarding_status = AWAITING_DL`, `200`, `next_step = dl_submission`. The user then submits a DL through the existing endpoint (`POST /api/onboarding/driver/dl/`, which now passes its role and status checks) and the DL -> vehicle -> (RC) flow applies unchanged. The DL attempt limit still applies and toggling roles does not reset `attempt_count`. This replaces the former `400 dl_required` dead end (ADR Decision 28).
- Switching to `driver` with a **pending** DL: `onboarding_status = PENDING_VERIFICATION`, `202`.
- Switching to `driver` with a **verified** DL no longer hard-codes `COMPLETE`. It sets `onboarding_status = _status_for_verified_driver(profile, vehicle)` in both flag modes, where `vehicle` is the user's newest `is_active` vehicle. `COMPLETE` is reachable only with an active vehicle or the grandfathered `vehicle_step_exempt` marker; otherwise the user is `awaiting_vehicle` with `next_step = vehicle_registration`. Flag ON delegates to `derive_driver_status` (RC status of the vehicle decides, table below). Flag OFF ignores the RC columns: any active vehicle gives `complete`; no vehicle gives `complete` if `vehicle_step_exempt` is set, else `awaiting_vehicle`. This deliberately changes flag-OFF role-switch edge cases (before v5 a flag-OFF switch with a verified DL always gave `complete`); initial onboarding with the flag OFF is unchanged.

| Vehicle state (flag ON) | Derived `onboarding_status` | Note |
|---|---|---|
| `verified` | `complete` | |
| `rc_verification_status IS NULL` (legacy self-declared) | `complete` | grandfathered, FR-45 |
| `pending` | `pending_rc_verification` | |
| `rejected` | `awaiting_vehicle` | |
| no vehicle row, `vehicle_step_exempt` set | `complete` | grandfathered driver (see below) |
| no vehicle row, `vehicle_step_exempt` not set | `awaiting_vehicle` | `next_step = vehicle_registration`; reachable, e.g. a driver who never submitted a vehicle and round-trips through passenger |

Flag OFF derivation (v5): an active vehicle of any state gives `complete` (the `rc_*` columns are ignored, and are `NULL` on the flag-OFF path anyway); no vehicle row gives `complete` when `vehicle_step_exempt` is set, otherwise `awaiting_vehicle`.

**Why an explicit marker (`vehicle_step_exempt`) is used instead of inferring the grandfathered case.** An earlier revision (v3) inferred it from "no vehicle row while the current status is `COMPLETE`" and argued no column was needed. That argument was wrong because of FR-52: a driver in `awaiting_vehicle` who never submitted a vehicle can switch to passenger (which sets `complete`) and back to driver, and would then match the inferred rule and become `COMPLETE` without a vehicle. From v4 the case is recorded by `UserProfile.vehicle_step_exempt`, set only by the data step of migration `0004` for profiles that are `complete`, have a `DriverVerification` row with `dl_verification_status = 'verified'` and have no `is_active` `Vehicle` row (v6). Nothing else ever sets it (application code never writes it; it is read-only in admin), so passenger round trips cannot create it, and deleting a vehicle row cannot create it either. Rows that exist keep the derivation in the table above. Accepted edge case of the marking rule (ADR Decision 27): a profile whose only vehicle is inactive is marked. (Before v6 a `complete` profile with a pending or rejected DL record was also marked; the rule now requires a verified DL, so that case no longer arises.) This matches FR-43 / AC-48 / AC-54 as amended in requirements v6.
- The response always includes `next_step` (v5; before, only for `awaiting_vehicle` / `pending_rc_verification`) via `compute_next_step(profile)`. HTTP `202` only when the resulting status is `pending_verification`, otherwise `200`. `RoleSwitchView` maps the dedicated exception classes (`OnboardingNotEligibleForSwitch`, `VehicleStepIncomplete`, both `ValueError` subclasses caught before the generic `ValueError` branch) explicitly, so no error is derived from message text. `DLRequired` is no longer raised anywhere.

#### Exceptions (`profiles/exceptions.py`, all subclass `core.exceptions.ApiError`)

| Class | HTTP | `error_code` | Used by |
|---|---|---|---|
| `RCVerificationPending` | 409 | `rc_verification_pending` | submit while pending |
| `RCAlreadyVerified` | 409 | `rc_already_verified` | submit when verified |
| `RCProviderError` | 422 | `rc_verification_provider_error` | adapter failure, no attempt consumed |
| `MaxRCAttemptsExceeded` | 429 | `max_rc_attempts_exceeded` | limit reached (no `retry_after`; staff action required) |
| `RCVerificationRejected` | 422 | `rc_verification_rejected` | rejection, carries `extra` |
| `RCReferenceNotFound` | 404 | `rc_reference_not_found` | webhook, unknown reference |
| `MalformedWebhookPayload` | 400 | `invalid_webhook_payload` | webhook, unparsable body |
| `RCReviewStateError` | 409 | `rc_review_invalid_state` | admin action on a vehicle in the wrong state |

Reused: `NotADriver`, `DLNotVerified`, `VehicleAlreadyRegistered`, `AlreadyProcessed`, `InvalidWebhookSignature`, `OnboardingIncomplete`. Flag-OFF webhook uses DRF `NotFound` (`404 not_found`). No code in the RC path derives an error from `str(exc)`.

#### Serializers, views, URLs

- `VehicleRegistrationResponseSerializer`: add `rc_verification_status`, `rejection_reason`, `reference_id` (all `allow_null`; the view always supplies them, `None` on the flag-off path). `VehicleRegistrationSerializer` (request) unchanged.
- `VehicleStatusSerializer` (new): `onboarding_status`, `next_step`, `rc_verification_status`, `rejection_reason`, `registration_number`, `vehicle_type`, `rc_attempts_remaining`. `OnboardingStatusSerializer`: add nullable `rc_verification_status`. `RoleSwitchResponseSerializer`: add optional `next_step`.
- Response serializers for vehicle data are plain `Serializer`s fed explicit dicts; `ModelSerializer` must not be used for `Vehicle`, so `rc_owner_name` can never be exposed by a field-list slip.
- `VehicleRegisterView`: replace the literal `next_step` with `compute_next_step(profile)`; add the three fields from `vehicle`; HTTP `202` when `profile.onboarding_status == PENDING_RC_VERIFICATION`, else `200`. The `except ValueError` block keeps the substring mapping but (v7 re-check) first answers `409 vehicle_already_registered` when the profile is `COMPLETE`, and serializer errors are mapped by `_raise_vehicle_validation_error` to `400 invalid_registration_format` / `400 invalid_vehicle_type`.
- `VehicleStatusView` (`permission_classes = [IsAuthenticated, RequireDriverRole]`), `RCWebhookView` (`[AllowAny]`, `authentication_classes = []`).
- `RequireDriverRole(IsDriverRole)` in `permissions.py` raises `NotADriver` instead of returning `False`, giving the specified `403 not_a_driver`. The existing `IsDriverRole` is not changed (ADR Decision 26). (v7: `RequireDriverRole` is now also the permission class of `VehicleRegisterView`; `DLSubmitView` and `DLStatusView` still use `IsDriverRole`, KG-03.)
- URLs: `onboarding/driver/vehicle/status/` (`vehicle-status`), `onboarding/driver/vehicle/rc/webhook/` (`vehicle-rc-webhook`).

#### Gate (`core/permissions.py`)

`ConditionalOnboardingGate` keeps its flag check and lazy import, but when the profile is not `COMPLETE` (or absent) it raises `OnboardingIncomplete(extra={'onboarding_status': ..., 'next_step': compute_next_step(profile)})`. This delivers FR-14/AC-41 (`403 onboarding_incomplete` with `next_step = awaiting_rc_verification`) and is dormant while `ONBOARDING_GATE_ENABLED` is False. A user with no profile row is reported as `not_started` / `role_selection`. It does not affect the vehicle endpoints (they override `permission_classes`).

#### Admin (`profiles/admin.py`, OQ-R13 stays an operations item)

`VehicleAdmin` is the review queue:
- **List:** registration number, user phone, `vehicle_type`, `rc_verification_status`, `rc_name_match`, `rc_attempt_count`, `rc_submitted_at`, and a computed `other_drivers_with_same_reg` (queryset annotated with a `Subquery` count of vehicles with the same `registration_number` and a different `user`; served by `idx_vehicle_regno`). Default ordering: `rc_submitted_at` ascending (oldest pending first). `rc_owner_name` is not in `list_display`, `list_filter` or `search_fields`.
- **Filters:** `rc_verification_status`, `rc_name_match`, a "needs review" filter (`pending`), `is_active`, and "has duplicate registration". **Search:** registration number, user phone.
- **Detail view:** all `rc_*` fields and `registration_number` are read-only; `rc_owner_name` is displayed here only, and since v6 only to users holding `profiles.review_rc` (`get_fieldsets` removes the field for other staff; SEC-002 F-07). State changes happen exclusively through actions.
- **Actions** (each guarded by `permissions=['review_rc']` backed by `has_review_rc_permission` -> `request.user.has_perm('profiles.review_rc')`): *Approve*, *Reject* (reason from an `ActionForm` text field beside the action selector; empty -> error message, no change), *Reset RC attempts*. Each calls the service function, catches `ApiError` and reports it with `message_user`, and calls `self.log_change(request, obj, message)` so the acting staff user is recorded in Django's `LogEntry` (no new audit table). The message never contains the owner name.
- `has_add_permission` and `has_delete_permission` return `False` (vehicles are created by the API and should not be removed by staff). Since v4, deleting a row cannot make a driver look grandfathered, because that is decided only by `UserProfile.vehicle_step_exempt`, which is read-only in `UserProfileAdmin`.
- **`UserProfileAdmin` (v6, SEC-002 F-11):** `onboarding_status` and `active_role` are read-only for non-superusers (a staff user with change permission can no longer bypass the state machine and the review audit), the `user` key is read-only for non-superusers once the row exists, and `vehicle_step_exempt` is read-only for everyone.
- **`DriverVerificationAdmin` (v6):** the encrypted `dl_number` is excluded from the form; `dl_verification_status`, `dl_verification_ref`, `attempt_count` and `dl_rejection_reason` are read-only for non-superusers; adding rows is disabled (rows are created only by the DL service, which encrypts the number).
- Review ownership, SLA and queue monitoring are operations decisions (OQ-R13) and are not designed here.

#### Configuration and startup checks (`config/settings.py`)

| Setting / env var | Default | Notes |
|---|---|---|
| `RC_VERIFICATION_ENABLED` | `False` | master flag, read at call time everywhere |
| `RC_ADAPTER_CLASS` | `profiles.adapters.mock.MockRCVerificationAdapter` | dotted path, loaded by `import_string` |
| `RC_ADAPTER_MOCK_RESULT` | `sync_verified` | one of the six modes; validated by `MockRCVerificationAdapter.from_settings` |
| `RC_PROVIDER_TIMEOUT_SECONDS` | `5` (float) | passed to `adapter.__init__(timeout_seconds=...)` |
| `RC_MAX_ATTEMPTS` | `3` (int) | read at call time |
| `RC_WEBHOOK_SECRET` | `''` (empty = webhook fails closed) | placeholder in `.env.example`; never committed |
| `RC_MOCK_ADAPTER_FORBIDDEN` (derived, not an env var) | `RC_VERIFICATION_ENABLED and not DEBUG` | computed once at import from the *environment* `DEBUG`, so Django's test runner forcing `DEBUG=False` cannot trip it |

Startup validation, placed after `ONBOARDING_GATE_ENABLED` in `settings.py` and executed **only when `RC_VERIFICATION_ENABLED` is true**, collects problems and raises one `ImproperlyConfigured`:
1. `RC_MAX_ATTEMPTS < 1` or `RC_PROVIDER_TIMEOUT_SECONDS <= 0`.
2. If `not DEBUG`: `'mock' in RC_ADAPTER_CLASS.lower()` (production with the mock and the flag ON is refused, NFR-SEC-08 / AC-51).
3. If `not DEBUG`: `RC_WEBHOOK_SECRET` empty or starting with `PLACEHOLDER`.
4. If `not DEBUG`: `ONBOARDING_GATE_ENABLED` is False (otherwise FR-14/FR-15 are not enforced and `pending_rc_verification` drivers would not be gated).

A settings-time check is used instead of a Django system check because `manage.py check` does not run when gunicorn/WSGI starts; only an import-time raise protects every entry point. `get_rc_adapter()` adds a second layer: it refuses any `MockRCVerificationAdapter` subclass when `RC_MOCK_ADAPTER_FORBIDDEN` (catches an alias or subclass whose dotted path does not contain "mock"). With the flag OFF none of these checks run, `manage.py check` passes with no RC variables set, and no RC setting can fail startup. Environment changes take effect only after a process restart.
---

## Frontend / Backend Responsibilities

| Concern | Backend | Frontend (Expo) |
|---------|---------|-----------------|
| DL format validation | Authoritative: normalise + regex, reject with `400` (contract code `invalid_dl_format`; the code currently returns `400 invalid_request` with `error.fields.dl_number`, KG-01, so clients should key on the `400` and `error.fields.dl_number`) | Recommended: client-side regex for instant UX feedback; server validation is the gate |
| Vehicle registration format validation | Authoritative: normalise + regex, reject `400 invalid_registration_format` | Recommended: client-side regex for instant UX feedback; server validation is the gate |
| Vehicle type validation | Authoritative: reject `400 invalid_vehicle_type` if not in allowed set | Client shows dropdown/picker restricted to allowed types |
| Onboarding state persistence | Owns the state machine; returns `onboarding_status` + `next_step` on every step response | Reads `next_step` to determine which screen to show next |
| Role label (`driver` vs "Rider") | Uses `driver` / `passenger` in all API contracts | Maps `driver` -> "Rider" in all UI copy |
| Resume mid-flow | Endpoint `GET /api/onboarding/status/` returns current state | On app open, call status endpoint and route to the appropriate screen |
| DL verification polling | `GET /api/onboarding/driver/dl/status/` returns `dl_verification_status` | Poll this endpoint while status is `pending` (suggested: exponential back-off starting at 5s) |
| DL provider failure (v6) | `POST /api/onboarding/driver/dl/` returns `422 dl_verification_provider_error` when the provider call fails or returns an invalid result; no attempt is consumed and nothing is saved. A timeout is `202` pending (an attempt is consumed). | Treats `422 dl_verification_provider_error` as retryable ("try again") and keeps the DL form; routes `202` to the pending screen. |
| Onboarding gate enforcement | `core.permissions.ConditionalOnboardingGate` returns `403 onboarding_incomplete` with `onboarding_status` and `next_step`, only while `ONBOARDING_GATE_ENABLED` is True (default False) | On `403 onboarding_incomplete`, navigate to the step indicated by `next_step` |
| Age validation range | Enforces 18-80; may reject boundary with `400 invalid_age` | Apply same 18-80 range in client form validation |
| Vehicle registration normalisation | Strips spaces/hyphens, uppercases before validation | May show normalised preview to user before submission |
| RC verification (flag-gated) | Owns the flag, the state machine, name matching, class mapping, attempt limits and all decisions; adapter only fetches provider facts. Returns `onboarding_status`, `next_step`, `rc_verification_status` on every vehicle response. | Reads `next_step` (must handle `vehicle_registration` and `awaiting_rc_verification`, with a safe default for unknown values). Polls `GET /api/onboarding/driver/vehicle/status/` while `pending`. Shows a neutral "your vehicle is being verified" message (never mentions a name mismatch). Shows `rejection_reason` and offers resubmission on `422 rc_verification_rejected`; shows a contact-support message when `rc_attempts_remaining = 0` or on `429 max_rc_attempts_exceeded`. |
| Flag-off redirect to home | Guarantees `onboarding_status = complete` and `next_step = none` on the vehicle response and on `/api/auth/me/`. | Redirects on `complete` / `none`; if it does not, that is a frontend defect. |
| Role switch to Driver without a verified DL (v5) | `PATCH /api/profile/role/` sets `active_role = driver`, `onboarding_status = awaiting_dl`, returns `200` with `next_step = dl_submission`. Switch to passenger is always available from any non-initial status and returns `complete`. | Confirms with the user before switching (while `ONBOARDING_GATE_ENABLED` is on the user is gated out of normal features until driver setup is finished or they switch back), routes by `next_step`, and offers a "switch back to Rider/Passenger" action on every driver-setup screen. No longer needs to handle `400 dl_required`. |
| Rollout ordering | Flag stays OFF until the client release that handles the two new `next_step` values is live. | Ships the vehicle and RC-pending screens first. |

---

## Failure Modes

| Scenario | Behaviour | Recovery |
|----------|-----------|----------|
| DL provider times out (v6) | Adapter raises `TimeoutError`; the service treats it as `pending`; `202` with `dl_verification_status=pending`, `PENDING_VERIFICATION`, an attempt is consumed, no `dl_verification_ref` is stored. | Client polls `/api/onboarding/driver/dl/status/`. Without a reference the webhook cannot resolve it: the driver resubmits (while attempts remain) or staff act. |
| DL provider raises any other error, returns an unknown status, or an over-long reference (v6) | `get_dl_adapter().submit()` runs with no transaction open; the failure is logged by exception type only and answered with `422 dl_verification_provider_error`. Nothing is written and no attempt is consumed. | Client retries. Operators alerted on the `onboarding.dl.provider_error` event. |
| Signed DL webhook with an unrecognised `status` (v6) | `WebhookPayloadSerializer` accepts only `verified` / `rejected`; anything else is `400 invalid_request`. Nothing is read or written beyond the signature check; the payload is not logged. | Provider corrects and retries. |
| Webhook arrives before client receives `202` | `process_webhook` sets state to VERIFIED/AWAITING_VEHICLE. Client polls and discovers `AWAITING_VEHICLE` state with `next_step=vehicle_registration`. State transitions are idempotent. | No action needed. Client receives correct state on next poll or app open. |
| Duplicate DL webhook delivery (v6) | The `DriverVerification` is already `verified` / `rejected`: `process_webhook_result` changes nothing and the view returns `200` (idempotent; earlier revisions returned `409 already_processed`). | No action needed. |
| Concurrent `POST /api/onboarding/role/` calls | `get_or_create` + DB unique constraint on `UserProfile.user` ensures one row. Second call gets `409 role_already_set` or sees existing role. | No action needed. |
| `DL_ENCRYPTION_KEY` misconfigured / missing (v7 corrected, KNOWN GAP KG-04) | The key is read lazily by `profiles/utils/crypto.py::_get_fernet()` on first encrypt/decrypt. Nothing reads it at startup or in `manage.py check`, so the process starts and serves traffic. `POST /api/onboarding/driver/dl/` raises `ImproperlyConfigured` after the phase-1 guard and before the provider call; it is not a domain error and is returned as `500 server_error`. Nothing is written and no attempt is consumed. | Set the variable before deployment and back it up (RISK-001). Startup validation of the key is an open item (U11, SEC-002 F-15). |
| `DL_ADAPTER_CLASS` points to a non-existent class or the mock is configured with `DEBUG` off (v6) | At startup: with `DEBUG` off and `'mock'` in the path the process refuses to start (`ImproperlyConfigured`). At request time `get_dl_adapter()` raises (import error, refused mock subclass, bad `DL_ADAPTER_MOCK_RESULT`): submit answers `422 dl_verification_provider_error` (no attempt consumed); the webhook answers `403 invalid_webhook_signature` (fail closed). | Fix the env var and restart. |
| `DL_WEBHOOK_SECRET` empty or wrong (v6) | Every DL webhook is rejected with `403 invalid_webhook_signature` before any DB access (fail closed). Startup is not blocked. | Set the secret on both sides. Drivers parked in `pending_verification` by an async provider stay pending until the provider can deliver. |
| DL webhook for an unknown `reference_id` (v6) | After a valid signature: `404 dl_reference_not_found`; one WARNING log with the (clipped) reference; no state change. | None. |
| Concurrent DL submissions for one user (v6) | Phase 3 re-locks profile then `DriverVerification` and re-runs the guard: a second request after a verified result gets `409 dl_already_verified`; `attempt_count` is incremented under the lock so the cap `DL_MAX_ATTEMPTS` cannot be exceeded by racing requests. The provider may be called twice. | None. |
| Provider reuses a `dl_verification_ref` already stored (unique constraint) (v6, known gap) | The partial unique constraint `uq_dl_verification_ref` raises `IntegrityError` in phase 3; the DL path, unlike the RC path (`onboarding.rc.ref_collision`), has no handler, so the client sees a `500`. Not reachable with the mock (random references). | Handle like the RC path before a real DL provider is enabled. |
| User calls onboarding endpoint with expired JWT | `IsAuthenticated` returns `401` before any profile lookup. | Client refreshes token via `/api/auth/token/refresh/`. |
| `UserProfile` row not yet created when `/api/onboarding/status/` called | `get_or_create_profile` creates the row lazily; always returns `200`. | No special handling needed. |
| Driver calls vehicle endpoint before DL verified | `VehicleRegisterView` checks `onboarding_status == AWAITING_VEHICLE`; returns `403 dl_not_verified` if DL not verified. | Client should only show vehicle screen when `next_step=vehicle_registration`. |
| Driver calls vehicle endpoint after onboarding already complete | Service checks `user.vehicles.filter(is_active=True).exists()`; returns `409 vehicle_already_registered`. | No action needed. Client should not show vehicle form after completion. |
| Concurrent vehicle registration calls | `register_vehicle()` runs in `transaction.atomic`. Second call sees existing active vehicle and returns `409 vehicle_already_registered`. | No action needed. |
| Duplicate vehicle registration number across users | Allowed (no uniqueness constraint, FR-46). With the flag ON a WARNING `onboarding.vehicle.duplicate_registration` is logged (count only) and admin shows the duplicate count. | Reviewers use the admin indicator. A future partial unique constraint on verified active vehicles is the upgrade path. |
| RC provider returns an error (non-timeout) or an unknown status (flag ON) | `422 rc_verification_provider_error`; no `Vehicle` row for a first submission; `rc_attempt_count` unchanged; ERROR log with exception type only. | Client retries. Operators alerted on the error-rate log event. |
| RC provider times out (flag ON) | Adapter raises `TimeoutError`; treated as `pending` with no reference; `202`; attempt consumed. | Cannot be resolved by webhook (no reference): staff approve/reject in admin. A flaky provider will therefore feed the review queue (see RISK-010). |
| RC adapter class path wrong / import error (flag ON) | `get_rc_adapter()` raises; surfaced as `422 rc_verification_provider_error` at request time; no startup failure unless the mock-in-production rule trips. | Fix env var and restart. |
| Concurrent double-submit of the vehicle form (flag ON) | Profile row lock serialises phases 1 and 3; the second request re-validates in phase 3 and gets `409` (`rc_verification_pending` or `vehicle_already_registered`). The provider may be called twice. | Client disables the button; accepted cost with the mock, revisit with a paid provider (optional per-user cache lock). |
| Provider reuses a `reference_id` already stored (unique constraint) | Reference saved as `NULL`, ERROR log `onboarding.rc.ref_collision`, vehicle resolves through admin. | Staff resolve. |
| RC webhook with a valid signature while the flag is OFF | `404 not_found`, body not read, no state change. | None. |
| RC webhook for a reference already `verified` / `rejected` | `409 already_processed`, no change. | None. |
| RC webhook `verified` with no owner data | `rc_name_match = not_checked`, vehicle stays `pending`, `200`. | Staff resolve in admin. |
| Admin action on a vehicle in the wrong state | `RCReviewStateError`, reported via `message_user`, no change. | None. |
| Flag turned ON then OFF with drivers in `pending_rc_verification` or with a `rejected` row | Not automatic. A rejected or pending active row makes the flag-off path return `409 vehicle_already_registered`. | Operational data patch in Migration / Rollout. |
| Driver switched to passenger while `pending_rc_verification` | Status becomes `complete` (passenger); a later webhook/admin resolution updates only the vehicle. | None. |
| Passenger (`complete`) starts driver setup (v5) | `PATCH /api/profile/role/` role `driver` with no verified DL: `active_role = driver`, `awaiting_dl`, `200`, `next_step = dl_submission`. With `ONBOARDING_GATE_ENABLED` on the user is gated out of normal features until done. | Finish DL/vehicle, or `PATCH role=passenger` (returns `complete`; DL and vehicle rows kept). |
| Role toggling to get around the DL attempt limit (v5) | `attempt_count` is not reset by a role switch; the DL endpoint's `max_dl_attempts_exceeded` still applies in `awaiting_dl`. | User can switch back to passenger; staff action needed for more attempts. |
| DL webhook `verified` arrives after the user switched back to passenger (v5) | `DriverVerification` becomes verified; the profile stays `complete` (advance happens only from `pending_verification`). | A later switch to driver derives the status from the vehicle. |
| Concurrent role switch and webhook / vehicle resolution (v5) | `switch_role` locks the profile row (then the vehicle) in both flag modes; webhook and RC paths use the same lock order. | None. |

---

## Security Considerations

### Authentication
- All onboarding endpoints require a valid JWT Bearer token (`IsAuthenticated`).
- The webhook endpoint (`POST /api/onboarding/driver/dl/webhook/`) is exempt from JWT auth; it authenticates via `adapter.validate_webhook(headers, body)`, which since v6 must verify a hex HMAC-SHA256 of the raw body in `X-DL-Signature` (optional `sha256=` prefix) with `hmac.compare_digest` and fail closed on an empty secret or missing header. The adapter is resolved per request through `get_dl_adapter()`. The view calls this before the payload is parsed and before any DB operation and returns `403` on failure.
- `DL_WEBHOOK_SECRET` env var holds the shared HMAC key; loaded via `python-decouple` (default empty, which rejects every webhook), never committed, and separate from `DL_ENCRYPTION_KEY` and `RC_WEBHOOK_SECRET`.

### DL number PII
- Full DL number encrypted at rest (Fernet, `DL_ENCRYPTION_KEY`).
- Only last-4 chars stored in plaintext (`dl_number_display`).
- DL number never logged, not even the last four characters. DL log events carry only ids, counts, statuses and `reference_id` through the allow-listed `_log_event` helper (v7 corrected; earlier text said `dl_number_display` was logged).
- Admin access to `DriverVerification` restricted to `is_staff=True` users (NFR-SEC-06). Since v6 the encrypted `dl_number` is excluded from the admin form, state fields are read-only for non-superusers and rows cannot be added by hand.

### Vehicle registration number
- Stored plaintext — registration numbers are publicly visible on vehicles (FR-31). No encryption needed.
- No uniqueness constraint — same registration number may be submitted by different users in v1.
- Admin access to `Vehicle` restricted to `is_staff=True` users.

### Onboarding gate
- The gate is server-enforced by `core.permissions.ConditionalOnboardingGate` (NFR-SEC-04), **but only while `ONBOARDING_GATE_ENABLED` is True; the default is False, so by default no endpoint is gated** (SEC-002 F-17). `profiles.permissions.IsOnboardingComplete` exists but is not wired (v7 correction). The Expo client redirect is a UX supplement only.
- `IsDriverVerified` independently checks `dl_verification_status == VERIFIED` for ride-offer endpoints; `active_role == driver` alone is not sufficient (FR-25, AC-26).

### Vehicle endpoint authorization
- `POST /api/onboarding/driver/vehicle/` requires `IsAuthenticated` + `RequireDriverRole` (v7 correction; the DL endpoints still use `IsDriverRole`, KG-03).
- Service layer additionally checks `onboarding_status == AWAITING_VEHICLE` (ensures DL is verified and vehicle not yet registered).
- A Passenger calling this endpoint receives `403 not_a_driver` from the permission class.
- A Driver whose DL is not verified receives `403 dl_not_verified` from the service layer.

### Role switch (v5)
- `PATCH /api/profile/role/` requires only `IsAuthenticated` (so a user mid-driver-setup can always switch back) and is guarded by `_SWITCH_ELIGIBLE_STATUSES`; `not_started` / `role_selected` users cannot use it to skip profile collection.
- Switching to `driver` grants no driver privileges by itself: `IsDriverVerified` still requires `dl_verification_status == VERIFIED`, and the gate still requires `onboarding_status == COMPLETE`, which is only reachable through a verified DL plus an active vehicle (or the explicit `vehicle_step_exempt` marker).
- Accepted side effect: while `ONBOARDING_GATE_ENABLED` is on, a passenger who starts driver setup is gated out of normal features until they finish or switch back (RISK-015).
- The profile row is locked (`select_for_update`) in both flag modes, so concurrent switches and webhook/RC resolutions cannot interleave status writes.

### Webhook security
- Signature validated before the payload is parsed and before any DB access (HMAC-SHA256 over the raw body, constant-time compare, fail closed; v6).
- `DL_WEBHOOK_SECRET` is a separate env var from `DL_ENCRYPTION_KEY`.
- Webhook endpoint is intentionally unauthenticated by JWT; its URL is not secret but its signature requirement makes spoofing difficult. Replays are harmless because processing is idempotent (a resolved reference changes nothing and returns `200`). An unknown reference returns `404` only after a valid signature, so the endpoint is not a reference-existence oracle for unauthenticated callers (SEC-002 F-09).

### Environment variables (all loaded via `python-decouple`)
```
DL_ENCRYPTION_KEY            # Fernet key; generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DL_WEBHOOK_SECRET            # HMAC-SHA256 key for X-DL-Signature; default empty = every webhook rejected
DL_ADAPTER_CLASS             # default: profiles.adapters.mock.MockDLVerificationAdapter; refused when DEBUG is off (import-time guard)
DL_ADAPTER_MOCK_RESULT       # default: sync_verified (mock only; also async_pending, sync_rejected)
(DL_PROVIDER_TIMEOUT_SECONDS is NOT implemented in the code as of v6; a real adapter owns its timeout)
DL_MAX_ATTEMPTS              # default: 3; must be >= 1 (startup check); enforced under a row lock
DIGILOCKER_CLIENT_ID         # planned: DigiLocker OAuth 2.0 client ID (no adapter reads it yet)
DIGILOCKER_CLIENT_SECRET     # planned: DigiLocker OAuth 2.0 client secret (no adapter reads it yet)
DIGILOCKER_API_URL           # planned: DigiLocker base URL (no adapter reads it yet)
```
These must be added to `backend/.env.example` with placeholder values. `DL_ENCRYPTION_KEY` is read lazily by `profiles/utils/crypto.py` at the first encrypt or decrypt, not at startup (KNOWN GAP KG-04).

### v3: RC verification security

- **Flag-off attack surface.** With the flag OFF the RC webhook returns `404` before reading the body, the status endpoint exposes only `null` RC values, and no adapter is built; no new unauthenticated behaviour is reachable except the 404.
- **RC owner name (third-party PII, DPDP Act 2023).** Stored only in `Vehicle.rc_owner_name` and only when a vehicle goes to name review; staff-only (v6: the admin field is shown only to holders of `profiles.review_rc`; the actions also require it); absent from every Driver-facing serializer (plain serializers with explicit fields); absent from logs; never included in `message_user` or `LogEntry` text; redacted out of any stored rejection reason by `sanitise_reason(redact=[owner_name])`. The raw provider payload is never persisted. Since v6 (SEC-002 F-07) `_clear_owner_data(vehicle)` runs on every terminal transition, including staff approve and reject, so the name survives only while a vehicle is pending review; the admin shows the field only to `profiles.review_rc` holders. The remaining open item (OQ-R7) is how long a name may be held while pending, and backups, which contain the column until the row is cleared.
- **Webhook.** Signature verified (HMAC-SHA256 over the raw body, `hmac.compare_digest`, fail closed on empty secret) before any DB access and before the payload is parsed; the flag check precedes it and costs no I/O. Replays are harmless because processing is idempotent (`409 already_processed` once terminal). `RC_WEBHOOK_SECRET` is separate from `DL_WEBHOOK_SECRET` and `DL_ENCRYPTION_KEY`, loaded through `python-decouple`, placeholder only in `.env.example`.
- **Mock adapter cannot run in production with the flag ON.** Layer 1: `settings.py` raises `ImproperlyConfigured` at import when `RC_VERIFICATION_ENABLED and not DEBUG` and the adapter path contains "mock" (also checks webhook secret and `ONBOARDING_GATE_ENABLED`). Layer 2: `get_rc_adapter()` refuses any `MockRCVerificationAdapter` subclass when `RC_MOCK_ADAPTER_FORBIDDEN`. Layer 3: the mock's `validate_webhook` fails closed without a secret. Residual gap: a production deployment run with `DEBUG=True` bypasses all three; `DEBUG=True` in production is already a critical misconfiguration (CORS allow-all, debug pages) and is out of scope here.
- **Authorization.** Vehicle and status endpoints require authenticated, driver-role users; the new status view raises `403 not_a_driver` via `RequireDriverRole`. Admin actions require `profiles.review_rc`. Driver-facing `rejection_reason` can contain staff-typed text, so the admin action form carries a help text forbidding personal data.
- **Information leakage.** The `202` response never distinguishes provider delay from name review; `rc_name_match` is not returned to drivers; unknown webhook references return `404` only after a valid signature.
- **Injection / size.** Provider strings are clipped to column widths and sanitised before storage; webhook body size is bounded by Django's `DATA_UPLOAD_MAX_MEMORY_SIZE`.
- **Locking.** Fixed lock order (`UserProfile` then `Vehicle`) in submit, webhook and admin paths to avoid deadlocks.

### v6: DL security

- **No unverifiable "verified driver" in production.** The mock DL adapter verifies any well-formed number. It cannot run with `DEBUG` off: `config/settings.py` raises `ImproperlyConfigured` at import when `'mock'` is in `DL_ADAPTER_CLASS`, and `get_dl_adapter()` refuses any `MockDLVerificationAdapter` subclass when `DL_MOCK_ADAPTER_FORBIDDEN`. The guard is not conditional on any flag (DL has none). Residual gap: a production process run with `DEBUG=True` bypasses both layers (already a critical misconfiguration). Until a real DL adapter exists, non-`DEBUG` deployments cannot start.
- **Webhook authentication.** HMAC-SHA256 over the raw body, `X-DL-Signature`, constant-time comparison, fail closed on an empty `DL_WEBHOOK_SECRET` or a missing header, checked before parsing and before any DB access. The adapter used to verify is resolved per request, so it cannot drift from the adapter in settings (F-03).
- **Attempt cap and races.** `DL_MAX_ATTEMPTS` is evaluated under `select_for_update` on the profile and `DriverVerification` rows, in the guard and again before persisting, so parallel requests cannot exceed it (F-04). The provider is called with no row lock and no transaction held.
- **Information leakage.** DL logging uses an allow-list helper; the DL number, rejection reasons and adapter exception messages are never logged; the webhook answers `404 dl_reference_not_found` only after a valid signature. Stored and returned rejection reasons are sanitised (`sanitise_reason`).
- **Admin.** State fields are read-only for non-superusers; the encrypted DL number is never rendered; rows cannot be created by hand (F-11).
- **Still open (SEC-002):** F-05 no throttling on onboarding endpoints or webhooks (so an authenticated user can still call the provider repeatedly within `DL_MAX_ATTEMPTS` and RC amplification is not limited); F-06 flag-transition semantics (flag-off role switch ignores the RC state of an existing vehicle; enabling RC does not re-verify legacy vehicles); F-08 verification is not bound to the person (the DL is not matched to the account holder, DL reuse across accounts is not detected). See Risks and Open Decisions.

---

## Observability

### Key log events emitted by the code (`logger = logging.getLogger('profiles')`; verified at `803e319`)

| Event | Level | Extra fields |
|-------|-------|--------------|
| `onboarding.dl.submitted` | INFO | `user_id`, `attempt_count`, `dl_status`, `onboarding_status`, `timed_out` (v6: allow-listed; no DL number, not even last-4) |
| `onboarding.dl.attempts_exhausted` | WARNING | `user_id`, `attempt_count` (v6) |
| `onboarding.dl.webhook.invalid_signature` | WARNING | (none; no body content) (v6) |
| `onboarding.dl.webhook.processed` | INFO | `reference_id`, `outcome` (`verified` / `rejected` / `duplicate`) (v6) |
| `onboarding.dl.webhook.unknown_reference` | WARNING | `reference_id` (clipped to 100 chars) (v6) |
| `onboarding.dl.provider_error` | ERROR | `user_id`, `adapter`, `error_type` (exception type name only, or `InvalidResult`); the webhook view logs `error_type` alone when the adapter cannot be built (v6) |

**Where the DL events are emitted.** `onboarding.dl.submitted`, `.attempts_exhausted`, `.provider_error`, `.webhook.processed` and `.webhook.unknown_reference` come from `services/dl_verification.py::_log_event` (allow-listed fields). `onboarding.dl.webhook.invalid_signature`, and an `onboarding.dl.provider_error` carrying only `error_type` when the adapter cannot be built, come directly from `DLWebhookView`. All RC events listed under "v3: RC observability" are emitted (verified).

**PLANNED, not implemented.** No code emits the following events. They were listed as existing in v1 to v6 of this document; do not alert on them or build dashboards on them.

| Event | Level | Extra fields |
|-------|-------|--------------|
| `onboarding.profile.created` | INFO | `user_id`, `request_id` |
| `onboarding.role.set` | INFO | `user_id`, `role`, `request_id` |
| `onboarding.profile.submitted` | INFO | `user_id`, `onboarding_status`, `request_id` |
| `onboarding.vehicle.registered` | INFO | `user_id`, `vehicle_type`, `request_id` |
| `onboarding.vehicle.duplicate_attempt` | WARNING | `user_id`, `request_id` |
| `onboarding.role.switch` | INFO | `user_id`, `from_role`, `to_role`, `request_id` |

**KNOWN GAP KG-05: no `profiles` logger in `LOGGING`.** The design said to register `profiles` with the `accounts_console` handler (phone redaction filter). `config/settings.py` registers only `accounts`, `core` and `django`; records from the `profiles` logger propagate to the root `console` handler (JSON formatter, request-id filter, no phone redaction). Redaction therefore relies on the call sites passing only non-PII, allow-listed fields. The funnel metrics below that count users reaching `COMPLETE` (and `vehicle_registration_rate`) must be derived from `UserProfile` / `Vehicle` rows, not from the planned events.

### Metrics (structured log fields for external aggregation)

- `dl_verification_provider_error_rate` — count of `onboarding.dl.provider_error` events / total DL submissions
- `onboarding_completion_rate_passenger` — users reaching `COMPLETE` from `NOT_STARTED` with `active_role=PASSENGER`
- `onboarding_completion_rate_driver` — users reaching `COMPLETE` from `NOT_STARTED` with `active_role=DRIVER`
- `dl_attempt_count_distribution` — histogram of `attempt_count` on `DriverVerification` rows
- `vehicle_registration_rate` — users reaching `COMPLETE` from `AWAITING_VEHICLE` (driver funnel completion)

### v3: RC observability

All RC log calls go through one helper, `_log_event(level, event, **fields)`, in `rc_verification.py`, which drops any field not in this allow-list: `user_id`, `vehicle_id`, `attempt_count`, `rc_status`, `outcome`, `cause`, `name_match`, `onboarding_status`, `reference_id`, `adapter`, `error_type`, `duplicate_count`, `staff_user_id`, `timed_out`. Because `JsonFormatter` writes every `extra` key verbatim, a free-form `extra=` is forbidden in RC code. Never logged: owner name, raw provider payload or the result object, provider/staff free-text reasons, exception messages from adapters (type name only, no `exc_info`), and the registration number alongside a user id.

| Event | Level | Fields |
|-------|-------|--------|
| `onboarding.rc.submitted` | INFO | `user_id`, `vehicle_id`, `attempt_count` |
| `onboarding.rc.verified` | INFO | `user_id`, `vehicle_id`, `name_match`, `reference_id` |
| `onboarding.rc.pending` | INFO | `user_id`, `vehicle_id`, `cause` (`provider_pending` / `timeout` / `name_review`), `name_match` |
| `onboarding.rc.rejected` | INFO | `user_id`, `vehicle_id`, `cause` (`provider` / `class_conflict` / `staff`) |
| `onboarding.rc.provider_error` | ERROR | `user_id`, `adapter`, `error_type` |
| `onboarding.rc.attempts_exhausted` | WARNING | `user_id`, `vehicle_id`, `attempt_count` |
| `onboarding.rc.ref_collision` | ERROR | `user_id`, `vehicle_id` |
| `onboarding.rc.webhook.received` | INFO | `reference_id` |
| `onboarding.rc.webhook.processed` | INFO | `reference_id`, `outcome`, `vehicle_id` |
| `onboarding.rc.webhook.duplicate` | WARNING | `reference_id` |
| `onboarding.rc.webhook.invalid_signature` | WARNING | (none; no body content) |
| `onboarding.rc.webhook.unknown_reference` | WARNING | `reference_id` |
| `onboarding.rc.review.approved` / `.rejected` / `.attempts_reset` | INFO | `vehicle_id`, `staff_user_id` |
| `onboarding.vehicle.duplicate_registration` | WARNING | `user_id`, `duplicate_count` (flag ON only) |

**Metrics (derived from logs/DB):** RC first-attempt auto-verify rate; share routed to review (`cause=name_review`); `pending_rc_verification` count and p50/p95 age (`rc_submitted_at`); provider error and timeout rate; attempts-exhausted count; webhook invalid-signature rate.
**Alerts (suggested):** any `provider_error` burst; any `ref_collision`; pending queue older than the SLA once OQ-R13 defines one; `invalid_signature` spike; any occurrence of `onboarding.rc.*` events while the flag is documented OFF (indicates misconfiguration).

---

## Performance

- `GET /api/onboarding/status/` and `GET /api/onboarding/driver/dl/status/`: single indexed row reads (`SELECT ... WHERE user_id = ?`). Expected p95 well within 100 ms at 50 rps (NFR-PERF-01).
- `POST /api/onboarding/profile/` and `POST /api/onboarding/role/`: single atomic DB write + a read to retrieve the profile. Expected p95 well within 200 ms (NFR-PERF-02).
- `POST /api/onboarding/driver/dl/` (sync provider): two short transactions plus one outbound provider call (v6). No row lock and no open transaction during the call. The request thread is blocked for the provider duration, which a real adapter must bound with its own timeout (there is no `DL_PROVIDER_TIMEOUT_SECONDS` setting); the mock does no I/O. Expected p95 <= 3 s (NFR-PERF-03). Async provider paths return in < 500 ms after dispatch.
- `POST /api/onboarding/driver/vehicle/`: single atomic DB write (create Vehicle + update UserProfile). No external calls. Expected p95 well within 200 ms (same category as profile/role writes).
- No caching layer is required at this stage. Profile and vehicle rows are tiny (< 1 KB), indexed by PK, and not shared across users.

### v3: RC performance

- Flag OFF: `POST /api/onboarding/driver/vehicle/` is the same single transaction as v2 (one lock-free code path, no extra query). `GET /api/onboarding/status/` makes no vehicle query when the flag is OFF.
- Flag ON: two short transactions plus one provider call. Bounded by `RC_PROVIDER_TIMEOUT_SECONDS` (5 s) in the worst case; NFR-PERF-04 targets 3 s p95 for synchronous responses. During the provider call no DB connection is held in a transaction and no row lock is held.
- Worker occupancy: a synchronous worker is blocked for the provider duration. At onboarding volumes this is acceptable; size gunicorn workers against peak concurrent vehicle submissions if a slow provider is adopted. Async/task-queue submission is a possible later change and is not needed with the mock.
- Admin duplicate count is one indexed subquery per page (`idx_vehicle_regno`).

---

## Migration / Rollout

### Migration dependency

`profiles/migrations/0001_initial.py` declares:
```python
dependencies = [
    ('accounts', '0002_alter_otpcode_phone_number'),
]
```

The new `0002_add_vehicle.py` migration depends on `0001_initial`:
```python
dependencies = [
    ('profiles', '0001_initial'),
]
```

### New migration: `profiles/migrations/0002_add_vehicle.py`

This migration:
1. Adds `AWAITING_VEHICLE` to `UserProfile.onboarding_status` choices (AlterField).
2. Creates the `profiles_vehicle` table with all columns, the composite index on `(user, is_active)`, and the ForeignKey to `accounts.User`.

### Migration checklist (v2 additions)

1. Update `profiles/models.py`: add `AWAITING_VEHICLE` to `ONBOARDING_STATUS_CHOICES`, add `Vehicle` model.
2. `python manage.py makemigrations profiles` — produces `0002_add_vehicle.py`.
3. `python manage.py migrate` in dev, then in staging before deploying app code.
4. No data backfill required: existing users in `COMPLETE` state are unaffected (only new Driver sign-ups go through the vehicle step). Existing users who have `onboarding_status=COMPLETE` with `active_role=driver` but no vehicle record are grandfathered in (v4: recorded explicitly by the `vehicle_step_exempt` marker set in migration `0004`; see v3 migration and rollout).

### Rollout strategy

The v2 changes are additive:
- New model `Vehicle` (no existing table modified).
- New choices value `AWAITING_VEHICLE` on `UserProfile.onboarding_status` (backwards-compatible: existing rows never have this value).
- New endpoint `POST /api/onboarding/driver/vehicle/` (new URL, no existing URL changed).
- Modified DL verification flow: sync verified now transitions to `AWAITING_VEHICLE` instead of `COMPLETE`.

**Breaking change for in-flight Drivers:** Any Driver who is currently in `AWAITING_DL` or `PENDING_VERIFICATION` state at deploy time will, upon DL verification, land in `AWAITING_VEHICLE` instead of `COMPLETE`. The Expo client must handle the `vehicle_registration` next step. Coordinate deployment with frontend release that includes the vehicle registration screen.

### Rollback (v2)

If the vehicle registration feature needs to be rolled back independently of the rest of onboarding:
1. Revert the DL verification service to transition to `COMPLETE` on verified (instead of `AWAITING_VEHICLE`).
2. Remove the vehicle endpoint from `profiles/urls.py`.
3. Run `python manage.py migrate profiles 0001_initial` to drop the `profiles_vehicle` table and revert the choices field.
4. Any Drivers stuck in `AWAITING_VEHICLE` state need a data fix: `UPDATE profiles_userprofile SET onboarding_status = 'complete' WHERE onboarding_status = 'awaiting_vehicle'`.

### v3 migration and rollout

**Migration order.**
1. Commit `0002_add_vehicle.py` unchanged (it is staged but uncommitted), then generate `0003_vehicle_rc_verification` with `makemigrations profiles`. Do not edit or regenerate 0002 (ADR Decision 22: any developer database that already applied 0002 would otherwise be out of sync).
2. Apply 0003 (and, from v4, 0004, which depends on 0003, in the same `migrate` run) **before** deploying the v3/v4 code. This is safe with v2 code still serving traffic because every new column is nullable or has a DB-level default (`db_default=0`), and the added choices are Python-side only. Index creation on `profiles_vehicle` takes a brief write lock; the table is small, so `AddIndexConcurrently` is not needed.
   - 0004 adds `vehicle_step_exempt` (`default=False`, `db_default=False`, so older processes keep inserting profiles safely) and then runs one idempotent `RunPython` `UPDATE` that sets the marker for profiles that are `complete`, have a `DriverVerification` row with `dl_verification_status = 'verified'` (v6) and have no `is_active` `Vehicle` row. The profiles table is small; no lock concerns beyond a single `UPDATE`. Run 0004 only after 0003 is applied and before the flag is enabled anywhere, so the marked set reflects the pre-RC state.
3. Deploy backend with `RC_VERIFICATION_ENABLED=False` everywhere. Behaviour of the vehicle endpoint is identical to v2.
4. Deploy the frontend that handles `vehicle_registration` and `awaiting_rc_verification` (safe default for unknown `next_step`).
5. Staging exercise of the flag against the mock requires `DEBUG=True` (the production guard refuses the mock otherwise) or a real adapter; see open decision U4.
6. Production flag-on prerequisites: a real provider adapter, an ops owner for the review queue (OQ-R13), the legal answer on owner-name retention (OQ-R7), the security review (TASK-125), `ONBOARDING_GATE_ENABLED=True`, and a non-placeholder `RC_WEBHOOK_SECRET`.

**Existing drivers.** `COMPLETE` drivers keep their state; their vehicles keep `rc_verification_status = NULL`; `switch_role` treats `NULL` as acceptable (AC-47). Migration 0003 has no backfill and no `RunPython`; migration 0004 (v4) has one `RunPython` data step that marks drivers who are `complete`, have a `DriverVerification` row with a verified DL (v6) and no active vehicle row with `vehicle_step_exempt = True`, and `switch_role` treats exactly those as the grandfathered no-vehicle case (FR-43, AC-48, AC-54). Accepted edge case: a profile whose only vehicle is inactive is marked (ADR Decision 27). Since v6 a `complete` profile with a pending, rejected or absent DL record is no longer marked (SEC-002 F-10).

**In-flight drivers (RISK-005, extended).** (a) Flag turned ON while a driver is in `awaiting_dl` / `pending_verification` / `awaiting_vehicle`: they follow the RC flow at the vehicle step. (b) A client that does not know `awaiting_rc_verification` would strand a driver who lands there: the flag must not be turned ON until the new client is the minimum supported version. (c) Drivers already `complete` are untouched.

**Rollback / flag OFF after ON.** Setting `RC_VERIFICATION_ENABLED=False` immediately restores the v2 vehicle behaviour for new submissions. Drivers left in RC states need an operational data patch, because the flag-off path rejects any user that still has an active vehicle row with `409 vehicle_already_registered`, and `pending_rc_verification` is not a state the flag-off path knows:

```sql
-- run after the flag is OFF
UPDATE profiles_vehicle SET is_active = FALSE
 WHERE rc_verification_status IN ('pending', 'rejected')
   AND user_id IN (SELECT user_id FROM profiles_userprofile
                   WHERE onboarding_status IN ('pending_rc_verification', 'awaiting_vehicle'));
UPDATE profiles_userprofile SET onboarding_status = 'awaiting_vehicle'
 WHERE onboarding_status = 'pending_rc_verification';
-- alternative if product accepts the self-declared vehicle: set onboarding_status = 'complete' instead and keep the rows active
```

Staff can alternatively use the admin approve action per vehicle (works regardless of the flag). Schema rollback after the patch: `migrate profiles 0002_add_vehicle` (drops the RC columns, indexes, constraint and permission; data loss is limited to RC fields). Code rollback must precede the schema rollback. Migration 0004 is reversible: its reverse step first clears `vehicle_step_exempt` on all rows, then the column is dropped (`migrate profiles 0003_vehicle_rc_verification`). Rolling back below 0003 (`migrate profiles 0002_add_vehicle`) therefore passes through 0004's reverse first. Rolling back 0004 discards the grandfather marking; re-applying it recomputes the marking from current data.

### v5 rollout (role switch fix)

No migration and no schema change. Behaviour changes: (1) `PATCH /api/profile/role/` to `driver` without a verified DL returns `200` / `awaiting_dl` / `next_step = dl_submission` instead of `400 dl_required`; (2) switch to passenger is accepted from every non-initial status in both flag modes and always yields `complete`; (3) flag-OFF switch to driver with a verified DL and no active vehicle (and no `vehicle_step_exempt`) now yields `awaiting_vehicle` instead of `complete` (a deliberate change to flag-OFF role-switch edge cases; initial onboarding and the vehicle endpoint with the flag OFF are unchanged); (4) a verified DL webhook advances only `pending_verification` profiles. The Expo client must route on `next_step` from the role-switch response and may drop its `dl_required` handling. No data patch is needed. Rollback is a code revert: the states created by the new behaviour (`active_role = driver` with `awaiting_dl`) are ordinary driver-path states that the previous code also handles.

### v6 rollout (DL security hardening)

No new migration and no schema change. Migration `0004` was edited in place because it was unmerged.

- **Environment.** New optional settings: `DL_ADAPTER_CLASS`, `DL_ADAPTER_MOCK_RESULT`, `DL_MAX_ATTEMPTS`, `DL_WEBHOOK_SECRET`. Add placeholders to `backend/.env.example` (its existence is still unverified: reading it was denied in this session as well). Local and CI environments run with `DEBUG` true and need no change.
- **Non-`DEBUG` deployments are blocked.** With `DEBUG` off and the default `DL_ADAPTER_CLASS` the process raises `ImproperlyConfigured` at import. There is no real DL adapter yet, so a staging or production deployment with `DEBUG` off cannot start until one is built and `DL_ADAPTER_CLASS` points at it (Open Decision U9). This is intended: the alternative is a production system that marks every well-formed DL as verified.
- **`DL_WEBHOOK_SECRET` must be set** (and shared with the provider) for the DL webhook to accept anything. The old static `X-Mock-Signature: mock-secret` header is no longer accepted; any integration or test script using it must switch to `X-DL-Signature`.
- **Clients.** The DL webhook now answers `200` (not `409`) to a duplicate delivery and `404 dl_reference_not_found` to an unknown reference; the submit endpoint can now answer `422 dl_verification_provider_error`. The Expo client treats the `422` as retryable.
- **Databases that already applied the old `0004`.** Developer or staging databases that ran the previous version of `0004` keep the broader marking (profiles with any `DriverVerification` row). Either run `migrate profiles 0003_vehicle_rc_verification` then `migrate profiles` (the reverse step clears the marker and the forward step recomputes it with the new rule), or run `UPDATE profiles_userprofile SET vehicle_step_exempt = FALSE WHERE vehicle_step_exempt AND user_id NOT IN (SELECT user_id FROM profiles_driververification WHERE dl_verification_status = 'verified');`. Fresh databases need nothing.
- **Existing `rc_owner_name` values** on vehicles that were resolved before v6 are not purged by the code change; clear them with `UPDATE profiles_vehicle SET rc_owner_name = NULL WHERE rc_verification_status IN ('verified', 'rejected');` if the flag was ever on in that environment.
- **Rollback** is a code revert plus removal of the `DL_*` settings; no data is shaped by this change.

---

## Alternatives Considered

### Alternative: separate `verification` app for `DriverVerification`

A `verification` app would have its own migration history and service layer, giving a cleaner conceptual boundary between "profile data" and "credential verification". Rejected for v1 because DL verification is tightly coupled to the onboarding state machine in `profiles`, and the added app registration + inter-app FK dependency graph complexity is not justified until the verification domain grows beyond DL.

### Alternative: proactive `UserProfile` creation via Django signal

A `post_save` signal on `accounts.User` would create the profile immediately on user creation, eliminating the `get_or_create` in every onboarding endpoint. Rejected because it couples `accounts` to `profiles` at the signal connection level and makes unit tests of the `accounts` app aware of `profiles`. Lazy creation via `get_or_create` with a DB unique constraint achieves the same safety guarantee without coupling.

### Alternative: Django middleware for the onboarding gate

Process-request middleware could check `request.user.profile.onboarding_status` and return a `403` before the view fires. Rejected because middleware runs before DRF's JWT authentication resolves `request.user`, requiring a re-authentication step inside the middleware. A DRF permission class integrates cleanly with the existing auth chain and benefits from DRF's established error-handling pipeline.

### Alternative: hash-only DL storage

Storing only a HMAC-SHA256 hash + last-4 chars would eliminate the need for key management. Rejected because India's legal landscape may require the platform to produce the full DL on government demand, and because re-verification scenarios may require the full plaintext to re-submit to a provider. Symmetric encryption preserves this optionality.

### Alternative: global `IsOnboardingComplete` via a custom DRF authentication class

Using a custom authentication class that injects onboarding state into the request would be less visible and harder to test than a named permission class. Rejected: permission classes are the established DRF extension point for access control.

### Alternative: OneToOneField for Vehicle model

A OneToOneField would enforce one vehicle per user at the database level. Rejected because the product roadmap includes multi-vehicle support. Using a ForeignKey now avoids a future schema migration from OneToOne to ForeignKey (which requires dropping and recreating the constraint). The v1 "max 1 active vehicle" rule is enforced at the application layer via a check in `register_vehicle()`. See ADR Decision 8.

### Alternative: separate `vehicles` app for Vehicle model

A standalone `vehicles` app would separate vehicle management from onboarding. Rejected for v1 because vehicle registration is currently a step in the onboarding flow, not an independent domain. The `Vehicle` model has no consumers outside onboarding in v1. Extraction to a standalone app remains possible later without a database schema change.

### v3 alternatives considered

- **Two views / two service entry points selected by URL or flag in the router.** Rejected: the endpoint contract is one URL; a single early branch inside `register_vehicle()` is smaller and easier to prove correct.
- **Return a richer result object from the service instead of `(profile, vehicle)`.** Rejected: it would change the flag-off call signature and require the view to branch. The RC outcome is already on the `Vehicle` row.
- **RC rules inside the adapter.** Rejected: name matching and class mapping would differ by provider; FR constraints require identical behaviour across providers.
- **Hold the DB transaction open across the provider call (as the DL module does).** Rejected: a 5 s network call would hold row locks and a connection; the three-phase design costs one extra lock/validate cycle.
- **Redis lock to prevent duplicate provider calls on double-submit.** Not adopted: adds a dependency to the request path; the profile row lock plus phase-3 re-validation is sufficient for correctness. Revisit with a paid provider.
- **Squash 0003 into the uncommitted 0002.** Rejected (ADR Decision 22): gains one file, risks desynchronised developer databases.
- **Derive grandfathered status from a stored marker (new column or `rc_verification_status = 'exempt'`).** Originally rejected in v3 on the claim that "no vehicle row while `COMPLETE`" identifies the case without schema change. **Adopted in v4 (ADR Decision 27)** as the `UserProfile.vehicle_step_exempt` column: the inferred rule is bypassable through FR-52 (switch to passenger sets `complete`, then back to driver). The `rc_verification_status = 'exempt'` variant remains rejected because it would put the marker on a `Vehicle` row that, by definition, does not exist for these drivers.
- **Return rejection as `200` with `rc_verification_status = "rejected"`.** Rejected (OQ-R12a): product chose an error code; the envelope is extended instead.
- **Django system check for the mock-in-production rule.** Rejected as the only guard: checks do not run under WSGI startup. Used only as a pattern reference; the guard is a settings-time raise plus a factory check.
- **Separate audit table for review actions.** Rejected: Django admin `LogEntry` already records the acting staff user and message.

### v5 alternatives considered (role switch fix, ADR Decision 28)

- **Let a `COMPLETE` passenger call `POST /api/onboarding/driver/dl/` directly.** Rejected: it leaves the user in the passenger role while a verification is in flight, so role, `onboarding_status` and DL state disagree; the DL endpoint's `IsDriverRole` and state guards would have to be loosened and the webhook would have to special-case passengers.
- **Keep `400 dl_required` and add a separate "start driver setup" endpoint.** Rejected: a second endpoint and an extra client call to express what the role switch already says.
- **Keep two `switch_role` implementations (flag ON / flag OFF).** Rejected: the divergence (passenger exit from `awaiting_vehicle` only with the flag ON, a row lock in only one variant) was itself part of the gap.
- **Reset `attempt_count` when the role changes.** Rejected: role toggling would bypass the DL attempt limit.
- **Always advance to `awaiting_vehicle` on a verified DL webhook.** Rejected: it would push a `COMPLETE` passenger with a pending DL behind the onboarding gate.

### v6 alternatives considered (DL security hardening, ADR Decision 29)

- **Keep the module-level `_adapter` and add a `set_adapter()` test or deployment hook.** Rejected: it is the shape that caused F-03 (webhook validation bound to the original instance), it cannot be audited from settings, and per-process mutable state is wrong under multiple workers. A per-call factory is already the RC pattern and is as cheap.
- **A DEBUG-independent override such as `DL_ALLOW_MOCK_ADAPTER=1` for staging.** Rejected for now: a knob that re-enables "verifies everything" is one environment variable away from production. A staging environment that needs `DEBUG=False` should use a real or purpose-built non-mock adapter. Same stance as Open Decision U4 for RC.
- **Make the DL guard conditional on a flag, as RC is.** Rejected: DL verification has no flag; it is always in the driver path, so the guard must always run.
- **A Django system check for the production guard.** Rejected as the only guard for the reason already recorded for RC: checks do not run under WSGI startup. A settings-time raise plus the factory check covers every entry point.
- **Keep the static header secret but compare in constant time.** Rejected: a static header is replayable and does not bind the body. HMAC over the raw body is what a real provider uses, so the mock exercises the same mechanism.
- **Return `409 already_processed` for duplicate DL webhooks.** Not kept: providers retry on non-2xx, and `409` tells a caller that a reference exists in a terminal state. `200` with no state change is idempotent and quiet. Needs product confirmation because requirements name `409` (U8).
- **Hold the transaction across the provider call (previous behaviour).** Rejected for the reasons already given for RC (Decision 14): a network call must not hold row locks and a connection.
- **Hash-only or deleted `rc_owner_name`.** Not needed: clearing it on every terminal transition leaves the name only while a review is pending, which is when staff need it.
- **A new migration to correct `0004`.** Rejected: `0004` was unmerged, so editing it is simpler than a corrective migration. The cost is that databases that already applied the old version need the one-off fix in "v6 rollout".

---

## Known Gaps (v7)

Deviations between the code (`803e319`, read from disk) and the intended contract. The intended contract in this document, the requirements and `docs/api/openapi-profiles.yaml` is **not** rewritten to match them. Status as of 2026-10-17.

| ID | Intended contract | Actual behaviour in code (traced) | Open item |
|----|-------------------|-----------------------------------|-----------|
| KG-01 | `POST /api/onboarding/driver/dl/` with a malformed DL returns `400 invalid_dl_format` (requirements FR-07, AC-11; OpenAPI; ADR Decision 1). | `DLSubmissionSerializer.validate_dl_number` raises a DRF `serializers.ValidationError`, and `DLSubmitView.post` calls `serializer.is_valid(raise_exception=True)` outside its `try`. A DRF `ValidationError` is not an `ApiError`, so `envelope_exception_handler` takes the generic path: HTTP `400`, `error.code = "invalid_request"`, `error.detail` and `message` = the first message ("Invalid DL format. Expected: XX00 0000 0000000 (13 digits after state code)"), `error.fields = {"dl_number": [<same message>]}`, `data = null`. `profiles.exceptions.InvalidDLFormat` (`invalid_dl_format`) is defined and referenced nowhere. Blank, missing or over-20-character input takes the same path with DRF's own messages. The vehicle endpoint, by contrast, maps its serializer errors to domain codes (`_raise_vehicle_validation_error`). | U10 |
| KG-02 | A DL rejection is not reported as a 2xx acceptance (contract: `200` verified, `202` pending; OpenAPI `DLSubmissionResponse.dl_verification_status` is `verified` or `pending`). | A synchronous `rejected` provider result is persisted (attempt consumed, sanitised `dl_rejection_reason` stored, onboarding status unchanged) and `DLSubmitView` answers `202` with `dl_verification_status = "rejected"`, `onboarding_status` `awaiting_dl` or `pending_verification`, the matching `next_step`, and the message "DL verification submitted successfully.". `DLSubmissionResponseSerializer` has no `rejection_reason` field, so the reason is not in this response; the client must read `GET /api/onboarding/driver/dl/status/`. Only the mock mode `sync_rejected` reaches this today. Also listed in ADR Decision 26. | U10 |
| KG-03 | A passenger calling a driver-only DL endpoint gets `403 not_a_driver` (requirements AC-20; OpenAPI). | `DLSubmitView` and `DLStatusView` use `IsDriverRole`, which returns `False`; DRF answers the generic `403 permission_denied`. `not_a_driver` is produced only by the service race path (`ValueError("Not a driver")` after the permission check) and by `DLStatusView` for a driver who has no `DriverVerification` row yet, which is misleading (SEC-002 F-18). The vehicle endpoints already use `RequireDriverRole` and conform. | U10 |
| KG-04 | `DL_ENCRYPTION_KEY` is validated at startup (this document up to v6; SEC-002 F-15 recommends it). | `profiles/utils/crypto.py::_get_fernet()` reads the key with python-decouple on each encrypt/decrypt; nothing reads it at import, in `AppConfig.ready()` or in `manage.py check`. A missing, empty or malformed key raises `ImproperlyConfigured` on the first DL submission (after the phase-1 guard, before the provider call), which is returned as `500 server_error`; nothing is written. There is also no key rotation (a single `Fernet`; ADR Decision 3 mentions a `dl_key_version` column that was never added). | U11 |
| KG-05 | Six `onboarding.*` events are emitted, and a `profiles` logger is registered with the redacting `accounts_console` handler. | The six events are not emitted (see Observability, PLANNED). `LOGGING` has no `profiles` logger; records reach the root `console` handler, which has no phone-redaction filter. | U12 |
| KG-06 | FR-07: one optional space or hyphen between the RTO code and the year. | `normalize_dl_number` removes every space and hyphen anywhere before `DL_PATTERN` is applied, so `MH01 2011 0012345` is accepted. The stored value is the same 15-character normalised string, so this is harmless to stored data but more permissive than FR-07. | U10 |

Resolved and therefore not listed above: the flag-off vehicle-endpoint discrepancies (fixed in code; the upper-case `vehicle_type` is the contract, FR-53) and the duplicate DL webhook status (`200` accepted, U8).

---

## Risks

| ID | Description | Severity | Mitigation |
|----|-------------|----------|-----------|
| RISK-001 | `DL_ENCRYPTION_KEY` loss makes all stored DL numbers permanently irrecoverable. | high | Key must be backed up to a secrets manager (AWS Secrets Manager or equivalent) before any DL is stored in production. Document in runbook. |
| RISK-002 | (v7 corrected) `core.permissions.ConditionalOnboardingGate` in `DEFAULT_PERMISSION_CLASSES` gates every authenticated endpoint once `ONBOARDING_GATE_ENABLED` is turned on (the default is False, so today nothing is gated). Any future endpoint must either require a completed onboarding or explicitly override `permission_classes`. | medium | Document the convention: all non-onboarding views that should be accessible pre-onboarding must declare `permission_classes = [IsAuthenticated]`. Add this to the project CLAUDE.md. |
| RISK-003 | Provider webhook delivery delay (hours to days) leaves Drivers in `PENDING_VERIFICATION` with no automatic escalation path. OQ-09 (timeout policy) is unresolved. | medium | Accept for v1: client polls on app open. A periodic task to auto-escalate stale `PENDING` records can be added in a follow-up. |
| RISK-004 | `cryptography` Fernet adds ~10 ms per DL encrypt/decrypt operation. Under 50 rps DL submission load this is negligible. | low | Acceptable. Monitor if DL submission rate grows significantly. |
| RISK-005 | In-flight Drivers (in `AWAITING_DL` or `PENDING_VERIFICATION` at deploy time) will land in `AWAITING_VEHICLE` instead of `COMPLETE` after DL verification. If the Expo client is not updated to handle `vehicle_registration` next step, these Drivers will be stuck. | medium | Coordinate backend deployment with frontend release. The frontend must ship the vehicle registration screen before or simultaneously with the backend change. |
| RISK-006 | (Updated v3) No uniqueness constraint on `registration_number` allows the same vehicle to be registered by multiple Drivers. | low | Accepted by product (OQ-R4). Non-unique index, WARNING log (flag ON) and admin duplicate indicator added. Upgrade path: partial unique constraint on `(registration_number) WHERE is_active AND rc_verification_status = 'verified'`. |
| RISK-007 | Mock RC adapter enabled in production with the flag ON would verify any vehicle. | high | Three layers (see v3 Security): settings-time `ImproperlyConfigured` when `RC_VERIFICATION_ENABLED and not DEBUG` with a mock adapter path, factory refusal of `MockRCVerificationAdapter` subclasses via `RC_MOCK_ADAPTER_FORBIDDEN`, fail-closed mock webhook. Residual: production run with `DEBUG=True`. |
| RISK-008 | In-flight drivers stranded by an old client or by flag rollback (extends RISK-005): unknown `next_step` values, drivers in `pending_rc_verification`, rejected rows blocking the flag-off path. | high | Flag ON only after the new client is the minimum version; documented rollback SQL and admin approve; `db_default` keeps migrate-then-deploy safe. |
| RISK-009 | Flag-off regression through RC code (import error, shared view/serializer edits). | high | Flag-off path is the old function body moved verbatim behind one `if`; RC module imported lazily; only additive nullable response fields; AC-31 regression test with the adapter patched to raise must be in CI before release. A syntax error in the shared `views.py`/`serializers.py` would still break everything, so CI must run the flag-off integration test. |
| RISK-010 | Review queue pollution and no SLA: timeouts (no reference), non-Latin profile names and family/fleet vehicles all route to `pending`; no auto-escalation (OQ-R13). | medium | Admin ordering by age and filters; metrics on review share and pending age; ops owner required before production enablement; possible later retry job. |
| RISK-011 | Owner-name retention and DPDP exposure (OQ-R7). | low (was medium) | v6: the name is cleared on every terminal transition and shown in admin only to `profiles.review_rc` holders; it survives only while a vehicle is pending review (and in backups). Legal answer on the pending-period retention is still needed before production flag-on. |
| RISK-012 | (Resolved in v7) Pre-existing flag-off contract discrepancies (wrong error codes, upper-case `vehicle_type`, gate response) that made AC-28, AC-29, AC-41 and "COMPLETE driver posts vehicle" untestable as written. | resolved | Fixed in code (`VehicleRegisterView` uses `RequireDriverRole`, domain error codes, `409` for a `COMPLETE` driver; the gate raises `onboarding_incomplete` with data); the upper-case `vehicle_type` became the contract (FR-53). History: ADR Decision 26. The equivalent DL-endpoint defect remains (KG-03). |
| RISK-013 | (Resolved in v6, ADR Decision 29) DL-module gaps from v3: global `_adapter` imported by views, provider call inside a transaction, missing `DL_*` settings, hardcoded attempt limit `3`, weak mock webhook check. | resolved | Fixed in commit `803e319`. `backend/.env.example` is still unverified (access denied). Residual: no real DL adapter exists (see RISK-016). |
| RISK-014 | (Resolved in v6) Admin staff could edit `UserProfile.onboarding_status` directly, bypassing the state machine and the review audit. | resolved | `onboarding_status` / `active_role` are read-only for non-superusers; DL state fields likewise (SEC-002 F-11). Superusers can still edit by design. |
| RISK-015 | (v5) A passenger who starts driver setup is gated out of normal features (`403 onboarding_incomplete`) while `ONBOARDING_GATE_ENABLED` is on, until they finish or switch back; an abandoned attempt leaves them stuck until they return to the role switch. | medium | Accepted (ADR Decision 28). Client confirms before switching and offers a visible "switch back" action; switching to passenger is always available from every non-initial status. |
| RISK-016 | (v6) Non-`DEBUG` deployments cannot start until a real DL adapter exists, and a deployment without `DL_WEBHOOK_SECRET` rejects every DL webhook. A team that sets `DEBUG=True` to get a staging environment running defeats the guard and the CORS/debug-page protections with it. | high | Intended fail-safe (ADR Decision 29). Build and configure a real DL adapter before any non-dev deployment; document `DL_WEBHOOK_SECRET` in the runbook and `.env.example`; never run staging with `DEBUG=True` against real users. |
| RISK-017 | (v6, open SEC-002 findings) F-05: no throttling on onboarding endpoints and webhooks; F-06: flag-transition semantics (flag-off `switch_role` ignores the RC state of an existing vehicle, enabling RC does not re-verify legacy vehicles); F-08: verification is not bound to the person (DL not matched to the account holder, DL reuse across accounts undetected). | medium | Not addressed by v6. F-05 and F-06 block enabling RC with a paid provider; F-08 matters once real providers are used. Tracked as Open Decisions U5-U7. |
| RISK-018 | (v6) A DL submission that times out is stored `pending` with no `dl_verification_ref`, and the DL path has no handler for a provider that reuses a reference (unique-constraint `IntegrityError` becomes a `500`, unlike RC). | low | Not reachable with the mock. Resolve before a real DL provider is enabled; staff resolve timed-out DLs (there is no DL review tooling in admin beyond the read-only record). |
| RISK-019 | (v7, KG-04) `DL_ENCRYPTION_KEY` is validated lazily. A deployment with a missing or malformed key starts normally, passes `manage.py check`, and returns `500` on every DL submission. | medium | Set and back up the key (RISK-001). Add startup validation of the key (U11, SEC-002 F-15) and a deployment smoke test that exercises `encrypt_dl_number`. |

---

## Open Decisions

- **OQ-03**: Should the DL number validator normalise lowercase input to uppercase before validation, or reject it outright? (Resolved in ADR Decision 1: normalise to uppercase.)
- **OQ-05**: Should `UserProfile` be created proactively via Django signal or lazily on first access? (Resolved in ADR Decision 2: lazy creation.)
- **OQ-08**: How should Drivers in `pending_verification` state be notified when their DL result arrives? Push notifications are listed as a non-goal; will the app poll on launch? Deferred.
- **OQ-09**: Auto-rejection of stale `PENDING_VERIFICATION` drivers after N hours — requires a Celery beat task and a product policy decision. Deferred.
- **U1 (product/requirements):** Closed in v4. FR-43 / AC-48 / AC-54 (requirements v6) now say a verified-DL user with no vehicle row becomes `awaiting_vehicle` on switch to driver unless the explicit `vehicle_step_exempt` marker is set, in which case they stay `COMPLETE`; this design matches (ADR Decision 27).
- **U2 (product):** Closed (v7). The flag-off vehicle error codes now conform in code (`RequireDriverRole`, `invalid_registration_format`, `invalid_vehicle_type`, `409 vehicle_already_registered`; requirements FR-51), and the upper-case `vehicle_type` was adopted as the contract (FR-53). The DL-endpoint equivalents remain open as KG-03 (U10).
- **U3 (product):** Closed in v5. A user toggled to `awaiting_vehicle` (for example a rejected vehicle with exhausted attempts) can now switch back to passenger in both flag modes (result `complete`); `switch_role` accepts every non-initial status (ADR Decision 28).
- **U4 (security/product):** exercising the mock in a `DEBUG=False` staging environment is refused by the production guard for RC (when the flag is ON) and, since v6, for DL unconditionally. If staging must run `DEBUG=False`, an explicit, security-approved override (for example `RC_ALLOW_MOCK_ADAPTER` / `DL_ALLOW_MOCK_ADAPTER`) would be needed; not designed (ADR Decision 29 records the rejected default).
- **U5 (security/engineering):** SEC-002 F-05, DRF throttling for onboarding endpoints and webhooks, and a per-user in-flight guard against concurrent provider calls. Still open.
- **U6 (product/engineering):** SEC-002 F-06, flag-transition semantics: backfill or review policy for legacy (`NULL`) vehicles when RC is enabled, and whether the flag-off role switch should consult the RC state of an existing vehicle. Still open.
- **U7 (product/security):** SEC-002 F-08, binding DL and RC verification to the person (name/DOB match from the DL provider, DL uniqueness across accounts, duplicate plates). Still open; depends on provider facts.
- **U8 (product/requirements):** duplicate DL webhook delivery returns `200` (idempotent, ADR Decision 29). **Accepted resolution (v7): `200`.** Requirements NFR-REL-02 and the duplicate-delivery paragraph (which name `409 already_processed` for both webhooks) are being aligned to the code for the DL webhook; the RC webhook keeps `409`. Kept open only as a tracking item until the requirements edit lands; no code change is needed.
- **U10 (product/engineering):** DL contract conformance. KG-01 (`400 invalid_request` instead of `invalid_dl_format`), KG-02 (`202` for a synchronous rejection, no `rejection_reason` in the body), KG-03 (`403 permission_denied` instead of `not_a_driver` on the DL endpoints; fix is to use `RequireDriverRole`) and KG-06 (separators accepted anywhere). For each, decide whether to change the code or amend the contract. Open.
- **U11 (engineering):** KG-04 / SEC-002 F-15. Validate `DL_ENCRYPTION_KEY` at startup (settings import or `AppConfig.ready()`), decide on rotation (`MultiFernet`, key version). Open.
- **U12 (engineering):** KG-05. Register the `profiles` logger (with the redacting handler) and either emit the six PLANNED events or remove them from this document. Open.
- **U9 (engineering/product):** a real DL adapter (DigiLocker, `profiles/adapters/digilocker.py`) does not exist; non-`DEBUG` deployments are blocked until it does. Also decide where the provider timeout setting lives (`DL_PROVIDER_TIMEOUT_SECONDS` was documented earlier but never implemented).
- **OQ-R7 (legal):** retention of `rc_owner_name`, narrowed in v6: it is cleared on every terminal transition, so the question is how long a name may be held while a vehicle is pending review and in backups. **OQ-R13 (operations):** review queue owner and SLA.
- **Provider facts:** all provider field/class/latency assumptions remain unverified until a provider is selected.

---

## Assumptions

- The `cryptography` package is available for installation (no OS-level build dependency issues in the deployment environment).
- The DL verification provider (DigiLocker) will communicate a definitive result either synchronously or via a timeout-recovery path. The business flow has no path for a provider that never responds.
- `DriverVerification.dl_verification_ref` is unique per provider call; the partial unique index on this column is sufficient for idempotency.
- Fernet encryption (AES-128-CBC with HMAC-SHA256) meets the data-at-rest protection requirement. If a future compliance audit requires AES-256, migrating the encryption library is an internal concern with no API contract impact.
- Age is self-reported; the product team accepts the risk that users may enter inaccurate values.
- `active_role = null` in `UserSerializer` output is an acceptable response for brand-new users (before any onboarding step). Expo clients must handle `null` for `onboarding_status` and `active_role`.
- The Indian vehicle registration number format `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$` covers the standard format for most Indian vehicles. Older or special-format registrations (e.g., diplomatic, military) are not validated in v1.
- (Revised in v3) At launch RC verification is OFF and the platform relies on format validation and self-declaration (v2 behaviour). RC verification is built and exercised against the mock only; no real provider adapter exists. Enabling it in production is a configuration change once a provider adapter exists.
- Existing Drivers who completed onboarding before the vehicle registration feature is deployed are grandfathered in (their `onboarding_status=COMPLETE` is not reverted). Only new Driver sign-ups go through the vehicle registration step.
- The `vehicle_type` choices use uppercase values in the database (`CAR`, `SUV`, etc.) but the API contract accepts lowercase values (`car`, `suv`, etc.). The serializer/service normalises to uppercase for storage. Responses return the upper-case form (requirements FR-53).
