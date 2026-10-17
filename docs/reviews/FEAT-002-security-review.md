# Security Review: User Onboarding, DL Verification, Vehicle/RC Verification, Role Switching (FEAT-002)

**ID:** SEC-002
**Type:** security-review
**Feature:** FEAT-002
**Reviewer:** security-reviewer
**Status:** changes_requested

---

Scope: uncommitted working tree on branch `onboarding-BE`, reviewed from the code on disk (not git history, not the docs). No `.env` file was opened. The shell was not available, so the tests were not run and this document was checked against `schemas/security-review.schema.yaml` by hand (required fields `id`, `type`, `feature_id`, `reviewer`, `status`, `findings[].{id,severity,title,description}` are present and use the allowed enums). It was not machine-validated.

Evidence is quoted as `file:line` relative to `C:\work\Spot rides\backend\`.

## Verdict

- RC flag OFF (the default), dev or staging only: acceptable to run. No unauthenticated path to a state change was found in the default configuration.
- Any environment that must enforce driver identity (production): BLOCKED by F-01, F-02 and F-03. In every configuration the "DL verification" is a mock that verifies any well-formed number. The DL webhook is guarded by a public constant. The RC-style production guards do not cover the DL path at all.
- Before enabling `RC_VERIFICATION_ENABLED`: resolve F-05 and F-06 and decide F-07. The RC module itself (HMAC webhook, locking, logging allow-list, import-time guard) is well built and has no high findings. The risks sit around it.

## Assets

- Driver-licence number (DL), stored as Fernet ciphertext plus a plaintext last-4 (`DriverVerification.dl_number`, `dl_number_display`)
- Vehicle registration number and RC data (`Vehicle.rc_*`), including `rc_owner_name`, which is third-party PII
- Onboarding state machine (`UserProfile.onboarding_status`, `active_role`, `vehicle_step_exempt`): this is the authorisation basis for every future driver-facing feature
- Verification decisions (verified/rejected) and the attempt counters that limit enumeration of the provider
- `DL_ENCRYPTION_KEY`, `RC_WEBHOOK_SECRET`, JWT signing key
- Provider quota and cost (DL/RC lookups)

## Actors

- Authenticated rider or aspiring driver (the main adversary: wants "verified driver" status without a real DL or vehicle)
- Anonymous internet caller (the two webhook endpoints are `AllowAny`)
- DL and RC verification providers (trusted but fallible; webhook senders)
- Django admin staff (`profiles.review_rc` reviewers, other staff with model permissions)
- Operator or deployer (feature flags, secrets, adapter wiring)
- Log and observability pipeline readers

## Trust Boundaries

- Mobile client to API: JWT bearer; `request.user` is the only identity used
- Internet to webhook endpoints: no JWT; the only authentication is the adapter's `validate_webhook`
- API to provider: DL call inside a DB transaction; RC call outside any transaction
- API to PostgreSQL: ORM only; no raw SQL anywhere in the scoped code (grep for `.raw(`, `.extra(`, `cursor(`, `RawSQL` found nothing)
- Django admin to the state machine: the review actions go through the service layer; the plain model admins bypass it

## Attack Surfaces

- POST `/api/onboarding/driver/dl/webhook/` (AllowAny, `authentication_classes = []`; `profiles/views.py:298-346`)
- POST `/api/onboarding/driver/vehicle/rc/webhook/` (AllowAny; flag-gated 404; `profiles/views.py:431-467`)
- POST `/api/onboarding/driver/dl/`, POST `/api/onboarding/driver/vehicle/`, PATCH `/api/profile/role/` (authenticated, unthrottled)
- POST `/api/onboarding/role/`, `/profile/`; GET `/status/`, `/driver/dl/status/`, `/driver/vehicle/status/`
- GET `/api/auth/me/` (`onboarding_status`, `active_role` read-only; `accounts/serializers.py:91-112`)
- `/admin/` (UserProfile, DriverVerification, Vehicle admins; RC review actions)
- Environment and settings: `RC_*`, `ONBOARDING_GATE_ENABLED`, `DEBUG`, `DL_ENCRYPTION_KEY`

## Threat Model

| ID | Threat | Mitigation present | Residual Risk |
|----|--------|--------------------|---------------|
| T-01 | User claims "verified driver" without a real DL | None in any configuration: the DL adapter is a hard-wired mock that verifies everything | High (F-01) |
| T-02 | Attacker forges a DL verification result via the webhook | Static header equality against a hard-coded default secret | High if any DL is ever pending (F-02, F-03); no state change reachable today |
| T-03 | Attacker forges an RC result via the webhook | HMAC-SHA256 over the raw body, constant-time compare, fail-closed on empty secret, 404 when flag off, signature checked before parse and DB, terminal-state idempotency, startup guard against mock/empty secret when `DEBUG` is off | Low (F-12) |
| T-04 | Skip steps / reach `complete` without verified DL + vehicle | Status gates in every service function, `PATCH /api/profile/role/` derives status from DL + vehicle, `vehicle_step_exempt` is read-only and migration-set | Low in the default configuration; see F-06 for flag transitions and F-10 for the migration rule |
| T-05 | IDOR on another user's DL / vehicle / RC data | Every view reads from `request.user`; no object identifiers in any URL or body | None found |
| T-06 | Brute-force the provider to find a valid DL/plate (enumeration, cost) | DL attempt cap 3 (unlocked); RC attempt cap 3 (serialised) | Medium (F-04, F-05) |
| T-07 | PII exposure (DL, RC owner name) via logs, errors, admin | DL never logged or returned beyond last-4; RC log allow-list; `owner_name` `repr=False`; `sanitise_reason` | Medium for owner-name retention and admin visibility (F-07) |
| T-08 | Staff abuse or mistake bypasses verification | Review actions behind `profiles.review_rc`; Vehicle admin is fully read-only | Low (F-11) |
| T-09 | Replay of a signed webhook | Terminal-state idempotency | Low (F-12) |
| T-10 | Mock adapter in production | RC: import-time `ImproperlyConfigured` plus factory check. DL: nothing | High for DL (F-01) |

## OWASP Top 10 Checklist

- [x] A01 Broken Access Control: no IDOR; role/status not mass-assignable; F-01 (verification is a no-op), F-06 (flag transitions), F-11 (admin)
- [x] A02 Cryptographic Failures: Fernet use is sound; lazy key validation, no rotation, outdated pin (F-15)
- [ ] A03 Injection: ORM only, no raw SQL, no template rendering of user data, regexes anchored and linear; no findings
- [x] A04 Insecure Design: F-01, F-04, F-08
- [x] A05 Security Misconfiguration: F-01, F-02, F-05; `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS` have no defaults (fail closed), which is good
- [x] A06 Vulnerable Components: F-15 (`cryptography==42.0.5`); other pins could not be assessed against advisories offline
- [x] A07 Auth Failures: F-02, F-03 (webhook authentication)
- [x] A08 Software/Data Integrity: F-10 (data migration rule), F-12
- [x] A09 Logging Failures: no DL/RC PII in logs found; F-09 (500 plus traceback log flooding), F-07
- [ ] A10 SSRF: no outbound URL is built from user input; adapters take only a normalised plate/DL

## Findings (summary)

| ID | Severity | Title | Location | Description | Recommendation | Blocking |
|----|----------|-------|----------|-------------|---------------|---------|
| F-01 | high | DL verification is a hard-wired mock that verifies everything, with no production guard | `profiles/services/dl_verification.py:18-19`; `profiles/adapters/mock.py:56-59` | Exploitable today: any driver submits any DL-shaped string and is immediately `verified`. | Make the DL adapter settings-driven with a forbidden-mock guard like RC; fail closed. | true (production) |
| F-02 | high | DL webhook authenticated by a public hard-coded secret; fail-open on empty secret; self-verification possible | `profiles/adapters/mock.py:79-98`; `profiles/views.py:305-313` | `'mock-secret'` is accepted from anyone. | Real HMAC over the body with a required secret; fail closed. | true (before any async DL provider) |
| F-03 | high (latent) | Webhook validation bound to the original mock adapter instance; `set_adapter()` does not affect it | `profiles/views.py:54-58,312`; `profiles/services/dl_verification.py:22-25` | A real adapter installed via the documented hook leaves the webhook guarded by the mock. | Resolve the adapter at call time (`dl_verification.get_adapter()`); test it. | true (before real DL provider) |
| F-04 | medium | DL submit has no row lock: attempt cap bypass, lost updates, provider call inside a transaction | `profiles/services/dl_verification.py:28-104` | Parallel requests defeat the 3-attempt cap. | `select_for_update` on profile and DV row; call the provider outside the transaction, as RC does. | false |
| F-05 | medium | No throttling on any onboarding endpoint or webhook; RC provider-call amplification | `config/settings.py:143-159`; `profiles/services/rc_verification.py:164-180` | Concurrent submits all pass phase 1 and each calls the provider. | DRF scoped throttles; per-user in-flight guard. | false (blocks enabling RC) |
| F-06 | medium | RC flag transitions: legacy vehicles auto-complete; flag-off role switch completes rejected/pending vehicles | `profiles/services/rc_verification.py:445-460`; `profiles/services/onboarding.py:223` | Enabling RC does not re-verify existing vehicles; rollback can launder a rejected vehicle. | Define backfill policy; check RC status regardless of flag in switch. | false (blocks enabling RC) |
| F-07 | medium | Third-party owner name retained after staff resolution; visible to any admin with view permission on Vehicle | `profiles/services/rc_verification.py:378-411`; `profiles/admin.py:115-118,135-136` | PII retention beyond purpose. | Clear on every terminal transition; separate permission for the PII fieldset; consider hashing. | false |
| F-08 | medium | Verification is not bound to the person: DL not matched to the user, DL reuse across accounts undetected, plate duplicates allowed, name match spoofable | `profiles/services/dl_verification.py:63-104`; `profiles/services/rc_matching.py:50-87`; `profiles/services/rc_verification.py:253-262` | Design gap that matters once real providers are used. | Match name/DOB from the DL provider; keyed-hash column for DL uniqueness; block or review duplicate plates. | false |
| F-09 | low | DL webhook error handling: unknown reference is an unhandled 500; substring error mapping; raw rejection reason stored | `profiles/views.py:323-336`; `profiles/services/dl_verification.py:122-124,140` | Reference-existence oracle plus log flooding for holders of the secret. | Catch `DoesNotExist`; return a uniform 404; sanitise reason. | false |
| F-10 | low | Data migration 0004 marks any COMPLETE user with any DV row (any DL status) and no vehicle as exempt | `profiles/migrations/0004_userprofile_vehicle_step_exempt.py:14-19` | A passenger with a pending DL who is later verified can become a driver without a vehicle. | Require `dl_verification_status='verified'` in the marking rule. | false |
| F-11 | low | Plain admins can edit `onboarding_status`, `active_role`, `dl_verification_status`, `attempt_count` | `profiles/admin.py:10-52` | Staff can bypass the state machine; audit is only Django's LogEntry. | Make those fields read-only; add review actions. | false |
| F-12 | low | RC webhook hardening gaps: no replay window, no `None` reference guard in the service, no secret strength check | `profiles/services/rc_verification.py:303-309`; `config/settings.py:136` | Defence in depth. | See below. | false |
| F-13 | low | Error mapping by substring on `ValueError` text; `str(e)` reflected to client | `profiles/views.py:148-155,192-199,231-244,380-388` | Fragile, and can echo internal text. | Use typed exceptions. | false |
| F-14 | low | Races in flag-off vehicle registration and stale full-row `profile.save()` in DL submit | `profiles/services/onboarding.py:163-186`; `profiles/services/dl_verification.py:42,97` | Duplicate active vehicles; role switch overwritten. | Lock the profile; use `update_fields`. | false |
| F-15 | low | Crypto and dependency hygiene: lazy key validation, no rotation path, `cryptography==42.0.5` | `profiles/utils/crypto.py:12-37`; `requirements.txt:14` | Operational. | Validate at startup; MultiFernet; bump the pin. | false |
| F-16 | low | No tests cover webhooks, RC service, role switching, matching or admin; `profiles/tests.py` is shadowed by `profiles/tests/` | `profiles/tests/` | None of the controls above is regression-protected. | Add tests listed below. | false |
| F-17 | informational | Onboarding gate is opt-out by overriding `permission_classes`, default flag False; `IsDriverVerified` ignores RC/vehicle status | `core/permissions.py:11-40`; `profiles/permissions.py:67-91` | Forward-looking. | See below. | false |
| F-18 | informational | Minor: stale DL fields, misleading 403, permissive name regex, Unicode `upper()`, RC lookup oracle | various | See below. | | false |

## Finding details

### Confirmed findings

**F-01 (high) DL verification is a hard-wired mock in every configuration**
- Evidence: `profiles/services/dl_verification.py:18-19` creates `_adapter = MockDLVerificationAdapter(response_mode='sync_verified')` at import. `profiles/adapters/mock.py:56-59` returns `verified` with a random reference for any input. `config/settings.py` has no DL adapter setting (grep for `DL_ADAPTER` and `DL_WEBHOOK_SECRET` finds only docstrings and `mock.py:95`). The mock class docstring (`mock.py:33-34`) says the mode comes from `settings.DL_ADAPTER_MOCK_RESULT`, but nothing reads it. The RC import-time guard (`settings.py:123-141`) and the factory check (`adapters/__init__.py:26-29`) cover only RC.
- Scenario: any user calls `POST /api/onboarding/role/` (driver), `/profile/`, `/driver/dl/` with `MH01 2011 0012345` and gets 200 `verified`. `DLSubmitView` (`views.py:260-263`) then returns `awaiting_vehicle`. With the RC flag off the vehicle step is self-declared, so the user reaches `complete` as a "verified driver" with no check at all.
- Exploitable in the default configuration: yes. The core security property of the feature (a driver holds a verified licence) does not exist yet.
- Remediation: add `DL_ADAPTER_CLASS` and related settings. Resolve the adapter per call (see F-03). Refuse the mock when `DEBUG` is off (reuse the RC guard pattern, but not conditional on an RC flag). Consider an explicit `DL_VERIFICATION_ENABLED` flag that fails closed.

**F-02 (high) DL webhook authentication is a public constant**
- Evidence: `adapters/mock.py:95-98`: `expected = getattr(settings, 'DL_WEBHOOK_SECRET', 'mock-secret')`; `return actual_signature == expected`. `DL_WEBHOOK_SECRET` is not defined in settings, so the accepted value is always the literal `mock-secret`, visible in the repository. Properties: not an HMAC, not bound to the body (the `body` argument is ignored), `==` not constant-time, and fail-open if a deployer sets `DL_WEBHOOK_SECRET=` to empty (a missing header yields `''`, which equals `''`). The view is `AllowAny` with `authentication_classes = []` (`views.py:305-306`).
- Scenario A (today): anyone sends `X-Mock-Signature: mock-secret` with a JSON body. The service (`dl_verification.py:122-144`) does nothing for rows already `verified` or `rejected`, which in the default sync-verified flow is every row. Practical effect today is limited to the oracle and noise described in F-09.
- Scenario B (as soon as any DL is pending, for example an async provider is wired through the mock class or rows are created by admin or tests): the user already receives their own `reference_id` in the submit response (`views.py:250-255`), so they can post `{"reference_id": "<theirs>", "status": "verified"}` with the known header and move themselves from `pending_verification` to `awaiting_vehicle` (`dl_verification.py:136-138`). They can also reject other users' pending DLs if they learn a reference. Mock references are `mock-` plus 8 hex characters (32 bits) and the endpoint is unthrottled.
- Exploitable in the default configuration: no state change is reachable (nothing is ever left pending); the oracle in F-09 is. Exploitable in scenario B.
- Remediation: require a real HMAC-SHA256 over the raw body with a mandatory secret and `hmac.compare_digest`, fail closed on empty. Keep the mock-only static check out of any non-DEBUG build. Reuse the RC `validate_webhook` implementation (`mock.py:174-187`), which is correct.

**F-03 (high, latent) The webhook view keeps a stale reference to the original adapter**
- Evidence: `profiles/views.py:54-58` does `from profiles.services.dl_verification import (..., _adapter)`, which binds the instance at import. `views.py:312` calls `_adapter.validate_webhook(...)`. `dl_verification.set_adapter()` (`dl_verification.py:22-25`) rebinds the module global only, so the view never sees it.
- Scenario: a developer installs a real provider with the documented `set_adapter()`. Submissions go to the real provider, but webhook authentication still uses the mock's `mock-secret` check. F-02 then applies in full with a real provider. Because `process_webhook_result` trusts the payload `status`, an attacker could verify their own DL.
- Exploitable in the default configuration: no (only the mock is ever installed). It becomes high the moment a real adapter is wired using the existing hook.
- Remediation: add `get_adapter()` in `dl_verification.py`, call it from the view, and add a test that `set_adapter(fake)` changes webhook validation. Do not import underscore-private module globals.

**F-04 (medium) DL submit is unlocked, so the attempt cap is bypassable; the provider call is inside a transaction**
- Evidence: `dl_verification.py:28-104`. `@transaction.atomic` but no `select_for_update`. The cap check at lines 54-59 reads `attempt_count` from a plain fetch, and line 85 does `attempt_count += 1` on the in-memory object. N parallel requests all read the same count and all write `count + 1` (lost update), so the cap of 3 is not enforced. First submissions by the same user race on the `OneToOne` insert and one gets an unhandled `IntegrityError` (500). The provider call at line 70 happens while the transaction (and a pooled DB connection) is open. `DLVerificationAdapter` has no timeout contract (`adapters/base.py:27-67`), and only `TimeoutError` is caught (line 71); any other adapter exception becomes a 500. Line 97 saves a stale full-row `profile`, so a concurrent `switch_role` can be overwritten.
- Scenario: with a real provider, the 3-attempt cap is the only barrier against a user probing many DL numbers (the DL is not matched to the user, see F-08). A script sending 50 parallel requests gets about 50 provider lookups.
- Exploitable in the default configuration: the cap can be exceeded, but the mock always verifies on the first try, so it has no effect today.
- Remediation: lock the `UserProfile` row (same order as RC: profile then verification), re-check state and count under the lock, run the provider call outside the transaction (the three-phase pattern in `rc_verification.py:164-180`), add a DL timeout setting and wrap non-timeout adapter errors in `DLProviderError`, and use `save(update_fields=...)`.

**F-05 (medium) No rate limiting on the new endpoints; RC provider-call amplification**
- Evidence: `config/settings.py:143-159` defines no `DEFAULT_THROTTLE_CLASSES` or rates, and nothing in `profiles/` throttles (grep for "throttle" finds nothing). Only the OTP endpoints in `accounts` have custom limits. For RC, `_assert_can_submit` runs in a short phase-1 transaction that releases its locks (`rc_verification.py:167-170`), then `_call_provider` runs (line 173). N concurrent requests all pass phase 1 and make N provider calls. Phase 3 serialises persistence and enforces the attempt cap (`_attempts_remaining` at line 109 is re-checked at 180), so the stored attempt count cannot exceed `RC_MAX_ATTEMPTS`. But the provider calls are already paid for. In addition, `RCProviderError` is documented as consuming no attempt (`profiles/exceptions.py:158-162`), so provider errors are unbounded by design.
- Scenario: a driver with one attempt left sends 100 parallel requests: 100 paid lookups, one persisted. Or they hammer `PATCH /api/profile/role/` or the DL endpoint indefinitely.
- Exploitable in the default configuration: DL and role endpoints are unthrottled (little to gain with the mock). RC amplification applies only when the flag is on with a paid provider.
- Remediation: DRF scoped throttles (for example `onboarding_submit` 5/min per user, `role_switch` 10/hour per user, webhooks per IP with a generous limit). For RC, add a per-user in-flight guard (a short Redis lock or a `rc_inflight_until` column) before the provider call, and cap consecutive provider errors per user.

**F-06 (medium) RC flag transitions weaken the verified-vehicle guarantee**
- Evidence:
  - `derive_driver_status` treats `rc_verification_status is None` as complete (`rc_verification.py:456-457`). Every vehicle registered while the flag was off has `NULL` (the model help text says so, `models.py:221`). Enabling the flag does not re-verify them.
  - With the flag off, `_status_for_verified_driver` returns `COMPLETE` for any active vehicle regardless of its RC status (`onboarding.py:223-224`). A driver whose vehicle was `rejected` can `PATCH role=passenger` then `PATCH role=driver` and become `complete` with a rejected vehicle (flag off, for example during a rollback). They keep that status when the flag is turned back on.
  - Flag-off registration for a user in `awaiting_vehicle` with a rejected active vehicle returns `vehicle_already_registered` (`onboarding.py:173-174`), and for `pending_rc_verification` returns the misleading `dl_not_verified` (`views.py:384-385`). These users are stranded until staff act.
- Scenario: see the bullets. Impact is an unverified or rejected vehicle behind a `complete` driver once rides exist.
- Exploitable in the default configuration: no (flag off means self-declared by design). Applies during enablement and rollback.
- Remediation: before enabling, write a backfill or re-verification policy for `NULL` vehicles (a management command to move them to `awaiting_vehicle`/pending, or an explicit grandfather marker like `vehicle_step_exempt`). In `_status_for_verified_driver`, never return `COMPLETE` for a vehicle whose `rc_verification_status` is `pending` or `rejected`, regardless of the flag. Document the rollback runbook.

**F-07 (medium) RC owner name (third-party PII) is retained and broadly visible**
- Evidence: `_clear_owner_data` is called on sync verified, sync rejected and webhook verified/rejected (`rc_verification.py:205,212,218,344,351`), but `resolve_rc_review` (staff approve and reject, `rc_verification.py:378-411`) never clears it (the docstring at line 58 says OQ-R7 is open and "resolution by staff keeps the name"). Pending-path vehicles keep it until resolved. The column is plaintext (`models.py:228-231`). `VehicleAdmin.get_readonly_fields` returns all fields (`admin.py:135-136`), so every staff user with `view_vehicle` sees `rc_owner_name`, not only holders of `review_rc` (which gates only the actions).
- Impact: indefinite storage of a non-user's name that was never needed after the decision; wider staff exposure than the review purpose requires.
- Exploitable in the default configuration: not applicable (flag off, column unused).
- Remediation: clear the name when staff resolve (record the decision and `rc_name_match` only); apply a retention limit to pending rows; split the PII fieldset behind `review_rc` (`get_fieldsets`/`get_readonly_fields` by permission). Consider storing a keyed hash of the normalised tokens instead of the name.

**F-08 (medium, design) Identity binding between DL, RC and the account**
- DL: the provider is called with only the DL number and `user.id` (`dl_verification.py:70`). No name or date of birth from the profile is compared with the DL holder. Nothing prevents two accounts from submitting the same DL (Fernet output is non-deterministic, so even a database-level check is impossible without a separate keyed hash).
- RC: duplicate plates across drivers are only logged (`rc_verification.py:253-262`) and surfaced in the admin filter; they are not blocked or put into review. Name match compares the user's self-declared profile name with the RC owner (`rc_matching.py:50-87`). It returns `match` when all profile tokens are found and ignores extra RC tokens (leftover `available` is never penalised), so the attacker only needs to know the owner's name. Single-letter profile tokens are accepted by `validate_name` and match by initial (at most one initial counts toward `match`).
- Exploitable in the default configuration: not meaningfully (mock). It decides whether the real-provider integration achieves its purpose.
- Remediation: require the DL provider to return holder name (and optionally DOB) and compare it with the profile; add a keyed HMAC of the normalised DL for a uniqueness check (the key separate from the Fernet key); treat shared plates as `pending` for review; require a minimum token length and penalise unmatched RC tokens beyond a threshold.

**F-09 (low) DL webhook error handling**
- Evidence: `process_webhook_result` uses `.get(dl_verification_ref=reference_id)` (`dl_verification.py:122-124`). A valid signature with an unknown reference raises `DriverVerification.DoesNotExist`. The view's `except Exception` (`views.py:325-336`) only converts messages containing "already" or "processed", so this is logged at ERROR and re-raised, and the exception handler returns 500 and calls `logger.exception` (`core/exceptions.py:75`). Duplicate delivery returns 200 (idempotent) rather than 409, so the "already/processed" branch is dead code. `rejection_reason` is stored unsanitised in a `TextField` (`dl_verification.py:140`, `serializers.py:116` has no `max_length`) and returned by `/dl/status/` (`views.py:290`), unlike RC where `sanitise_reason` is applied.
- Impact: with the default secret (F-02), anyone can distinguish existing (200) from unknown (500) references and generate error logs with tracebacks at will. After a real provider is wired, stored content from the webhook reaches the mobile client unsanitised.
- Remediation: catch `DoesNotExist` and return a uniform response (404 or 200) without an error log; drop the substring mapping; apply `sanitise_reason` and a length cap to DL rejection reasons.

**F-10 (low) Data migration marking rule**
- Evidence: `0004_userprofile_vehicle_step_exempt.py:14-19` marks every `complete` profile that has any `DriverVerification` row and no active vehicle. It does not check `dl_verification_status`, `active_role` or the DL verified timestamp. A passenger who earlier submitted a DL (pending or rejected) is marked. If the pending DL is later verified (webhook), `switch_role` to driver yields `COMPLETE` without a vehicle (`onboarding.py:223`). A rejected-DL user is marked too, though they are blocked by the DL check until verified.
- Impact: small population (only pre-migration users), but the flag is permanent and not visible anywhere except the read-only admin field.
- Exploitable in the default configuration: only for such grandfathered accounts.
- Remediation: restrict the rule to `dl_verification_status='verified'`. Log the count of affected rows. For already-applied environments, run a corrective data migration (clear the flag where the DL is not verified).

**F-11 (low) Plain admins bypass the state machine; thin audit**
- Evidence: `UserProfileAdmin` leaves `active_role` and `onboarding_status` editable (`admin.py:10-30`; only `vehicle_step_exempt` and timestamps are read-only). `DriverVerificationAdmin` leaves `dl_verification_status`, `dl_verification_ref`, `attempt_count` and `dl_rejection_reason` editable (`admin.py:32-52`) and there is no DL review action. Any staff member with `change_*` can set a user `complete` as a driver, or a DL `verified`, with no corresponding profile transition. Audit is Django's default LogEntry (who/when/changed fields); the `onboarding.rc.review.*` log events do not record before/after status. `UserProfile.__str__` and `DriverVerification.__str__` put the full phone number into LogEntry `object_repr`. The RC review actions themselves are well designed (service layer, `review_rc` permission, per-vehicle log entry).
- Remediation: make the state fields read-only in these admins and provide review actions through the service layer (as for RC); record from/to status in the log event; limit `change_userprofile`/`change_driververification` to a small group; require MFA on the admin.

**F-12 (low) RC webhook hardening (the implementation is otherwise sound)**
- Verified good: signature is checked before `parse_webhook` and before any DB access (`views.py:454-462`); `hmac.compare_digest` (`mock.py:187`); empty secret fails closed (`mock.py:178-180`); adapter-construction failure fails closed with 403 (`views.py:448-452`); flag off returns 404 before reading anything (`views.py:442-443`); unique partial index on `rc_verification_ref` (`models.py:248-254`); terminal-state idempotency (`rc_verification.py:318-320`); a webhook "verified" without a matching owner name stays pending (`rc_matching.py:160-162`).
- Gaps: (1) no timestamp or nonce, so a captured signed body can be replayed; terminal-state idempotency neutralises it for verified/rejected, and for pending it only re-applies the same fields. (2) `process_rc_webhook` trusts the adapter to supply a non-empty `reference_id`. `Vehicle.objects.filter(rc_verification_ref=None)` compiles to `IS NULL` and would match an arbitrary legacy vehicle. The mock's `parse_webhook` rejects empty values (`mock.py:199-200`); the abstract contract (`adapters/base.py:119-121`) does not require it. (3) The secret has no strength requirement beyond non-empty and not starting with `PLACEHOLDER`, and the check is only applied when `DEBUG` is off (`settings.py:133-139`). (4) A string with NUL in `owner_name`/`vehicle_class` from the provider would raise a database error and a 500 that providers will retry (only `rejection_reason` is stripped of control characters). (5) 404 vs 403 reveals whether the flag is on.
- Remediation: reject empty or non-string `reference_id` in `process_rc_webhook`; add an optional signed timestamp with a 5-minute window if the provider supports it; enforce a minimum secret length; strip control characters from all provider strings.

**F-13 (low) Error mapping by substring; internal text reflected**
- Evidence: the views convert `ValueError` text to API errors by substring (`views.py:148-155`, `192-199`, `231-244`, `380-388`), and the catch-all passes `str(e)` to the client (`InvalidOnboardingState(detail=str(e))`). Any unrelated `ValueError` (for example a driver-level "A string literal cannot contain NUL" or a typo'd message that contains "attempts" or "provider") is misclassified or echoed. `DLSubmitView` maps `'attempts' in error_msg` to `MaxDLAttemptsExceeded`. Also `_validate_role_payload` echoes DRF's `"<input>" is not a valid choice.` (JSON, so not XSS, but unbounded reflection of the submitted value).
- Remediation: raise typed exceptions from the services (as RC already does); never return `str(e)` for unexpected exceptions.

**F-14 (low) Races outside the RC path**
- Evidence: `_register_vehicle_self_declared` (`onboarding.py:143-186`) has no lock, so two concurrent flag-off requests both pass the `exists()` check and create two active vehicles (no DB uniqueness for "one active vehicle per user"). `set_role`/`set_profile_details` (`onboarding.py:54-124`) are unlocked; their transitions are idempotent, so the impact is low. `submit_dl_verification` and `process_webhook_result` do full-row saves of stale objects (`dl_verification.py:97,143`).
- Remediation: lock the profile (as `switch_role` and the RC path do), and add a partial unique index on `(user) WHERE is_active` for v1.

**F-15 (low) Crypto and dependency hygiene**
- Verified good: `profiles/utils/crypto.py` uses Fernet (AES-128-CBC + HMAC-SHA256) with a key from the environment; a missing or invalid key raises `ImproperlyConfigured` before the provider is called, so no DL is verified and then lost; the key never appears in the exception text (only the underlying library message does, `crypto.py:36`). Ciphertext length is not a problem: the normalised DL is 15 characters (`validators.py:11`), giving a 100-character token (for a plaintext up to 20 characters it would be about 140); the column is 256 (`models.py:126-129`). DL plaintext is never persisted, logged, serialised or shown in admin (admin shows ciphertext and the last-4).
- Gaps: the key is only validated at first use, so a deployment with a missing key starts fine and returns 500 on the first DL submission (and `manage.py check` does not catch it); there is no key-rotation path (a single `Fernet`, no `MultiFernet`; rotating the key makes all existing ciphertexts undecryptable, but since `decrypt_dl_number` has no callers today nobody would notice); the ciphertext is not bound to the row (no associated data), so swapping values between rows is undetectable. `requirements.txt` pins `cryptography==42.0.5`. I could not check advisories online; I recall that wheels of that range bundle OpenSSL versions covered by GHSA-h4gh-qq45-vh27 (fixed in 43.0.1), so please run `pip-audit` and bump. The file is UTF-16 with NUL bytes (pip tolerates a BOM, other tools such as Dependabot or Safety may not parse it). No hash pinning or lockfile for transitive dependencies.
- Remediation: validate `DL_ENCRYPTION_KEY` in `settings.py` (or an `AppConfig.ready` / system check); support `DL_ENCRYPTION_KEYS` with `MultiFernet` and a re-encryption command; update and re-save `requirements.txt` as UTF-8; run `pip-audit` in CI.

**F-16 (low) No security regression tests**
- Evidence: a search of all `backend/profiles/**/test*.py` for `webhook`, `rc_verification`, `switch_role` and `RoleSwitch` finds nothing. Only `tests/test_permissions.py` and `tests/test_serializers.py` exist, and `profiles/tests.py` is shadowed by the `profiles/tests/` package (Python imports the package, so that module is never collected). I did not run the suite.
- Remediation: add tests for: webhook signature accepted/rejected/empty secret/missing header for both webhooks; flag-off RC webhook 404; replay returns 409; `set_adapter` takes effect on webhook validation; DL attempt cap under concurrency (`TransactionTestCase`); every `switch_role` transition including the rollback cases in F-06; admin actions without `review_rc`; no owner name or DL plaintext in captured logs and responses.

### Informational

**F-17 Gate and permission design (no current impact)**
- The onboarding gate is the default permission class, and a view opts out simply by setting `permission_classes = [IsAuthenticated]`. Every onboarding view and `/api/auth/me/` do this, which is correct today, but any future view that copies that line silently skips the gate. `ONBOARDING_GATE_ENABLED` defaults to `False` (`settings.py:112`), and the RC startup guard only forces it on when RC is on and `DEBUG` is off (`settings.py:138`). There are currently no non-onboarding protected endpoints, so there is no gap today.
- `IsDriverVerified` (`profiles/permissions.py:67-91`) checks role and DL only. It does not check `onboarding_status == complete`, an active vehicle, or RC status. Using it alone to protect a ride-posting endpoint would let a driver with a pending or rejected vehicle through. `IsOnboardingComplete` is defined but unused.
- Suggestion: for ride features use `[IsAuthenticated, IsDriverVerified, <complete+vehicle check>]`, and make the gate opt-out explicit (a marker attribute) so the default stays closed.

**F-18 Minor observations**
- Stale data: `dl_rejection_reason` and `dl_verified_at` are not cleared when a resubmission later succeeds or goes pending (`dl_verification.py:87-94`), so `/dl/status/` can return `verified` with an old reason.
- `DLStatusView` returns `403 not_a_driver` for a driver without a `DriverVerification` row (`views.py:281-282`), which is misleading.
- `validate_name` uses `^[\w\s'-]+$` (`validators.py:57`): permits digits, underscores, tabs and internal newlines; the name is later used in matching. Not exploitable; consider letters/marks plus space, hyphen and apostrophe.
- `str.upper()` in the normalisers maps some non-ASCII characters to ASCII (for example `ſ` to `S`, `ı` to `I`), so the stored value can differ from the typed one. Validation happens after normalisation, so no bypass.
- RC lookup oracle: a rejected user can resubmit a different plate (`rc_verification.py:189` overwrites the plate), so each account can test up to 3 plates for existence, blacklist status and owner-name match. Requires an OTP-verified phone per account.
- Role switching has no cool-down or limit (F-05).
- `GET /api/onboarding/status/` creates a profile row lazily (a write on GET); harmless.
- `OnboardingStatusView` and others expose only the caller's own data. `/api/auth/me/` fields are read-only.

## Checked and found fine

- AuthN/AuthZ: every view and its permission classes were enumerated. `DLSubmitView` `[IsAuthenticated, IsDriverRole]`; `DLStatusView` same; `VehicleRegisterView` and `VehicleStatusView` `[IsAuthenticated, RequireDriverRole]` (403 `not_a_driver`, unauthenticated still 401); `OnboardingStatusView`, `RoleSelectView`, `ProfileSubmitView`, `RoleSwitchView` `[IsAuthenticated]`. Only the two webhooks are `AllowAny`, with `authentication_classes = []` (so no CSRF exposure; JWT is header-based).
- No IDOR: no object ID appears in any URL or body; all lookups key on `request.user` (or on a webhook reference after signature validation).
- `active_role` and `onboarding_status` are never read from request data. `role` is a `ChoiceField(['driver','passenger'])`; `RoleSelectView` only works from `not_started` (`onboarding.py:70`) and the profile step only from `role_selected` (`onboarding.py:105`). No model serializers anywhere (no mass assignment).
- `switch_role` locks the profile row (`onboarding.py:255`), rejects `not_started`/`role_selected`, and never produces `complete` for a driver without a vehicle (flag on) or exemption; with a pending DL the user lands in `pending_verification`, with none or a rejected one in `awaiting_dl`. DL webhook only advances users still in `pending_verification` (`dl_verification.py:136`), so a user who switched to passenger is not gated out.
- RC service: three-phase design with the provider call outside any transaction; lock order is always profile then vehicle; phase 3 re-validates under lock; attempts increment under lock so the persisted count cannot exceed the cap; rejection is raised after commit (no `ATOMIC_REQUESTS` is set, so it does persist); provider reference-collision handled (`_save_vehicle`); result validation rejects bad status/reference (`rc_verification.py:132-143`).
- Logging: RC logging uses an allow-list (`_LOG_FIELDS`, `rc_verification.py:44-54`); `owner_name` is `repr=False` (`adapters/base.py:79`); no owner name, plate or DL appears in any `logger` call I found. The `profiles` logger propagates to the root JSON handler (no redaction filter, but nothing sensitive is logged). `unhandled_exception` logs the traceback but returns a generic envelope (`core/exceptions.py:75-79`); no stack trace reaches the client.
- Envelope `extra` keys: `check_error_extra` blocks `code`, `detail`, `fields`, `retry_after` (`core/envelope.py:37-44`) and is enforced in both `ApiError.__init__` and `error_envelope`. The extras used are `onboarding_status`, `next_step`, `rc_verification_status`, `rc_attempts_remaining`, all non-sensitive and about the caller.
- `ConditionalOnboardingGate` fails closed for unauthenticated callers, handles missing profiles, and returns only the caller's own status.
- `sanitise_reason` strips tags and control characters, redacts the owner name case-insensitively and truncates to 500; it is applied to every RC reason path (sync, webhook, staff). Weakness: redaction is exact-match, so a provider reason containing only a first name passes.
- Input validation: DL regex anchored and input stripped before matching (so the `$`-newline quirk does not apply); registration normaliser removes all whitespace before the anchored regex; lengths capped (`dl_number` 20, `registration_number` 15, names 50); no catastrophic backtracking patterns (`_RELATION_RE`, `_MASKED_RUN_RE`, name regex are linear); `age` validated 18-80 via DRF `IntegerField`; DRF `CharField` rejects NUL.
- Duplicate-plate handling gives no enumeration oracle to drivers: there is no uniqueness error, and the duplicate count is only in a staff log and the admin.
- Settings: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `JWT_SIGNING_KEY`, `OTP_PEPPER` have no defaults, so a missing value fails at startup; HSTS and secure cookies are on when `DEBUG` is off; CORS is an allow-list when `DEBUG` is off; the browsable API only in `DEBUG`. The RC guard (`settings.py:125-141`) is import-time and independent of the test runner; the factory re-checks the class (`adapters/__init__.py:26-29`). `RC_VERIFICATION_ENABLED` and `ONBOARDING_GATE_ENABLED` default to False. `.gitignore` excludes `backend/.env` and `*.env` and allows `.env.example`.
- Migrations: 0003 adds only nullable or defaulted columns, one partial unique index and indexes; nothing is dropped or rewritten. 0004's `RunPython` is idempotent and reversible (apart from F-10's rule).
- Admin RC actions: gated by `profiles.review_rc` (`permissions=['review_rc']` with `has_review_rc_permission`); service-layer state checks (`RCReviewStateError`); reject requires a non-empty sanitised reason; each action writes `log_change` and a structured log event with `staff_user_id`; the Vehicle admin is fully read-only with add and delete disabled.

## What could not be verified

- Tests were not run (no shell); I did not execute the migrations or the concurrency scenarios. F-04 and F-05 conclusions come from reading the transaction and lock structure.
- `.env.example` and `.env` were not opened (as instructed); I could not confirm what placeholders or values they carry (for example whether `RC_WEBHOOK_SECRET` or `DL_ENCRYPTION_KEY` are present).
- Real provider behaviour: no real DL or RC adapter exists in the tree, so provider-specific signature schemes, field formats and timeouts are unreviewed.
- Dependency advisories were not checked online (F-15 is from memory); Django 6.1 and the other pins post-date what I can independently confirm.
- Admin authentication (password policy, MFA, `/admin/` exposure) and the OTP/JWT flows belong to FEAT-001 and were not re-reviewed beyond how `request.user` is used here.
- Production topology (ALB, whether the app is reachable directly, WAF or rate limits at the edge): none exists in the repository, so I assumed no compensating layer.

## Prioritised fix list

1. F-01: settings-driven DL adapter with a forbidden-mock guard when `DEBUG` is off; fail closed. (Blocker for production.)
2. F-03: resolve the DL adapter at call time in the webhook view and test it. Do together with F-02.
3. F-02: real HMAC-SHA256 body signature for the DL webhook, required secret, constant-time compare, fail closed on empty. (Blocker before any async DL provider.)
4. F-04 and F-05: lock the profile and DL row in DL submit and move the provider call out of the transaction; add DRF throttles for DL, vehicle, role-switch and webhooks; add a per-user in-flight guard for RC. (Blockers before enabling RC with a paid provider.)
5. F-06: backfill/rollback policy for `NULL` and flag-off vehicles; never derive `complete` from a pending or rejected vehicle. (Blocker before enabling RC.)
6. F-07: clear the owner name on staff resolution; restrict the PII fieldset to `review_rc`; set a retention rule.
7. F-08: bind DL and RC to the person (name or DOB match, keyed-hash DL uniqueness, duplicate plates go to review).
8. F-10 (corrective migration), F-11 (read-only state fields in plain admins), F-09 and F-13 (typed errors, uniform webhook responses).
9. F-12, F-14, F-15 (startup key validation, MultiFernet, `pip-audit` and bump `cryptography`, UTF-8 requirements).
10. F-16: add the security tests listed; F-17: make the gate opt-out explicit and extend `IsDriverVerified` before ride endpoints are built.

## Residual Risk

- Until F-01 to F-03 are fixed, the DL step provides no identity assurance, and any deployment must treat all "verified" drivers as unverified.
- Even with the RC flag on and a correct provider, F-08 means RC verification confirms that a vehicle exists and that a name token matches, not that the account holder is the owner.
- Replay of signed RC webhooks is bounded by idempotency but not eliminated.
- Admin staff remain a trusted insider class with the ability to edit state directly until F-11 is addressed.
