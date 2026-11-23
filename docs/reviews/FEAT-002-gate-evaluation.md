# Gate Evaluation: FEAT-002 User Onboarding Flow

**Evaluator:** workflow-controller
**Date:** 2026-10-09
**Feature:** FEAT-002
**Branch:** onboarding-BE
**Verdict:** BLOCKED

---

## Stage Checklist

| # | Stage | Artifact | Status |
|---|-------|----------|--------|
| 1 | Requirements | `docs/requirements/FEAT-002-user-onboarding.md` | PARTIAL |
| 2 | Architecture | `docs/architecture/ARCH-002-user-onboarding.md` | PASS |
| 3 | Architecture Decision Record | `docs/decisions/2026-09-23-arch-feat-002-user-onboarding.md` | PASS |
| 4 | Plan | `docs/plans/PLAN-002-user-onboarding.md` | PASS |
| 5 | Implementation | `backend/profiles/` app + modified files | PARTIAL |
| 6 | API Documentation | `docs/api/openapi-profiles.yaml` | PASS |
| 7 | Tests | `backend/profiles/tests/` | PARTIAL |
| 8 | Testing Review | `docs/reviews/FEAT-002-testing.md` | FAIL (missing) |
| 9 | Code Review | `docs/reviews/FEAT-002-code-review.md` | FAIL (missing) |
| 10 | Security Review | `docs/reviews/FEAT-002-security-review.md` | FAIL (missing) |

---

## Detailed Assessment

### 1. Requirements -- PARTIAL

**Artifact exists:** Yes
**Status in document:** `ready`
**Goal defined:** Yes
**Acceptance criteria:** 26 criteria (AC-01 through AC-26) defined
**User stories:** 11 stories (US-01 through US-11) defined

**Blocking open questions still unresolved:**

| ID | Question | Mitigated? |
|----|----------|-----------|
| OQ-01 | DL verification provider not selected | Yes -- mock adapter pattern isolates provider dependency |
| OQ-02 | Provider sync vs async support unknown | Yes -- both code paths implemented |
| OQ-04 | Webhook auth mechanism depends on provider | Yes -- mock uses signature header; concrete impl deferred |
| OQ-06 | Minimum age for passengers (18 or lower?) | Partially -- implementation uses 18 for both; product must confirm |
| OQ-07 | Vehicle registration in v1? | Yes -- listed as non-goal in requirements; architecture confirms deferred |

**Resolved blocking OQs:**

| ID | Resolution |
|----|-----------|
| OQ-10 | ADR Decision 3: Fernet symmetric encryption at rest |
| OQ-03 | ADR Decision 1: normalize lowercase to uppercase (non-blocking) |
| OQ-05 | ADR Decision 2: lazy creation via get_or_create (non-blocking) |

**Gate condition `size(artifact.open_questions[?blocking == true]) == 0` is NOT met.** Five blocking OQs remain in the requirements document (OQ-01, OQ-02, OQ-04, OQ-06, OQ-07), though all have been architecturally mitigated to allow development to proceed. The requirements document itself has not been updated to mark these as resolved or deferred.

### 2. Architecture -- PASS

**Artifact exists:** Yes (`docs/architecture/ARCH-002-user-onboarding.md`)
**Status in document:** `ready`
**Components identified:** 14 components (COMP-001 through COMP-014)
**Proposed solution:** Yes -- single `profiles` app with service layer, adapter pattern, permission classes
**Risk assessment:** 5 risks identified (RISK-001 through RISK-005)
**Alternatives considered:** 5 alternatives documented with rationale for rejection

All architecture gate conditions are met.

### 3. Architecture Decision Record -- PASS

**Artifact exists:** Yes (`docs/decisions/2026-09-23-arch-feat-002-user-onboarding.md`)
**Status:** `accepted`
**Decisions recorded:** 7 decisions covering DL normalization, profile creation timing, DL storage, onboarding gate, model placement, adapter interface, and `GET /api/auth/me/` amendment

### 4. Plan -- PASS

**Artifact exists:** Yes (`docs/plans/PLAN-002-user-onboarding.md`)
**Status in document:** `ready`
**Tasks defined:** 42 tasks (TASK-001 through TASK-042)
**All tasks have owners:** Yes (backend-engineer, test-engineer, frontend-engineer)
**Critical path identified:** Yes
**Rollout strategy defined:** Yes, with feature flag recommendation

**Note:** All 42 task statuses remain `pending` in the plan document. The plan itself has not been updated to reflect implementation progress.

### 5. Implementation -- PARTIAL

The backend implementation is substantially complete. All core files exist and are structurally correct.

**Files present and verified:**

| File | Expected | Present | Notes |
|------|----------|---------|-------|
| `backend/profiles/__init__.py` | Yes | Yes | |
| `backend/profiles/apps.py` | Yes | Yes | |
| `backend/profiles/models.py` | Yes | Yes | UserProfile + DriverVerification with correct fields |
| `backend/profiles/views.py` | Yes | Yes | All 7 views implemented |
| `backend/profiles/urls.py` | Yes | Yes | All 7 URL routes |
| `backend/profiles/services/onboarding.py` | Yes | Yes | get_or_create_profile, set_role, set_profile_details, switch_role |
| `backend/profiles/services/dl_verification.py` | Yes | Yes | submit_dl_verification, process_webhook_result |
| `backend/profiles/services/validators.py` | Yes | Yes | validate_dl_format, validate_age, validate_name |
| `backend/profiles/adapters/base.py` | Yes | Yes | DLVerificationAdapter ABC + DLVerificationResult dataclass |
| `backend/profiles/adapters/mock.py` | Yes | Yes | MockDLVerificationAdapter with 3 response modes |
| `backend/profiles/adapters/__init__.py` | Yes | Yes | Exports adapter classes |
| `backend/profiles/utils/crypto.py` | Yes | Yes | encrypt_dl_number, decrypt_dl_number, normalize_dl_number |
| `backend/profiles/permissions.py` | Yes | Yes | IsOnboardingComplete, IsDriverRole, IsDriverVerified |
| `backend/profiles/serializers.py` | Yes | Yes | 11 serializers covering all endpoints |
| `backend/profiles/exceptions.py` | Yes | Yes | 13 domain exception classes |
| `backend/profiles/admin.py` | Yes | Yes | UserProfile + DriverVerification admin |
| `backend/core/permissions.py` | Yes | Yes | ConditionalOnboardingGate with feature flag |
| `backend/profiles/migrations/0001_initial.py` | Yes | Yes | Correct dependency on accounts 0002 |
| `backend/config/settings.py` | Modified | Yes | profiles in INSTALLED_APPS, ConditionalOnboardingGate in DEFAULT_PERMISSION_CLASSES, ONBOARDING_GATE_ENABLED flag |
| `backend/config/urls.py` | Modified | Yes | `include('profiles.urls')` at `api/` prefix |
| `backend/accounts/serializers.py` | Modified | Yes | onboarding_status + active_role SerializerMethodFields added |
| `backend/requirements.txt` | Modified | Yes | cryptography==42.0.5 added |

**Deviations from architecture:**

1. **Crypto module location:** Architecture specifies `profiles/crypto.py`; implementation places it at `profiles/utils/crypto.py`. Functional behavior is identical.

2. **Missing `dl_key_version` field:** Architecture (ARCH-002) specifies a `dl_key_version` (PositiveSmallIntegerField, default 1) on `DriverVerification` for future key rotation. This field is absent from both `models.py` and the migration. Low severity for v1 but creates a gap for key rotation.

3. **Onboarding gate mechanism:** Architecture specifies adding `profiles.permissions.IsOnboardingComplete` directly to `DEFAULT_PERMISSION_CLASSES`. Implementation instead creates `core.permissions.ConditionalOnboardingGate` with a `ONBOARDING_GATE_ENABLED` feature flag. This is an improvement that aligns with the plan's recommendation (PLAN-002 Rollout section).

4. **Missing `_sanitise_rejection_reason()` function:** Architecture specifies this in `dl_verification.py`. Implementation does not include it. Rejection reasons from the provider are stored raw.

5. **Missing `profiles` logger in LOGGING config:** Architecture specifies adding a `profiles` logger to `settings.py` LOGGING config sharing the `accounts_console` handler with phone redaction. This logger entry is absent from `settings.py`. The `views.py` does use `logging.getLogger('profiles')` which will fall through to root logger, but without the phone redaction filter.

6. **DL settings not centralized in settings.py:** Architecture specifies `DL_ENCRYPTION_KEY`, `DL_WEBHOOK_SECRET`, `DL_ADAPTER_CLASS`, `DL_PROVIDER_TIMEOUT_SECONDS`, `DL_MAX_ATTEMPTS` as settings loaded in `settings.py`. Implementation loads `DL_ENCRYPTION_KEY` directly in `utils/crypto.py` via `decouple.config()` and hardcodes max attempts to 3 in `dl_verification.py`. The other DL settings are not centralized.

7. **Missing `.env.example` updates:** No `backend/.env.example` file exists. The DL-related env vars are not documented with placeholder values.

8. **`get_dl_adapter()` factory function missing:** Architecture specifies a `get_dl_adapter()` factory in `adapters/__init__.py` that loads the adapter class from `settings.DL_ADAPTER_CLASS`. Implementation hardcodes `MockDLVerificationAdapter` instantiation directly in `dl_verification.py`.

**Django system check:** I was unable to run `python manage.py check` as no shell tool is available. Based on code inspection, the app structure, migration dependencies, model definitions, and URL configuration appear correct. The migration declares the proper dependency on `accounts.0002_alter_otpcode_phone_number`.

### 6. API Documentation -- PASS

**Artifact exists:** Yes (`docs/api/openapi-profiles.yaml`)
**Format:** OpenAPI 3.0.3
**All 7 endpoints documented:**

| Endpoint | Documented |
|----------|-----------|
| `GET /api/onboarding/status/` | Yes |
| `POST /api/onboarding/role/` | Yes |
| `POST /api/onboarding/profile/` | Yes |
| `POST /api/onboarding/driver/dl/` | Yes |
| `GET /api/onboarding/driver/dl/status/` | Yes |
| `POST /api/onboarding/driver/dl/webhook/` | Yes |
| `PATCH /api/profile/role/` | Yes |

Request/response schemas, error codes, and examples are comprehensive.

### 7. Tests -- PARTIAL

**Test files exist:**

| File | Scope | Tests |
|------|-------|-------|
| `backend/profiles/tests/test_permissions.py` | Unit: 3 permission classes | 7 test methods |
| `backend/profiles/tests/test_serializers.py` | Unit: serializer validation | 12 test methods |

**Tests present cover:**
- `IsOnboardingComplete`: incomplete denied, complete allowed, no-profile denied
- `IsDriverRole`: passenger denied, driver allowed
- `IsDriverVerified`: unverified denied, verified allowed, passenger denied
- `ProfileDetailsSerializer`: valid data, age boundaries (17/18/80/81), invalid gender, all valid genders, blank name
- `DLSubmissionSerializer`: valid with space/hyphen/no-separator, lowercase normalized, invalid formats
- `RoleSelectionSerializer`: valid roles, invalid role

**Tests missing (per plan TASK-026 through TASK-035):**
- Crypto unit tests (TASK-027): encrypt/decrypt round-trip, IV randomization, wrong key, missing key
- Onboarding service unit tests (TASK-028): get_or_create idempotency, state guards, role switching logic
- DL verification service unit tests (TASK-029): submit_dl, process_webhook, attempt counting, adapter timeout
- Integration tests for onboarding flow (TASK-031)
- Integration tests for DL submission + webhook (TASK-032)
- Integration tests for role switching (TASK-033)
- Integration tests for onboarding gate (TASK-034)
- Edge case tests (TASK-035)

**Note:** Tests were intentionally skipped per user request. This is flagged as a known gap.

### 8. Testing Review -- FAIL

**No artifact found at `docs/reviews/FEAT-002-testing.md`.**
The testing stage has not been formally executed or documented.

### 9. Code Review -- FAIL

**No artifact found at `docs/reviews/FEAT-002-code-review.md`.**
The code review stage has not been executed.

### 10. Security Review -- FAIL

**No artifact found at `docs/reviews/FEAT-002-security-review.md`.**
The security review stage has not been executed. Given this feature handles PII (DL numbers), uses symmetric encryption, and exposes a webhook endpoint, a security review is strongly recommended.

---

## Blockers

| # | Blocker | Severity | Stage |
|---|---------|----------|-------|
| B-01 | Testing review artifact missing (`docs/reviews/FEAT-002-testing.md`) | High | Testing |
| B-02 | Code review artifact missing (`docs/reviews/FEAT-002-code-review.md`) | High | Code Review |
| B-03 | Security review artifact missing (`docs/reviews/FEAT-002-security-review.md`) | Critical | Security Review |
| B-04 | Blocking open questions (OQ-01, OQ-02, OQ-04, OQ-06) not formally resolved in requirements doc | Medium | Requirements |
| B-05 | Plan task statuses not updated from `pending` to `complete` | Low | Planning / Implementation |

---

## Known Gaps and Risks

| # | Gap/Risk | Severity | Notes |
|---|----------|----------|-------|
| G-01 | Missing `dl_key_version` field on DriverVerification model | Low | Blocks future encryption key rotation; can be added in a later migration |
| G-02 | Missing `_sanitise_rejection_reason()` function | Medium | Provider rejection reasons stored raw; potential XSS vector if displayed in admin or frontend |
| G-03 | Missing `profiles` logger in LOGGING config | Low | Logs fall through to root; phone redaction filter not applied to profiles logs |
| G-04 | DL settings not centralized in settings.py | Low | DL_ENCRYPTION_KEY loaded directly in crypto module; DL_MAX_ATTEMPTS hardcoded to 3 |
| G-05 | No `.env.example` with DL env var placeholders | Low | Deployment documentation gap |
| G-06 | `get_dl_adapter()` factory not implemented; adapter hardcoded | Medium | Provider swapping requires code change instead of env var change |
| G-07 | Integration and edge-case tests not written | High | Only serializer and permission unit tests exist; no end-to-end flow validation |
| G-08 | DL provider not selected (OQ-01) | High | Mock adapter sufficient for dev/test; blocks production deployment |
| G-09 | Django system check not verified | Low | Unable to run; code inspection suggests no issues |

---

## Workflow Final Gate Evaluation

| Condition | Required | Actual | Result |
|-----------|----------|--------|--------|
| `requirements.status == 'passed'` | passed | partial (blocking OQs unresolved in doc) | FAIL |
| `architecture.status == 'passed'` | passed | ready (all conditions met) | PASS |
| `planning.status == 'passed'` | passed | ready (all conditions met) | PASS |
| `implementation.status == 'passed'` | passed | partial (code present, tasks not updated, deviations) | FAIL |
| `testing.status == 'passed'` | passed | not started (no review artifact) | FAIL |
| `code_review.status == 'approved'` | approved | not started (no review artifact) | FAIL |
| `security.status == 'approved'` | approved | not started (no review artifact) | FAIL |

**Final Verdict: BLOCKED**

---

## Recommendations

### Immediate (to unblock)

1. **Run the testing stage:** Execute existing tests, write missing integration tests for the critical onboarding flows (AC-01 through AC-10, AC-14, AC-22-26), and produce `docs/reviews/FEAT-002-testing.md`.

2. **Run the code review stage:** Review all implementation files for correctness, adherence to architecture, and code quality. Produce `docs/reviews/FEAT-002-code-review.md`.

3. **Run the security review stage:** Review encryption implementation, webhook authentication, PII handling, permission enforcement, and onboarding gate bypass resistance. Produce `docs/reviews/FEAT-002-security-review.md`.

4. **Update requirements doc OQs:** Mark OQ-07 and OQ-10 as resolved. Add architectural mitigation notes to OQ-01, OQ-02, OQ-04. Get product confirmation on OQ-06 (minimum age).

5. **Update plan task statuses:** Advance completed tasks from `pending` to `complete`.

### Short-term (implementation gaps)

6. Add `dl_key_version` field to DriverVerification via a new migration.
7. Implement `_sanitise_rejection_reason()` to strip HTML and truncate before storage.
8. Add `profiles` logger to `settings.py` LOGGING config.
9. Centralize DL settings in `settings.py` (DL_MAX_ATTEMPTS, DL_PROVIDER_TIMEOUT_SECONDS).
10. Implement `get_dl_adapter()` factory for env-var-based adapter selection.
11. Create `backend/.env.example` with DL env var placeholders.

### Pre-production

12. Select DL verification provider (OQ-01) and implement concrete adapter.
13. Run `python manage.py check` to verify Django system check passes.
14. Verify migration applies cleanly on a fresh database.
