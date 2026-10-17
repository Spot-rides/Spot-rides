# Plan: Vehicle RC (Registration Certificate) Verification

**ID:** PLAN-003
**Type:** plan
**Feature:** FEAT-002
**Architecture:** ARCH-002
**Version:** 1
**Status:** draft
**Date:** 2026-10-14

> Status is `draft`, not `ready`, because this plan changes approved scope (FEAT-002 v3 lists third-party vehicle verification as a non-goal) and has unresolved product decisions (section "Open Questions Requiring a Product Decision"). It becomes `ready` after TASK-101 to TASK-103 are complete.

---

## Overview

Today a Driver self-declares a vehicle (`POST /api/onboarding/driver/vehicle/`), a `Vehicle` row is created, and onboarding becomes COMPLETE immediately. Nothing checks that the registration number belongs to a real, valid vehicle or to the driver. This plan adds an RC verification step behind a provider-agnostic adapter, exactly as DL verification was built: an abstract `RCVerificationAdapter`, a `MockRCVerificationAdapter` as the only implementation, and a service layer that depends only on the abstraction.

**Scope boundary (explicit):** the real provider adapter is OUT OF SCOPE until a provider is chosen. This mirrors the DL situation, where `DigiLockerDLVerificationAdapter` does not exist and only `MockDLVerificationAdapter` runs. Everything here is built and exercised against the mock. Provider selection is a separate follow-up plan.

**Conventions:**
- Task IDs start at TASK-101 so they do not collide with PLAN-002 (TASK-001..042).
- Tests are listed but marked **deferred** (user instruction: skip tests for now). Do not drop them from the plan.
- No code is written by this plan. Existing code facts below were verified by reading the repo on 2026-10-14.

**Totals:** 27 tasks (3 upstream doc/decision, 14 backend, 4 frontend, 1 security review, 5 tests deferred).

---

## Verified Current State (relevant to design)

- `Vehicle` has only `user`, `registration_number`, `vehicle_type`, `is_active`, timestamps. No uniqueness on `registration_number`. Index on `(user, is_active)`.
- `register_vehicle()` requires `AWAITING_VEHICLE` + DL verified + no active vehicle; creates the vehicle and sets COMPLETE. It raises bare `ValueError`, and `VehicleRegisterView` maps errors by substring matching (`'dl' in msg or 'verified' in msg` -> `DLNotVerified`). Any new message containing "verified" (e.g. "RC verified") would be mis-mapped. New code must raise domain `ApiError` subclasses directly.
- DL pattern: `DLVerificationAdapter` (ABC, `submit(dl_number, user_id)`, `validate_webhook`), `DLVerificationResult(status, reference_id, rejection_reason)`, `MockDLVerificationAdapter(response_mode=sync_verified|async_pending|sync_rejected)`.
- DL wiring gaps that RC should NOT copy: `dl_verification.py` hardcodes a module-global `_adapter = MockDLVerificationAdapter(response_mode='sync_verified')` and `views.py` imports the private `_adapter` directly; `DL_ADAPTER_CLASS` / `DL_ADAPTER_MOCK_RESULT` / `DL_MAX_ATTEMPTS` / `DL_PROVIDER_TIMEOUT_SECONDS` / `DL_WEBHOOK_SECRET` are planned in PLAN-002 but are NOT present in `config/settings.py` (only `ONBOARDING_GATE_ENABLED` exists); the attempt limit `3` is hardcoded; the adapter call runs inside `transaction.atomic`, holding a DB transaction open during the network call. RC should use a factory + settings, a named attempt limit, and make the provider call outside the write transaction.
- `next_step` maps are duplicated in `OnboardingStatusView`, `DLSubmitView`, and `ProfileSubmitView`; there is no `compute_next_step` in code despite PLAN-002. Adding a state means touching every copy unless centralised (TASK-111).
- `switch_role()` to driver with a verified DL sets `COMPLETE` regardless of whether any vehicle exists or is verified. With RC verification this is a gate bypass (see TASK-111).
- `profiles/migrations/0002_add_vehicle.py` is staged but not committed or deployed.
- There are no vehicle tests and no frontend vehicle screen. `backend/.env.example` does not exist.

---

## Part 1 - Verification Options (India)

**All provider-specific claims below (pricing, API shape, availability, field coverage, licensing) are UNVERIFIED. They come from general knowledge, not from browsing or contracts. Every one must be confirmed with the provider's current docs and a commercial conversation before commitment.**

| # | Option | What it can verify | Sync / async | Cost model | Onboarding friction | Compliance / access constraints | Fit with adapter pattern |
|---|--------|--------------------|--------------|-----------|---------------------|--------------------------------|--------------------------|
| A | Self-declaration + format regex (current) | Format only. Nothing about existence, owner, class, validity. | Sync, local | Free | Lowest (2 fields) | None | Trivial; no adapter. Not a real verification. |
| B | DigiLocker issued-document (RC fetched with user consent) | Owner name and RC details as issued, if the RC is in the user's DigiLocker. Insurance/fitness validity generally NOT in the RC document (UNVERIFIED). | Sync after a user-consent OAuth redirect | Likely low/none per fetch, but requires requester registration (UNVERIFIED) | High: user must have DigiLocker, link it, and have the RC pushed to it. Many drivers' RCs are likely not there (UNVERIFIED). | Government onboarding as a requester org; consent-based; ARCH-002 OQ-04 already chose DigiLocker for DL, so there is organisational alignment. | Poor fit for `verify(reg_no)`: needs an interactive consent flow, so the contract becomes "initiate -> redirect -> callback". Would need an adapter interface variant. |
| C | Direct Parivahan / Vahan access | Authoritative registry: owner, class, fuel, registration date, fitness, sometimes insurance/PUC. | Sync (if available) | n/a | Low | No general public API for private companies (UNVERIFIED); access is restricted to authorised channels/partners. Not realistically obtainable directly for a startup. | Would fit `verify(reg_no)` if access existed. Treat as unreachable; the aggregators in D are the practical route to the same data. |
| D | Third-party KYC / data aggregator RC-lookup API (candidates to evaluate, none confirmed: Surepass, IDfy, Signzy, Karza/Perfios, Zoop, Setu, AuthBridge) | Typically a lookup by registration number returning owner name (possibly masked on some providers - UNVERIFIED), vehicle class, fuel, maker/model, registration date, fitness-upto, insurance-upto, PUC, blacklist/NOC/hypothecation flags (field coverage varies and is UNVERIFIED). | Usually sync request/response; some may be async or flaky when the upstream registry is down (UNVERIFIED) | Typically per-call pricing, often per successful call (UNVERIFIED); volume tiers and minimum commitments to be negotiated | Low: driver enters the reg number only (already collected) | Handling third-party personal data (owner name/address) engages DPDP Act obligations: purpose limitation, consent notice, retention. Provider contract, data-processing terms, and uptime SLAs needed. Some providers may require business KYC before API access. | Excellent. Matches `verify(registration_number, user_id) -> result` and the existing sync/pending/rejected result shape. Webhook only if the provider supports async. |
| E | Manual: RC photo upload + ops review | Whatever a human checks: photo matches reg number, owner name, validity dates visible on the document. Forgery risk. | Async (hours to days) | Ops labour; storage; optional OCR cost | Higher: camera upload, wait time | Needs private object storage with access control and retention; PII images. Admin tooling for approve/reject. | Fits as an adapter that always returns `pending`, resolved by an admin action instead of a webhook. Also usable as the fallback path for D (lookup failed or name mismatch). |
| F | Hybrid: D primary, E as fallback | Combination. | Sync by default, async fallback | D per-call + occasional ops | Low for most, extra step only for exceptions | Union of D and E | Same adapter; "pending" is resolved by admin. |

### Recommendation

**Option D (aggregator RC lookup by registration number) as the target integration for v1, designed so Option E can be bolted on as the exception path later (Option F). Keep the adapter swappable.**

Why:
- It adds no onboarding friction beyond what the app already collects (registration number), which protects the 55% driver-completion target in FEAT-002.
- It verifies what actually matters for a ride platform: the vehicle exists, its class matches the declared `vehicle_type`, and (if the provider returns it) fitness/insurance are valid and the vehicle is not blacklisted.
- It matches the existing adapter contract and result states with minimal new concepts, so the mock work in this plan translates directly to any aggregator.
- DigiLocker (B) has the highest friction and an interactive flow that does not fit the current adapter shape; Parivahan direct (C) is not practically accessible; self-declaration (A) is the status quo being replaced; manual-only (E) does not scale and adds storage and ops burden before it is needed.

What is deliberately NOT decided here: which aggregator. Selection criteria for the follow-up plan: field coverage (owner name unmasked, insurance/fitness dates), success rate for two-wheelers and autos, latency and timeout behaviour, price per successful call, data-processing terms, webhook/async support, sandbox availability. All UNVERIFIED until evaluated.

The adapter contract in this plan is designed around the superset of fields an aggregator might return, with every field optional, so a provider returning fewer fields still works.

---

## Part 2 - Design Decisions (recommended; confirm via open questions)

### D1. Ownership matching policy

RC owner name vs the user's profile name (`UserProfile.first_name + last_name`; DL name is not stored, only an encrypted number).

**Recommendation: flag-for-review, never hard-reject on name alone.**
- Matching runs in the service layer, not in the adapter, so the policy is identical across providers. The adapter only returns the raw `owner_name`.
- Algorithm: normalise both names (uppercase, strip punctuation and honorifics, drop relation markers such as S/O, D/O, W/O, handle initials), then compare as token sets. Classify as `match` (all profile tokens found, allowing initial-to-full-name), `partial` (some overlap), `mismatch` (none), or `not_checked` (provider returned no owner or a masked owner that cannot be compared).
- `match` and RC otherwise valid -> verified.
- `partial` / `mismatch` / masked / missing owner -> **not rejected**. Vehicle goes to `pending` (review) with `rc_name_match` recorded; onboarding moves to PENDING_RC_VERIFICATION; staff resolve it in Django admin (approve with a note, or reject with a reason). Rationale: Indian drivers routinely drive vehicles owned by family members, fleet operators, or finance companies, so a strict rule would wrongly reject legitimate drivers, and a fuzzy auto-accept on `partial` would let through lookalike names.
- Strict rejection only for objective RC failures: not found, blacklisted, class incompatible with declared type, fitness or insurance expired (the last two only if the provider returns them AND product confirms they are blocking; see open questions).
- Stored: match classification only, plus owner name for the reviewer (see PII note in TASK-108/TASK-125).

### D2. State machine

**Add one new onboarding state: `PENDING_RC_VERIFICATION` (`pending_rc_verification`, 24 chars, fits CharField(30)); `next_step = "awaiting_rc_verification"`.** Do not fold into `AWAITING_VEHICLE`.

Reason: with only `AWAITING_VEHICLE`, "vehicle submitted, awaiting result" is indistinguishable from "vehicle not yet submitted", the endpoint's `409 vehicle_already_registered` guard conflicts with resubmission, and the client needs a distinct screen (polling) exactly like `PENDING_VERIFICATION` for DL.

```
AWAITING_VEHICLE --POST vehicle (sync verified)--------> COMPLETE
AWAITING_VEHICLE --POST vehicle (pending/review/timeout)-> PENDING_RC_VERIFICATION
AWAITING_VEHICLE --POST vehicle (sync rejected)--------> AWAITING_VEHICLE  (rc status=rejected, reason shown, resubmit allowed)
PENDING_RC_VERIFICATION --webhook/admin verified-------> COMPLETE
PENDING_RC_VERIFICATION --webhook/admin rejected-------> AWAITING_VEHICLE  (resubmit allowed, attempts permitting)
```

- Rejected RC returns the driver to `AWAITING_VEHICLE` (not a terminal state) so they can correct a typo or enter a different vehicle.
- Resubmission while a vehicle is `rejected` updates the same `Vehicle` row in place (keeps `rc_attempt_count`, prevents attempt-limit evasion by re-registering; v1 still allows exactly one active vehicle, FR-30).
- Submitting while `PENDING_RC_VERIFICATION` returns `409 rc_verification_pending`.
- Attempt limit: `RC_MAX_ATTEMPTS` (default 3, product to confirm), checked before the provider call; exceeding returns `429 max_rc_attempts_exceeded`. Recovery after the limit is a staff action in admin (reset attempts / manually approve).
- A provider timeout is treated as `pending` (same as DL). A non-timeout adapter exception returns `422 rc_verification_provider_error` and does NOT consume an attempt.
- Feature flag `RC_VERIFICATION_ENABLED` (default False): when False, `register_vehicle()` behaves exactly as today (self-declare -> COMPLETE) and new Vehicle rows have `rc_verification_status = NULL`.
- `switch_role` to driver must derive the target status from DL **and** vehicle state instead of hardcoding COMPLETE (TASK-111). `PENDING_RC_VERIFICATION` is treated like `PENDING_VERIFICATION` for the "user may switch to passenger" exception.
- `IsOnboardingComplete` already gates on `COMPLETE` only, so the new state is gated with no change.

### D3. Mock behaviour (mirrors `MockDLVerificationAdapter`)

`MockRCVerificationAdapter(response_mode=...)`, configured through `RC_ADAPTER_MOCK_RESULT`:

| Mode | Result |
|------|--------|
| `sync_verified` (default) | `verified`, reference id `mock-rc-<8hex>`, `owner_name` = the user's profile name (looked up via `user_id`, mock-only), plausible class/fuel, fitness and insurance dates one year ahead |
| `sync_verified_name_mismatch` | `verified` by the provider but `owner_name = "MOCK OTHER OWNER"`, so the service flags the vehicle for review (exercises D1) |
| `async_pending` | `pending` with reference id |
| `sync_rejected` | `rejected`, `rejection_reason = "Mock rejection for testing"` |
| `timeout` | raises `TimeoutError` (exercises the pending-on-timeout path) |
| `provider_error` | raises a generic exception (exercises 422 path) |

`validate_webhook` uses an `X-Mock-Signature` header compared to `RC_WEBHOOK_SECRET`, constant-time compare (improvement over the DL mock's plain `==`).

### D4. Data model (Vehicle additions, migration 0003)

All new columns nullable or defaulted so existing rows and the migration are safe.

| Field | Type | Notes |
|-------|------|-------|
| `rc_verification_status` | CharField(20), null, choices `pending`/`verified`/`rejected` | NULL = never verified (legacy/self-declared or flag off) |
| `rc_verification_ref` | CharField(100), null | Provider reference; partial unique constraint when not null (mirrors `uq_dl_verification_ref`) |
| `rc_submitted_at` | DateTimeField, null | |
| `rc_verified_at` | DateTimeField, null | |
| `rc_rejection_reason` | TextField, null | Sanitised, max 500 chars (reuse DL sanitiser) |
| `rc_attempt_count` | PositiveSmallIntegerField, default 0 | Per-vehicle row, which is reused on resubmit |
| `rc_owner_name` | CharField(100), null | PII; staff-only visibility; retention per open question OQ-R7 |
| `rc_name_match` | CharField(15), null, choices `match`/`partial`/`mismatch`/`not_checked` | |
| `rc_vehicle_class` | CharField(50), null | Provider's class string; compared against declared `vehicle_type` through a mapping in the service |
| `rc_fuel_type` | CharField(30), null | |
| `rc_fitness_valid_upto` | DateField, null | |
| `rc_insurance_valid_upto` | DateField, null | |

- Add `UserProfile.PENDING_RC_VERIFICATION` to the choices (AlterField only; no data change).
- Add a non-unique index on `registration_number` (lookups, duplicate detection) and an index on `rc_verification_status`.
- No raw provider payload is stored (data minimisation).

**Uniqueness of `registration_number`: recommendation is NO hard unique constraint in v1; add a plain index plus a duplicate flag in admin.** In India, one commercial vehicle is commonly driven by multiple drivers (shifts, fleet owners, family), so a hard unique constraint would block legitimate drivers and create support load. Instead: log `onboarding.vehicle.duplicate_registration` (WARNING) and show a "also registered by N other drivers" indicator in admin for reviewers. If product wants exclusivity later, the upgrade path is a partial unique constraint on `(registration_number) WHERE is_active AND rc_verification_status='verified'`. RISK-006 is updated, not closed. Needs product confirmation (OQ-R4).

### D5. Existing (grandfathered) drivers

Drivers already COMPLETE without a Vehicle, or with a legacy unverified Vehicle, must **not** be moved back to `AWAITING_VEHICLE` or any non-COMPLETE state: that would trip the global `IsOnboardingComplete` gate and lock them out of the app.

**Recommendation: two phases.**
- Phase 1 (this plan, always on): grandfather them untouched. They stay COMPLETE; their vehicle (if any) has `rc_verification_status = NULL`. No migration backfill.
- Phase 2 (optional, behind its own flag, blocked on product decision OQ-R5): a post-onboarding endpoint `POST /api/driver/vehicle/verify/` that lets a COMPLETE driver add or verify a vehicle without changing `onboarding_status`, plus a non-blocking in-app banner. Any hard enforcement (e.g. "cannot accept rides without a verified vehicle") belongs to the future ride feature as a separate permission (`IsVehicleVerified`), not to onboarding. Enforcement deadline is a product decision.

### D6. Error codes (new)

| HTTP | `error_code` | When |
|------|--------------|------|
| 400 | `invalid_registration_format` | existing, unchanged |
| 409 | `rc_verification_pending` | submit while PENDING_RC_VERIFICATION |
| 409 | `rc_already_verified` | submit when the vehicle is already verified |
| 422 | `rc_verification_provider_error` | adapter raised a non-timeout error |
| 429 | `max_rc_attempts_exceeded` | attempt limit reached |
| 403 | `invalid_webhook_signature` | existing exception reused |
| 409 | `already_processed` | existing exception reused (webhook idempotency) |

Rejected RC is a normal 200 response with `rc_verification_status = "rejected"` and `rejection_reason`, not an error (same convention as DL).

---

## Open Questions Requiring a Product Decision

These are NOT assumed in the tasks; implementation of the affected tasks is gated on the answers (defaults shown are only what the plan will build against if the product owner has no preference).

| ID | Question | Plan default if undecided | Blocks |
|----|----------|---------------------------|--------|
| OQ-R1 | Is RC verification a must-have for launch, or can the self-declared flow ship first with RC verification flagged off? | Ship flagged off (`RC_VERIFICATION_ENABLED=False`) | TASK-111 rollout order |
| OQ-R2 | Name-mismatch policy: flag-for-review (recommended), hard reject, or accept silently? What evidence should a driver supply for a family/fleet-owned vehicle (nothing, a text note, an uploaded authorisation letter)? | Flag-for-review, admin resolves, no upload in v1 | TASK-109, TASK-110, TASK-115 |
| OQ-R3 | Are expired insurance or expired fitness blocking rejections, or only informational? (Only applicable if the chosen provider returns them.) | Informational only; stored, not enforced | TASK-110 |
| OQ-R4 | Should one registration number be exclusive to one driver (hard unique), or may several drivers share a vehicle (recommended)? | Shared allowed, duplicate flagged in admin | TASK-106 |
| OQ-R5 | Are grandfathered drivers required to verify, by when, and is a banner enough? | No enforcement, no prompt in v1 | TASK-117, TASK-121 |
| OQ-R6 | Attempt limit and recovery: `RC_MAX_ATTEMPTS = 3` ok? Who unlocks a driver after the limit (support via admin)? Time-boxed auto-reject for stale pending (cf. OQ-09 for DL)? | 3 attempts, admin unlock, no auto-reject | TASK-107, TASK-110 |
| OQ-R7 | Is storing the RC owner's name acceptable (DPDP Act implications), and for how long? Alternative: store only the match result and discard the name. | Store for reviewer use, staff-only, retention TBD by security-reviewer | TASK-106, TASK-125 |
| OQ-R8 | Which `vehicle_type` values are compatible with which RC vehicle classes (e.g. SUV/HATCHBACK/SEDAN all map to "motor car"; AUTO_RICKSHAW; BIKE)? Is a class mismatch a rejection? | Mapping table in service; mismatch = reject | TASK-110 |
| OQ-R9 | Is a manual RC photo upload (Option E) wanted as the exception path now, or only after a provider is chosen? | Later; v1 exceptions are resolved by admin without documents | scope of TASK-115 |
| OQ-R10 | Provider selection (budget, volume, data-processing terms). | Out of scope; mock only | follow-up plan |
| OQ-R11 | Commercial/permit vehicles: do taxis need additional proof (e.g. commercial permit, yellow/black plates) beyond the RC? | Out of scope for v1 | requirements revision |

---

## Tasks

| ID | Title | Owner | Depends On | Risk | Status |
|----|-------|-------|-----------|------|--------|
| TASK-101 | Product decisions on OQ-R1..R11 | product-manager | - | high | pending |
| TASK-102 | Revise FEAT-002 requirements (v4) for RC verification | product-manager | TASK-101 | medium | pending |
| TASK-103 | Revise ARCH-002 (v3) + ADR for RC verification | architect | TASK-101, TASK-102 | medium | done (ARCH-002 v3, 2026-10-15) |
| TASK-104 | `RCVerificationResult` + `RCVerificationAdapter` ABC + factory | backend-engineer | TASK-103 | low | pending |
| TASK-105 | `MockRCVerificationAdapter` | backend-engineer | TASK-104 | low | pending |
| TASK-106 | Vehicle RC fields, new onboarding state, migration 0003 | backend-engineer | TASK-103 | high | pending |
| TASK-107 | Settings and env placeholders | backend-engineer | TASK-104 | low | pending |
| TASK-108 | RC domain exceptions | backend-engineer | TASK-103 | low | pending |
| TASK-109 | Owner-name matching and vehicle-class mapping utilities | backend-engineer | TASK-103 | medium | pending |
| TASK-110 | RC verification service layer | backend-engineer | TASK-105, TASK-106, TASK-107, TASK-108, TASK-109 | high | pending |
| TASK-111 | Rework `register_vehicle`, centralise `next_step`, fix `switch_role` | backend-engineer | TASK-110 | high | pending |
| TASK-112 | RC serializers | backend-engineer | TASK-106, TASK-108 | medium | pending |
| TASK-113 | Views: update `VehicleRegisterView`, add status and webhook views | backend-engineer | TASK-110, TASK-111, TASK-112 | high | pending |
| TASK-114 | URL routing for RC endpoints | backend-engineer | TASK-113 | low | pending |
| TASK-115 | Admin: RC fields, duplicate flag, review actions | backend-engineer | TASK-106, TASK-110 | medium | pending |
| TASK-116 | OpenAPI + API README updates | backend-engineer | TASK-114 | low | pending |
| TASK-117 | (Optional, blocked) post-onboarding verify endpoint for grandfathered drivers | backend-engineer | TASK-110, TASK-114, OQ-R5 | medium | blocked |
| TASK-118 | Frontend: `VehicleRegistrationScreen` | frontend-engineer | TASK-114 | medium | pending |
| TASK-119 | Frontend: `RCPendingScreen` with polling and rejection handling | frontend-engineer | TASK-114 | medium | pending |
| TASK-120 | Frontend: `OnboardingGate` / navigation `next_step` handling for vehicle states | frontend-engineer | TASK-118, TASK-119 | high | pending |
| TASK-121 | (Optional, blocked) Frontend: grandfathered-driver verify banner | frontend-engineer | TASK-117, OQ-R5 | low | blocked |
| TASK-122 | Unit tests: name matching, class mapping, RC validators (DEFERRED) | test-engineer | TASK-109 | low | pending |
| TASK-123 | Unit tests: mock RC adapter and factory (DEFERRED) | test-engineer | TASK-105 | low | pending |
| TASK-124 | Unit tests: RC service and state machine (DEFERRED) | test-engineer | TASK-110, TASK-111 | medium | pending |
| TASK-125 | Security review: RC PII storage, webhook, admin exposure | security-reviewer | TASK-113, TASK-115 | medium | pending |
| TASK-126 | Integration tests: vehicle endpoints, webhook, flag-off regression (DEFERRED) | test-engineer | TASK-114 | high | pending |
| TASK-127 | Integration + migration tests: switch_role, gate, in-flight and legacy data (DEFERRED) | test-engineer | TASK-114, TASK-106 | high | pending |

Note: the Totals line in Overview counts 29; the table lists 27 tasks (TASK-101..127). Authoritative count is **27**.

---

## Task Details

### TASK-101 - Product decisions on OQ-R1..R11
- **Owner:** product-manager
- **Goal:** Obtain answers to the open questions above from the user/product owner and record them.
- **Rationale:** The plan changes approved scope and several behaviours (mismatch policy, uniqueness, grandfathering, PII retention) are product calls.
- **Dependencies:** none
- **Affected files:** `docs/decisions/2026-10-14-rc-verification-product-decisions.md` (new; per CLAUDE.md convention)
- **Implementation notes:** Present options with the plan defaults. Record each decision with date and rationale.
- **Acceptance criteria:** OQ-R1, R2, R3, R4, R6, R7, R8 answered (R5, R9, R10, R11 may be deferred explicitly); decision file exists.
- **Testing:** n/a
- **Risk:** high (blocks everything downstream)
- **Status:** pending

### TASK-102 - Revise FEAT-002 requirements (v4) for RC verification
- **Owner:** product-manager
- **Goal:** Update the approved requirement so RC verification is in scope.
- **Rationale:** Current text explicitly excludes it, so building it silently would contradict an approved artifact.
- **Dependencies:** TASK-101
- **Affected files:** `docs/requirements/FEAT-002-user-onboarding.md`
- **Implementation notes:**
  - Remove/revise Non-Goals line "Third-party verification of vehicle registration numbers (format validation and self-declaration only in v1)".
  - Revise Assumptions line "No third-party verification of vehicle registration numbers is performed in v1" and the Edge Case "Duplicate vehicle registration number across users" (per OQ-R4).
  - Revise FR-27 (success no longer always sets `complete`; it depends on verification result) and FR-30 interplay with resubmission after rejection.
  - Add FRs (suggested numbering FR-32 onward): RC verification via provider adapter; owner-name match policy; new `pending_rc_verification` state and `awaiting_rc_verification` next step; status endpoint; webhook endpoint with signature validation; attempt limit and error codes (D6); sync/pending/rejected handling; provider timeout treated as pending; feature flag behaviour; grandfathering statement; PII handling for RC owner data.
  - Add ACs (suggested AC-31 onward): sync verified -> complete; pending -> 202 + `pending_rc_verification`; rejected -> stays `awaiting_vehicle` with reason; name mismatch -> pending review; attempt limit -> 429; resubmit while pending -> 409; webhook valid/invalid/duplicate; flag off = legacy behaviour; grandfathered driver unaffected; switch_role cannot bypass RC gate.
  - Add `next_step` value `awaiting_rc_verification` to the documented list; add Open Questions from this plan; add success metric for RC verification pass rate.
  - Bump version to 4 and note the change in a changelog line.
- **Acceptance criteria:** Non-goal line removed or reworded; every FR has at least one AC; schema-valid frontmatter retained.
- **Testing:** n/a
- **Risk:** medium
- **Status:** pending

### TASK-103 - Revise ARCH-002 (v3) + ADR for RC verification
- **Owner:** architect
- **Goal:** Record the architectural additions and decisions.
- **Rationale:** New state, adapter, model fields, endpoints, and a reversal of ADR Decision 8 notes ("no third-party verification, duplicates allowed").
- **Dependencies:** TASK-101, TASK-102
- **Affected files:** `docs/architecture/ARCH-002-user-onboarding.md`, `docs/decisions/2026-10-14-rc-verification.md` (new)
- **Implementation notes:**
  - Add: `RCVerificationAdapter` interface and result contract; `PENDING_RC_VERIFICATION` state and transition table (D2); Vehicle field table (D4); migration 0003 and whether to squash into unmerged 0002; new endpoints (`GET .../vehicle/status/`, `POST .../vehicle/rc/webhook/`, behaviour change of `POST .../vehicle/`); error codes (D6); observability events (`onboarding.rc.submitted|verified|rejected|pending|name_mismatch|provider_error`); security section for RC owner PII and webhook.
  - Decide and document: provider call outside the DB write transaction; service raises `ApiError` subclasses (no `ValueError` string sniffing); `switch_role` derivation fix; update RISK-005 and RISK-006; add new risks from this plan.
  - Ratify the ownership-match policy (D1) and uniqueness outcome (OQ-R4).
  - State explicitly that the real provider adapter is out of scope until OQ-R10 is resolved.
- **Acceptance criteria:** ARCH-002 version 3 consistent with requirements v4; ADR file created.
- **Testing:** n/a
- **Risk:** medium
- **Status:** done

### TASK-104 - `RCVerificationResult` + `RCVerificationAdapter` ABC + factory
- **Owner:** backend-engineer
- **Goal:** Define the provider-agnostic RC contract.
- **Rationale:** Isolates provider specifics; same role as `DLVerificationAdapter`.
- **Dependencies:** TASK-103
- **Affected files:** `backend/profiles/adapters/base.py`, `backend/profiles/adapters/__init__.py`
- **Implementation notes:**
  - `@dataclass RCVerificationResult`: `status` ('verified'|'pending'|'rejected'), `reference_id: Optional[str]`, `rejection_reason: Optional[str]`, `owner_name`, `vehicle_class`, `fuel_type` (all Optional[str]), `fitness_valid_upto`, `insurance_valid_upto` (Optional[date]). Every provider-derived field optional.
  - `RCVerificationAdapter(ABC)`: `verify(registration_number: str, user_id: int) -> RCVerificationResult` (raises `TimeoutError` on timeout) and `validate_webhook(headers: dict, body: bytes) -> bool`.
  - `get_rc_adapter()` factory in `adapters/__init__.py` loading `settings.RC_ADAPTER_CLASS` via `import_string` and passing `RC_ADAPTER_MOCK_RESULT` to the mock. Do not use a module-level global and do not import a private `_adapter` into views (unlike DL); provide `set_rc_adapter()` or settings override for tests.
- **Acceptance criteria:** ABC cannot be instantiated; factory returns the mock by default; no import cycles.
- **Testing (deferred, TASK-123):** ABC instantiation raises TypeError; factory returns configured class.
- **Risk:** low
- **Status:** pending

### TASK-105 - `MockRCVerificationAdapter`
- **Owner:** backend-engineer
- **Goal:** Mock implementing every mode in D3 without external calls.
- **Rationale:** The only adapter until a provider is chosen (mirrors DL).
- **Dependencies:** TASK-104
- **Affected files:** `backend/profiles/adapters/mock.py`
- **Implementation notes:** Modes `sync_verified`, `sync_verified_name_mismatch`, `async_pending`, `sync_rejected`, `timeout`, `provider_error`. In `sync_verified`, look up the user's profile name via `user_id` so the name-match path yields `match`. Unknown mode falls back to `sync_verified` with a logged warning (DL mock silently falls back; log it). `validate_webhook` uses `hmac.compare_digest`. Docstring must state it is dev/test only and must not run in production.
- **Acceptance criteria:** Each mode returns the documented result; webhook signature check works.
- **Testing (deferred, TASK-123):** one test per mode, signature true/false.
- **Risk:** low
- **Status:** pending

### TASK-106 - Vehicle RC fields, new onboarding state, migration 0003
- **Owner:** backend-engineer
- **Goal:** Persist RC verification state.
- **Rationale:** D4.
- **Dependencies:** TASK-103
- **Affected files:** `backend/profiles/models.py`, `backend/profiles/migrations/0003_vehicle_rc_verification.py` (generated)
- **Implementation notes:**
  - Add fields per D4 plus choices constants on `Vehicle`.
  - Add `PENDING_RC_VERIFICATION = 'pending_rc_verification'` to `UserProfile` choices.
  - Indexes: `registration_number`, `rc_verification_status`. Partial `UniqueConstraint` on `rc_verification_ref` where not null (name `uq_vehicle_rc_verification_ref`).
  - No unique constraint on `registration_number` unless OQ-R4 says otherwise (then partial unique on verified+active).
  - Migration depends on `0002_add_vehicle`; coordinate with architect on squashing if 0002 was never applied outside dev. No data migration; legacy rows stay NULL.
  - Update `Vehicle.__str__`? Leave unchanged.
- **Acceptance criteria:** `makemigrations --check` clean; migration applies on a DB containing legacy `Vehicle` rows; reversible.
- **Testing (deferred, TASK-127):** migrate forward/back with seeded legacy vehicle; constraint on ref.
- **Risk:** high (schema; interacts with unmerged 0002)
- **Status:** pending

### TASK-107 - Settings and env placeholders
- **Owner:** backend-engineer
- **Goal:** Add RC configuration surface.
- **Rationale:** Adapter selection and limits must be config, not code.
- **Dependencies:** TASK-104
- **Affected files:** `backend/config/settings.py`, `backend/.env.example` (does not exist; create it, and include the existing DL and ONBOARDING_GATE entries only if they are missing so the file is coherent)
- **Implementation notes:** Add with defaults:
  ```
  RC_VERIFICATION_ENABLED=False
  RC_ADAPTER_CLASS=profiles.adapters.mock.MockRCVerificationAdapter
  RC_ADAPTER_MOCK_RESULT=sync_verified
  RC_PROVIDER_TIMEOUT_SECONDS=5
  RC_MAX_ATTEMPTS=3
  RC_WEBHOOK_SECRET=PLACEHOLDER_SECRET_REPLACE_WITH_RANDOM_STRING
  ```
  Webhook secret has no default in production (fail fast when flag enabled and class is not the mock). Add a startup check that refuses `RC_ADAPTER_CLASS` = mock when `DEBUG=False` and `RC_VERIFICATION_ENABLED=True`. Note in the PR that the DL equivalents are also missing from settings (existing gap, not fixed here).
- **Acceptance criteria:** `manage.py check` passes with no new env vars set; flag defaults off.
- **Testing:** manual check.
- **Risk:** low
- **Status:** pending

### TASK-108 - RC domain exceptions
- **Owner:** backend-engineer
- **Goal:** Add exceptions for D6 codes.
- **Rationale:** Stable error codes in the API envelope.
- **Dependencies:** TASK-103
- **Affected files:** `backend/profiles/exceptions.py`
- **Implementation notes:** `RCVerificationPending` (409), `RCAlreadyVerified` (409), `RCProviderError` (422), `MaxRCAttemptsExceeded` (429); reuse `AlreadyProcessed`, `InvalidWebhookSignature`, `DLNotVerified`, `VehicleAlreadyRegistered`.
- **Acceptance criteria:** Each has correct `status_code`/`error_code`.
- **Testing (deferred):** covered in TASK-124/126.
- **Risk:** low
- **Status:** pending

### TASK-109 - Owner-name matching and vehicle-class mapping utilities
- **Owner:** backend-engineer
- **Goal:** Pure functions implementing D1 and OQ-R8.
- **Rationale:** Policy lives outside adapters so it is provider-independent and unit-testable.
- **Dependencies:** TASK-103
- **Affected files:** `backend/profiles/services/rc_matching.py` (new)
- **Implementation notes:** `classify_owner_match(profile_first, profile_last, rc_owner) -> 'match'|'partial'|'mismatch'|'not_checked'` (normalisation: casefold/upper, strip punctuation and honorifics, remove S/O D/O W/O tails, initial-vs-full-name matching, detect masked names containing `*` or `X` runs as `not_checked`); `is_class_compatible(declared_vehicle_type, rc_vehicle_class) -> Optional[bool]` (None when class unknown). No third-party fuzzy library required; avoid adding dependencies.
- **Acceptance criteria:** Deterministic, no DB access, handles None inputs.
- **Testing (deferred, TASK-122):** parametrised names including initials, relation suffixes, masked, empty.
- **Risk:** medium (policy edge cases)
- **Status:** pending

### TASK-110 - RC verification service layer
- **Owner:** backend-engineer
- **Goal:** Implement submit, status, and webhook processing for RC.
- **Rationale:** Business logic outside views; mirrors `dl_verification.py` but fixes its wiring gaps.
- **Dependencies:** TASK-105, TASK-106, TASK-107, TASK-108, TASK-109
- **Affected files:** `backend/profiles/services/rc_verification.py` (new)
- **Implementation notes:**
  - `submit_rc_verification(user, vehicle) -> dict`:
    1. Short transaction with `select_for_update` on the profile and vehicle: check state is `AWAITING_VEHICLE`; vehicle not already verified (`RCAlreadyVerified`); not pending (`RCVerificationPending`); `rc_attempt_count < RC_MAX_ATTEMPTS` (`MaxRCAttemptsExceeded`).
    2. Release the transaction, call `get_rc_adapter().verify(...)`, enforcing `RC_PROVIDER_TIMEOUT_SECONDS`. `TimeoutError` -> treat as pending. Other exception -> `RCProviderError`, attempt not consumed.
    3. New short transaction to persist: increment attempt, store provider fields, run `classify_owner_match` and `is_class_compatible`, then decide:
       - provider `verified` + name `match` + class compatible/unknown -> vehicle verified, profile COMPLETE.
       - provider `verified` + name not `match` -> vehicle `pending` (review), profile PENDING_RC_VERIFICATION, event `name_mismatch`.
       - provider `pending` -> vehicle pending, profile PENDING_RC_VERIFICATION.
       - provider `rejected` or class incompatible -> vehicle rejected with sanitised reason, profile stays AWAITING_VEHICLE.
    4. Log structured events; never log full owner name (log match classification only).
  - `get_vehicle_rc_status(user) -> dict`.
  - `process_rc_webhook(reference_id, status, rejection_reason)`: lookup by `rc_verification_ref`; idempotent (terminal state raises `AlreadyProcessed` so the view returns 409, unlike DL's silent True); on verified apply the same name/class decision; transitions per D2.
  - `resolve_rc_review(vehicle, approve: bool, reason, staff_user)` used by admin (TASK-115); same state transitions, writes audit log line.
  - Provider-derived `rejection_reason` is sanitised/truncated (reuse the DL sanitiser if present, otherwise add one).
- **Acceptance criteria:** All D2 transitions implemented; provider call is not inside the write transaction; attempts counted per D2; no `ValueError` string protocol.
- **Testing (deferred, TASK-124):** each mock mode, attempt limit, timeout -> pending, provider error does not consume attempt, webhook idempotency, review resolution, concurrent double-submit.
- **Risk:** high
- **Status:** pending

### TASK-111 - Rework `register_vehicle`, centralise `next_step`, fix `switch_role`
- **Owner:** backend-engineer
- **Goal:** Integrate RC step into existing onboarding service and remove duplicated state maps.
- **Rationale:** `register_vehicle` currently completes onboarding itself; `switch_role` can set COMPLETE without a verified vehicle; three views hold copies of `next_step` maps.
- **Dependencies:** TASK-110
- **Affected files:** `backend/profiles/services/onboarding.py`, `backend/profiles/views.py` (map call sites only)
- **Implementation notes:**
  - `register_vehicle`: validate/normalise, create the `Vehicle` (or update the existing `rejected` row in place on resubmit, replacing registration number and type), then if `RC_VERIFICATION_ENABLED` delegate to `submit_rc_verification`; if disabled keep legacy behaviour (set COMPLETE, `rc_verification_status` NULL). Raise `ApiError` subclasses instead of `ValueError`. Return `(profile, vehicle)` plus the RC outcome.
  - Add a single `NEXT_STEP_BY_STATUS` mapping (including `PENDING_RC_VERIFICATION -> 'awaiting_rc_verification'`) and `compute_next_step(profile)` in the service; replace the three view-local maps.
  - `switch_role` to driver: compute target status from DL and vehicle state (DL verified + vehicle verified or legacy NULL-with-flag-off/grandfathered -> COMPLETE; DL verified + no vehicle -> AWAITING_VEHICLE; vehicle pending -> PENDING_RC_VERIFICATION). Treat `PENDING_RC_VERIFICATION` like `PENDING_VERIFICATION` for the switch-to-passenger exception. Confirm with architect whether a grandfathered COMPLETE driver without a vehicle may switch passenger -> driver and stay COMPLETE (recommended: yes, D5).
  - Duplicate registration: log WARNING `onboarding.vehicle.duplicate_registration` with count only.
- **Acceptance criteria:** Flag off -> byte-for-byte legacy response shape and state; flag on -> D2 transitions; `switch_role` cannot yield COMPLETE for a driver with a rejected/pending vehicle; one `next_step` source of truth.
- **Testing (deferred, TASK-124/127):** flag-off regression, switch_role matrix, next_step for all 7 states.
- **Risk:** high (touches live state machine; in-flight drivers)
- **Status:** pending

### TASK-112 - RC serializers
- **Owner:** backend-engineer
- **Goal:** Request/response contracts.
- **Rationale:** Consistent API envelope and docs.
- **Dependencies:** TASK-106, TASK-108
- **Affected files:** `backend/profiles/serializers.py`
- **Implementation notes:** Extend `VehicleRegistrationResponseSerializer` with `rc_verification_status`, `rejection_reason`, and `reference_id` (nullable); add `VehicleStatusSerializer` (`onboarding_status`, `next_step`, `rc_verification_status`, `rejection_reason`, `registration_number`, `vehicle_type`, `rc_attempts_remaining`); add `RCWebhookPayloadSerializer` (`reference_id`, `status` in verified|rejected, optional `rejection_reason`). Do not expose `rc_owner_name`, class, or dates to the driver beyond what product approves (default: expose none of the owner data).
- **Acceptance criteria:** Existing fields unchanged (additive only).
- **Testing (deferred, TASK-126):** serializer shape.
- **Risk:** medium
- **Status:** pending

### TASK-113 - Views: update `VehicleRegisterView`, add status and webhook views
- **Owner:** backend-engineer
- **Goal:** Expose the RC flow over HTTP.
- **Rationale:** FR additions in TASK-102.
- **Dependencies:** TASK-110, TASK-111, TASK-112
- **Affected files:** `backend/profiles/views.py`
- **Implementation notes:**
  - `VehicleRegisterView.post`: 200 when COMPLETE (verified or flag off), 202 when PENDING_RC_VERIFICATION, 200 with `rc_verification_status="rejected"` and `next_step="vehicle_registration"` on sync rejection. Remove `ValueError` substring mapping for vehicle errors.
  - `VehicleStatusView`: `GET /api/onboarding/driver/vehicle/status/`, `[IsAuthenticated, IsDriverRole]`, explicitly not gated by `IsOnboardingComplete`.
  - `RCWebhookView`: `AllowAny`, `authentication_classes = []`, validates signature via `get_rc_adapter().validate_webhook` BEFORE any DB access or payload parsing, then `process_rc_webhook`; 409 on duplicate.
- **Acceptance criteria:** Behaviour matches D2/D6; webhook rejects bad signature with 403 and no state change; pending driver can poll status.
- **Testing (deferred, TASK-126):** all of the above.
- **Risk:** high (security-sensitive webhook; response contract change)
- **Status:** pending

### TASK-114 - URL routing for RC endpoints
- **Owner:** backend-engineer
- **Goal:** Wire new routes.
- **Rationale:** Make endpoints reachable.
- **Dependencies:** TASK-113
- **Affected files:** `backend/profiles/urls.py`
- **Implementation notes:** `onboarding/driver/vehicle/status/` and `onboarding/driver/vehicle/rc/webhook/`. All under the existing `/api/` prefix.
- **Acceptance criteria:** Routes resolve; unauthenticated status call returns 401; webhook reachable without JWT.
- **Testing (deferred, TASK-126):** route resolution.
- **Risk:** low
- **Status:** pending

### TASK-115 - Admin: RC fields, duplicate flag, review actions
- **Owner:** backend-engineer
- **Goal:** Let staff see and resolve RC reviews.
- **Rationale:** With no provider and with name-mismatch flagging, admin is the resolution path for `pending` vehicles and for attempt-limit unlocks.
- **Dependencies:** TASK-106, TASK-110
- **Affected files:** `backend/profiles/admin.py`
- **Implementation notes:** Vehicle list: registration number, user phone, type, `rc_verification_status`, `rc_name_match`, `rc_attempt_count`; filters on status and name match; search by registration number; read-only RC fields; computed "other drivers with same registration" count; actions "Approve RC (review)", "Reject RC (review)" calling `resolve_rc_review`, and "Reset RC attempts". Staff-only. Owner name displayed only on the detail page (per OQ-R7 outcome).
- **Acceptance criteria:** A pending vehicle can be approved/rejected and the driver's onboarding status updates accordingly.
- **Testing:** manual; automated deferred (TASK-126).
- **Risk:** medium
- **Status:** pending

### TASK-116 - OpenAPI + API README updates
- **Owner:** backend-engineer
- **Goal:** Document new/changed endpoints, states, error codes.
- **Rationale:** The frontend and test engineers depend on the contract.
- **Dependencies:** TASK-114
- **Affected files:** `docs/api/openapi-profiles.yaml`, `docs/api/README.md`
- **Implementation notes:** Add `pending_rc_verification` to the onboarding_status enum and `awaiting_rc_verification` to next_step; document 202 on `POST .../vehicle/`, the new status and webhook endpoints, new error codes, the feature-flag behaviour note.
- **Acceptance criteria:** Spec valid YAML and consistent with serializers.
- **Testing:** lint the YAML.
- **Risk:** low
- **Status:** pending

### TASK-117 - (Optional, blocked) post-onboarding verify endpoint for grandfathered drivers
- **Owner:** backend-engineer
- **Goal:** Allow a COMPLETE driver to add/verify a vehicle without changing `onboarding_status`.
- **Rationale:** D5 Phase 2.
- **Dependencies:** TASK-110, TASK-114; blocked on OQ-R5
- **Affected files:** `backend/profiles/views.py`, `backend/profiles/urls.py`, service module
- **Implementation notes:** `POST /api/driver/vehicle/verify/` under `IsAuthenticated, IsOnboardingComplete, IsDriverRole`. Reuses `submit_rc_verification` with a `post_onboarding=True` mode that never alters `onboarding_status`. Own flag.
- **Acceptance criteria:** COMPLETE driver stays COMPLETE through every outcome.
- **Testing (deferred):** in TASK-127.
- **Risk:** medium
- **Status:** blocked

### TASK-118 - Frontend: `VehicleRegistrationScreen`
- **Owner:** frontend-engineer
- **Goal:** Screen to enter registration number and vehicle type.
- **Rationale:** None exists today; required before the backend flag is enabled (RISK-005: stuck in-flight drivers).
- **Dependencies:** TASK-114 (contract in TASK-116)
- **Affected files:** `frontend/screens/onboarding/VehicleRegistrationScreen.tsx` (new)
- **Implementation notes:** Client-side regex `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$` after stripping spaces/hyphens and uppercasing; type picker restricted to the six allowed values (lowercase sent); handle 200 complete -> main app, 202 -> `RCPendingScreen`, 200 rejected -> show `rejection_reason` and stay; errors `invalid_registration_format`, `max_rc_attempts_exceeded` (show contact-support message), `rc_verification_pending` (route to pending screen), `rc_verification_provider_error` (retry). Use `frontend/config/constants.js` for API base URL.
- **Acceptance criteria:** All response branches handled; no crash on unknown error code.
- **Testing (deferred):** frontend unit tests.
- **Risk:** medium
- **Status:** pending

### TASK-119 - Frontend: `RCPendingScreen`
- **Owner:** frontend-engineer
- **Goal:** Waiting screen polling vehicle status.
- **Rationale:** Mirrors `DLPendingScreen`.
- **Dependencies:** TASK-114
- **Affected files:** `frontend/screens/onboarding/RCPendingScreen.tsx` (new)
- **Implementation notes:** Poll `GET /api/onboarding/driver/vehicle/status/` with backoff (5s up to 30s); copy should say the vehicle is being verified or reviewed, not accuse the driver on name mismatch; on verified -> main app; on rejected -> show reason and offer resubmit; stop polling on unmount.
- **Acceptance criteria:** Navigates on terminal status; no leaked timers.
- **Testing (deferred).**
- **Risk:** medium
- **Status:** pending

### TASK-120 - Frontend: `OnboardingGate` / navigation `next_step` handling
- **Owner:** frontend-engineer
- **Goal:** Route `vehicle_registration` and `awaiting_rc_verification` to the new screens.
- **Rationale:** Unknown `next_step` values would strand drivers.
- **Dependencies:** TASK-118, TASK-119 (and the PLAN-002 gate tasks TASK-036/042)
- **Affected files:** `frontend/components/OnboardingGate.tsx`, navigation root
- **Implementation notes:** Add both values to the `next_step` router; add a safe default for unknown values (show update-required/support screen rather than loop).
- **Acceptance criteria:** Resuming on another device lands on the correct screen for every status.
- **Testing (deferred).**
- **Risk:** high
- **Status:** pending

### TASK-121 - (Optional, blocked) Frontend: grandfathered-driver verify banner
- **Owner:** frontend-engineer
- **Goal:** Non-blocking prompt for COMPLETE drivers without a verified vehicle.
- **Dependencies:** TASK-117; blocked on OQ-R5
- **Affected files:** `frontend/components/` (new component), home screen
- **Acceptance criteria:** Banner dismissible, never blocks app use.
- **Testing:** deferred
- **Risk:** low
- **Status:** blocked

### TASK-122 - Unit tests: name matching, class mapping, RC validators (DEFERRED)
- **Owner:** test-engineer
- **Goal:** Cover TASK-109.
- **Dependencies:** TASK-109
- **Affected files:** `backend/profiles/tests/test_rc_matching.py`
- **Acceptance criteria:** Parametrised cases for exact, reordered, initials, S/O suffix, partial, mismatch, masked, empty.
- **Risk:** low
- **Status:** pending (deferred by user instruction)

### TASK-123 - Unit tests: mock RC adapter and factory (DEFERRED)
- **Owner:** test-engineer
- **Goal:** Cover TASK-104/105.
- **Dependencies:** TASK-105
- **Affected files:** `backend/profiles/tests/test_rc_adapters.py`
- **Acceptance criteria:** All six modes, signature true/false, ABC not instantiable, factory resolution.
- **Risk:** low
- **Status:** pending (deferred)

### TASK-124 - Unit tests: RC service and state machine (DEFERRED)
- **Owner:** test-engineer
- **Goal:** Cover TASK-110/111.
- **Dependencies:** TASK-110, TASK-111
- **Affected files:** `backend/profiles/tests/test_rc_service.py`, `backend/profiles/tests/test_onboarding_vehicle.py`
- **Acceptance criteria:** Every D2 transition; attempt limit; timeout -> pending; provider error keeps attempt count; resubmission reuses row; flag-off regression; webhook idempotency; review resolution; `next_step` for all states.
- **Risk:** medium
- **Status:** pending (deferred)

### TASK-125 - Security review: RC PII storage, webhook, admin exposure
- **Owner:** security-reviewer
- **Goal:** Review before enabling the flag in any shared environment.
- **Rationale:** RC owner name/data is third-party personal data (DPDP Act considerations), plus an unauthenticated webhook.
- **Dependencies:** TASK-113, TASK-115
- **Affected files:** review only (findings to `docs/decisions/`)
- **Acceptance criteria:** Decision on owner-name storage/retention (OQ-R7), logs verified free of owner data, webhook signature handling approved, mock-in-production guard confirmed.
- **Risk:** medium
- **Status:** pending

### TASK-126 - Integration tests: vehicle endpoints, webhook, flag-off regression (DEFERRED)
- **Owner:** test-engineer
- **Goal:** HTTP-level coverage.
- **Dependencies:** TASK-114
- **Affected files:** `backend/profiles/tests/test_integration_vehicle_rc.py`
- **Acceptance criteria:** Sync verified 200 complete; pending 202; rejected 200 stays awaiting_vehicle; name mismatch -> pending; attempt limit 429; resubmit while pending 409; passenger 403; DL-unverified 403; webhook valid/invalid signature/duplicate; status endpoint; flag-off equals current behaviour; admin approve/reject moves state.
- **Risk:** high
- **Status:** pending (deferred)

### TASK-127 - Integration + migration tests: switch_role, gate, in-flight and legacy data (DEFERRED)
- **Owner:** test-engineer
- **Goal:** Guard the bypass and rollout risks.
- **Dependencies:** TASK-114, TASK-106
- **Affected files:** `backend/profiles/tests/test_rc_rollout.py`
- **Acceptance criteria:** `switch_role` matrix cannot reach COMPLETE without a verified/legacy vehicle; `PENDING_RC_VERIFICATION` blocked by `IsOnboardingComplete`; in-flight driver in AWAITING_DL reaches vehicle step; grandfathered COMPLETE driver untouched; migration forward/backward with legacy vehicle rows.
- **Risk:** high
- **Status:** pending (deferred)

---

## Dependency Summary and Critical Path

Critical path: TASK-101 -> TASK-102 -> TASK-103 -> TASK-104 -> TASK-105 -> TASK-110 -> TASK-111 -> TASK-113 -> TASK-114 -> TASK-118/119 -> TASK-120.

Bottlenecks: TASK-101 (product decisions; nothing is safely buildable before the mismatch and attempt policies are fixed), TASK-110 (core service), TASK-113/114 (frontend depends on the contract).

## Parallel Groups

| Group | Tasks | Notes |
|-------|-------|-------|
| A: Upstream | TASK-101 then TASK-102, TASK-103 sequentially | PM then architect; architect may draft in parallel once OQ-R2/R4 are answered |
| B: Foundations (after TASK-103) | TASK-104, TASK-106, TASK-108, TASK-109 | Independent files; TASK-105 and TASK-107 follow TASK-104 |
| C: Service | TASK-110 then TASK-111 | Sequential, same area of code |
| D: API surface | TASK-112, TASK-115 in parallel; then TASK-113, TASK-114, TASK-116 | |
| E: Frontend | TASK-118, TASK-119 in parallel after the contract in TASK-116 is available; contract can be mocked from the OpenAPI before backend completes | TASK-120 last |
| F: Deferred tests | TASK-122, TASK-123 (early); TASK-124; TASK-126, TASK-127 | Not scheduled now |
| G: Review | TASK-125 | Before enabling the flag anywhere shared |

## Rollout

1. Land TASK-101..103 (docs) first.
2. Backend with `RC_VERIFICATION_ENABLED=False` everywhere (behaviour identical to today). Run migration 0003 before deploying app code (additive, nullable, safe).
3. Ship the frontend with TASK-118/119/120 (vehicle and pending screens). **The vehicle screen already needs to exist for the DL-to-vehicle change in v2 (RISK-005); this plan reuses that dependency and adds the pending state.**
4. Enable `RC_VERIFICATION_ENABLED=True` in staging against the mock (default `sync_verified`); exercise each mock mode manually.
5. Production stays flag-off, or on with the mock explicitly disallowed by the TASK-107 guard, until a provider adapter exists (separate plan). Enabling the flag in production with only the mock is blocked by design.
6. Feature flag: yes (`RC_VERIFICATION_ENABLED`). Migration: yes. 

**In-flight drivers (existing deployment risk, RISK-005):** drivers in `AWAITING_DL`/`PENDING_VERIFICATION` at deploy time land in `AWAITING_VEHICLE` after DL verification; with this plan some may instead land in `PENDING_RC_VERIFICATION`. An old client that does not know `vehicle_registration` or `awaiting_rc_verification` strands them. Mitigations: frontend ships first (TASK-120 includes a safe default for unknown `next_step`); flag flipped only after the minimum app version is deployed; drivers stuck in `AWAITING_VEHICLE`/`PENDING_RC_VERIFICATION` on rollback are fixed with the data patch below.

**Rollback:** set `RC_VERIFICATION_ENABLED=False` (stops new RC checks; `register_vehicle` returns to self-declare). Drivers currently in `PENDING_RC_VERIFICATION`:
`UPDATE profiles_userprofile SET onboarding_status='awaiting_vehicle' WHERE onboarding_status='pending_rc_verification';` (they resubmit under the legacy flow) or set `complete` if product accepts. Schema rollback: `migrate profiles 0002_add_vehicle` after the data patch (the AlterField choices revert is metadata-only; added columns drop with data loss limited to RC fields).

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| Real provider fields/behaviour differ from the contract designed here (all provider claims UNVERIFIED) | medium | All provider-derived result fields optional; name matching and class mapping live in the service, not adapters; provider adapter is a separate plan |
| Name-mismatch policy blocks legitimate family/fleet drivers or admits fraud | high | Flag-for-review, never auto-reject on name alone; admin resolution; metrics on review rate |
| Admin becomes the manual-review bottleneck with no SLA | medium | Track pending age; OQ-R6 stale-pending policy; ops owner needed before enabling in production |
| `switch_role` bypass yields COMPLETE without verified vehicle | high | Fixed in TASK-111; covered by TASK-127 |
| Substring-based error mapping in views mis-routes new errors (`'verified'` in message) | medium | Service raises `ApiError` subclasses; vehicle branch of `ValueError` mapping removed in TASK-113 |
| Provider call inside a DB transaction (as DL does today) holds locks | medium | RC performs the call outside the write transaction (TASK-110); DL left as is, noted for a separate fix |
| In-flight drivers stranded by an outdated client | high | Frontend first, unknown-`next_step` safe default, flag gated rollout |
| Unmerged migration 0002 plus new 0003 | low | Architect decides whether to squash before anything ships |
| RC owner PII retention/legal exposure | medium | OQ-R7, TASK-125; minimal storage; no raw payload; staff-only; no logging of names |
| Same-vehicle multi-driver fraud or disputes (RISK-006 persists) | low | Duplicate flag in admin; upgrade path to partial unique documented |
| Mock accidentally used in production | high | Startup guard in TASK-107 refuses mock when `DEBUG=False` and flag on |
| DL settings (`DL_*`) are absent from `settings.py` although PLAN-002 specified them | low | Out of scope; flagged to the user as an existing gap |

## Out of Scope

- The real provider adapter (any aggregator, DigiLocker RC, or Parivahan), provider selection, contracts, credentials, sandbox testing. Remains out of scope until OQ-R10 is resolved, mirroring `DigiLockerDLVerificationAdapter` not yet existing.
- Manual RC document upload and storage (Option E) unless OQ-R9 pulls it in.
- Multi-vehicle support, commercial permit verification (OQ-R11), push notifications for review outcomes, automatic stale-pending escalation, insurance/PUC expiry reminders.
- Fixing the DL module's wiring gaps (global adapter, missing DL settings, in-transaction provider call).

## Success Criteria

- With the flag on and the mock, each of the six mock modes produces the documented state and response.
- With the flag off, behaviour is unchanged from today.
- No path exists to `COMPLETE` for a driver whose vehicle is pending or rejected.
- Grandfathered drivers are unaffected.
- Requirements v4 and ARCH-002 v3 approved before any backend code ships.

---

**End of Plan**

---

## Architecture deltas (ARCH-002 v3, 2026-10-15)

TASK-103 is complete. The design changes these tasks relative to the descriptions above (authoritative detail: `docs/architecture/ARCH-002-user-onboarding.md` v3 and ADR Decisions 11-26):

- **D6 (error codes) superseded:** a rejected RC is `422 rc_verification_rejected` (not a `200`), per requirements v4 and OQ-R12a.
- **TASK-104:** factory is `adapter_cls.from_settings(settings)`; ABC gains `parse_webhook(body)`; `RCAdapterError` added; `owner_name` is `repr=False`; adapter applies `timeout_seconds` itself.
- **TASK-105:** mock webhook is HMAC-SHA256 over the body in `x-rc-signature` (not a static `X-Mock-Signature`), fails closed on an empty secret; unknown mode raises `ImproperlyConfigured`; `sync_verified` returns no vehicle class.
- **TASK-106:** no squash of 0002 (commit it unchanged, generate 0003); `rc_attempt_count` needs `db_default=0`; add `profiles.review_rc` permission; indexes `idx_vehicle_regno`, `idx_vehicle_rc_status`.
- **TASK-107:** startup validation lives in `settings.py` (import-time, flag ON only): mock-in-production, empty/placeholder `RC_WEBHOOK_SECRET`, `ONBOARDING_GATE_ENABLED` false, bad limits; plus derived `RC_MOCK_ADAPTER_FORBIDDEN`. Verify whether `backend/.env.example` exists before creating it.
- **TASK-108:** add `RCVerificationRejected`, `RCReferenceNotFound`, `MalformedWebhookPayload`, `RCReviewStateError` to the list.
- **NEW (proposed) TASK-128:** `core` envelope extension (`ApiError(extra=)`, `error_envelope(extra=)`), prerequisite of TASK-108/TASK-113. **NEW (proposed) TASK-129:** `ConditionalOnboardingGate` raises `OnboardingIncomplete` with `onboarding_status` and `next_step` (needed for FR-14/AC-41). **NEW (proposed) TASK-130:** `services/sanitise.py` (`sanitise_reason`) and `RequireDriverRole`.
- **TASK-109:** `rc_matching.py` also holds `decide_rc_outcome` and the class keyword table; matching rules are specified in ARCH-002 (one full-token match required).
- **TASK-110:** entry point is `register_vehicle_with_rc`; three phases; rejection raised after commit; webhook takes an `RCVerificationResult` from `adapter.parse_webhook`; `resolve_rc_review` allows approve on `rejected` as well as `pending`; admin functions ignore the flag.
- **TASK-111:** flag-off branch is the existing body renamed `_register_vehicle_self_declared`, return type unchanged, view `ValueError` mapping left untouched; `switch_role` keeps grandfathered `COMPLETE` + no vehicle row as `COMPLETE` (deviates from FR-43/AC-48 "absent vehicle"); switch to passenger from `pending_rc_verification` sets `COMPLETE`.
- **TASK-112:** no `RCWebhookPayloadSerializer` (the adapter parses the webhook); add optional `next_step` to the role-switch response and nullable `rc_verification_status` to the onboarding status response.
- **TASK-113:** webhook view checks the flag (404) before the signature; `VehicleStatusView` uses `RequireDriverRole`; response `202` when `pending_rc_verification`.
- **TASK-115:** reject reason via `ActionForm`; actions guarded by `review_rc`; add/delete disabled; audit through `log_change`.
- **TASK-127 / TASK-126 test expectations:** the "no vehicle row" case in the `switch_role` matrix expects `complete`; the rollback runbook (deactivate pending/rejected rows) needs a test.
- **Rollout step 4** (staging against the mock) requires `DEBUG=True` or a security-approved override (ARCH-002 U4).
