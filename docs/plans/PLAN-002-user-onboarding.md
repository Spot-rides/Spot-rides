# Plan: User Onboarding Flow

**ID:** PLAN-002
**Type:** plan
**Feature:** FEAT-002
**Architecture:** ARCH-002
**Version:** 1
**Status:** ready
**Date:** 2026-09-27

---

## Overview

This plan implements the complete user onboarding flow that gates access to the main Spot Rides app. After OTP authentication, users must select a role (Driver or Passenger), complete a personal profile, and — for Drivers only — submit a driving licence for verification. The onboarding state is persisted server-side and resumable across devices. A server-enforced permission class blocks all non-onboarding endpoints until onboarding is complete.

**Total Tasks:** 42
**Estimated Backend Tasks:** 25
**Estimated Frontend Tasks:** 7
**Estimated Test Tasks:** 10

---

## Tasks

| ID | Title | Owner | Depends On | Risk | Status |
|----|-------|-------|-----------|------|--------|
| TASK-001 | Add cryptography dependency | backend-engineer | — | low | pending |
| TASK-002 | Create profiles Django app | backend-engineer | — | low | pending |
| TASK-003 | Create UserProfile model + migration | backend-engineer | TASK-002 | medium | pending |
| TASK-004 | Create DriverVerification model (same migration) | backend-engineer | TASK-003 | medium | pending |
| TASK-005 | Run migrations in dev | backend-engineer | TASK-004 | low | pending |
| TASK-006 | Create encryption utilities (crypto.py) | backend-engineer | TASK-001, TASK-002 | medium | pending |
| TASK-007 | Create domain exceptions | backend-engineer | TASK-002 | low | pending |
| TASK-008 | Create DL adapter interface (base.py) | backend-engineer | TASK-002 | low | pending |
| TASK-009 | Create mock DL adapter | backend-engineer | TASK-008 | low | pending |
| TASK-010 | Create onboarding service layer | backend-engineer | TASK-003, TASK-007 | medium | pending |
| TASK-011 | Create DL verification service layer | backend-engineer | TASK-004, TASK-006, TASK-008 | high | pending |
| TASK-012 | Create permission classes | backend-engineer | TASK-003, TASK-004, TASK-007 | high | pending |
| TASK-013 | Create serializers | backend-engineer | TASK-003, TASK-004, TASK-007 | medium | pending |
| TASK-014 | Create OnboardingStatusView | backend-engineer | TASK-010, TASK-013 | medium | pending |
| TASK-015 | Create RoleSelectView | backend-engineer | TASK-010, TASK-013 | medium | pending |
| TASK-016 | Create ProfileSubmitView | backend-engineer | TASK-010, TASK-013 | medium | pending |
| TASK-017 | Create DLSubmitView | backend-engineer | TASK-011, TASK-012, TASK-013 | high | pending |
| TASK-018 | Create DLStatusView | backend-engineer | TASK-011, TASK-012, TASK-013 | low | pending |
| TASK-019 | Create DLWebhookView | backend-engineer | TASK-011, TASK-009, TASK-013 | high | pending |
| TASK-020 | Create RoleSwitchView | backend-engineer | TASK-010, TASK-011, TASK-012, TASK-013 | medium | pending |
| TASK-021 | Create profiles URL routing | backend-engineer | TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020 | low | pending |
| TASK-022 | Update UserSerializer (accounts) | backend-engineer | TASK-003 | medium | pending |
| TASK-023 | Update settings.py | backend-engineer | TASK-002, TASK-012 | high | pending |
| TASK-024 | Update .env.example | backend-engineer | TASK-006, TASK-009 | low | pending |
| TASK-025 | Register models in admin | backend-engineer | TASK-003, TASK-004 | low | pending |
| TASK-026 | Unit tests: DL format validation | test-engineer | TASK-011 | low | pending |
| TASK-027 | Unit tests: encryption/decryption | test-engineer | TASK-006 | low | pending |
| TASK-028 | Unit tests: onboarding service | test-engineer | TASK-010 | medium | pending |
| TASK-029 | Unit tests: DL verification service | test-engineer | TASK-011 | medium | pending |
| TASK-030 | Unit tests: permission classes | test-engineer | TASK-012 | medium | pending |
| TASK-031 | Integration tests: onboarding flow | test-engineer | TASK-021, TASK-023 | high | pending |
| TASK-032 | Integration tests: DL submission + webhook | test-engineer | TASK-021, TASK-023 | high | pending |
| TASK-033 | Integration tests: role switching | test-engineer | TASK-021, TASK-023 | medium | pending |
| TASK-034 | Integration tests: onboarding gate | test-engineer | TASK-023, TASK-021 | high | pending |
| TASK-035 | Edge case tests | test-engineer | TASK-031, TASK-032 | medium | pending |
| TASK-036 | Create OnboardingGate component | frontend-engineer | TASK-021 | high | pending |
| TASK-037 | Create RoleSelectionScreen | frontend-engineer | TASK-021 | medium | pending |
| TASK-038 | Create ProfileFormScreen | frontend-engineer | TASK-021 | medium | pending |
| TASK-039 | Create DLSubmissionScreen | frontend-engineer | TASK-021 | high | pending |
| TASK-040 | Create DLPendingScreen | frontend-engineer | TASK-021 | medium | pending |
| TASK-041 | Create RoleSwitcher component | frontend-engineer | TASK-021 | medium | pending |
| TASK-042 | Integrate onboarding gate in app navigation | frontend-engineer | TASK-036, TASK-037, TASK-038, TASK-039, TASK-040, TASK-041 | high | pending |

---

## Task Details

### TASK-001 — Add cryptography dependency

- **Owner:** backend-engineer
- **Goal:** Add `cryptography` package to requirements.txt for Fernet DL encryption
- **Rationale:** ADR Decision 3 requires symmetric encryption at rest for DL numbers; Fernet is the chosen implementation
- **Dependencies:** none
- **Affected Files:**
  - `backend/requirements.txt`
- **Implementation Notes:**
  - Add `cryptography==43.0.0` (or latest stable) to requirements.txt
  - Install in venv: `pip install cryptography`
- **Acceptance Criteria:**
  - cryptography appears in requirements.txt
  - `python -c "from cryptography.fernet import Fernet; print('OK')"` succeeds in the backend venv
- **Tests Required:**
  - None (dependency addition only)
- **Risk:** low
- **Status:** pending

---

### TASK-002 — Create profiles Django app

- **Owner:** backend-engineer
- **Goal:** Create the new `profiles` app that will own all onboarding domain logic
- **Rationale:** ARCH-002 specifies a single new app for onboarding; separates concerns from `accounts`
- **Dependencies:** none
- **Affected Files:**
  - `backend/profiles/` (new directory)
  - `backend/profiles/__init__.py`
  - `backend/profiles/apps.py`
  - `backend/profiles/models.py`
  - `backend/profiles/admin.py`
  - `backend/profiles/views.py`
  - `backend/profiles/urls.py`
  - `backend/profiles/tests.py`
- **Implementation Notes:**
  - Run `cd backend && python manage.py startapp profiles`
  - Create subdirectories: `services/`, `adapters/`
  - Do NOT register in `INSTALLED_APPS` yet (TASK-023)
- **Acceptance Criteria:**
  - `backend/profiles/` directory exists with Django app structure
  - `backend/profiles/services/` directory exists
  - `backend/profiles/adapters/` directory exists
- **Tests Required:**
  - None (structure only)
- **Risk:** low
- **Status:** pending

---

### TASK-003 — Create UserProfile model + migration

- **Owner:** backend-engineer
- **Goal:** Define the `UserProfile` model that holds onboarding state and personal profile data
- **Rationale:** Central model for the onboarding state machine; OneToOneField on User
- **Dependencies:** TASK-002
- **Affected Files:**
  - `backend/profiles/models.py`
  - `backend/profiles/migrations/0001_initial.py` (generated)
- **Implementation Notes:**
  - Fields per ARCH-002 data model:
    - `user` (OneToOneField → accounts.User, CASCADE, related_name="profile")
    - `active_role` (CharField(10), nullable, choices: DRIVER, PASSENGER)
    - `first_name` (CharField(50), nullable)
    - `last_name` (CharField(50), nullable)
    - `age` (PositiveSmallIntegerField, nullable)
    - `gender` (CharField(20), nullable, choices: MALE, FEMALE, OTHER, PREFER_NOT_TO_SAY)
    - `onboarding_status` (CharField(30), default=NOT_STARTED, choices: NOT_STARTED, ROLE_SELECTED, AWAITING_DL, PENDING_VERIFICATION, COMPLETE)
    - `created_at` (DateTimeField, auto_now_add)
    - `updated_at` (DateTimeField, auto_now)
  - Migration dependency: `dependencies = [('accounts', '0002_alter_otpcode_phone_number')]`
  - Add `__str__` method returning `f"{self.user.phone_number} - {self.onboarding_status}"`
- **Acceptance Criteria:**
  - UserProfile model defined with all required fields
  - Migration file declares dependency on accounts 0002
  - `python manage.py makemigrations profiles` succeeds (after app registered in TASK-023)
- **Tests Required:**
  - Unit test: create UserProfile with valid data, assert all fields saved
  - Unit test: OneToOneField constraint prevents duplicate profiles for same user
- **Risk:** medium (migration dependency must be correct)
- **Status:** pending

---

### TASK-004 — Create DriverVerification model (same migration)

- **Owner:** backend-engineer
- **Goal:** Define the `DriverVerification` model that holds DL submission state and encrypted DL number
- **Rationale:** Extends User model for drivers; stores encrypted DL, verification status, attempt count
- **Dependencies:** TASK-003
- **Affected Files:**
  - `backend/profiles/models.py` (add to same file)
  - `backend/profiles/migrations/0001_initial.py` (will include both models)
- **Implementation Notes:**
  - Fields per ARCH-002 data model:
    - `user` (OneToOneField → accounts.User, CASCADE, related_name="driver_verification")
    - `dl_number` (CharField(256)) — Fernet ciphertext
    - `dl_number_display` (CharField(4)) — last 4 chars plaintext
    - `dl_key_version` (PositiveSmallIntegerField, default=1) — for future key rotation
    - `dl_verification_status` (CharField(20), choices: PENDING, VERIFIED, REJECTED)
    - `dl_verification_ref` (CharField(100), nullable) — provider reference ID
    - `dl_submitted_at` (DateTimeField)
    - `dl_verified_at` (DateTimeField, nullable)
    - `dl_rejection_reason` (TextField, nullable)
    - `attempt_count` (PositiveSmallIntegerField, default=0)
    - `created_at` (DateTimeField, auto_now_add)
    - `updated_at` (DateTimeField, auto_now)
  - Add constraint: `UniqueConstraint(fields=['dl_verification_ref'], condition=Q(dl_verification_ref__isnull=False), name='uq_dl_verification_ref')`
  - Add `__str__` method returning `f"{self.user.phone_number} - DL {self.dl_verification_status}"`
- **Acceptance Criteria:**
  - DriverVerification model defined with all required fields
  - Partial unique index on `dl_verification_ref` defined in migration
  - Both UserProfile and DriverVerification appear in 0001_initial migration
- **Tests Required:**
  - Unit test: create DriverVerification, assert encrypted dl_number stored
  - Unit test: unique constraint on dl_verification_ref enforced
- **Risk:** medium (encryption field sizing, constraint definition)
- **Status:** pending

---

### TASK-005 — Run migrations in dev

- **Owner:** backend-engineer
- **Goal:** Execute the profiles 0001 migration in the dev database
- **Rationale:** Establishes the tables for all subsequent development and testing
- **Dependencies:** TASK-004
- **Affected Files:**
  - PostgreSQL dev database (state change only)
- **Implementation Notes:**
  - `python manage.py migrate profiles`
  - Verify: `python manage.py showmigrations profiles` shows 0001 applied
- **Acceptance Criteria:**
  - `profiles_userprofile` table exists in PostgreSQL
  - `profiles_driververification` table exists in PostgreSQL
  - No migration errors in console
- **Tests Required:**
  - Manual: `psql` into dev DB, `\dt profiles*`, confirm both tables present
- **Risk:** low
- **Status:** pending

---

### TASK-006 — Create encryption utilities (crypto.py)

- **Owner:** backend-engineer
- **Goal:** Implement `encrypt_dl()` and `decrypt_dl()` functions using Fernet symmetric encryption
- **Rationale:** ADR Decision 3 mandates encrypted DL storage; centralizes encryption logic
- **Dependencies:** TASK-001, TASK-002
- **Affected Files:**
  - `backend/profiles/crypto.py` (new file)
- **Implementation Notes:**
  - Load `DL_ENCRYPTION_KEY` from env via `decouple.config('DL_ENCRYPTION_KEY')`
  - `encrypt_dl(plaintext: str) -> str`: returns base64-encoded Fernet token
  - `decrypt_dl(ciphertext: str) -> str`: returns plaintext DL number
  - Raise `ImproperlyConfigured` if `DL_ENCRYPTION_KEY` is missing or invalid
  - Validate key format on module load (must be 44-char base64url string)
- **Acceptance Criteria:**
  - `encrypt_dl("MH01 20110012345")` returns a base64 string of ~120 chars
  - `decrypt_dl(encrypt_dl("MH01 20110012345"))` returns original plaintext
  - Missing `DL_ENCRYPTION_KEY` raises `ImproperlyConfigured` at import time
- **Tests Required:**
  - Unit test: encrypt then decrypt returns original value
  - Unit test: encrypt same plaintext twice yields different ciphertexts (IV randomization)
  - Unit test: decrypt with wrong key raises `cryptography.fernet.InvalidToken`
  - Unit test: missing env var raises `ImproperlyConfigured`
- **Risk:** medium (key management is critical; errors here break all DL operations)
- **Status:** pending

---

### TASK-007 — Create domain exceptions

- **Owner:** backend-engineer
- **Goal:** Define all domain exception classes for the onboarding flow
- **Rationale:** Exceptions map to stable error codes in API responses; inherits from `core.exceptions.ApiError`
- **Dependencies:** TASK-002
- **Affected Files:**
  - `backend/profiles/exceptions.py` (new file)
- **Implementation Notes:**
  - All exceptions extend `core.exceptions.ApiError`
  - Define:
    - `OnboardingIncomplete(status_code=403, error_code="onboarding_incomplete")`
    - `NotADriver(status_code=403, error_code="not_a_driver")`
    - `InvalidAge(status_code=400, error_code="invalid_age")`
    - `InvalidGender(status_code=400, error_code="invalid_gender")`
    - `InvalidDLFormat(status_code=400, error_code="invalid_dl_format")`
    - `DLAlreadyVerified(status_code=409, error_code="dl_already_verified")`
    - `DLProviderError(status_code=422, error_code="dl_verification_provider_error")`
    - `MaxDLAttemptsExceeded(status_code=429, error_code="max_dl_attempts_exceeded")`
    - `RoleAlreadySet(status_code=409, error_code="role_already_set")`
    - `ProfileAlreadySet(status_code=409, error_code="profile_already_set")`
    - `DLRequired(status_code=400, error_code="dl_required")`
    - `AlreadyProcessed(status_code=409, error_code="already_processed")` — for webhook idempotency
  - Each exception accepts `detail` (human-readable message) and optional `extra` dict
- **Acceptance Criteria:**
  - All exception classes defined
  - Each has correct status_code and error_code
  - Raising any exception in a DRF view produces the correct envelope response
- **Tests Required:**
  - Unit test: instantiate each exception, assert status_code and error_code
  - Integration test: raise exception in a view, assert envelope format
- **Risk:** low
- **Status:** pending

---

### TASK-008 — Create DL adapter interface (base.py)

- **Owner:** backend-engineer
- **Goal:** Define the abstract `DLVerificationAdapter` class and `DLVerificationResult` dataclass
- **Rationale:** ADR Decision 6 isolates provider-specific code behind an interface; enables mock for dev/test
- **Dependencies:** TASK-002
- **Affected Files:**
  - `backend/profiles/adapters/__init__.py` (new file)
  - `backend/profiles/adapters/base.py` (new file)
- **Implementation Notes:**
  - `DLVerificationResult` dataclass with fields:
    - `status: Literal["verified", "pending", "rejected"]`
    - `provider_ref: Optional[str]`
    - `rejection_reason: Optional[str]`
  - `DLVerificationAdapter` ABC with methods:
    - `submit(self, dl_number: str) -> DLVerificationResult` (abstractmethod)
    - `validate_webhook(self, request_headers: dict, raw_body: bytes) -> bool` (abstractmethod)
  - Factory function in `adapters/__init__.py`:
    - `get_dl_adapter() -> DLVerificationAdapter`: loads class from `settings.DL_ADAPTER_CLASS`, instantiates, returns
- **Acceptance Criteria:**
  - `DLVerificationAdapter` is an ABC with 2 abstract methods
  - `DLVerificationResult` dataclass has 3 fields
  - `get_dl_adapter()` factory can be called
- **Tests Required:**
  - Unit test: attempting to instantiate `DLVerificationAdapter` directly raises `TypeError`
- **Risk:** low
- **Status:** pending

---

### TASK-009 — Create mock DL adapter

- **Owner:** backend-engineer
- **Goal:** Implement `MockDLVerificationAdapter` that returns configurable results without calling external API
- **Rationale:** Enables development and testing without a real DL provider (OQ-01 unresolved)
- **Dependencies:** TASK-008
- **Affected Files:**
  - `backend/profiles/adapters/mock.py` (new file)
- **Implementation Notes:**
  - Reads `settings.DL_ADAPTER_MOCK_RESULT` (default: "verified")
  - `submit(dl_number)`:
    - If mock_result == "verified": return `DLVerificationResult(status="verified", provider_ref=None, rejection_reason=None)`
    - If mock_result == "pending": return `DLVerificationResult(status="pending", provider_ref=f"mock-{uuid.uuid4().hex[:8]}", rejection_reason=None)`
    - If mock_result == "rejected": return `DLVerificationResult(status="rejected", provider_ref=None, rejection_reason="Mock rejection for testing")`
  - `validate_webhook(headers, body)`:
    - Check for `X-Mock-Signature` header == `settings.DL_WEBHOOK_SECRET`
    - Return True if match, False otherwise
- **Acceptance Criteria:**
  - `MockDLVerificationAdapter().submit("MH01 20110012345")` returns "verified" result by default
  - Configurable via `DL_ADAPTER_MOCK_RESULT` setting
  - `validate_webhook` checks `X-Mock-Signature` header
- **Tests Required:**
  - Unit test: mock adapter returns verified result
  - Unit test: mock adapter returns pending result with provider_ref
  - Unit test: mock adapter returns rejected result with reason
  - Unit test: validate_webhook returns True with correct signature, False otherwise
- **Risk:** low
- **Status:** pending

---

### TASK-010 — Create onboarding service layer

- **Owner:** backend-engineer
- **Goal:** Implement state machine logic for onboarding: profile creation, role selection, profile details, role switching
- **Rationale:** Centralizes business logic outside views; enables unit testing without HTTP layer
- **Dependencies:** TASK-003, TASK-007
- **Affected Files:**
  - `backend/profiles/services/__init__.py` (new file)
  - `backend/profiles/services/onboarding.py` (new file)
- **Implementation Notes:**
  - Functions to implement:
    - `get_or_create_profile(user) -> (UserProfile, created: bool)`: wraps `UserProfile.objects.get_or_create(user=user, defaults={'onboarding_status': 'NOT_STARTED'})`
    - `set_role(profile, role: str) -> UserProfile`: guards status==NOT_STARTED, raises `RoleAlreadySet` if beyond; sets `active_role` and `onboarding_status=ROLE_SELECTED`
    - `set_profile_details(profile, first_name, last_name, age, gender) -> UserProfile`: guards status==ROLE_SELECTED, raises `ProfileAlreadySet` otherwise; validates age 18-80, gender choices, name format; sets fields and transitions to COMPLETE (passenger) or AWAITING_DL (driver)
    - `switch_role(profile, new_role: str) -> UserProfile`: guards status==COMPLETE; implements FR-22-24 logic (passenger switch immediate, driver switch checks DL status)
    - `compute_next_step(profile: UserProfile | None) -> str`: pure function mapping onboarding_status to next_step string per API contract
  - Use `transaction.atomic()` for state-changing functions
- **Acceptance Criteria:**
  - All 5 functions implemented
  - `get_or_create_profile` is idempotent under concurrent calls
  - `set_role` enforces state guard (raises if not NOT_STARTED)
  - `set_profile_details` transitions Passenger to COMPLETE, Driver to AWAITING_DL
  - `switch_role` enforces FR-22-24 (passenger immediate, driver checks DL)
  - `compute_next_step` returns correct next_step for all states
- **Tests Required:**
  - Unit test: get_or_create returns existing profile on second call
  - Unit test: set_role with status != NOT_STARTED raises RoleAlreadySet
  - Unit test: set_profile_details with age=17 raises InvalidAge
  - Unit test: set_profile_details for passenger sets status=COMPLETE
  - Unit test: set_profile_details for driver sets status=AWAITING_DL
  - Unit test: switch_role from passenger to driver without DL raises DLRequired
  - Unit test: compute_next_step(None) returns "role_selection"
- **Risk:** medium (state machine logic is complex; errors here affect all onboarding flow)
- **Status:** pending

---

### TASK-011 — Create DL verification service layer

- **Owner:** backend-engineer
- **Goal:** Implement DL validation, submission, and webhook processing logic
- **Rationale:** Centralizes DL business logic; wraps adapter calls with timeout and error handling
- **Dependencies:** TASK-004, TASK-006, TASK-008
- **Affected Files:**
  - `backend/profiles/services/dl_verification.py` (new file)
- **Implementation Notes:**
  - Functions to implement:
    - `validate_dl_format(raw: str) -> str`: strip → upper → regex `^[A-Z]{2}[0-9]{2}[ -]?[0-9]{4}[0-9]{7}$`; return normalized or raise `InvalidDLFormat`
    - `submit_dl(user, raw_dl_number: str) -> DLVerificationResult`:
      1. Validate format → normalized
      2. Get or create DriverVerification
      3. Check status != VERIFIED (raise DLAlreadyVerified)
      4. Check attempt_count < settings.DL_MAX_ATTEMPTS (raise MaxDLAttemptsExceeded)
      5. Increment attempt_count
      6. Encrypt DL → dl_number; extract last-4 → dl_number_display
      7. Call adapter.submit(normalized) with timeout (default 5s from settings.DL_PROVIDER_TIMEOUT_SECONDS)
      8. On timeout or provider error: treat as pending
      9. Update DriverVerification + UserProfile based on result.status
      10. Return result
    - `process_webhook(reference_id, status, rejection_reason) -> None`: idempotent webhook handler; fetches by dl_verification_ref, checks terminal state (raise AlreadyProcessed if so), updates fields based on status
    - `_sanitise_rejection_reason(reason: str) -> str`: truncate to 500 chars, strip HTML
  - Wrap all DB writes in `transaction.atomic()`
  - Load timeout from `settings.DL_PROVIDER_TIMEOUT_SECONDS` (default 5)
- **Acceptance Criteria:**
  - `validate_dl_format("mh01 20110012345")` returns "MH01 20110012345"
  - `validate_dl_format("invalid")` raises InvalidDLFormat
  - `submit_dl` encrypts DL number and stores in DriverVerification
  - `submit_dl` respects attempt_count limit
  - `submit_dl` treats adapter timeout as pending result
  - `process_webhook` is idempotent (duplicate calls with same reference_id raise AlreadyProcessed)
  - `process_webhook` transitions UserProfile.onboarding_status correctly
- **Tests Required:**
  - Unit test: validate_dl_format with valid inputs
  - Unit test: validate_dl_format with invalid inputs raises InvalidDLFormat
  - Unit test: submit_dl increments attempt_count
  - Unit test: submit_dl with attempt_count >= max raises MaxDLAttemptsExceeded
  - Unit test: submit_dl with adapter returning verified updates status
  - Unit test: submit_dl with adapter timeout treats as pending
  - Unit test: process_webhook with verified status sets COMPLETE
  - Unit test: process_webhook called twice raises AlreadyProcessed
- **Risk:** high (complex logic, critical for driver onboarding, encryption/decryption errors impact all drivers)
- **Status:** pending

---

### TASK-012 — Create permission classes

- **Owner:** backend-engineer
- **Goal:** Implement DRF permission classes for onboarding gate and driver-specific endpoints
- **Rationale:** FR-14, FR-25 require server-enforced gating; ADR Decision 4 uses permission classes
- **Dependencies:** TASK-003, TASK-004, TASK-007
- **Affected Files:**
  - `backend/profiles/permissions.py` (new file)
- **Implementation Notes:**
  - `IsOnboardingComplete(BasePermission)`:
    - Check `request.user.profile.onboarding_status == UserProfile.COMPLETE`
    - If not, raise `OnboardingIncomplete` with current status and next_step
    - Handle case where profile doesn't exist (create lazily or treat as NOT_STARTED)
  - `IsDriverRole(BasePermission)`:
    - Check `request.user.profile.active_role == UserProfile.DRIVER`
    - If not, raise `NotADriver`
  - `IsDriverVerified(BasePermission)`:
    - Check `request.user.driver_verification.dl_verification_status == DriverVerification.VERIFIED`
    - If not, raise appropriate error (onboarding_incomplete or not_a_driver)
    - Handle case where driver_verification doesn't exist
- **Acceptance Criteria:**
  - `IsOnboardingComplete` returns False for user with status != COMPLETE
  - `IsOnboardingComplete` returns True for user with status == COMPLETE
  - `IsDriverRole` returns False for passenger, True for driver
  - `IsDriverVerified` returns True only when DL is VERIFIED
- **Tests Required:**
  - Unit test: IsOnboardingComplete with incomplete user raises OnboardingIncomplete
  - Unit test: IsOnboardingComplete with complete user returns True
  - Unit test: IsDriverRole with passenger raises NotADriver
  - Unit test: IsDriverVerified with unverified DL returns False
- **Risk:** high (errors here allow onboarding bypass, security vulnerability)
- **Status:** pending

---

### TASK-013 — Create serializers

- **Owner:** backend-engineer
- **Goal:** Implement DRF serializers for all onboarding endpoints
- **Rationale:** Validates input, enforces data contracts from FEAT-002 API contracts
- **Dependencies:** TASK-003, TASK-004, TASK-007
- **Affected Files:**
  - `backend/profiles/serializers.py` (new file)
- **Implementation Notes:**
  - Define serializers:
    - `OnboardingStatusSerializer`: read-only, returns onboarding_status, active_role, next_step, profile_complete, dl_verification_status
    - `RoleSelectSerializer`: accepts role (driver/passenger), validates choices
    - `ProfileSubmitSerializer`: accepts first_name, last_name, age, gender; validates per FR-17-19
    - `DLSubmitSerializer`: accepts dl_number, delegates format validation to service layer
    - `DLStatusSerializer`: read-only, returns dl_verification_status, onboarding_status, rejection_reason
    - `RoleSwitchSerializer`: accepts role (driver/passenger), validates choices
  - Use DRF field validators and custom `validate_<field>` methods
  - Age validation: 18-80 inclusive
  - Gender validation: male, female, other, prefer_not_to_say
  - Name validation: 1-50 chars, Unicode letters/space/hyphen/apostrophe only
- **Acceptance Criteria:**
  - All 6 serializers defined
  - `ProfileSubmitSerializer` rejects age=17 with "invalid_age"
  - `ProfileSubmitSerializer` rejects gender="invalid" with "invalid_gender"
  - `ProfileSubmitSerializer` rejects names with digits or special chars
  - `RoleSelectSerializer` rejects role="admin"
- **Tests Required:**
  - Unit test: each serializer with valid data passes validation
  - Unit test: age validation (17→reject, 18→accept, 80→accept, 81→reject)
  - Unit test: gender validation (all 4 valid values accept, others reject)
  - Unit test: name validation (letters/space/hyphen/apostrophe accept, digits reject)
- **Risk:** medium (incorrect validation allows bad data)
- **Status:** pending

---

### TASK-014 — Create OnboardingStatusView

- **Owner:** backend-engineer
- **Goal:** Implement `GET /api/onboarding/status/` endpoint
- **Rationale:** FR-01 — returns current onboarding state and next step
- **Dependencies:** TASK-010, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py` (new file)
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [IsAuthenticated]` (explicitly opt out of IsOnboardingComplete)
  - GET handler:
    - Call `get_or_create_profile(request.user)`
    - Call `compute_next_step(profile)`
    - Serialize with `OnboardingStatusSerializer`
    - Return bare dict (envelope added by renderer)
- **Acceptance Criteria:**
  - GET returns 200 with onboarding_status, active_role, next_step
  - Lazily creates profile if not exists (first call for new user)
  - AC-01: new user returns NOT_STARTED with next_step=role_selection
- **Tests Required:**
  - Integration test: AC-01 (new user, status endpoint returns NOT_STARTED)
  - Integration test: user with ROLE_SELECTED returns next_step=profile
- **Risk:** medium (lazy creation race condition if not handled correctly)
- **Status:** pending

---

### TASK-015 — Create RoleSelectView

- **Owner:** backend-engineer
- **Goal:** Implement `POST /api/onboarding/role/` endpoint
- **Rationale:** FR-02 — accepts role selection during initial onboarding
- **Dependencies:** TASK-010, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py`
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [IsAuthenticated]`
  - POST handler:
    - Validate with `RoleSelectSerializer`
    - Call `get_or_create_profile(request.user)`
    - Call `set_role(profile, validated_data['role'])`
    - Return new status + next_step
  - Service layer raises `RoleAlreadySet` if called more than once
- **Acceptance Criteria:**
  - POST with role=passenger returns 200 with active_role=passenger, next_step=profile
  - POST with role=driver returns 200 with active_role=driver, next_step=profile
  - AC-02: POST with role=passenger returns active_role=passenger, status=ROLE_SELECTED
  - AC-03: second POST raises 409 role_already_set
- **Tests Required:**
  - Integration test: AC-02 (role=passenger succeeds)
  - Integration test: AC-03 (second role POST raises 409)
  - Integration test: invalid role rejected
- **Risk:** medium (must prevent duplicate role setting)
- **Status:** pending

---

### TASK-016 — Create ProfileSubmitView

- **Owner:** backend-engineer
- **Goal:** Implement `POST /api/onboarding/profile/` endpoint
- **Rationale:** FR-03-05 — accepts personal profile details
- **Dependencies:** TASK-010, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py`
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [IsAuthenticated]`
  - POST handler:
    - Validate with `ProfileSubmitSerializer`
    - Fetch profile (must exist, role must be set)
    - Call `set_profile_details(profile, first_name, last_name, age, gender)`
    - Return new status + next_step
  - Passenger: status → COMPLETE, next_step → none
  - Driver: status → AWAITING_DL, next_step → dl_submission
- **Acceptance Criteria:**
  - POST for passenger returns status=COMPLETE
  - POST for driver returns status=AWAITING_DL
  - AC-04: passenger profile submission sets status=COMPLETE
  - AC-06: driver profile submission sets status=AWAITING_DL
  - AC-12: age=17 rejected, age=18/80 accepted, age=81 rejected
  - AC-13: invalid gender rejected
- **Tests Required:**
  - Integration test: AC-04 (passenger profile complete)
  - Integration test: AC-06 (driver profile → AWAITING_DL)
  - Integration test: AC-12 (age validation)
  - Integration test: AC-13 (gender validation)
  - Integration test: name validation (valid chars accepted, invalid rejected)
- **Risk:** medium (validation errors allow bad data)
- **Status:** pending

---

### TASK-017 — Create DLSubmitView

- **Owner:** backend-engineer
- **Goal:** Implement `POST /api/onboarding/driver/dl/` endpoint
- **Rationale:** FR-06-10 — accepts DL number, validates, calls provider, returns result
- **Dependencies:** TASK-011, TASK-012, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py`
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [IsAuthenticated, IsDriverRole]`
  - POST handler:
    - Validate with `DLSubmitSerializer`
    - Call `submit_dl(request.user, validated_data['dl_number'])`
    - If result.status == "verified": return 200 with status=COMPLETE
    - If result.status == "pending": return 202 with status=PENDING_VERIFICATION
    - If result.status == "rejected": return 200 with status=AWAITING_DL (allow resubmit)
  - Service layer handles format validation, encryption, adapter call, state transitions
- **Acceptance Criteria:**
  - POST with valid DL and mock adapter=verified returns 200 with status=COMPLETE
  - POST with mock adapter=pending returns 202 with status=PENDING_VERIFICATION
  - AC-07: valid DL with sync verified result returns status=COMPLETE
  - AC-08: pending result returns 202 with status=PENDING_VERIFICATION
  - AC-11: invalid format rejected 400
  - AC-17: attempt_count >= 3 raises 429
  - AC-19: adapter timeout treated as pending
  - AC-20: passenger calling this endpoint raises 403 not_a_driver
- **Tests Required:**
  - Integration test: AC-07 (sync verified)
  - Integration test: AC-08 (pending result)
  - Integration test: AC-11 (format validation)
  - Integration test: AC-17 (max attempts)
  - Integration test: AC-19 (timeout → pending)
  - Integration test: AC-20 (passenger rejected)
- **Risk:** high (complex logic, encryption, external call, multiple state transitions)
- **Status:** pending

---

### TASK-018 — Create DLStatusView

- **Owner:** backend-engineer
- **Goal:** Implement `GET /api/onboarding/driver/dl/status/` endpoint
- **Rationale:** FR-12 — allows client to poll for DL verification outcome
- **Dependencies:** TASK-011, TASK-012, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py`
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [IsAuthenticated, IsDriverRole]`
  - GET handler:
    - Fetch `request.user.driver_verification`
    - Serialize with `DLStatusSerializer`
    - Return dl_verification_status, onboarding_status, rejection_reason
- **Acceptance Criteria:**
  - GET returns current DL status
  - rejection_reason populated when status=REJECTED
  - Passenger calling this endpoint raises 403
- **Tests Required:**
  - Integration test: driver with pending DL returns status=PENDING
  - Integration test: driver with verified DL returns status=VERIFIED
  - Integration test: passenger raises 403
- **Risk:** low (read-only endpoint)
- **Status:** pending

---

### TASK-019 — Create DLWebhookView

- **Owner:** backend-engineer
- **Goal:** Implement `POST /api/onboarding/driver/dl/webhook/` endpoint
- **Rationale:** FR-11 — receives async verification results from DL provider
- **Dependencies:** TASK-011, TASK-009, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py`
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [AllowAny]` (webhook is authenticated via signature, not JWT)
  - POST handler:
    - Call `adapter.validate_webhook(request.headers, request.body)` FIRST
    - If False, raise 403 immediately
    - Parse payload (shape depends on provider; mock expects: `{reference_id, status, rejection_reason}`)
    - Call `process_webhook(reference_id, status, rejection_reason)`
    - Return 200 on success
    - Return 409 if already processed (idempotent)
  - Must be exempt from `IsOnboardingComplete` permission (not a user request)
- **Acceptance Criteria:**
  - POST with valid signature and verified status updates DriverVerification + UserProfile
  - POST with invalid signature returns 403 before any DB operation
  - Duplicate POST returns 409
  - AC-09: webhook with verified payload sets status=VERIFIED and onboarding_status=COMPLETE
  - AC-10: webhook with rejected payload sets status=REJECTED
  - AC-18: invalid signature returns 403, no state change
- **Tests Required:**
  - Integration test: AC-09 (verified webhook)
  - Integration test: AC-10 (rejected webhook)
  - Integration test: AC-18 (invalid signature)
  - Integration test: duplicate webhook returns 409
- **Risk:** high (security-critical; unauthenticated webhooks must be rejected)
- **Status:** pending

---

### TASK-020 — Create RoleSwitchView

- **Owner:** backend-engineer
- **Goal:** Implement `PATCH /api/profile/role/` endpoint
- **Rationale:** FR-22-26 — allows fully onboarded users to switch active role
- **Dependencies:** TASK-010, TASK-011, TASK-012, TASK-013
- **Affected Files:**
  - `backend/profiles/views.py`
- **Implementation Notes:**
  - DRF `APIView` subclass
  - `permission_classes = [IsAuthenticated, IsOnboardingComplete]` (only callable after full onboarding)
  - PATCH handler:
    - Validate with `RoleSwitchSerializer`
    - Fetch profile
    - Call `switch_role(profile, validated_data['role'])`
    - Return new active_role + relevant status fields
  - Service layer handles DL checks per FR-24
- **Acceptance Criteria:**
  - PATCH to passenger returns 200 immediately
  - PATCH to driver with verified DL returns 200
  - PATCH to driver without DL returns 400 dl_required
  - AC-22: passenger → driver without DL raises 400
  - AC-23: user with verified DL can switch to driver
  - AC-24: driver → passenger preserves DriverVerification
  - AC-25: switching back to driver does not require DL resubmit
- **Tests Required:**
  - Integration test: AC-22 (no DL → dl_required)
  - Integration test: AC-23 (verified DL allows switch)
  - Integration test: AC-24 (passenger switch preserves DL)
  - Integration test: AC-25 (switch back to driver)
- **Risk:** medium (complex DL check logic)
- **Status:** pending

---

### TASK-021 — Create profiles URL routing

- **Owner:** backend-engineer
- **Goal:** Wire all onboarding/profile views to URL paths and integrate into main URL config
- **Rationale:** Makes all endpoints accessible; defines stable URL structure
- **Dependencies:** TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020
- **Affected Files:**
  - `backend/profiles/urls.py`
  - `backend/config/urls.py`
- **Implementation Notes:**
  - In `profiles/urls.py`:
    - `path('onboarding/status/', OnboardingStatusView.as_view())`
    - `path('onboarding/role/', RoleSelectView.as_view())`
    - `path('onboarding/profile/', ProfileSubmitView.as_view())`
    - `path('onboarding/driver/dl/', DLSubmitView.as_view())`
    - `path('onboarding/driver/dl/status/', DLStatusView.as_view())`
    - `path('onboarding/driver/dl/webhook/', DLWebhookView.as_view())`
    - `path('profile/role/', RoleSwitchView.as_view())`
  - In `config/urls.py`: `path('api/', include('profiles.urls'))`
- **Acceptance Criteria:**
  - `curl http://localhost:8000/api/onboarding/status/` returns 401 (requires auth)
  - All 7 endpoints accessible at documented paths
- **Tests Required:**
  - Integration test: each endpoint resolves to correct view
- **Risk:** low
- **Status:** pending

---

### TASK-022 — Update UserSerializer (accounts)

- **Owner:** backend-engineer
- **Goal:** Extend `accounts.serializers.UserSerializer` to include onboarding_status and active_role
- **Rationale:** FR-21 — `GET /api/auth/me/` must return these fields so client can gate on app launch
- **Dependencies:** TASK-003
- **Affected Files:**
  - `backend/accounts/serializers.py`
- **Implementation Notes:**
  - Add two `SerializerMethodField` to `UserSerializer`:
    - `onboarding_status = serializers.SerializerMethodField()`
    - `active_role = serializers.SerializerMethodField()`
  - Implement methods:
    - `get_onboarding_status(self, obj)`:
      - Try `return obj.profile.onboarding_status`
      - Except `RelatedObjectDoesNotExist`: `return None`
    - `get_active_role(self, obj)`:
      - Try `return obj.profile.active_role`
      - Except `RelatedObjectDoesNotExist`: `return None`
  - Update `Meta.fields` to include the two new fields
  - NO import from profiles (uses reverse relation on User model)
- **Acceptance Criteria:**
  - `GET /api/auth/me/` includes onboarding_status and active_role
  - New user (no profile yet) returns null for both fields
  - User with profile returns actual values
  - AC-05: completed passenger returns onboarding_status=COMPLETE, active_role=PASSENGER
- **Tests Required:**
  - Integration test: AC-05 (completed user in /me/ response)
  - Integration test: new user returns null for both fields
- **Risk:** medium (must handle missing profile gracefully)
- **Status:** pending

---

### TASK-023 — Update settings.py

- **Owner:** backend-engineer
- **Goal:** Register profiles app, add IsOnboardingComplete to DEFAULT_PERMISSION_CLASSES, add env vars
- **Rationale:** Required for Django to recognize profiles app and enable global onboarding gate
- **Dependencies:** TASK-002, TASK-012
- **Affected Files:**
  - `backend/config/settings.py`
- **Implementation Notes:**
  - Add `'profiles'` to `INSTALLED_APPS`
  - Update `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']`:
    ```python
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
        'profiles.permissions.IsOnboardingComplete',
    ],
    ```
  - Add to bottom of settings (after other env vars):
    ```python
    # DL verification (profiles)
    DL_ENCRYPTION_KEY = config('DL_ENCRYPTION_KEY')
    DL_WEBHOOK_SECRET = config('DL_WEBHOOK_SECRET')
    DL_ADAPTER_CLASS = config('DL_ADAPTER_CLASS', default='profiles.adapters.mock.MockDLVerificationAdapter')
    DL_ADAPTER_MOCK_RESULT = config('DL_ADAPTER_MOCK_RESULT', default='verified')
    DL_PROVIDER_TIMEOUT_SECONDS = config('DL_PROVIDER_TIMEOUT_SECONDS', default=5, cast=int)
    DL_MAX_ATTEMPTS = config('DL_MAX_ATTEMPTS', default=3, cast=int)
    ```
  - Add 'profiles' logger to LOGGING config:
    ```python
    'profiles': {
        'handlers': ['accounts_console'],  # shares phone redaction handler
        'level': 'INFO',
        'propagate': False,
    },
    ```
- **Acceptance Criteria:**
  - `python manage.py check` succeeds
  - `profiles` appears in `INSTALLED_APPS`
  - `IsOnboardingComplete` is in `DEFAULT_PERMISSION_CLASSES`
  - All DL_* env vars loaded
  - Missing `DL_ENCRYPTION_KEY` causes startup failure (expected)
- **Tests Required:**
  - Integration test: onboarding gate blocks non-onboarding endpoint (after this task)
  - Integration test: AC-14 (incomplete user calling protected endpoint raises 403)
- **Risk:** high (breaking change — all existing endpoints now gated by onboarding; must coordinate with frontend)
- **Status:** pending

---

### TASK-024 — Update .env.example

- **Owner:** backend-engineer
- **Goal:** Document all new environment variables with placeholder values
- **Rationale:** Required for deployment; documents configuration surface
- **Dependencies:** TASK-006, TASK-009
- **Affected Files:**
  - `backend/.env.example`
- **Implementation Notes:**
  - Add lines:
    ```
    # DL Verification (profiles app)
    DL_ENCRYPTION_KEY=PLACEHOLDER_KEY_REPLACE_WITH_FERNET_KEY
    DL_WEBHOOK_SECRET=PLACEHOLDER_SECRET_REPLACE_WITH_RANDOM_STRING
    DL_ADAPTER_CLASS=profiles.adapters.mock.MockDLVerificationAdapter
    DL_ADAPTER_MOCK_RESULT=verified
    DL_PROVIDER_TIMEOUT_SECONDS=5
    DL_MAX_ATTEMPTS=3
    ```
  - Add comment explaining how to generate Fernet key:
    ```
    # Generate DL_ENCRYPTION_KEY with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ```
- **Acceptance Criteria:**
  - All 6 DL_* vars present in .env.example
  - Generation instructions included
- **Tests Required:**
  - Manual: verify .env.example can be copied to .env and app starts (with real key)
- **Risk:** low
- **Status:** pending

---

### TASK-025 — Register models in admin

- **Owner:** backend-engineer
- **Goal:** Make UserProfile and DriverVerification accessible in Django Admin
- **Rationale:** Enables manual review, debugging, and support operations
- **Dependencies:** TASK-003, TASK-004
- **Affected Files:**
  - `backend/profiles/admin.py`
- **Implementation Notes:**
  - Register `UserProfile` with custom admin:
    - List display: user phone_number, active_role, onboarding_status, created_at
    - List filter: onboarding_status, active_role
    - Search: user__phone_number
    - Readonly: created_at, updated_at
  - Register `DriverVerification` with custom admin:
    - List display: user phone_number, dl_number_display (NOT full dl_number), dl_verification_status, attempt_count, created_at
    - List filter: dl_verification_status
    - Search: user__phone_number, dl_number_display
    - Readonly: dl_number, created_at, updated_at
    - Exclude dl_number from form (never show encrypted value in admin)
  - Restrict to staff only (default Django admin behavior)
- **Acceptance Criteria:**
  - `http://localhost:8000/admin/profiles/userprofile/` accessible to staff
  - `http://localhost:8000/admin/profiles/driververification/` accessible to staff
  - Full dl_number NOT visible in admin list or detail
- **Tests Required:**
  - Manual: create profile via API, verify appears in admin
  - Manual: verify encrypted dl_number not displayed
- **Risk:** low
- **Status:** pending

---

### TASK-026 — Unit tests: DL format validation

- **Owner:** test-engineer
- **Goal:** Test `validate_dl_format` function with all valid/invalid cases from AC-11
- **Rationale:** FR-07 mandates strict format validation; this is a critical security/data-quality gate
- **Dependencies:** TASK-011
- **Affected Files:**
  - `backend/profiles/tests/test_dl_verification.py` (new file)
- **Implementation Notes:**
  - Parameterized test with valid inputs:
    - `"MH01 20110012345"` → accepts
    - `"MH0120110012345"` → accepts (no space)
    - `"MH01-20110012345"` → accepts (hyphen separator)
    - `"DL14 20190001234"` → accepts (different state code)
  - Parameterized test with invalid inputs:
    - `"mh01 20110012345"` → rejects (lowercase; or normalizes to uppercase per ADR)
    - `"ABCD1234"` → rejects
    - `"MH01 201100123"` → rejects (too short)
    - `"MH01 2011001234567"` → rejects (too long)
    - `""` → rejects
  - Assert `InvalidDLFormat` raised for invalid inputs
- **Acceptance Criteria:**
  - AC-11 verified: all valid formats accepted, invalid formats rejected
- **Tests Required:**
  - 4+ valid format tests
  - 5+ invalid format tests
- **Risk:** low
- **Status:** pending

---

### TASK-027 — Unit tests: encryption/decryption

- **Owner:** test-engineer
- **Goal:** Test `encrypt_dl` and `decrypt_dl` functions
- **Rationale:** Validates encryption layer; ensures reversibility and security properties
- **Dependencies:** TASK-006
- **Affected Files:**
  - `backend/profiles/tests/test_crypto.py` (new file)
- **Implementation Notes:**
  - Test: encrypt then decrypt returns original plaintext
  - Test: encrypt same plaintext twice yields different ciphertexts (IV randomization)
  - Test: decrypt with wrong key raises `InvalidToken`
  - Test: missing `DL_ENCRYPTION_KEY` env var raises `ImproperlyConfigured`
- **Acceptance Criteria:**
  - All crypto properties verified
  - Round-trip encryption works
  - Security properties (IV randomization, key requirement) enforced
- **Tests Required:**
  - 4 unit tests
- **Risk:** low
- **Status:** pending

---

### TASK-028 — Unit tests: onboarding service

- **Owner:** test-engineer
- **Goal:** Test state machine transitions in `profiles/services/onboarding.py`
- **Rationale:** Complex state logic; errors here break entire onboarding flow
- **Dependencies:** TASK-010
- **Affected Files:**
  - `backend/profiles/tests/test_onboarding_service.py` (new file)
- **Implementation Notes:**
  - Test: `get_or_create_profile` is idempotent (second call returns existing)
  - Test: `set_role` with status != NOT_STARTED raises `RoleAlreadySet`
  - Test: `set_profile_details` with age=17 raises `InvalidAge`
  - Test: `set_profile_details` for passenger sets status=COMPLETE
  - Test: `set_profile_details` for driver sets status=AWAITING_DL
  - Test: `switch_role` from passenger to driver without DL raises `DLRequired`
  - Test: `switch_role` from driver to passenger preserves DriverVerification
  - Test: `compute_next_step` returns correct value for each state
- **Acceptance Criteria:**
  - All state transitions verified
  - Guards enforced (role_already_set, profile_already_set)
  - Age/gender/name validation enforced
- **Tests Required:**
  - 8+ unit tests
- **Risk:** medium
- **Status:** pending

---

### TASK-029 — Unit tests: DL verification service

- **Owner:** test-engineer
- **Goal:** Test `submit_dl` and `process_webhook` functions
- **Rationale:** Complex logic with encryption, adapter calls, state transitions
- **Dependencies:** TASK-011
- **Affected Files:**
  - `backend/profiles/tests/test_dl_verification.py` (append to file from TASK-026)
- **Implementation Notes:**
  - Test: `submit_dl` increments attempt_count
  - Test: `submit_dl` with attempt_count >= max raises `MaxDLAttemptsExceeded`
  - Test: `submit_dl` with adapter returning verified updates status=COMPLETE
  - Test: `submit_dl` with adapter timeout treats as pending
  - Test: `submit_dl` encrypts DL number and stores in DriverVerification
  - Test: `process_webhook` with verified status sets COMPLETE
  - Test: `process_webhook` called twice raises `AlreadyProcessed`
  - Test: `process_webhook` with rejected status sets REJECTED
- **Acceptance Criteria:**
  - Attempt counting verified
  - Encryption verified
  - Adapter integration verified (with mock adapter)
  - Webhook idempotency verified
- **Tests Required:**
  - 8+ unit tests
- **Risk:** medium
- **Status:** pending

---

### TASK-030 — Unit tests: permission classes

- **Owner:** test-engineer
- **Goal:** Test all three permission classes
- **Rationale:** Security-critical; permissions must enforce correctly
- **Dependencies:** TASK-012
- **Affected Files:**
  - `backend/profiles/tests/test_permissions.py` (new file)
- **Implementation Notes:**
  - Test: `IsOnboardingComplete` with incomplete user raises `OnboardingIncomplete`
  - Test: `IsOnboardingComplete` with complete user returns True
  - Test: `IsDriverRole` with passenger raises `NotADriver`
  - Test: `IsDriverRole` with driver returns True
  - Test: `IsDriverVerified` with unverified DL returns False
  - Test: `IsDriverVerified` with verified DL returns True
- **Acceptance Criteria:**
  - All permission logic verified
  - Errors raised correctly
- **Tests Required:**
  - 6 unit tests
- **Risk:** medium
- **Status:** pending

---

### TASK-031 — Integration tests: onboarding flow

- **Owner:** test-engineer
- **Goal:** End-to-end test of the full onboarding flow for both passenger and driver
- **Rationale:** Validates complete user journey through onboarding
- **Dependencies:** TASK-021, TASK-023
- **Affected Files:**
  - `backend/profiles/tests/test_integration_onboarding.py` (new file)
- **Implementation Notes:**
  - Passenger flow:
    - Create user via OTP (FEAT-001)
    - GET /api/onboarding/status/ → NOT_STARTED (AC-01)
    - POST /api/onboarding/role/ {role: passenger} → ROLE_SELECTED (AC-02)
    - POST /api/onboarding/profile/ {valid fields} → COMPLETE (AC-04)
    - GET /api/auth/me/ → includes onboarding_status=COMPLETE, active_role=passenger (AC-05)
  - Driver flow:
    - Same role selection
    - Profile submission → AWAITING_DL (AC-06)
    - POST /api/onboarding/driver/dl/ {valid DL, mock=verified} → COMPLETE (AC-07)
  - Test duplicate submissions (AC-03, AC-21)
- **Acceptance Criteria:**
  - AC-01, AC-02, AC-03, AC-04, AC-05, AC-06, AC-07 verified
  - Both passenger and driver flows complete successfully
- **Tests Required:**
  - 2 integration tests (passenger flow, driver flow)
  - 2 negative tests (duplicate submissions)
- **Risk:** high (covers most critical functionality)
- **Status:** pending

---

### TASK-032 — Integration tests: DL submission + webhook

- **Owner:** test-engineer
- **Goal:** Test DL submission with all result types and webhook processing
- **Rationale:** Validates async verification flow, webhook security, idempotency
- **Dependencies:** TASK-021, TASK-023
- **Affected Files:**
  - `backend/profiles/tests/test_integration_dl.py` (new file)
- **Implementation Notes:**
  - Test: DL submission with mock=pending returns 202 (AC-08)
  - Test: Webhook with verified payload updates status (AC-09)
  - Test: Webhook with rejected payload updates status (AC-10)
  - Test: Webhook with invalid signature returns 403 (AC-18)
  - Test: Duplicate webhook returns 409 (idempotency)
  - Test: DL format validation (AC-11)
  - Test: Max attempts exceeded (AC-17)
  - Test: Adapter timeout → pending (AC-19)
  - Test: Passenger calling DL endpoint raises 403 (AC-20)
- **Acceptance Criteria:**
  - AC-08, AC-09, AC-10, AC-11, AC-17, AC-18, AC-19, AC-20 verified
- **Tests Required:**
  - 9 integration tests
- **Risk:** high (security-critical webhook authentication)
- **Status:** pending

---

### TASK-033 — Integration tests: role switching

- **Owner:** test-engineer
- **Goal:** Test role switching logic (FR-22-26)
- **Rationale:** Complex DL check logic; must verify all scenarios
- **Dependencies:** TASK-021, TASK-023
- **Affected Files:**
  - `backend/profiles/tests/test_integration_role_switch.py` (new file)
- **Implementation Notes:**
  - Test: Passenger → driver without DL raises 400 dl_required (AC-22)
  - Test: User with verified DL switches to driver successfully (AC-23)
  - Test: Driver → passenger preserves DriverVerification (AC-24)
  - Test: Switch back to driver does not require DL resubmit (AC-25)
  - Test: Passenger with active_role=passenger cannot access driver endpoints (AC-26)
- **Acceptance Criteria:**
  - AC-22, AC-23, AC-24, AC-25, AC-26 verified
- **Tests Required:**
  - 5 integration tests
- **Risk:** medium
- **Status:** pending

---

### TASK-034 — Integration tests: onboarding gate

- **Owner:** test-engineer
- **Goal:** Test that `IsOnboardingComplete` permission blocks incomplete users from protected endpoints
- **Rationale:** Security gate must work correctly; FR-14 enforcement
- **Dependencies:** TASK-023, TASK-021
- **Affected Files:**
  - `backend/profiles/tests/test_integration_gate.py` (new file)
- **Implementation Notes:**
  - Create a stub protected endpoint (or use an existing one from future features)
  - Test: Incomplete user calling protected endpoint raises 403 onboarding_incomplete (AC-14)
  - Test: Complete user calling protected endpoint succeeds
  - Test: Driver in PENDING_VERIFICATION calling ride endpoint raises 403 (AC-15)
  - Test: Onboarding endpoints (status, role, profile) are NOT blocked
  - Test: Webhook endpoint is NOT blocked (AllowAny permission)
- **Acceptance Criteria:**
  - AC-14, AC-15 verified
  - Onboarding endpoints accessible to incomplete users
  - Protected endpoints gated correctly
- **Tests Required:**
  - 5 integration tests
- **Risk:** high (security gate must not have bypass)
- **Status:** pending

---

### TASK-035 — Edge case tests

- **Owner:** test-engineer
- **Goal:** Test all edge cases documented in FEAT-002 Edge Cases section
- **Rationale:** Ensures robustness under concurrent access, race conditions, and error scenarios
- **Dependencies:** TASK-031, TASK-032
- **Affected Files:**
  - `backend/profiles/tests/test_edge_cases.py` (new file)
- **Implementation Notes:**
  - Test: Concurrent role submissions (get_or_create prevents duplicate profiles) (AC-16 partially)
  - Test: UserProfile creation race (lazy creation via get_or_create)
  - Test: Webhook arrives before client receives 202 (state transitions are idempotent)
  - Test: DL number with mixed-case input (normalizes to uppercase per ADR)
  - Test: Age boundary values (age=18, age=80 accepted; age=17, age=81 rejected)
  - Test: Provider returns unrecognized status value (webhook logs error, returns 400)
  - Test: Profile resumption on different device (AC-16)
- **Acceptance Criteria:**
  - AC-16 verified (resume on different device)
  - All edge cases from FEAT-002 handled
- **Tests Required:**
  - 7+ tests
- **Risk:** medium
- **Status:** pending

---

### TASK-036 — Create OnboardingGate component

- **Owner:** frontend-engineer
- **Goal:** Create a React Native component that checks onboarding status and redirects incomplete users
- **Rationale:** Client-side enforcement of onboarding gate (UX supplement to server enforcement)
- **Dependencies:** TASK-021
- **Affected Files:**
  - `frontend/components/OnboardingGate.tsx` (new file)
- **Implementation Notes:**
  - On mount: call `GET /api/auth/me/`
  - Check `onboarding_status` field
  - If not `complete`: navigate to appropriate onboarding screen based on `next_step`
  - If `complete`: render children (main app)
  - Handle 403 responses from any API call (redirect to onboarding)
- **Acceptance Criteria:**
  - Component redirects incomplete users to onboarding
  - Component renders children for complete users
  - 403 responses trigger redirect
- **Tests Required:**
  - Unit test: incomplete user redirected
  - Unit test: complete user renders children
- **Risk:** high (critical UX flow)
- **Status:** pending

---

### TASK-037 — Create RoleSelectionScreen

- **Owner:** frontend-engineer
- **Goal:** Screen for selecting Driver or Passenger role
- **Rationale:** First onboarding step per UX flow
- **Dependencies:** TASK-021
- **Affected Files:**
  - `frontend/screens/onboarding/RoleSelectionScreen.tsx` (new file)
- **Implementation Notes:**
  - Two buttons: "Passenger" and "Rider" (maps to driver in API)
  - On selection: POST /api/onboarding/role/ with chosen role
  - On success: navigate to ProfileFormScreen
  - Map "Rider" label → "driver" value for API
- **Acceptance Criteria:**
  - Screen displays role options
  - Selection calls API and navigates on success
  - Error handling for API failures
- **Tests Required:**
  - Unit test: button press calls API with correct role
- **Risk:** medium
- **Status:** pending

---

### TASK-038 — Create ProfileFormScreen

- **Owner:** frontend-engineer
- **Goal:** Form screen for entering personal profile details
- **Rationale:** Second onboarding step
- **Dependencies:** TASK-021
- **Affected Files:**
  - `frontend/screens/onboarding/ProfileFormScreen.tsx` (new file)
- **Implementation Notes:**
  - Form fields: first_name, last_name, age, gender
  - Client-side validation: age 18-80, gender choices, name format
  - On submit: POST /api/onboarding/profile/
  - On success:
    - If passenger: navigate to main app
    - If driver: navigate to DLSubmissionScreen
  - Display validation errors from API
- **Acceptance Criteria:**
  - Form validates input
  - Successful submission navigates appropriately
  - Error messages displayed
- **Tests Required:**
  - Unit test: validation logic
  - Unit test: API call and navigation
- **Risk:** medium
- **Status:** pending

---

### TASK-039 — Create DLSubmissionScreen

- **Owner:** frontend-engineer
- **Goal:** Screen for entering and submitting driving licence number
- **Rationale:** Third onboarding step for drivers
- **Dependencies:** TASK-021
- **Affected Files:**
  - `frontend/screens/onboarding/DLSubmissionScreen.tsx` (new file)
- **Implementation Notes:**
  - Input field for DL number
  - Client-side regex validation: `^[A-Z]{2}[0-9]{2}[ -]?[0-9]{4}[0-9]{7}$`
  - On submit: POST /api/onboarding/driver/dl/
  - On 200 (verified): navigate to main app
  - On 202 (pending): navigate to DLPendingScreen
  - Display error messages (format error, max attempts, provider error)
- **Acceptance Criteria:**
  - DL input validated client-side
  - API responses handled correctly
  - Navigation based on result status
- **Tests Required:**
  - Unit test: DL format validation
  - Unit test: API call handling
- **Risk:** high (complex validation and state handling)
- **Status:** pending

---

### TASK-040 — Create DLPendingScreen

- **Owner:** frontend-engineer
- **Goal:** Screen shown while DL verification is pending; polls for result
- **Rationale:** Handles async verification flow (FR-10)
- **Dependencies:** TASK-021
- **Affected Files:**
  - `frontend/screens/onboarding/DLPendingScreen.tsx` (new file)
- **Implementation Notes:**
  - Display: "Your driving licence is being verified..."
  - Poll `GET /api/onboarding/driver/dl/status/` every 5s (exponential backoff up to 30s)
  - On status=verified: navigate to main app
  - On status=rejected: show rejection_reason, offer resubmit button → DLSubmissionScreen
  - On app close/reopen: OnboardingGate will handle resume
- **Acceptance Criteria:**
  - Polling starts on mount
  - Navigation on status change
  - Rejection reason displayed
- **Tests Required:**
  - Unit test: polling logic
  - Unit test: navigation on status change
- **Risk:** medium
- **Status:** pending

---

### TASK-041 — Create RoleSwitcher component

- **Owner:** frontend-engineer
- **Goal:** UI component for switching between driver and passenger roles
- **Rationale:** Implements FR-22-26 role switching
- **Dependencies:** TASK-021
- **Affected Files:**
  - `frontend/components/RoleSwitcher.tsx` (new file)
- **Implementation Notes:**
  - Display current active_role
  - Toggle control to switch roles
  - On toggle: PATCH /api/profile/role/ with new role
  - Handle errors (dl_required, onboarding_incomplete)
  - Display error messages
  - On success: update local state and refresh UI
- **Acceptance Criteria:**
  - Component displays current role
  - Switch calls API and updates state
  - Errors displayed
- **Tests Required:**
  - Unit test: API call on switch
  - Unit test: error handling
- **Risk:** medium
- **Status:** pending

---

### TASK-042 — Integrate onboarding gate in app navigation

- **Owner:** frontend-engineer
- **Goal:** Wire OnboardingGate into app root navigation so it checks status on every app launch
- **Rationale:** Ensures all users pass through onboarding gate
- **Dependencies:** TASK-036, TASK-037, TASK-038, TASK-039, TASK-040, TASK-041
- **Affected Files:**
  - `frontend/App.tsx` (or equivalent navigation root)
  - `frontend/navigation/index.tsx` (if separate)
- **Implementation Notes:**
  - Wrap main app navigator in `<OnboardingGate>`
  - Define onboarding stack navigator:
    - RoleSelectionScreen
    - ProfileFormScreen
    - DLSubmissionScreen
    - DLPendingScreen
  - OnboardingGate decides which navigator to render based on status
- **Acceptance Criteria:**
  - Incomplete users redirected to onboarding on app launch
  - Complete users see main app
  - Onboarding screens navigable
- **Tests Required:**
  - Integration test: app launch with incomplete user shows onboarding
  - Integration test: app launch with complete user shows main app
- **Risk:** high (critical integration point)
- **Status:** pending

---

## Critical Path

TASK-001 → TASK-002 → TASK-003 → TASK-004 → TASK-005 → TASK-006 → TASK-007 → TASK-008 → TASK-009 → TASK-010 → TASK-011 → TASK-012 → TASK-013 → TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020 → TASK-021 → TASK-022 → TASK-023 → TASK-031 → TASK-034

**Critical Path Length:** ~18 tasks (accounting for parallel view creation)

**Bottlenecks:**
- TASK-011 (DL verification service) — high risk, blocks TASK-017, TASK-019
- TASK-023 (settings update) — blocks all integration tests and frontend work
- TASK-021 (URL routing) — blocks all frontend screens

---

## Parallel Groups

| Group | Tasks | Notes |
|-------|-------|-------|
| Group A: Foundation | TASK-001, TASK-002 | Independent; can start immediately |
| Group B: Utilities | TASK-006, TASK-007, TASK-008 | All depend on TASK-002; no interdependencies |
| Group C: Service Layer | TASK-010, TASK-011 | Can develop in parallel after models exist; TASK-011 is higher risk |
| Group D: Views | TASK-014, TASK-015, TASK-016, TASK-017, TASK-018, TASK-019, TASK-020 | All depend on TASK-013; can be developed in parallel by multiple engineers |
| Group E: Integration | TASK-021, TASK-022, TASK-024, TASK-025 | After views complete; minimal interdependencies |
| Group F: Unit Tests | TASK-026, TASK-027, TASK-028, TASK-029, TASK-030 | Can start as soon as implementation tasks complete; independent of each other |
| Group G: Integration Tests | TASK-031, TASK-032, TASK-033 | After TASK-023 and TASK-021; can run in parallel |
| Group H: Frontend Screens | TASK-037, TASK-038, TASK-039, TASK-040, TASK-041 | After TASK-021; mostly independent (share API) |

**Maximum Parallelism:** 7 tasks (Group D: all views simultaneously)

---

## Rollout

### Order

1. **Phase 1: Backend Foundation** (TASK-001 through TASK-012)
   - Create app structure
   - Define models and migrations
   - Implement service layer and adapters
   - Run migrations in dev

2. **Phase 2: Backend API** (TASK-013 through TASK-021)
   - Create serializers and views
   - Wire URL routing

3. **Phase 3: Backend Integration** (TASK-022 through TASK-025)
   - Update existing code (UserSerializer, settings)
   - Register admin
   - Document env vars

4. **Phase 4: Backend Tests** (TASK-026 through TASK-035)
   - Unit tests
   - Integration tests
   - Edge case tests

5. **Phase 5: Frontend** (TASK-036 through TASK-042)
   - Create onboarding screens
   - Integrate gate into app navigation

### Feature Flag

**Recommended:** Yes

- Flag name: `ONBOARDING_GATE_ENABLED`
- Default: `False` in staging, `True` in production
- When `False`: `IsOnboardingComplete` permission is a no-op (always returns True)
- Allows backend deployment without breaking existing clients
- Coordinate flag flip with frontend release

### Migration

**Required:** Yes

- `profiles` 0001_initial migration creates `profiles_userprofile` and `profiles_driververification` tables
- Migration dependency: `('accounts', '0002_alter_otpcode_phone_number')`
- **Must run migration before deploying app code**
- Existing users have no `UserProfile` row; created lazily on first onboarding endpoint call

### Rollback

If critical issue discovered post-deployment:

1. Set `ONBOARDING_GATE_ENABLED=False` (if using feature flag)
2. OR: Remove `IsOnboardingComplete` from `DEFAULT_PERMISSION_CLASSES` in `settings.py`
3. Remove `'profiles'` from `INSTALLED_APPS`
4. Remove `include('profiles.urls')` from `config/urls.py`
5. Revert `UserSerializer` changes
6. Run `python manage.py migrate profiles zero` (drops tables)

**No data loss** on rollback (profiles data persists until migration zeroed)

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| `DL_ENCRYPTION_KEY` loss makes all DL numbers irrecoverable | **Critical** | Back up key to AWS Secrets Manager or equivalent before production; document key rotation procedure |
| OQ-01 (provider selection) blocks concrete adapter implementation | **High** | Use `MockDLVerificationAdapter` for all dev/test; provider integration is additive (no architecture change) |
| Adding `IsOnboardingComplete` to `DEFAULT_PERMISSION_CLASSES` gates all existing endpoints | **High** | Use feature flag; coordinate deployment with frontend release; ensure all non-onboarding endpoints explicitly declare `permission_classes` |
| Concurrent profile creation race | **Medium** | Handled by `get_or_create` + DB unique constraint on `UserProfile.user`; existing solution |
| DL adapter timeout leaves drivers in perpetual PENDING state | **Medium** | Acceptable for v1; polling + manual review workflow; future: Celery task to auto-escalate stale pending records |
| Frontend cannot handle 403 onboarding_incomplete responses | **High** | OnboardingGate component must handle this; include in TASK-036 acceptance criteria |

---

## Success Criteria

- All 42 tasks complete with status=complete
- All acceptance criteria from FEAT-002 verified (AC-01 through AC-26)
- Zero P0/P1 bugs in first week post-launch
- Passenger onboarding completion rate >= 80% (metric from FEAT-002)
- Driver onboarding through DL submission >= 60%
- No onboarding gate bypass incidents detected

---

## Open Questions (Inherited from FEAT-002)

- **OQ-01:** DL verification provider not yet selected — blocks concrete adapter implementation; `MockDLVerificationAdapter` used for v1
- **OQ-02:** Provider sync vs async — both paths implemented; concrete provider determines which is primary
- **OQ-04:** Webhook signature mechanism — depends on provider; mock uses `X-Mock-Signature` header
- **OQ-06:** Minimum age for Passengers — currently 18 for both roles; confirm before TASK-013
- **OQ-07:** Vehicle registration in v1 — out of scope per requirements

---

## Notes

- Migration dependency on `accounts` 0002 is critical — verify before running migrations
- `cryptography` package must be installed before any DL submission (TASK-001 is blocking)
- Settings update (TASK-023) is a breaking change — all existing endpoints now gated; coordinate with frontend
- Mock adapter is production-ready for dev/test but should NOT be used in production (provider integration required)
- Admin panel displays last-4 of DL only; full encrypted DL is never shown (security requirement)

---

**End of Plan**
