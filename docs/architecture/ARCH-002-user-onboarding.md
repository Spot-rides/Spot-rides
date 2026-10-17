# Architecture: User Onboarding Flow

**ID:** ARCH-002
**Type:** architecture
**Feature:** FEAT-002
**Version:** 2
**Status:** ready
**Date:** 2026-10-10

---

## Context

FEAT-001 established a passwordless phone/OTP authentication layer that produces a `User` row keyed on E.164 phone number and issues a JWT pair. After successful OTP verification a user has only a phone number on record: no role, no name, no demographic data, and no mechanism to vet driving licences. The main Spot Rides experience cannot function without knowing whether the user intends to be a Passenger or a Driver ("Rider" in UI copy), and Driver accounts require a verified Indian driving licence before they can offer rides.

FEAT-002 adds the complete onboarding flow: role selection, personal profile collection, DL verification for Drivers, vehicle registration for Drivers, server-side progress persistence (resumable across devices), and a server-enforced gate that blocks any non-onboarding API call until onboarding is complete.

**v2 changes (2026-10-10):** Requirements v3 added a vehicle registration step to the Driver onboarding flow. Drivers must register a vehicle (registration number + type) after DL verification and before onboarding is complete. This introduces a new `AWAITING_VEHICLE` onboarding state, a new `Vehicle` model, a new API endpoint, and corresponding service/serializer/validator additions.

ADR decisions made during design are recorded in `docs/decisions/2026-09-23-arch-feat-002-user-onboarding.md`.

---

## Current State

- `backend/` contains two apps: `accounts` (custom `AUTH_USER_MODEL`, OTP/phone auth, JWT) and `core` (envelope, exceptions, renderers — no models).
- `accounts.User` has fields: `phone_number`, `is_active`, `is_staff`, `date_joined`. No role or profile data.
- `config/settings.py` `DEFAULT_PERMISSION_CLASSES` is `[IsAuthenticated]`.
- `config/urls.py` wires `api/auth/` to `accounts.urls` and `api/health/`.
- The `profiles` app has been partially implemented: `UserProfile`, `DriverVerification` models, onboarding service, DL verification service, validators, adapters, and views for the first 7 endpoints exist.
- The `profiles` app does **not** yet contain the `Vehicle` model, vehicle registration endpoint, or `AWAITING_VEHICLE` onboarding status.
- `accounts/serializers.py` `UserSerializer` exposes `id`, `phone_number`, `date_joined` only.
- `core.exceptions.ApiError` is the base for all domain errors; `core.exceptions.envelope_exception_handler` is the DRF exception handler.
- Redis is available (used by `accounts` for rate-limiting).
- `python-decouple` is used throughout for env var loading.
- `cryptography` is in `requirements.txt`.

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
4. **Onboarding gate** — DRF permission class `IsOnboardingComplete`; onboarding views opt out by declaring `permission_classes = [IsAuthenticated]`.
5. **`DriverVerification` placement** — inside `profiles` app.
6. **DL adapter interface** — abstract class `DLVerificationAdapter` with concrete mock adapter for dev/test and `DigiLockerDLVerificationAdapter` for production.
7. **Vehicle model uses ForeignKey** (not OneToOneField) — allows future multi-vehicle support while v1 enforces max 1 active vehicle at the application layer.
8. **Vehicle registration numbers stored plaintext** — they are publicly visible on vehicles; no encryption needed.
9. **Vehicle registration number normalisation** — strip spaces/hyphens, uppercase before validation (same normalisation philosophy as DL numbers, see ADR Decision 1).

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
        MockAdapter[adapters/mock.py]
        DigiLockerAdapter[adapters/digilocker.py]
        IsOnboardingComplete[permissions.IsOnboardingComplete]
        IsDriverRole[permissions.IsDriverRole]
        IsDriverVerified[permissions.IsDriverVerified]
        OnboardingViews[views - status, role, profile, dl, webhook, vehicle, role-switch]
    end

    DRF --> IsOnboardingComplete
    DRF --> OnboardingViews
    OnboardingViews --> OnboardingService
    OnboardingViews --> DLService
    OnboardingViews --> Validators
    OnboardingService --> UP
    OnboardingService --> VH
    DLService --> DV
    DLService --> Adapter
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
    admin.py                # UserProfile (staff-only), DriverVerification (staff-only), Vehicle (staff-only)
    models.py               # UserProfile (modified: +AWAITING_VEHICLE), DriverVerification, Vehicle (NEW)
    serializers.py          # Existing serializers + VehicleRegistrationSerializer (NEW),
                            # VehicleRegistrationResponseSerializer (NEW)
    views.py                # Existing views + VehicleRegisterView (NEW)
    urls.py                 # existing routes + vehicle endpoint (NEW)
    permissions.py          # IsOnboardingComplete, IsDriverRole, IsDriverVerified
    exceptions.py           # Existing exceptions + InvalidRegistrationFormat (NEW),
                            # InvalidVehicleType (NEW), DLNotVerified (NEW),
                            # VehicleAlreadyRegistered (NEW)
    services/
      __init__.py
      onboarding.py         # Existing functions + register_vehicle (NEW)
      dl_verification.py    # Modified: DL verified → AWAITING_VEHICLE (not COMPLETE)
      validators.py         # Existing validators + validate_registration_number (NEW)
    adapters/
      __init__.py           # get_dl_adapter() factory
      base.py               # DLVerificationAdapter ABC, DLVerificationResult dataclass
      mock.py               # MockDLVerificationAdapter (dev/test)
      digilocker.py         # DigiLockerDLVerificationAdapter (production)
    utils/
      __init__.py
      crypto.py             # encrypt_dl(), decrypt_dl() using Fernet + DL_ENCRYPTION_KEY
    migrations/
      0001_initial.py       # existing: UserProfile, DriverVerification
      0002_add_vehicle.py   # NEW: Vehicle model + AWAITING_VEHICLE status choice
```

---

## Components

| ID | Name | Responsibility | Changes |
|----|------|----------------|---------|
| COMP-001 | `profiles.models.UserProfile` | Stores onboarding state machine status, active role, and personal profile fields for every user. OneToOneField on `accounts.User`. | Modified: add `AWAITING_VEHICLE` to `ONBOARDING_STATUS_CHOICES` |
| COMP-002 | `profiles.models.DriverVerification` | Stores DL submission state, encrypted DL number, last-4 display, provider reference ID, attempt count, and verification timestamps. OneToOneField on `accounts.User`. | Unchanged |
| COMP-003 | `profiles.services.onboarding` | State machine transitions: get-or-create profile, set role, set profile details, register vehicle, switch role, derive next_step. No HTTP concerns. | Modified: add `register_vehicle()` function |
| COMP-004 | `profiles.services.dl_verification` | DL format normalisation and validation, adapter invocation, timeout handling, webhook processing (idempotent), attempt counting. No HTTP concerns. | Modified: DL verified transitions to `AWAITING_VEHICLE` instead of `COMPLETE` |
| COMP-005 | `profiles.adapters.base` | `DLVerificationAdapter` ABC + `DLVerificationResult` dataclass. Defines the contract the service uses; concrete providers implement this. | Unchanged |
| COMP-006 | `profiles.adapters.mock` | `MockDLVerificationAdapter` returns a configurable result (`verified`, `pending`, `rejected`) without calling any external service. Used in dev and tests. | Unchanged |
| COMP-007 | `profiles.permissions` | `IsOnboardingComplete` (gate for all protected non-onboarding endpoints), `IsDriverRole` (driver-only endpoints), `IsDriverVerified` (ride-offer endpoints). | Unchanged |
| COMP-008 | `profiles.exceptions` | Domain error subclasses of `core.exceptions.ApiError`, covering every error code defined in the API contract. | Modified: add `InvalidRegistrationFormat`, `InvalidVehicleType`, `DLNotVerified`, `VehicleAlreadyRegistered` |
| COMP-009 | `profiles.utils.crypto` | `encrypt_dl(plaintext) -> str` and `decrypt_dl(ciphertext) -> str` using Fernet with key from `DL_ENCRYPTION_KEY` env var. | Unchanged |
| COMP-010 | `profiles.views` | Thin DRF `APIView` subclasses. Validate input with serializers, delegate business logic to service layer, return bare data for envelope rendering. | Modified: add `VehicleRegisterView` |
| COMP-011 | `profiles.urls` | URL routing for all onboarding and profile endpoints. | Modified: add `onboarding/driver/vehicle/` route |
| COMP-012 | `accounts.serializers.UserSerializer` | Extended with `onboarding_status` and `active_role` as nullable `SerializerMethodField` values reading the `profile` reverse relation. | Modified (from v1, unchanged in v2) |
| COMP-013 | `config.settings` | `INSTALLED_APPS` gains `profiles`. `DEFAULT_PERMISSION_CLASSES` gains `IsOnboardingComplete`. New env vars: `DL_ENCRYPTION_KEY`, `DL_ADAPTER_CLASS`, `DL_WEBHOOK_SECRET`, `DL_PROVIDER_TIMEOUT_SECONDS`, `DL_MAX_ATTEMPTS`. | Modified (from v1, unchanged in v2) |
| COMP-014 | `config.urls` | `include('profiles.urls')` added under `api/`. | Modified (from v1, unchanged in v2) |
| COMP-015 | `profiles.models.Vehicle` | Stores vehicle registration number (plaintext), vehicle type, and active status. ForeignKey on `accounts.User` (supports future multi-vehicle). | New |
| COMP-016 | `profiles.services.validators` | Input validation functions for DL format, age, name, and vehicle registration number. | Modified: add `validate_registration_number()` |

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
created_at           DateTimeField(auto_now_add)
updated_at           DateTimeField(auto_now)
```

**v2 change:** `AWAITING_VEHICLE` added to `onboarding_status` choices between `PENDING_VERIFICATION` and `COMPLETE`.

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
dl_rejection_reason      TextField(nullable)               Provider-supplied reason; sanitised before storage
attempt_count            PositiveSmallIntegerField         Default 0; incremented on each POST /api/onboarding/driver/dl/
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
- **No uniqueness constraint on `registration_number`**: Two different Drivers may submit the same registration number. A future enhancement could flag duplicates for manual review.
- **Composite index on `(user, is_active)`**: Optimizes the common query pattern of "get active vehicles for a user".

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
| POST | `/api/onboarding/driver/dl/` | JWT | `IsAuthenticated`, `IsDriverRole` | Only valid in `AWAITING_DL` or `REJECTED` states |
| GET | `/api/onboarding/driver/dl/status/` | JWT | `IsAuthenticated`, `IsDriverRole` | |
| POST | `/api/onboarding/driver/dl/webhook/` | None (signature) | `AllowAny` + in-view signature check | Exempt from `IsOnboardingComplete` |
| POST | `/api/onboarding/driver/vehicle/` | JWT | `IsAuthenticated`, `IsDriverRole` | **NEW** — only valid in `AWAITING_VEHICLE` state |
| PATCH | `/api/profile/role/` | JWT | `IsAuthenticated`, `IsOnboardingComplete` | Only callable after full onboarding |
| GET | `/api/auth/me/` | JWT | `IsAuthenticated` only (existing endpoint) | Amended: adds `onboarding_status`, `active_role` |

### Contract refinements vs requirements doc

1. **`POST /api/onboarding/driver/dl/` on sync verified** — DL verified now transitions to `onboarding_status=AWAITING_VEHICLE` with `next_step="vehicle_registration"` (not `COMPLETE`). The Driver must still complete vehicle registration.

2. **`POST /api/onboarding/driver/dl/` on timeout** — The provider adapter wraps all provider calls in a configurable timeout (`DL_PROVIDER_TIMEOUT_SECONDS`, default 5s). On timeout, the service saves `dl_verification_status=PENDING`, `onboarding_status=PENDING_VERIFICATION` and returns `202 Accepted` (same as the async path). No `500` reaches the client (NFR-REL-01, AC-19).

3. **Webhook verified result** — `process_webhook_result()` on verified now sets `onboarding_status=AWAITING_VEHICLE` (not `COMPLETE`). The Driver must still complete vehicle registration before onboarding is fully complete.

4. **Webhook `403` before any DB read** — `DLWebhookView.post()` calls `self.adapter.validate_webhook(request.headers, request.body)` as the very first operation. If it returns `False`, the view raises `403` before any query (NFR-SEC-02, AC-18).

5. **`PATCH /api/profile/role/` — partial response for `dl_required`** — The requirements doc shows this as `400` with an error body. In the DEC-011 envelope this maps to an `ApiError` with `error_code = "dl_required"` and `status_code = 400`. No change to the contract; just confirming the error flows through the existing exception handler.

6. **`dl_rejection_reason` sanitisation** — Provider-supplied strings are truncated to 500 characters and stripped of HTML before storage. The exact sanitisation function is in `profiles/services/dl_verification.py::_sanitise_rejection_reason()`.

7. **`409 already_processed` on duplicate webhook** — When a webhook arrives for a `reference_id` already in a terminal state (`VERIFIED` or `REJECTED`), `process_webhook()` returns early and the view responds `409`. This satisfies NFR-REL-02 and AC-09.

8. **`POST /api/onboarding/driver/vehicle/` validation** — Registration number is normalised (strip spaces/hyphens, uppercase) before regex validation. Invalid format returns `400 invalid_registration_format`. Invalid vehicle type returns `400 invalid_vehicle_type`. Driver without verified DL returns `403 dl_not_verified`. Already-registered vehicle returns `409 vehicle_already_registered`.

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
    "vehicle_type": "sedan"
  }
}
```

Errors:
- `400 invalid_registration_format` — registration number does not match `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$`
- `400 invalid_vehicle_type` — value not in allowed set
- `403 not_a_driver` — endpoint called by a Passenger account
- `403 dl_not_verified` — Driver's DL is not in `verified` state
- `409 vehicle_already_registered` — Driver has already registered a vehicle during onboarding

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

switch_role(user, new_role: str) -> UserProfile
    Guards: status must be COMPLETE.
    PASSENGER -> active_role = PASSENGER immediately.
    DRIVER:
      - If DriverVerification.dl_verification_status == VERIFIED: active_role = DRIVER.
      - If PENDING: active_role = DRIVER, onboarding_status = PENDING_VERIFICATION.
      - If REJECTED or no record: raises DLRequired.

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

### `profiles/services/dl_verification.py`

```
validate_dl_format(raw: str) -> str
    strip() -> upper() -> regex match.
    Returns normalised string on success. Raises InvalidDLFormat on failure.

submit_dl(user, raw_dl_number: str) -> DLVerificationResult
    1. validate_dl_format -> normalised DL.
    2. get_or_create DriverVerification row for user.
    3. Check dl_verification_status != VERIFIED (raises DLAlreadyVerified).
    4. Check attempt_count < DL_MAX_ATTEMPTS (raises MaxDLAttemptsExceeded).
    5. Increment attempt_count. Encrypt DL -> dl_number. Store last-4 -> dl_number_display.
    6. Save reference_id placeholder, set status = PENDING, dl_submitted_at = now.
       (All of steps 2-6 in transaction.atomic)
    7. Call adapter.submit(normalised_dl). On DLProviderError or timeout, result.status = "pending".
    8. If result.status == "verified": update dl_verification_status = VERIFIED,
       update UserProfile.onboarding_status = AWAITING_VEHICLE.              [CHANGED from COMPLETE]
       If result.status == "pending": update dl_verification_ref = result.provider_ref,
       update UserProfile.onboarding_status = PENDING_VERIFICATION.
       If result.status == "rejected": update dl_verification_status = REJECTED,
       store rejection_reason, UserProfile.onboarding_status stays AWAITING_DL.
    9. Return result.

process_webhook(reference_id, status, rejection_reason) -> None
    Idempotent. Fetches DriverVerification by dl_verification_ref.
    If already in terminal state: raises AlreadyProcessed (-> 409).
    If status == "verified": set VERIFIED, set UserProfile.onboarding_status = AWAITING_VEHICLE.   [CHANGED from COMPLETE]
    If status == "rejected": set REJECTED, store sanitised reason,
      UserProfile.onboarding_status = PENDING_VERIFICATION (not COMPLETE; user must resubmit).
    If status unrecognised: log error, raise DLProviderError.
    All writes in transaction.atomic.
```

### `profiles/services/validators.py`

```
validate_dl_format(dl_number: str) -> Tuple[bool, str]
    Validates normalised DL number against ^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$.

validate_age(age: int) -> Tuple[bool, str]
    Validates age range 18-80 inclusive.

validate_name(name: str, field_name: str) -> Tuple[bool, str]
    Validates name charset and length.

validate_registration_number(number: str) -> Tuple[bool, str]                              [NEW]
    Normalises input: strip whitespace, remove hyphens, uppercase.
    Validates against ^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$.
    Returns (True, normalised_number) on success or (False, error_message) on failure.
    Note: returns the normalised value in the error_message position on success for
    convenience, or the service function can normalise separately and call validate.
```

Implementation detail for `validate_registration_number`:
```python
import re

VEHICLE_REG_PATTERN = re.compile(r'^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$')

def normalize_registration_number(number: str) -> str:
    """Strip spaces, hyphens, and uppercase."""
    return number.strip().replace(' ', '').replace('-', '').upper()

def validate_registration_number(number: str) -> Tuple[bool, str]:
    """Validate Indian vehicle registration number format after normalisation."""
    normalized = normalize_registration_number(number)
    if not VEHICLE_REG_PATTERN.match(normalized):
        return False, "Invalid registration number format. Expected: XX00XX0000"
    return True, ""
```

---

## Frontend / Backend Responsibilities

| Concern | Backend | Frontend (Expo) |
|---------|---------|-----------------|
| DL format validation | Authoritative: normalise + regex, reject `400 invalid_dl_format` | Recommended: client-side regex for instant UX feedback; server validation is the gate |
| Vehicle registration format validation | Authoritative: normalise + regex, reject `400 invalid_registration_format` | Recommended: client-side regex for instant UX feedback; server validation is the gate |
| Vehicle type validation | Authoritative: reject `400 invalid_vehicle_type` if not in allowed set | Client shows dropdown/picker restricted to allowed types |
| Onboarding state persistence | Owns the state machine; returns `onboarding_status` + `next_step` on every step response | Reads `next_step` to determine which screen to show next |
| Role label (`driver` vs "Rider") | Uses `driver` / `passenger` in all API contracts | Maps `driver` -> "Rider" in all UI copy |
| Resume mid-flow | Endpoint `GET /api/onboarding/status/` returns current state | On app open, call status endpoint and route to the appropriate screen |
| DL verification polling | `GET /api/onboarding/driver/dl/status/` returns `dl_verification_status` | Poll this endpoint while status is `pending` (suggested: exponential back-off starting at 5s) |
| Onboarding gate enforcement | `IsOnboardingComplete` returns `403 onboarding_incomplete` with `next_step` | On `403 onboarding_incomplete`, navigate to the step indicated by `next_step` |
| Age validation range | Enforces 18-80; may reject boundary with `400 invalid_age` | Apply same 18-80 range in client form validation |
| Vehicle registration normalisation | Strips spaces/hyphens, uppercases before validation | May show normalised preview to user before submission |

---

## Failure Modes

| Scenario | Behaviour | Recovery |
|----------|-----------|----------|
| DL provider returns error (5xx or network timeout) | Service treats as `pending`; returns `202` with `dl_verification_status=pending`. `DriverVerification` row saved in PENDING state with no `dl_verification_ref`. | Client polls `/api/onboarding/driver/dl/status/`. Operator retries via manual review or provider dashboard. |
| DL provider returns unrecognised `status` value in webhook | Logs raw payload at ERROR level, raises `DLProviderError`. View returns `400`. Provider retries. | Operator alerted via log; manual review required. State unchanged. |
| Webhook arrives before client receives `202` | `process_webhook` sets state to VERIFIED/AWAITING_VEHICLE. Client polls and discovers `AWAITING_VEHICLE` state with `next_step=vehicle_registration`. State transitions are idempotent. | No action needed. Client receives correct state on next poll or app open. |
| Duplicate webhook delivery | `process_webhook` checks for terminal state; returns `409 already_processed`. No state change. | No action needed. |
| Concurrent `POST /api/onboarding/role/` calls | `get_or_create` + DB unique constraint on `UserProfile.user` ensures one row. Second call gets `409 role_already_set` or sees existing role. | No action needed. |
| `DL_ENCRYPTION_KEY` misconfigured / missing | `crypto.py` raises `ImproperlyConfigured` at startup; Django fails to start. | Fix env var before deployment. |
| `DL_ADAPTER_CLASS` points to non-existent class | `get_dl_adapter()` raises `ImportError` at first DL submission call; view returns `422 dl_verification_provider_error`. | Fix env var. |
| User calls onboarding endpoint with expired JWT | `IsAuthenticated` returns `401` before any profile lookup. | Client refreshes token via `/api/auth/token/refresh/`. |
| `UserProfile` row not yet created when `/api/onboarding/status/` called | `get_or_create_profile` creates the row lazily; always returns `200`. | No special handling needed. |
| Driver calls vehicle endpoint before DL verified | `VehicleRegisterView` checks `onboarding_status == AWAITING_VEHICLE`; returns `403 dl_not_verified` if DL not verified. | Client should only show vehicle screen when `next_step=vehicle_registration`. |
| Driver calls vehicle endpoint after onboarding already complete | Service checks `user.vehicles.filter(is_active=True).exists()`; returns `409 vehicle_already_registered`. | No action needed. Client should not show vehicle form after completion. |
| Concurrent vehicle registration calls | `register_vehicle()` runs in `transaction.atomic`. Second call sees existing active vehicle and returns `409 vehicle_already_registered`. | No action needed. |
| Duplicate vehicle registration number across users | Allowed in v1 (no uniqueness constraint). Future enhancement could flag for manual review. | No action needed in v1. |

---

## Security Considerations

### Authentication
- All onboarding endpoints require a valid JWT Bearer token (`IsAuthenticated`).
- The webhook endpoint (`POST /api/onboarding/driver/dl/webhook/`) is exempt from JWT auth; it authenticates via `adapter.validate_webhook(headers, body)` which checks an HMAC-SHA256 signature (or provider equivalent). The view calls this before any DB operation and returns `403` on failure.
- `DL_WEBHOOK_SECRET` env var holds the shared secret; loaded via `python-decouple`, never committed.

### DL number PII
- Full DL number encrypted at rest (Fernet, `DL_ENCRYPTION_KEY`).
- Only last-4 chars stored in plaintext (`dl_number_display`).
- DL number never logged. Log records contain only `dl_number_display` and `dl_verification_ref`.
- Admin access to `DriverVerification` restricted to `is_staff=True` users (NFR-SEC-06).

### Vehicle registration number
- Stored plaintext — registration numbers are publicly visible on vehicles (FR-31). No encryption needed.
- No uniqueness constraint — same registration number may be submitted by different users in v1.
- Admin access to `Vehicle` restricted to `is_staff=True` users.

### Onboarding gate
- `IsOnboardingComplete` is server-enforced (NFR-SEC-04). The Expo client redirect is a UX supplement only.
- `IsDriverVerified` independently checks `dl_verification_status == VERIFIED` for ride-offer endpoints; `active_role == driver` alone is not sufficient (FR-25, AC-26).

### Vehicle endpoint authorization
- `POST /api/onboarding/driver/vehicle/` requires `IsAuthenticated` + `IsDriverRole`.
- Service layer additionally checks `onboarding_status == AWAITING_VEHICLE` (ensures DL is verified and vehicle not yet registered).
- A Passenger calling this endpoint receives `403 not_a_driver` from the permission class.
- A Driver whose DL is not verified receives `403 dl_not_verified` from the service layer.

### Webhook security
- Signature validated before any DB access.
- `DL_WEBHOOK_SECRET` is a separate env var from `DL_ENCRYPTION_KEY`.
- Webhook endpoint is intentionally unauthenticated by JWT; its URL is not secret but its signature requirement makes replays and spoofing difficult.

### Environment variables (all loaded via `python-decouple`)
```
DL_ENCRYPTION_KEY            # Fernet key; generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DL_WEBHOOK_SECRET            # Shared secret for webhook HMAC validation
DL_ADAPTER_CLASS             # default: profiles.adapters.mock.MockDLVerificationAdapter
DL_PROVIDER_TIMEOUT_SECONDS  # default: 5
DL_MAX_ATTEMPTS              # default: 3
DIGILOCKER_CLIENT_ID         # DigiLocker OAuth 2.0 client ID
DIGILOCKER_CLIENT_SECRET     # DigiLocker OAuth 2.0 client secret
DIGILOCKER_API_URL           # DigiLocker base URL (sandbox or production)
```
These must be added to `backend/.env.example` with placeholder values.

---

## Observability

### Key log events (`logger = logging.getLogger('profiles')`)

| Event | Level | Extra fields |
|-------|-------|--------------|
| `onboarding.profile.created` | INFO | `user_id`, `request_id` |
| `onboarding.role.set` | INFO | `user_id`, `role`, `request_id` |
| `onboarding.profile.submitted` | INFO | `user_id`, `onboarding_status`, `request_id` |
| `onboarding.dl.submitted` | INFO | `user_id`, `dl_number_display`, `attempt_count`, `request_id` |
| `onboarding.dl.result` | INFO | `user_id`, `dl_verification_status`, `provider_ref`, `request_id` |
| `onboarding.vehicle.registered` | INFO | `user_id`, `vehicle_type`, `request_id` |
| `onboarding.vehicle.duplicate_attempt` | WARNING | `user_id`, `request_id` |
| `onboarding.webhook.received` | INFO | `reference_id`, `status` |
| `onboarding.webhook.processed` | INFO | `reference_id`, `dl_verification_status`, `user_id` |
| `onboarding.webhook.duplicate` | WARNING | `reference_id`, `existing_status` |
| `onboarding.dl.provider_error` | ERROR | `user_id`, `error`, `request_id` |
| `onboarding.webhook.unknown_status` | ERROR | `reference_id`, `raw_status` |
| `onboarding.role.switch` | INFO | `user_id`, `from_role`, `to_role`, `request_id` |

The `profiles` logger must be registered in `settings.py` `LOGGING` config with the same `accounts_console` handler (phone redaction filter applies).

### Metrics (structured log fields for external aggregation)

- `dl_verification_provider_error_rate` — count of `onboarding.dl.provider_error` events / total DL submissions
- `onboarding_completion_rate_passenger` — users reaching `COMPLETE` from `NOT_STARTED` with `active_role=PASSENGER`
- `onboarding_completion_rate_driver` — users reaching `COMPLETE` from `NOT_STARTED` with `active_role=DRIVER`
- `dl_attempt_count_distribution` — histogram of `attempt_count` on `DriverVerification` rows
- `vehicle_registration_rate` — users reaching `COMPLETE` from `AWAITING_VEHICLE` (driver funnel completion)

---

## Performance

- `GET /api/onboarding/status/` and `GET /api/onboarding/driver/dl/status/`: single indexed row reads (`SELECT ... WHERE user_id = ?`). Expected p95 well within 100 ms at 50 rps (NFR-PERF-01).
- `POST /api/onboarding/profile/` and `POST /api/onboarding/role/`: single atomic DB write + a read to retrieve the profile. Expected p95 well within 200 ms (NFR-PERF-02).
- `POST /api/onboarding/driver/dl/` (sync provider): DB write + outbound HTTP to provider. Provider timeout set to 5s. Expected p95 <= 3 s (NFR-PERF-03). Django's request thread is blocked for the duration; async provider paths return in < 500 ms after dispatch.
- `POST /api/onboarding/driver/vehicle/`: single atomic DB write (create Vehicle + update UserProfile). No external calls. Expected p95 well within 200 ms (same category as profile/role writes).
- No caching layer is required at this stage. Profile and vehicle rows are tiny (< 1 KB), indexed by PK, and not shared across users.

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
4. No data backfill required: existing users in `COMPLETE` state are unaffected (only new Driver sign-ups go through the vehicle step). Existing users who have `onboarding_status=COMPLETE` with `active_role=driver` but no vehicle record are grandfathered in.

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

---

## Risks

| ID | Description | Severity | Mitigation |
|----|-------------|----------|-----------|
| RISK-001 | `DL_ENCRYPTION_KEY` loss makes all stored DL numbers permanently irrecoverable. | high | Key must be backed up to a secrets manager (AWS Secrets Manager or equivalent) before any DL is stored in production. Document in runbook. |
| RISK-002 | Adding `IsOnboardingComplete` to `DEFAULT_PERMISSION_CLASSES` gates all existing API users (currently none in production, but any future endpoint must either complete onboarding or explicitly override `permission_classes`). | medium | Document the convention: all non-onboarding views that should be accessible pre-onboarding must declare `permission_classes = [IsAuthenticated]`. Add this to the project CLAUDE.md. |
| RISK-003 | Provider webhook delivery delay (hours to days) leaves Drivers in `PENDING_VERIFICATION` with no automatic escalation path. OQ-09 (timeout policy) is unresolved. | medium | Accept for v1: client polls on app open. A periodic task to auto-escalate stale `PENDING` records can be added in a follow-up. |
| RISK-004 | `cryptography` Fernet adds ~10 ms per DL encrypt/decrypt operation. Under 50 rps DL submission load this is negligible. | low | Acceptable. Monitor if DL submission rate grows significantly. |
| RISK-005 | In-flight Drivers (in `AWAITING_DL` or `PENDING_VERIFICATION` at deploy time) will land in `AWAITING_VEHICLE` instead of `COMPLETE` after DL verification. If the Expo client is not updated to handle `vehicle_registration` next step, these Drivers will be stuck. | medium | Coordinate backend deployment with frontend release. The frontend must ship the vehicle registration screen before or simultaneously with the backend change. |
| RISK-006 | No uniqueness constraint on `registration_number` allows the same vehicle to be registered by multiple Drivers. Potential for abuse or disputes. | low | Accept for v1. A future enhancement can flag duplicate registrations for manual review. No third-party verification in v1. |

---

## Open Decisions

- **OQ-03**: Should the DL number validator normalise lowercase input to uppercase before validation, or reject it outright? (Resolved in ADR Decision 1: normalise to uppercase.)
- **OQ-05**: Should `UserProfile` be created proactively via Django signal or lazily on first access? (Resolved in ADR Decision 2: lazy creation.)
- **OQ-08**: How should Drivers in `pending_verification` state be notified when their DL result arrives? Push notifications are listed as a non-goal; will the app poll on launch? Deferred.
- **OQ-09**: Auto-rejection of stale `PENDING_VERIFICATION` drivers after N hours — requires a Celery beat task and a product policy decision. Deferred.

---

## Assumptions

- The `cryptography` package is available for installation (no OS-level build dependency issues in the deployment environment).
- The DL verification provider (DigiLocker) will communicate a definitive result either synchronously or via a timeout-recovery path. The business flow has no path for a provider that never responds.
- `DriverVerification.dl_verification_ref` is unique per provider call; the partial unique index on this column is sufficient for idempotency.
- Fernet encryption (AES-128-CBC with HMAC-SHA256) meets the data-at-rest protection requirement. If a future compliance audit requires AES-256, migrating the encryption library is an internal concern with no API contract impact.
- Age is self-reported; the product team accepts the risk that users may enter inaccurate values.
- `active_role = null` in `UserSerializer` output is an acceptable response for brand-new users (before any onboarding step). Expo clients must handle `null` for `onboarding_status` and `active_role`.
- The Indian vehicle registration number format `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$` covers the standard format for most Indian vehicles. Older or special-format registrations (e.g., diplomatic, military) are not validated in v1.
- No third-party verification of vehicle registration numbers is performed in v1. The platform relies on format validation and self-declaration by the Driver.
- Existing Drivers who completed onboarding before the vehicle registration feature is deployed are grandfathered in (their `onboarding_status=COMPLETE` is not reverted). Only new Driver sign-ups go through the vehicle registration step.
- The `vehicle_type` choices use uppercase values in the database (`CAR`, `SUV`, etc.) but the API contract accepts lowercase values (`car`, `suv`, etc.). The serializer/service normalises to uppercase for storage.
