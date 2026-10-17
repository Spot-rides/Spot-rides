# Requirement: User Onboarding Flow

**ID:** FEAT-002
**Type:** requirement
**Version:** 8
**Status:** ready
**Owner:** product-manager
**Date:** 2026-10-17
**Priority:** critical

**Changelog:**
- v8 (2026-10-17): Closes a gap: a `complete` Passenger had no way to become a Driver. FR-24 said a user switching to driver without a verified DL is "directed to complete DL submission", but the DL submission endpoint requires the driver role and an `awaiting_dl` / `pending_verification` status, so a `complete` Passenger could never submit a DL and the switch returned `400 dl_required`. Decided behaviour: (1) switching to `driver` with no `DriverVerification`, or a rejected one, now starts driver setup (`active_role = driver`, `onboarding_status = awaiting_dl`, `next_step = dl_submission`, `200`) with the RC flag ON or OFF, after which the normal DL -> vehicle -> (RC if enabled) flow applies unchanged and the DL attempt limit still applies; a pending DL keeps the `pending_verification` behaviour (FR-24). (2) Switching to `passenger` is always allowed from `awaiting_dl`, `awaiting_vehicle`, `pending_verification` and `pending_rc_verification`, flag ON or OFF; the result is `complete`, records are kept (FR-23, FR-52 broadened). (3) Switching to `driver` with a verified DL derives status from vehicle presence in both flag modes (FR-43): active vehicle or `vehicle_step_exempt` -> `complete`; otherwise `awaiting_vehicle`. This is a deliberate change to flag-OFF role-switch edge cases (v3 set `complete` for any verified-DL switch); the initial onboarding happy path with the flag OFF is unchanged (`200`, `complete`, `next_step none`). (4) `400 dl_required` on role switch is retired (superseded). (5) The v7 `400 invalid_onboarding_state` for driver-from-`awaiting_vehicle` (FR-55) is also retired: a switch to `driver` by a user already in an in-progress driver state is now an idempotent no-op. (6) The frontend must handle the `awaiting_dl` result of a role switch; while the onboarding gate (`ONBOARDING_GATE_ENABLED`) is on, a Passenger who starts driver setup is gated out of normal features until they finish or switch back to Passenger (accepted). Amended: FR-14 (wording), FR-22, FR-23, FR-24, FR-25, FR-26, FR-43, FR-52, FR-55; the `PATCH /api/profile/role/` contract, the `POST /api/onboarding/driver/dl/` access note and the status-values note; the Data Model `active_role` note and the state-machine diagrams; AC-22 (rewritten), AC-23, AC-25, AC-26, AC-49 (rewritten), AC-54, AC-57 (rewritten); new US-21, US-22 and AC-60 to AC-66; the edge cases, Dependencies, Assumptions, Success Metrics, and new open item OQ-R16. History entries for v5 to v7 are left as written; where they conflict with v8, v8 governs.
- v7 (2026-10-17): Contract refinements recorded to match the implementation. No change to product intent. (1) New FR-53 / AC-55: `vehicle_type` is accepted lowercase in requests and returned UPPERCASE in vehicle responses; response examples corrected. (2) New FR-54 / AC-56: API enum values for `onboarding_status`, `active_role` and `dl_verification_status` are lowercase in responses (`vehicle_type` is the uppercase exception); the uppercase model-constant names in this document are internal names. (3) New FR-55 / AC-57: with the flag ON, `PATCH /api/profile/role/` to `driver` from `awaiting_vehicle` returns `400 invalid_onboarding_state`. (4) New FR-56 / AC-58: `rejection_reason` is always `null` on successful (200/202) vehicle responses; a rejection arrives only as `422 rc_verification_rejected` with the sanitised reason in `error.detail`. (5) New FR-57 / AC-59: RC webhook 404 codes are `not_found` (flag OFF) and `rc_reference_not_found` (flag ON, unknown reference). Also amended for consistency: FR-51, AC-32, AC-43(e), AC-53(a), the `POST /api/onboarding/driver/vehicle/` and `GET /api/onboarding/driver/vehicle/status/` examples and notes, the RC webhook errors, the `PATCH /api/profile/role/` requirements line and errors, the Data Model note on internal names, the v5 assumption on `vehicle_type` casing, OQ-R12(c), and new open item OQ-R15.
- v6 (2026-10-17): Refinement of the grandfathered-driver rule, closing a gate bypass found in implementation: a Driver in `awaiting_vehicle` who never submitted a vehicle could switch to passenger and back and end up `complete` with no vehicle, because a missing vehicle row was being treated as "grandfathered". Exemption from the vehicle step is now an explicit marker, `UserProfile.vehicle_step_exempt`, set only by a one-time data migration. Amended: FR-43, AC-48, AC-54, the `UserProfile` data model, the Driver role-switch derivation (state machine), the `PATCH /api/profile/role/` contract text, the grandfathered-driver edge case, and a note on OQ-R12(b). The v5 (U1) wording ("a `complete` Driver with no vehicle row stays `complete` on a role round trip") is superseded by this refinement (see Assumptions). FR-52 is unchanged; with the flag OFF nothing changes.
- v5 (2026-10-15): Amendments after the architecture review (ARCH-002 v3, ADR items U1-U4), decided under the instruction "go with best decision". (U1) FR-43, AC-48, the Driver state machine and the grandfathered edge case: a `complete` Driver with no vehicle row stays `complete` on a role round trip. (U2) New FR-51 and AC-53: with the flag OFF the vehicle endpoint error responses must conform to the contract and the success response is unchanged; AC-28 and AC-29 depend on it. (U3) New FR-52 and AC-54: a user in `awaiting_vehicle` can always switch to passenger. (Gate) FR-14 and AC-41: the gate response format and its dependency on the additive error `extra` mechanism. (U4) Recorded as open item OQ-R14; OQ-R7 and OQ-R13 re-marked as not blocking the flag-off launch; OQ-R12(b) resolved.
- v4 (2026-10-15): Added vehicle RC (Registration Certificate) verification behind the `RC_VERIFICATION_ENABLED` feature flag (default OFF). Flag-off behaviour is unchanged from v3 and is an explicit requirement (FR-32). Added `pending_rc_verification` state, `awaiting_rc_verification` next step, RC status endpoint, RC webhook, mock adapter modes, attempt limit, admin review for owner-name mismatch, `switch_role` fix, data model additions, and resolutions of OQ-R1..OQ-R11 (recorded in the Open Questions table). Revised the v3 non-goal and assumption that excluded third-party vehicle verification. Source analysis: `docs/plans/PLAN-003-vehicle-rc-verification.md`.
- v3: Vehicle registration added to Driver onboarding (FR-27..FR-31).

---

## Summary

After a user completes OTP-based phone signup (FEAT-001), they must complete a
structured onboarding flow before accessing the main app. The flow captures
role selection (Driver or Passenger), personal details, and — for Drivers only
— driving licence (DL) verification via a third-party API and vehicle
registration. Vehicle registration can optionally be verified against the
vehicle's RC (Registration Certificate) through a provider adapter; this RC
verification is controlled by a feature flag that ships OFF. Onboarding state is
persisted server-side so a user can resume mid-flow on any device. The main app
experience is gated behind onboarding completion.

## Goal

Collect role, personal profile information, and (for Drivers) verified driving
licence status and vehicle registration details from every new user before
granting access to the Spot Rides main experience, with an optional,
feature-flagged RC verification of the Driver's vehicle that never blocks
onboarding while the flag is off.

## Problem

After FEAT-001, a successfully authenticated user has only a phone number on
record. The app has no role signal to distinguish Drivers from Passengers, no
name or demographic data needed to populate ride interfaces, and no mechanism to
vet drivers' licence validity before they begin offering rides. Without this
layer, no functional ride experience can be launched safely or legally.

Additionally, there is no gate preventing a partially-registered user from
accessing the main app, which would produce undefined behaviour downstream.

A Driver's vehicle is currently self-declared: nothing checks that the
registration number belongs to a real, valid vehicle, matches the declared
vehicle type, or is connected to the Driver. RC verification closes this gap
once a provider is available, without delaying launch.

## Users

| Role | Description |
|------|-------------|
| New Passenger | A user who completed OTP signup and is setting up their Passenger account for the first time. |
| New Driver | A user who completed OTP signup and intends to offer rides as a Driver (labeled "Rider" in the UI). |
| Returning partial user | A user who started onboarding on one device and resumes on another. |
| Existing Passenger who later wants to drive | **(v8)** A user who completed onboarding as a Passenger (`complete`, no verified DL) and later decides to offer rides. They start driver setup from within the app through the role switch (FR-24). |
| Operations / Trust & Safety | Internal team that reviews DL verification outcomes and RC verification reviews (owner-name mismatches), and may need to manually approve, reject, or unlock Driver accounts. |

## User Stories

| ID | Statement | Priority |
|----|-----------|---------|
| US-01 | As a new user, I want to choose whether I am a Passenger or a Driver (labeled "Rider") immediately after signup, so that the app can collect the right information. | must |
| US-02 | As a new Passenger, I want to enter my first name, last name, age, and gender, so that I can complete my profile and start booking rides. | must |
| US-03 | As a new Driver, I want to enter my first name, last name, age, and gender, so that I can proceed to the licence verification step. | must |
| US-04 | As a new Driver, I want to enter my Indian driving licence number and have it validated and verified, so that the platform can confirm I am legally permitted to drive. | must |
| US-05 | As a Driver whose DL verification is processing asynchronously, I want to know my account is pending approval, so that I am not left confused about whether sign-up succeeded. | must |
| US-06 | As a Driver whose DL was rejected, I want to resubmit a corrected DL number, so that a data entry error does not permanently block my account. | must |
| US-07 | As a returning user who started onboarding on another device, I want to resume from the step I left off, so that I do not have to restart the flow. | must |
| US-08 | As an unapproved user (onboarding incomplete or pending), I want any attempt to access the main app to redirect me back to onboarding, so that the experience remains consistent. | must |
| US-09 | As a fully onboarded Passenger, I want to switch to the Driver role from within the app, so that I can also offer rides without creating a new account. | must |
| US-10 | As a fully onboarded Driver with a verified DL, I want to switch to the Passenger role, so that I can book rides without offering them. | must |
| US-11 | As a user, I want the app to enforce that I can only act as a Driver when my DL is verified, so that unverified users cannot offer rides. | must |
| US-12 | As a new Driver, I want to register my vehicle (registration number and type) during onboarding, so that the platform knows what vehicle I will be using for rides. | must |
| US-13 | As a Driver, I want to see my registered vehicle details, so that I can verify the information is correct. | must |
| US-14 | As a new Driver, when RC verification is not enabled, I want vehicle registration to finish my onboarding straight away and take me to the home page, so that I can start using the app without extra steps. | must |
| US-15 | As a new Driver, when RC verification is enabled, I want my vehicle's registration to be checked automatically and to be told the outcome, so that riders can trust my vehicle. | should |
| US-16 | As a Driver whose vehicle verification is pending or under review, I want to see that my vehicle is being verified (without being accused of anything), so that I know what to expect. | should |
| US-17 | As a Driver whose vehicle verification was rejected, I want to see why and resubmit a corrected registration number, so that a typo does not permanently block me. | should |
| US-18 | As a Driver who drives a vehicle owned by a family member or fleet operator, I want my vehicle to go to a human review rather than being rejected outright, so that I am not wrongly blocked. | should |
| US-19 | As an Operations / Trust & Safety staff member, I want to see vehicles flagged for review (with owner-name match result and a duplicate-registration indicator) and to approve, reject, or reset attempts in admin, so that edge cases are resolved by a person. | should |
| US-20 | As an already-onboarded Driver, I want my account to remain fully active when RC verification is introduced, so that I am not locked out of the app. | must |
| US-21 | **(v8)** As a Passenger who completed onboarding and later wants to drive, I want to switch to the Driver role and be taken through driving licence submission, then vehicle registration (and RC verification if enabled), so that I can start offering rides without creating a new account. | must |
| US-22 | **(v8)** As a user partway through driver setup (waiting to submit a DL, waiting for DL or vehicle verification, or needing to register a vehicle), I want to switch back to Passenger at any time, so that I am never locked out of the app while I sort out driver requirements. | must |

## Functional Requirements

| ID | Description | Priority |
|----|-------------|---------|
| FR-01 | The backend must expose `GET /api/onboarding/status/` (authenticated) returning the user's current onboarding state, their active role (if set), and the next required step. | must |
| FR-02 | The backend must expose `POST /api/onboarding/role/` (authenticated) accepting `role` (`driver` or `passenger`). During initial onboarding, this step sets the role for the first time. | must |
| FR-03 | The backend must expose `POST /api/onboarding/profile/` (authenticated) accepting `first_name`, `last_name`, `age`, and `gender`. Requires role to have been selected (FR-02). | must |
| FR-04 | For Passengers, successful profile submission (FR-03) must immediately set `onboarding_status` to `complete` and make the account fully active. | must |
| FR-05 | For Drivers, successful profile submission (FR-03) must advance `onboarding_status` to `awaiting_dl` and require the next step. | must |
| FR-06 | The backend must expose `POST /api/onboarding/driver/dl/` (authenticated, Drivers only) accepting a DL number string. It must validate the format against the Indian DL pattern client-side (documented below) and also server-side before calling the external verification provider. | must |
| FR-07 | DL number format validation must enforce the Indian standard: two uppercase state-code letters, two-digit RTO code, four-digit year, seven-digit serial number, with an optional single space or hyphen between the RTO code and the year. Pattern: `^[A-Z]{2}[0-9]{2}[ -]?[0-9]{4}[0-9]{7}$`. Inputs failing this pattern must be rejected `400 invalid_dl_format` without calling the external provider. | must |
| FR-08 | The backend must call the configured DL verification provider after format validation. The integration must be implemented behind an abstract `DLVerificationAdapter` interface so the concrete provider can be swapped without modifying business logic. The concrete production adapter is `DigiLockerDLVerificationAdapter`, which implements the `DLVerificationAdapter` interface and communicates with the DigiLocker Pull URI API using OAuth 2.0 authentication. | must |
| FR-09 | If the DL verification provider responds synchronously with a verified result, `dl_verification_status` must be set to `verified` and `onboarding_status` must be set to `awaiting_vehicle` with `next_step = "vehicle_registration"` in the same request cycle. Driver onboarding is not complete until the vehicle registration step (FR-27) is also finished. | must |
| FR-10 | If the DL verification provider responds asynchronously (deferred/pending result), `onboarding_status` must be set to `pending_verification` and `dl_verification_status` to `pending`. The provider must be able to deliver the final result via a webhook endpoint. **Note:** DigiLocker uses a synchronous Pull URI API; this async/pending code path is retained as a fallback for timeout scenarios (e.g., when the DigiLocker API call exceeds the configured timeout and the result is treated as pending per NFR-REL-01) and for future-proofing if an async provider is ever substituted. It is not the primary flow with DigiLocker. | must |
| FR-11 | The backend must expose `POST /api/onboarding/driver/dl/webhook/` for inbound DL verification results from the provider. On receipt of a verified result, `dl_verification_status` is set to `verified` and `onboarding_status` to `awaiting_vehicle` (the Driver must still complete vehicle registration before onboarding is fully complete). On rejection, `dl_verification_status` is set to `rejected` and the Driver is notified (mechanism TBD — push notification is out of scope for this feature; the client must poll or the status must surface on next app open). **Note:** DigiLocker uses a synchronous API and does not deliver results via webhook. This endpoint is retained as a fallback for timeout-recovery workflows and for future-proofing if an async provider is ever integrated. It is not exercised in the primary DigiLocker flow. | must |
| FR-12 | The backend must expose `GET /api/onboarding/driver/dl/status/` (authenticated, Drivers only) so the mobile client can poll for DL verification outcome. | must |
| FR-13 | A Driver whose DL was rejected must be allowed to resubmit via `POST /api/onboarding/driver/dl/` with a corrected DL number. The maximum number of resubmission attempts before manual review is required is a configurable setting (default: 3). | must |
| FR-14 | Any authenticated request to a protected non-onboarding endpoint by a user whose `onboarding_status` is not `complete` must return `403 onboarding_incomplete` with the current `onboarding_status` and `next_step` in the response body, enabling the client to redirect the user. This applies equally to `pending_rc_verification`. **(v5)** When the onboarding gate blocks a request, the response must be `403` with error code `onboarding_incomplete` and the keys `onboarding_status` and `next_step` inside the `error` object (not a generic `permission_denied`). This requires the additive optional `extra` mechanism on the error envelope (extra keys merged flat into `error`; existing errors unchanged), which also carries the RC rejection data. **(v8)** The former `dl_required` error on role switch, which used the same mechanism to carry `next_step`, is retired (FR-24). | must |
| FR-15 | A Driver with `onboarding_status = pending_verification` or `pending_rc_verification` must not be able to accept ride requests. The backend must enforce this even if the client attempts to bypass the gate. | must |
| FR-22 | **(amended v8)** The backend must expose `PATCH /api/profile/role/` (authenticated) to allow an eligible user to switch their active role between `driver` and `passenger` from within the app. Eligible users are: (a) users whose `onboarding_status` is `complete`, who may switch in either direction at any time; and (b) users in an in-progress driver state (`awaiting_dl`, `awaiting_vehicle`, `pending_verification`, `pending_rc_verification`), who may always switch to `passenger` (FR-52), while a switch to `driver` is a no-op (FR-55). Users in `not_started` or `role_selected` are not eligible and receive `403 onboarding_incomplete`. The endpoint must not be blocked by the onboarding gate (FR-14) for eligible users. | must |
| FR-23 | When a user switches to `passenger` via FR-22, the switch must take effect immediately regardless of DL status and regardless of which in-progress driver state the user is in (FR-52). The existing `DriverVerification` record (if any) and `Vehicle` records are preserved so they can switch back to driver later without re-submitting their DL. | must |
| FR-24 | **(rewritten v8)** When an eligible `complete` user switches to `driver` via FR-22, the backend must act on the user's `DriverVerification` record, with `RC_VERIFICATION_ENABLED` ON or OFF: **(a) No `DriverVerification` record, or `dl_verification_status = rejected`:** the switch starts driver setup. `active_role = driver`, `onboarding_status = awaiting_dl`, `next_step = "dl_submission"`, HTTP `200`. The user then follows the normal flow unchanged: DL submission (FR-06), vehicle registration (FR-27) and, with the flag ON, RC verification (FR-33 to FR-40). The DL attempt limit (FR-13) still applies: the switch neither resets nor bypasses `attempt_count`. **(b) `dl_verification_status = pending`:** the user enters `pending_verification` (`active_role = driver`, HTTP `202`) and cannot offer rides until confirmed (existing behaviour, unchanged). **(c) `dl_verification_status = verified`:** the switch takes effect and the resulting status is derived from vehicle state per FR-43. The v3 to v7 behaviour for case (a), `400 dl_required` ("directed to complete DL submission" without any way to do so), is superseded and the `dl_required` error is retired for role switch. | must |
| FR-25 | Only a user with `dl_verification_status = verified` may use driver-facing endpoints (e.g. posting a ride offer). The backend must enforce this independently of the `active_role` field — having `active_role = driver` alone is not sufficient. **(v8)** This matters more now: a user who starts driver setup has `active_role = driver` while their DL is unsubmitted, pending or rejected (FR-24), and must not be able to use driver-facing endpoints until the DL is verified and onboarding is `complete`. | must |
| FR-26 | The `GET /api/onboarding/status/` and `GET /api/auth/me/` responses must include `active_role`, reflecting the role the user is currently operating as. This is the single source of truth for role; there is no separate immutable "registered role" field. **(v8)** `active_role = driver` can coexist with an in-progress `onboarding_status` (`awaiting_dl`, `awaiting_vehicle`, `pending_verification`, `pending_rc_verification`), including for a user who originally onboarded as a Passenger. Clients must read `onboarding_status` and `next_step` together with `active_role`; `active_role = driver` alone does not mean driver features are available. | must |
| FR-16 | Onboarding progress must be stored server-side and associated with the authenticated user so that resuming on a different device returns to the correct step. | must |
| FR-17 | Age must be validated as a positive integer between 18 and 80 inclusive. Any input outside this range must be rejected `400 invalid_age`. The minimum age of 18 applies equally to both Passengers and Drivers; no role-conditional age validation is needed. | must |
| FR-18 | Gender must be one of: `male`, `female`, `other`, `prefer_not_to_say`. Any other value must be rejected `400 invalid_gender`. | must |
| FR-19 | `first_name` and `last_name` must each be between 1 and 50 characters, contain only Unicode letters, spaces, hyphens, and apostrophes, and must not be blank or whitespace-only. | must |
| FR-20 | The DL number must be stored encrypted at rest using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) with the encryption key loaded from the `DL_ENCRYPTION_KEY` environment variable. The last four characters of the DL number must always be available in plaintext in `dl_number_display` for display/audit purposes. | must |
| FR-21 | The `GET /api/auth/me/` response (from FEAT-001) must be extended to include `onboarding_status` and `active_role` (nullable until set) so the Expo client can determine gating on app launch in a single call. | must |
| FR-27 | The backend must expose `POST /api/onboarding/driver/vehicle/` (authenticated, Drivers only) accepting `registration_number` and `vehicle_type`. This endpoint is only accessible to Drivers with `dl_verification_status = verified` (i.e., in `awaiting_vehicle` state). **When `RC_VERIFICATION_ENABLED` is OFF**, successful submission creates the `Vehicle`, sets `onboarding_status` to `complete`, and returns `next_step = "none"` (FR-32). **When the flag is ON**, the outcome depends on RC verification (FR-33 to FR-40). | must |
| FR-28 | Vehicle registration number must be validated against the Indian format: `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$` (2-letter state code, 2-digit RTO code, 1-3 letter series, 1-4 digit number). Input must be normalised to uppercase with spaces and hyphens stripped before validation. Inputs failing this pattern must be rejected `400 invalid_registration_format`. This validation applies regardless of the flag and runs before any provider call. | must |
| FR-29 | `vehicle_type` must be one of: `car`, `suv`, `hatchback`, `sedan`, `auto_rickshaw`, `bike`. Any other value must be rejected `400 invalid_vehicle_type`. **(v7)** These lowercase values are the accepted request values; responses return the uppercase form (FR-53). | must |
| FR-30 | For v1, a Driver can register exactly one active vehicle during onboarding. Attempting to register a second vehicle must be rejected `409 vehicle_already_registered`. **Exception (flag ON only):** when the Driver's existing vehicle has `rc_verification_status = rejected`, resubmission is permitted and must update that same `Vehicle` row in place (FR-37) rather than creating a second row. | must |
| FR-31 | Vehicle registration number is stored plaintext (no encryption needed — it is publicly visible on the vehicle). | must |
| FR-32 | **Flag-off completion rule (top priority).** RC verification is controlled by the boolean setting `RC_VERIFICATION_ENABLED`, which defaults to OFF and is read from environment configuration. **While the flag is OFF, vehicle registration must complete Driver onboarding exactly as it does today:** `POST /api/onboarding/driver/vehicle/` creates the `Vehicle`, sets `onboarding_status = complete`, and returns `200` with `next_step = "none"`. The request and response shape is identical to v3 (the additive RC response fields of FR-41 may appear only as `null`). No RC adapter call is made, no RC attempt is counted, no RC state is evaluated, and the new Vehicle row has `rc_verification_status = null`. RC verification must never block, delay, or fail onboarding while the flag is OFF. The client redirect to the home page is client behaviour driven by `onboarding_status = complete` / `next_step = "none"`; the backend's responsibility is the API contract only, and the redirect screen work is a separate frontend task. | must |
| FR-33 | **(Flag ON)** After format and `vehicle_type` validation (FR-28, FR-29), the backend must verify the registration number through an abstract `RCVerificationAdapter` interface so the provider can be swapped without changing business logic. The only adapter built in v1 is `MockRCVerificationAdapter`; no real provider adapter is built until a provider is selected (see Non-Goals). The adapter is obtained through configuration (`RC_ADAPTER_CLASS`), not a hardcoded global. | must |
| FR-34 | **(Flag ON)** A new onboarding state `pending_rc_verification` must exist, with `next_step = "awaiting_rc_verification"`. It means the Driver has submitted a vehicle whose verification is pending, timed out, or flagged for admin review. It is gated by FR-14 and FR-15 like `pending_verification`. | must |
| FR-35 | **(Flag ON, synchronous pass)** If the adapter returns `verified`, the owner-name match (FR-38) is `match`, and the RC vehicle class is compatible with or unknown for the declared `vehicle_type` (FR-39), then `Vehicle.rc_verification_status` is set to `verified`, `onboarding_status` is set to `complete`, and the response is `200` with `next_step = "none"`. | must |
| FR-36 | **(Flag ON, pending / timeout)** If the adapter returns `pending`, or the provider call exceeds `RC_PROVIDER_TIMEOUT_SECONDS` (default 5), the result is treated as pending: `rc_verification_status = pending`, `onboarding_status = pending_rc_verification`, `next_step = "awaiting_rc_verification"`, response `202`. A timeout must never surface as a 500. A pending vehicle resolves through the RC webhook (FR-42) or staff action in admin (FR-44). | must |
| FR-37 | **(Flag ON, rejection)** If the adapter returns `rejected`, or the RC vehicle class conflicts with the declared `vehicle_type`, then `rc_verification_status = rejected`, a sanitised `rc_rejection_reason` is stored (max 500 characters), `onboarding_status` stays (or returns to) `awaiting_vehicle`, and the response is `422 rc_verification_rejected` carrying `onboarding_status`, `next_step = "vehicle_registration"` and the sanitised reason. The Driver may resubmit via the same endpoint; resubmission must update the same `Vehicle` row in place (replacing `registration_number` and `vehicle_type`), preserving `rc_attempt_count`. A rejection reached through the webhook or admin (from `pending_rc_verification`) returns the Driver to `awaiting_vehicle` in the same way. Objective failures that are rejected include: RC not found, vehicle blacklisted/blocked, and a clear vehicle-class conflict. | must |
| FR-38 | **(Flag ON, owner-name match)** The service layer (not the adapter) must compare the RC owner name against the Driver's profile name (`first_name` + `last_name`) and classify it as `match`, `partial`, `mismatch`, or `not_checked` (provider returned no owner, or a masked owner that cannot be compared). Only `match` allows automatic verification. For `partial`, `mismatch`, and `not_checked`, when the provider otherwise returned `verified`, the vehicle must NOT be rejected: it is flagged for admin review (`rc_verification_status = pending`, `rc_name_match` recorded), `onboarding_status` moves to `pending_rc_verification`, and the response is `202`. Family-owned and fleet-owned vehicles use this review path; v1 collects no extra evidence from the Driver. The Driver-facing copy and API fields must not state or imply a name mismatch. | must |
| FR-39 | **(Flag ON, vehicle class)** A documented mapping from `vehicle_type` (`car`, `suv`, `hatchback`, `sedan`, `auto_rickshaw`, `bike`) to RC vehicle classes must be maintained (exact mapping table is defined in the architecture document). A vehicle is rejected for class only on a clear conflict (e.g. declared `car` but the RC class is two-wheeler). If the RC class is missing or unrecognised, the check is skipped and does not reject. | must |
| FR-40 | **(Flag ON, attempt limit)** The maximum number of RC verification submissions per vehicle is `RC_MAX_ATTEMPTS` (default 3, configurable without a code change). The limit is checked before the provider call; exceeding it returns `429 max_rc_attempts_exceeded`. A provider error (`422 rc_verification_provider_error`) must not consume an attempt. A submission that reaches a provider result (verified, pending, timeout, rejected) consumes one attempt. After the limit is reached, only a staff member can recover the Driver, by resetting attempts or manually approving in admin (a Driver may still switch to passenger meanwhile, FR-52). Stale `pending_rc_verification` entries are not auto-rejected in v1. | must |
| FR-41 | **(API additions)** The `POST /api/onboarding/driver/vehicle/` response gains the additive fields `rc_verification_status` (`null` / `pending` / `verified` / `rejected`), `rejection_reason`, and `reference_id` (all nullable). The backend must also expose `GET /api/onboarding/driver/vehicle/status/` (authenticated, Drivers only, not blocked by the onboarding gate) so the client can poll the vehicle verification outcome. Existing fields and their meaning are unchanged. Submitting while `pending_rc_verification` returns `409 rc_verification_pending`; submitting for an already-verified vehicle returns `409 rc_already_verified`. | must |
| FR-42 | **(Flag ON, webhook)** The backend must expose `POST /api/onboarding/driver/vehicle/rc/webhook/` for inbound asynchronous RC results. The request signature must be validated before any database access or payload processing; invalid or missing signatures return `403` and change no state. The handler is idempotent: a result for a reference already in a terminal state returns `409 already_processed` without modifying data. A verified webhook result applies the same name-match and class rules as FR-38 and FR-39. This endpoint is a fallback for async-capable providers and for the mock `async_pending` mode. While the flag is OFF it must not change any onboarding state. | must |
| FR-43 | **(`switch_role` vehicle-state derivation; rewritten v8)** `PATCH /api/profile/role/` switching to `driver` by a user with `dl_verification_status = verified` must derive the resulting `onboarding_status` from vehicle state. It must never set `complete` merely because the DL is verified. This applies with `RC_VERIFICATION_ENABLED` ON **and OFF**. **Flag OFF:** an active vehicle (`Vehicle.is_active = true`) or `vehicle_step_exempt = true` -> `complete` (`next_step = "none"`); no active vehicle and not exempt -> `awaiting_vehicle` with `next_step = "vehicle_registration"`. RC status of the vehicle is not evaluated with the flag OFF. **Flag ON (RC derivation, unchanged from v4 to v6):** verified vehicle, or a legacy vehicle with `rc_verification_status = null` (grandfathered per FR-45) -> `complete`; a `rejected` vehicle -> `awaiting_vehicle` (`next_step = "vehicle_registration"`); a `pending` vehicle -> `pending_rc_verification`; no active vehicle -> `complete` only if exempt, otherwise `awaiting_vehicle`. **(v6, retained)** A driver is exempt from the vehicle step only if explicitly marked grandfathered (`UserProfile.vehicle_step_exempt = true`), which is set solely by the one-time data migration (see Data Model Changes). A missing vehicle record alone never implies exemption. A driver with the marker and no active vehicle record stays `complete` (`next_step = "none"`). The marker is never set by any user, API, DL-verification or admin action after the migration. `pending_rc_verification` is treated like `pending_verification` for the rule that permits switching to `passenger` (FR-52). **Consequence:** `complete` is never reachable for a Driver without an active vehicle unless grandfathered. **Deliberate change (v8) to flag-OFF role-switch edge cases:** in v3 to v7 the flag-OFF switch to driver with a verified DL set `complete` unconditionally, including for users with no vehicle. That is superseded, because with FR-24 a Passenger can now acquire a verified DL through role switching and would otherwise reach `complete` without ever registering a vehicle. The initial onboarding happy path with the flag OFF is unchanged: `POST /api/onboarding/driver/vehicle/` still returns `200`, `onboarding_status = complete`, `next_step = "none"` (FR-32). | must |
| FR-44 | **(Admin review)** Staff users must be able, in Django admin, to: see vehicles with `rc_verification_status`, `rc_name_match`, `rc_attempt_count`; filter by status and name match; search by registration number; see an indicator of how many other drivers have registered the same registration number (FR-46); approve a pending vehicle (Driver -> `complete`); reject a pending vehicle with a reason (Driver -> `awaiting_vehicle`); and reset `rc_attempt_count`. Owner name is visible to staff only, on the detail view. Review actions must be audit-logged with the acting staff user. | should |
| FR-45 | **(Existing drivers)** Drivers who already have `onboarding_status = complete` when RC verification is introduced must NOT be moved back to any earlier state or forced to verify. Their existing `Vehicle` rows (if any) keep `rc_verification_status = null`; no backfill is performed. An optional later phase may add a post-onboarding verify prompt (see Non-Goals). | must |
| FR-46 | **(Duplicates)** Several Drivers may register the same `registration_number` in v1: no unique constraint is added. A non-unique database index on `registration_number` must be added, and the admin view must show a duplicate indicator (count of other drivers with the same number). A duplicate registration must be logged at WARNING level without logging personal data. | must |
| FR-47 | **(Data handling)** The RC owner name is stored (needed for name matching and admin review) and is visible only to staff. Only the fields needed for matching, review, and display are stored; the raw provider payload must not be stored; the owner name must not be written to logs (log the match classification only); the Driver-facing API must not expose the owner name or other RC-derived owner data. The retention period is an open item for legal/compliance (see Open Questions, OQ-R7). | must |
| FR-48 | **(Informational RC data)** If the provider returns fitness-valid-upto or insurance-valid-upto dates, they are stored but are informational only in v1: expired fitness or insurance must not reject or delay a vehicle. | should |
| FR-49 | **(Mock adapter modes)** `MockRCVerificationAdapter` must support the modes `sync_verified` (default), `sync_verified_name_mismatch`, `async_pending`, `sync_rejected`, `timeout`, and `provider_error`, selected through configuration (`RC_ADAPTER_MOCK_RESULT`). Their effects: `sync_verified` -> verified with owner name equal to the user's profile name; `sync_verified_name_mismatch` -> provider-verified with a different owner name, so the vehicle is flagged for review (FR-38); `async_pending` -> pending with a reference id; `sync_rejected` -> rejected with a reason; `timeout` -> timeout handled as pending (FR-36); `provider_error` -> `422 rc_verification_provider_error`, no attempt consumed. The mock is for development and test only and must not be usable in production when RC verification is enabled. | must |
| FR-50 | **(Provider error)** If the adapter raises a non-timeout error, `POST /api/onboarding/driver/vehicle/` must return `422 rc_verification_provider_error` (never a 500), the Driver stays in `awaiting_vehicle`, the attempt is not consumed, and operators are alerted through logs. | must |
| FR-51 | **(v5, U2: flag-off error contract)** With `RC_VERIFICATION_ENABLED` OFF, the success path of `POST /api/onboarding/driver/vehicle/` is unchanged: the `200` response keeps the same fields and values as today (the additive RC fields stay `null` per FR-32), with `vehicle_type` returned in the uppercase form defined in FR-53 (**v7**; v5 had required the then-current casing to be preserved byte-for-byte, see Assumptions). The ERROR responses, however, must conform to the contract regardless of the flag: `400 invalid_registration_format` (FR-28), `400 invalid_vehicle_type` (FR-29), `403 not_a_driver` for a non-Driver (e.g. a Passenger), and `409 vehicle_already_registered` for a `complete` Driver who posts a vehicle again (FR-30). Today the flag-off endpoint returns a generic `400 invalid_request`, `403 permission_denied`, and `403 dl_not_verified` respectively; this is a deliberate, approved change to flag-off error bodies only. AC-28 and AC-29 as written depend on this requirement. | must |
| FR-52 | **(v5, U3: never locked out; broadened v8)** A user in **any** in-progress driver state, that is `awaiting_dl`, `awaiting_vehicle` (including a Driver whose vehicle was rejected or whose RC attempts are exhausted), `pending_verification` or `pending_rc_verification`, must always be able to switch to passenger via `PATCH /api/profile/role/`, with `RC_VERIFICATION_ENABLED` ON or OFF. The switch takes effect immediately, the result is `onboarding_status = complete` and `active_role = passenger`, the `DriverVerification` and `Vehicle` records are preserved (no field on them is changed, including `attempt_count`, `rc_attempt_count` and `vehicle_step_exempt`), and the user is not gated out of the app as a passenger. The endpoint must not be blocked by the onboarding gate (FR-14) for these transitions. Before v8 this requirement was written for `awaiting_vehicle` only and its flag-OFF coverage was implicit. | must |
| FR-53 | **(v7, `vehicle_type` casing)** `vehicle_type` is accepted in requests in lowercase (`car`, `suv`, `hatchback`, `sedan`, `auto_rickshaw`, `bike`; FR-29) and is returned in UPPERCASE (`CAR`, `SUV`, `HATCHBACK`, `SEDAN`, `AUTO_RICKSHAW`, `BIKE`) in the `vehicle` object of the `POST /api/onboarding/driver/vehicle/` response and in the `vehicle_type` field of the `GET /api/onboarding/driver/vehicle/status/` response. This applies with the flag ON or OFF. | must |
| FR-54 | **(v7, enum casing)** API enum values for `onboarding_status`, `active_role` and `dl_verification_status` are lowercase in responses (for example `complete`, `driver`, `verified`). `vehicle_type` (FR-53) is the single uppercase exception. The uppercase names used elsewhere in this document for model constants and choices (for example `AWAITING_VEHICLE`, `COMPLETE`, `DRIVER`, `VERIFIED`, `PENDING_RC_VERIFICATION`) are internal names, not API values. | must |
| FR-55 | **(v7, reconciled v8: role switch to `driver` by a user already in an in-progress driver state)** `PATCH /api/profile/role/` with `role = "driver"` by a user whose `onboarding_status` is `awaiting_dl`, `awaiting_vehicle`, `pending_verification` or `pending_rc_verification` (such a user already has `active_role = driver`, see FR-52) is an idempotent no-op, with the flag ON or OFF: nothing changes (`active_role`, `onboarding_status`, `DriverVerification` and `Vehicle` are untouched, and no vehicle-state derivation per FR-43 is run), and the response returns the current `active_role`, `onboarding_status`, `next_step` and `dl_verification_status` (`202` for `pending_verification`, `200` otherwise, matching the corresponding switch responses in the API contract). This supersedes the v7 rule that, with the flag ON, this request from `awaiting_vehicle` returned `400 invalid_onboarding_state`: the user is already in the driver role, a derivation could otherwise move them out of an in-progress state (for example to `complete` with the flag OFF and an inactive-flag-era vehicle row), and a single no-op rule is consistent across all four states and both flag modes. `invalid_onboarding_state` is no longer a documented error of this endpoint. A switch to `passenger` from these states is unaffected (FR-52). | must |
| FR-56 | **(v7, vehicle response `rejection_reason`)** On every successful (`200` or `202`) `POST /api/onboarding/driver/vehicle/` response, `rejection_reason` is always `null`. A rejection is delivered only as `422 rc_verification_rejected`, with the sanitised reason in `error.detail` (FR-37). | must |
| FR-57 | **(v7, RC webhook 404 codes)** `POST /api/onboarding/driver/vehicle/rc/webhook/` returns `404 not_found` when `RC_VERIFICATION_ENABLED` is OFF (no state change, FR-42), and `404 rc_reference_not_found` when the flag is ON and the `reference_id` matches no vehicle. | must |

## API Contract

All responses use the unified envelope defined in DEC-011:

```json
{
  "success": true | false,
  "message": "...",
  "data": { ... } | null,
  "error": null | { "code": "...", "detail": "...", "fields": { ... } },
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

The `data` payloads described below are the contents of the `data` key.

**(v5)** Several errors in this contract carry additional keys inside `error`
(`onboarding_status`, `next_step`, `rc_verification_status`,
`rc_attempts_remaining`). This depends on an additive, optional `extra`
mechanism on the error envelope: extra keys are merged flat into `error`, keys
that collide with the reserved envelope keys are not allowed, and errors that
do not use it are unchanged (FR-14).

**(v7) Enum casing.** API enum values for `onboarding_status`, `active_role`
and `dl_verification_status` are lowercase in responses (for example `complete`,
`driver`, `verified`). `vehicle_type` is the one uppercase exception: it is
accepted lowercase in requests and returned UPPERCASE in vehicle responses
(FR-53, FR-54). Uppercase constant names elsewhere in this document are
internal names, not API values.

---

### `GET /api/onboarding/status/`

Requires: valid access token.

**Response `200 OK`:**
```json
{
  "onboarding_status": "not_started",
  "active_role": null,
  "next_step": "role_selection",
  "profile_complete": false,
  "dl_verification_status": null,
  "rc_verification_status": null
}
```

`onboarding_status` values: `not_started`, `role_selected`, `awaiting_dl`,
`pending_verification`, `awaiting_vehicle`, `pending_rc_verification`, `complete`.

**(v8)** `awaiting_dl` is also reached by a `complete` user who switches to
`driver` via `PATCH /api/profile/role/` without a verified or pending DL
(FR-24). For such a user `profile_complete` is `true` and `active_role` is
`driver`.

`next_step` values: `role_selection`, `profile`, `dl_submission`, `awaiting_verification`, `vehicle_registration`, `awaiting_rc_verification`, `none`.

`dl_verification_status` values: `null` (not a driver or not yet submitted),
`pending`, `verified`, `rejected`.

`rc_verification_status` (new, additive) values: `null` (no vehicle, flag off,
or legacy self-declared vehicle), `pending`, `verified`, `rejected`.

`pending_rc_verification` / `awaiting_rc_verification` are only reachable while
`RC_VERIFICATION_ENABLED` is ON (or for Drivers already in that state if the
flag is later turned off; see Edge Cases). With the flag OFF no user is moved
into this state.

---

### `POST /api/onboarding/role/`

Requires: valid access token. User must be in `not_started` state.

**Request:**
```json
{ "role": "passenger" }
```
`role` must be `"driver"` or `"passenger"`.

**Response `200 OK`:**
```json
{
  "active_role": "passenger",
  "onboarding_status": "role_selected",
  "next_step": "profile"
}
```

**Errors:**
- `400 invalid_role` — value not in allowed set
- `409 role_already_set` — role was already set on this account (initial onboarding only; use `PATCH /api/profile/role/` to switch after onboarding)

---

### `POST /api/onboarding/profile/`

Requires: valid access token. User must be in `role_selected` state.

**Request:**
```json
{
  "first_name": "Priya",
  "last_name": "Sharma",
  "age": 27,
  "gender": "female"
}
```

**Response `200 OK` (Passenger):**
```json
{
  "onboarding_status": "complete",
  "next_step": "none"
}
```

**Response `200 OK` (Driver):**
```json
{
  "onboarding_status": "awaiting_dl",
  "next_step": "dl_submission"
}
```

**Errors:**
- `400 invalid_age` — age outside 18–80
- `400 invalid_gender` — value not in allowed set
- `400 validation_error` — with `error.fields` map for name violations
- `409 profile_already_set` — profile was already submitted

---

### `POST /api/onboarding/driver/dl/`

Requires: valid access token. User must have `role = driver` and be in
`awaiting_dl` or `dl_rejected` state. Not accessible to Passengers.

**(v8)** A `complete` Passenger becomes eligible for this endpoint by switching
to `driver` via `PATCH /api/profile/role/`, which sets `active_role = driver` and
`onboarding_status = awaiting_dl` when no verified or pending DL exists (FR-24).
Until that switch the endpoint still returns `403 not_a_driver` (AC-20). The DL
attempt limit (`429 max_dl_attempts_exceeded`) applies to the user's lifetime
`attempt_count` regardless of how they entered the DL step.

**Request:**
```json
{ "dl_number": "MH01 20110012345" }
```

**Response `200 OK` (synchronous verified result — primary flow with DigiLocker):**
```json
{
  "dl_verification_status": "verified",
  "onboarding_status": "awaiting_vehicle",
  "next_step": "vehicle_registration"
}
```

**Response `202 Accepted` (timeout fallback — returned when the DigiLocker API call exceeds the configured timeout and the result is treated as pending):**
```json
{
  "dl_verification_status": "pending",
  "onboarding_status": "pending_verification",
  "next_step": "awaiting_verification"
}
```

**Errors:**
- `400 invalid_dl_format` — DL string does not match Indian format
- `403 not_a_driver` — endpoint called by a Passenger account
- `409 dl_already_verified` — DL is already in verified state
- `422 dl_verification_provider_error` — provider call failed; client may retry
- `429 max_dl_attempts_exceeded` — resubmission limit reached; manual review required

---

### `GET /api/onboarding/driver/dl/status/`

Requires: valid access token. Driver role only.

**Response `200 OK`:**
```json
{
  "dl_verification_status": "pending",
  "onboarding_status": "pending_verification",
  "rejection_reason": null
}
```

`rejection_reason` is a human-readable string when `dl_verification_status =
"rejected"`, otherwise `null`. The value comes from the provider and must be
sanitised before exposure.

---

### `POST /api/onboarding/driver/dl/webhook/`

**Note:** This endpoint is not exercised in the primary DigiLocker flow (DigiLocker uses synchronous responses). It is retained as a fallback for timeout-recovery and for future-proofing if an async provider is ever substituted.

Called by the DL verification provider. Authentication mechanism: if a webhook
is ever used, the provider must supply an HMAC-SHA256 signature header for
request authentication. The endpoint must reject unsigned or unverifiable
requests with `403`.

**Request (illustrative — exact shape determined by provider):**
```json
{
  "reference_id": "provider-ref-abc123",
  "status": "verified",
  "rejection_reason": null
}
```

**Response `200 OK`** on successful processing (regardless of verification
outcome). Provider must retry on any non-`200`.

**Errors:**
- `400` — malformed payload
- `403` — invalid signature / unauthenticated
- `404` — `reference_id` not found
- `409` — result already applied (idempotent re-delivery)

---

### `POST /api/onboarding/driver/vehicle/`

Requires: valid access token. User must have `role = driver` and `dl_verification_status = verified` (i.e., `onboarding_status = awaiting_vehicle`). Not accessible to Passengers or Drivers whose DL is not yet verified. Behaviour depends on `RC_VERIFICATION_ENABLED`.

**Request (unchanged; `vehicle_type` is sent lowercase, FR-53):**
```json
{
  "registration_number": "MH01AB1234",
  "vehicle_type": "sedan"
}
```

**Response `200 OK` — flag OFF (launch behaviour; identical to v3 apart from `vehicle_type` casing, FR-53), and flag ON with a synchronous pass:**
```json
{
  "onboarding_status": "complete",
  "next_step": "none",
  "vehicle": {
    "registration_number": "MH01AB1234",
    "vehicle_type": "SEDAN"
  },
  "rc_verification_status": null,
  "rejection_reason": null,
  "reference_id": null
}
```
With the flag OFF, `rc_verification_status` is `null`. With the flag ON and a pass, it is `"verified"` and `reference_id` carries the provider reference if any. `rejection_reason` is always `null` on a successful response (FR-56). `vehicle.vehicle_type` is returned UPPERCASE (FR-53). On this response the client is expected to redirect to the home page (client behaviour driven by `onboarding_status = complete` / `next_step = "none"`). **(v5, amended v7)** With the flag OFF this success response keeps the same fields and values as before the RC change (FR-51); the example above is illustrative of the shape, and `vehicle_type` is returned in the uppercase form defined in FR-53.

**Response `202 Accepted` — flag ON, pending / timeout / flagged for admin review:**
```json
{
  "onboarding_status": "pending_rc_verification",
  "next_step": "awaiting_rc_verification",
  "vehicle": {
    "registration_number": "MH01AB1234",
    "vehicle_type": "SEDAN"
  },
  "rc_verification_status": "pending",
  "rejection_reason": null,
  "reference_id": "mock-rc-1a2b3c4d"
}
```
The response must not reveal whether the cause is a provider delay or an owner-name review.

**Response `422 rc_verification_rejected` — flag ON, RC rejected (RC not found, blacklisted/blocked, or clear vehicle-class conflict):**
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "rc_verification_rejected",
    "detail": "Sanitised, human-readable rejection reason.",
    "onboarding_status": "awaiting_vehicle",
    "next_step": "vehicle_registration",
    "rc_verification_status": "rejected",
    "rc_attempts_remaining": 2
  }
}
```
The Driver stays in `awaiting_vehicle` and may resubmit; the same `Vehicle` row is reused. **(v7)** This `422` is the only place a vehicle rejection reason is delivered on this endpoint: the sanitised reason is in `error.detail`, and `rejection_reason` on the `200` / `202` responses is always `null` (FR-56).

**Errors (the first four apply with the flag ON or OFF, FR-51):**
- `400 invalid_registration_format` — registration number does not match Indian format `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$`
- `400 invalid_vehicle_type` — value not in allowed set (`car`, `suv`, `hatchback`, `sedan`, `auto_rickshaw`, `bike`)
- `403 not_a_driver` — endpoint called by a non-Driver (e.g. a Passenger account)
- `403 dl_not_verified` — Driver's DL is not in `verified` state
- `409 vehicle_already_registered` — Driver already has an active vehicle that is not in `rejected` RC state (flag OFF: any registered vehicle). A `complete` Driver posting again receives this code, not `dl_not_verified`.
- `409 rc_verification_pending` — (flag ON) a submission is already pending / under review
- `409 rc_already_verified` — (flag ON) the vehicle is already RC-verified
- `422 rc_verification_rejected` — (flag ON) see above
- `422 rc_verification_provider_error` — (flag ON) provider call failed with a non-timeout error; client may retry; attempt not consumed
- `429 max_rc_attempts_exceeded` — (flag ON) `RC_MAX_ATTEMPTS` reached; staff intervention required

Note: `rc_verification_rejected` is specified here as a `422` error (carrying `onboarding_status` and `next_step` in `error`) per the product decision to treat RC rejection as an error code. PLAN-003 suggested a `200` body convention; the architect confirmed `422` (OQ-R12a) using the additive error `extra` mechanism described above.

---

### `GET /api/onboarding/driver/vehicle/status/` (new)

Requires: valid access token. Driver role only. Not blocked by the onboarding gate (so a Driver in `pending_rc_verification` can poll).

**Response `200 OK`:**
```json
{
  "onboarding_status": "pending_rc_verification",
  "next_step": "awaiting_rc_verification",
  "rc_verification_status": "pending",
  "rejection_reason": null,
  "registration_number": "MH01AB1234",
  "vehicle_type": "SEDAN",
  "rc_attempts_remaining": 2
}
```
When no vehicle exists, vehicle fields and `rc_verification_status` are `null`. When the flag is OFF, `rc_verification_status` is `null` and `rc_attempts_remaining` is `null`. Owner name and other RC owner data are never returned. `rejection_reason` is sanitised. `vehicle_type` is returned UPPERCASE (FR-53).

**Errors:** `401` unauthenticated; `403 not_a_driver`.

---

### `POST /api/onboarding/driver/vehicle/rc/webhook/` (new, fallback)

Called by an async-capable RC provider (and used for the mock `async_pending` mode). Not authenticated by user token; authenticated by request signature (HMAC-SHA256 / provider mechanism; secret `RC_WEBHOOK_SECRET`). The signature must be verified before any database access.

**Request (illustrative):**
```json
{
  "reference_id": "mock-rc-1a2b3c4d",
  "status": "verified",
  "rejection_reason": null
}
```
`status` is `verified` or `rejected`.

**Response `200 OK`** on successful processing.

**Errors:**
- `400` — malformed payload
- `403 invalid_webhook_signature` — missing/invalid signature; no state change
- `404 not_found` — **(v7)** the flag is OFF; no state change (FR-57)
- `404 rc_reference_not_found` — **(v7)** the flag is ON and `reference_id` matches no vehicle (FR-57)
- `409 already_processed` — result already applied (idempotent re-delivery)

---

### `PATCH /api/profile/role/`

Requires: valid access token. **(v8, FR-22)** Eligible users are those with `onboarding_status = complete` (either direction), and users in an in-progress driver state (`awaiting_dl`, `awaiting_vehicle`, `pending_verification`, `pending_rc_verification`). In an in-progress state, switching to `passenger` is always allowed (FR-52) and switching to `driver` is a no-op (FR-55). Users in `not_started` or `role_selected` receive `403 onboarding_incomplete`. The endpoint is not blocked by the onboarding gate for eligible users. Behaviour is identical with `RC_VERIFICATION_ENABLED` ON or OFF except where stated for the vehicle derivation (FR-43).

**Request:**
```json
{ "role": "driver" }
```

**Response `200 OK` (switch to passenger, from `complete` or from any in-progress driver state; FR-23, FR-52):**
```json
{
  "active_role": "passenger",
  "dl_verification_status": "verified"
}
```
`dl_verification_status` reflects the user's current `DriverVerification` record (`null` if none, otherwise `pending`, `verified` or `rejected`). The resulting `onboarding_status` is `complete`, so the additive `onboarding_status` / `next_step` keys are absent. `DriverVerification` and `Vehicle` records are preserved.

**Response `200 OK` (switch to driver, DL verified, resulting status `complete` per FR-43: active vehicle or exempt, and with the flag ON a verified or legacy vehicle):**
```json
{
  "active_role": "driver",
  "dl_verification_status": "verified"
}
```

**Response `200 OK` (v8: switch to driver, no `DriverVerification` record or DL rejected, FR-24(a); flag ON or OFF):**
```json
{
  "active_role": "driver",
  "dl_verification_status": null,
  "onboarding_status": "awaiting_dl",
  "next_step": "dl_submission"
}
```
`dl_verification_status` is `null` when the user has never submitted a DL, or `"rejected"` when the previous DL was rejected. The client must continue with DL submission (`POST /api/onboarding/driver/dl/`).

**Response `202 Accepted` (switch to driver, DL is pending):**
```json
{
  "active_role": "driver",
  "onboarding_status": "pending_verification",
  "dl_verification_status": "pending"
}
```

**Response `200 OK` (switch to driver, DL verified, and per FR-43 no active vehicle and not grandfathered (flag ON or OFF), or with the flag ON a vehicle that is rejected / pending):**
```json
{
  "active_role": "driver",
  "dl_verification_status": "verified",
  "onboarding_status": "awaiting_vehicle",
  "next_step": "vehicle_registration"
}
```
or `onboarding_status = "pending_rc_verification"`, `next_step = "awaiting_rc_verification"` when the vehicle is pending (flag ON). The `onboarding_status` and `next_step` keys are additive and present only when the resulting status is not `complete`; **(v8)** for the `awaiting_dl` result above both keys are required, and the `202` pending-DL response above is unchanged. **(v6, amended v8)** A Driver with no active vehicle record receives the standard `200` response with the status remaining `complete` only if marked grandfathered (`vehicle_step_exempt = true`, FR-43); without the marker the response is the `awaiting_vehicle` / `vehicle_registration` example above. This applies with the flag ON **and OFF** (v3 to v7 returned `complete` with the flag OFF; deliberate change, FR-43).

**Response `200 OK` / `202 Accepted` (v8, no-op: switch to driver by a user already in an in-progress driver state, FR-55):** the response mirrors the user's current state and nothing is changed: `200` with the current `active_role`, `onboarding_status`, `next_step` and `dl_verification_status` for `awaiting_dl`, `awaiting_vehicle` and `pending_rc_verification`; `202` for `pending_verification`.

**Errors:**
- `400 invalid_role` — value not in allowed set
- ~~`400 dl_required`~~ — **(v8) retired.** Switching to driver with no DL on file or a rejected DL now starts driver setup (`200`, `awaiting_dl`, FR-24(a)) instead of erroring.
- ~~`400 invalid_onboarding_state`~~ — **(v8) retired** for this endpoint. The v7 case (flag ON, switching to `driver` while in `awaiting_vehicle`) is now a no-op (FR-55).
- `403 onboarding_incomplete` — user is in `not_started` or `role_selected` (initial onboarding not yet through the profile step); the error carries `onboarding_status` and `next_step`. Users in an in-progress driver state are not an error (FR-52, FR-55).

---

### Extended `GET /api/auth/me/` (FEAT-001 amendment)

The existing response must include two additional fields:

```json
{
  "id": 42,
  "phone_number": "+919812345678",
  "date_joined": "2026-09-23T10:00:00Z",
  "onboarding_status": "complete",
  "active_role": "passenger"
}
```

- `active_role` — the role the user is currently operating as; the single source of truth for role (changes via `PATCH /api/profile/role/`)
- `active_role` is `null` for users who have not started onboarding.
- `onboarding_status` may now also be `pending_rc_verification`.
- **(v8)** `active_role = "driver"` may be returned together with an in-progress `onboarding_status` (FR-26); clients must gate driver features on `onboarding_status = complete` as well.

---

## Data Model Changes

**(v7)** Uppercase choice names in the tables below (for example `DRIVER`, `AWAITING_VEHICLE`, `CAR`) are internal model-constant names. They are not API values: API enum values are lowercase except `vehicle_type`, which is returned uppercase (FR-53, FR-54).

### New model: `UserProfile`

Proposed app: `profiles` (created via `python manage.py startapp profiles`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField | PK |
| `user` | OneToOneField → `accounts.User` | `on_delete=CASCADE`, `related_name="profile"` |
| `active_role` | CharField(10, choices) | `DRIVER`, `PASSENGER`; the role currently in use; set during onboarding and freely mutable afterwards via `PATCH /api/profile/role/`; nullable until onboarding step 1. **(v8)** `DRIVER` may coexist with an in-progress `onboarding_status` (FR-26), including for a user who originally onboarded as a Passenger |
| `first_name` | CharField(50) | nullable until step 2 |
| `last_name` | CharField(50) | nullable until step 2 |
| `age` | PositiveSmallIntegerField | nullable until step 2 |
| `gender` | CharField(20, choices) | `MALE`, `FEMALE`, `OTHER`, `PREFER_NOT_TO_SAY`; nullable until step 2 |
| `onboarding_status` | CharField(30, choices) | `NOT_STARTED`, `ROLE_SELECTED`, `AWAITING_DL`, `PENDING_VERIFICATION`, `AWAITING_VEHICLE`, `PENDING_RC_VERIFICATION` (new, value `pending_rc_verification`, 24 chars), `COMPLETE` |
| `vehicle_step_exempt` | BooleanField | **(v6)** default `False`, `db_default False`. Marks a Driver as grandfathered, i.e. exempt from the vehicle step (FR-43, FR-45). Set only by data migration 0004 (`0004_userprofile_vehicle_step_exempt`); never written by application code, any API, DL verification, or admin; read-only in admin |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

Adding `PENDING_RC_VERIFICATION` is a choices change only; no data migration.

**(v6)** `vehicle_step_exempt` is added by an additive migration, and its values are set by the one-time data migration 0004. Marking rule: at migration time, a profile is marked `vehicle_step_exempt = true` if it is `complete`, has a `DriverVerification` record, and has no active `Vehicle` row. Edge cases of this rule: (a) a `complete` Driver whose only vehicle is inactive (`is_active = false`) counts as having no active vehicle and is marked; (b) a `complete` profile whose `DriverVerification` record is pending or rejected is also marked, which is harmless because switching to driver still requires a verified DL (FR-24, FR-25). No profile is marked after the migration, and the migration changes no `onboarding_status` (FR-45).

A `UserProfile` row must be created automatically when a user completes OTP
verification for the first time (i.e., on first login / `is_new_user=true`
event from FEAT-001).

### New model: `DriverVerification`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField | PK |
| `user` | OneToOneField → `accounts.User` | `on_delete=CASCADE`, `related_name="driver_verification"` |
| `dl_number` | CharField(20) | Stored encrypted at rest using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256); see FR-20 |
| `dl_number_display` | CharField(4) | Last 4 chars of DL number, always plaintext |
| `dl_verification_status` | CharField(20, choices) | `PENDING`, `VERIFIED`, `REJECTED` |
| `dl_verification_ref` | CharField(100, nullable) | Provider-issued reference ID for async lookup |
| `dl_submitted_at` | DateTimeField | Timestamp of most recent submission |
| `dl_verified_at` | DateTimeField(nullable) | Timestamp of verification confirmation |
| `dl_rejection_reason` | TextField(nullable) | Provider-supplied reason |
| `attempt_count` | PositiveSmallIntegerField(default=0) | Number of DL submissions; enforces FR-13 |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

### New model: `Vehicle`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField | PK |
| `user` | ForeignKey → `accounts.User` | `on_delete=CASCADE`, `related_name="vehicles"` |
| `registration_number` | CharField(15) | Indian vehicle registration number; stored plaintext (FR-31); non-unique index added (FR-46) |
| `vehicle_type` | CharField(20, choices) | `CAR`, `SUV`, `HATCHBACK`, `SEDAN`, `AUTO_RICKSHAW`, `BIKE` |
| `is_active` | BooleanField(default=True) | For future multi-vehicle support |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

### `Vehicle` additions for RC verification (v4; all nullable or defaulted, additive migration)

| Column | Type | Notes |
|--------|------|-------|
| `rc_verification_status` | CharField(20, null, choices) | `pending`, `verified`, `rejected`; `null` = never RC-verified (flag off, or legacy self-declared); indexed |
| `rc_verification_ref` | CharField(100, null) | Provider reference; unique when not null |
| `rc_submitted_at` | DateTimeField(null) | Most recent submission |
| `rc_verified_at` | DateTimeField(null) | Verification confirmation (provider or staff) |
| `rc_rejection_reason` | TextField(null) | Sanitised, max 500 characters |
| `rc_attempt_count` | PositiveSmallIntegerField(default=0) | Per vehicle row; the row is reused on resubmit (FR-37); enforces FR-40 |
| `rc_owner_name` | CharField(100, null) | PII; staff-only; retention per OQ-R7 |
| `rc_name_match` | CharField(15, null, choices) | `match`, `partial`, `mismatch`, `not_checked` |
| `rc_vehicle_class` | CharField(50, null) | Provider's RC class string; compared via the mapping in FR-39 |
| `rc_fuel_type` | CharField(30, null) | |
| `rc_fitness_valid_upto` | DateField(null) | Informational only (FR-48) |
| `rc_insurance_valid_upto` | DateField(null) | Informational only (FR-48) |

Data minimisation: only the fields above are stored; the raw provider payload is not stored. No column is added to `accounts.User`.

### Onboarding state machine (Driver)

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

Async/timeout fallback path (DL):
```
AWAITING_DL
  → (DL submitted, provider timeout) →
PENDING_VERIFICATION
  → (DL verified via webhook or retry) →
AWAITING_VEHICLE
  → (vehicle registered) →
COMPLETE
```

Vehicle step, flag OFF (launch behaviour, identical to v3):
```
AWAITING_VEHICLE --POST vehicle--> COMPLETE   (next_step = "none")
```

Vehicle step, flag ON:
```
AWAITING_VEHICLE --POST vehicle, sync pass-----------------------> COMPLETE
AWAITING_VEHICLE --POST vehicle, pending / timeout / name review-> PENDING_RC_VERIFICATION
AWAITING_VEHICLE --POST vehicle, rejected------------------------> AWAITING_VEHICLE (same Vehicle row reused on resubmit)
PENDING_RC_VERIFICATION --webhook / admin approve----------------> COMPLETE
PENDING_RC_VERIFICATION --webhook / admin reject-----------------> AWAITING_VEHICLE
```

Role switch to driver by a `COMPLETE` user (`PATCH /api/profile/role/`), flag ON **or OFF**, by DL state (v8, FR-24):
```
no DriverVerification record, or DL REJECTED --> AWAITING_DL              (200, next_step = "dl_submission"; DL attempt limit still applies)
DL PENDING ----------------------------------> PENDING_VERIFICATION      (202; existing behaviour)
DL VERIFIED ---------------------------------> derived from vehicle state (next two diagrams)
```
From `AWAITING_DL` the normal Driver flow applies unchanged: DL verified -> `AWAITING_VEHICLE` -> vehicle step (flag OFF or ON diagrams above) -> `COMPLETE`. The DL attempt limit (FR-13) applies throughout.

Role switch to driver, DL verified, flag OFF (v8, FR-43; deliberate change from v3):
```
active vehicle ---------------------------------> COMPLETE   (next_step = "none")
no active vehicle, vehicle_step_exempt = true --> COMPLETE   (grandfathered; next_step = "none")
no active vehicle, vehicle_step_exempt = false -> AWAITING_VEHICLE   (next_step = "vehicle_registration")
```

Role switch to driver, flag ON, DL verified (v5, FR-43; no-vehicle rows revised in v6):
```
vehicle verified or legacy null ------------------> COMPLETE
vehicle pending ----------------------------------> PENDING_RC_VERIFICATION
vehicle rejected ---------------------------------> AWAITING_VEHICLE
no active vehicle, vehicle_step_exempt = true ----> COMPLETE   (grandfathered, FR-45; next_step = "none")
no active vehicle, vehicle_step_exempt = false ---> AWAITING_VEHICLE   (next_step = "vehicle_registration")
```
(v6) A missing vehicle record alone never implies exemption; only the `vehicle_step_exempt` marker does (FR-43). The marker is set only by data migration 0004.

(v8, replaces the v7 paragraph) The derivations above apply to a user who is `complete` (a Passenger, or a user who switched to passenger earlier) and switches to driver. A switch to driver by a user already in an in-progress driver state (`AWAITING_DL`, `AWAITING_VEHICLE`, `PENDING_VERIFICATION`, `PENDING_RC_VERIFICATION`) is not derived: it is an idempotent no-op with the flag ON or OFF (FR-55). The v7 `400 invalid_onboarding_state` for `AWAITING_VEHICLE` with the flag ON is retired.

Role switch to passenger from any in-progress driver state (v5 FR-52, broadened v8; flag ON or OFF):
```
AWAITING_DL ------------\
AWAITING_VEHICLE -------+--PATCH role=passenger--> COMPLETE   (never locked out; DriverVerification and Vehicle records preserved)
PENDING_VERIFICATION ---|
PENDING_RC_VERIFICATION-/
```

Passenger path (unchanged):
```
NOT_STARTED → ROLE_SELECTED → COMPLETE
```

### Migration dependency

`profiles` migrations must depend on `accounts` migrations (the custom
`AUTH_USER_MODEL` must exist before the FK is created). The RC additions are a
new additive migration depending on the Vehicle migration (the architect may
decide to fold it into the not-yet-deployed Vehicle migration).

### `accounts.User` model — no schema change required

`onboarding_status` and `role` are exposed on `GET /api/auth/me/` by joining
through `UserProfile`; the `User` table itself is not modified.

### Configuration (new settings)

| Setting | Default | Purpose |
|---------|---------|---------|
| `RC_VERIFICATION_ENABLED` | `False` | Master feature flag (FR-32) |
| `RC_ADAPTER_CLASS` | `profiles.adapters.mock.MockRCVerificationAdapter` | Adapter selection (FR-33) |
| `RC_ADAPTER_MOCK_RESULT` | `sync_verified` | Mock mode (FR-49) |
| `RC_PROVIDER_TIMEOUT_SECONDS` | `5` | Provider timeout (FR-36) |
| `RC_MAX_ATTEMPTS` | `3` | Attempt limit (FR-40) |
| `RC_WEBHOOK_SECRET` | none (placeholder in `.env.example`) | Webhook signature (FR-42) |

---

## Non-Functional Requirements

### Security

| ID | Description |
|----|-------------|
| NFR-SEC-01 | DL numbers must be stored encrypted at rest using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256). The encryption key is loaded from the `DL_ENCRYPTION_KEY` environment variable. The last four characters of the DL number are stored in plaintext in `dl_number_display` for display/audit purposes. The `DL_ENCRYPTION_KEY` must be documented in `backend/.env.example` with a placeholder value only. |
| NFR-SEC-02 | The webhook endpoint (`POST /api/onboarding/driver/dl/webhook/`) must authenticate the inbound request using the mechanism provided by the DL verification provider. **Note:** The webhook is not the primary verification path with DigiLocker (DigiLocker uses synchronous responses). This endpoint is retained as a fallback and for future-proofing. If the webhook endpoint is ever activated for a provider, HMAC-SHA256 signature verification must be used. Unauthenticated requests must be rejected `403` before any database state is modified. |
| NFR-SEC-03 | Onboarding endpoints must require a valid JWT access token (standard DRF permission class `IsAuthenticated`). The webhook endpoints are authenticated by provider signature, not by a user token. |
| NFR-SEC-04 | The gating behaviour (FR-14) must be enforced server-side. The client-side redirect is a UX convenience only; it must not be the sole enforcement mechanism. |
| NFR-SEC-05 | The DL verification provider API credentials and any webhook shared secret must be loaded from environment variables via `python-decouple` and documented in `backend/.env.example` with placeholder values only. Required DigiLocker-specific environment variables: `DIGILOCKER_CLIENT_ID` (OAuth 2.0 client ID issued by DigiLocker), `DIGILOCKER_CLIENT_SECRET` (OAuth 2.0 client secret issued by DigiLocker), `DIGILOCKER_API_URL` (base URL — sandbox URL for dev/staging, production URL for production; sandbox: `https://sandbox.digitallocker.gov.in/`, production: `https://api.digitallocker.gov.in/`). |
| NFR-SEC-06 | `first_name`, `last_name`, age, and gender are PII. Admin access must be restricted to staff users. |
| NFR-SEC-07 | RC owner name and other RC-derived owner data are third-party personal data. They must be staff-only in admin, absent from Driver-facing API responses, absent from logs (log match classification only), and subject to the retention decision in OQ-R7 (Digital Personal Data Protection Act, 2023). The raw provider payload must not be persisted. |
| NFR-SEC-08 | The RC webhook secret and any future RC provider credentials must be loaded from environment variables and documented in `backend/.env.example` with placeholder values only. Signature comparison must be constant-time. The application must refuse to run with the mock RC adapter in production (`DEBUG=False`) when `RC_VERIFICATION_ENABLED` is ON. (Consequence for staging: see open item OQ-R14.) |

### Performance

| ID | Description |
|----|-------------|
| NFR-PERF-01 | `GET /api/onboarding/status/`, `GET /api/onboarding/driver/dl/status/`, and `GET /api/onboarding/driver/vehicle/status/` must return within 100 ms at p95 under a load of 50 requests/second (reads against a single indexed row). |
| NFR-PERF-02 | `POST /api/onboarding/profile/` and `POST /api/onboarding/role/` must return within 200 ms at p95 (local DB writes only). |
| NFR-PERF-03 | `POST /api/onboarding/driver/dl/` must return within 3000 ms at p95 when the provider responds synchronously. If the provider is async the endpoint must return within 500 ms after dispatching the request. |
| NFR-PERF-04 | `POST /api/onboarding/driver/vehicle/` with the flag OFF must return within 200 ms at p95 (local DB writes only). With the flag ON and a synchronous provider response it must return within 3000 ms at p95 (the 5 s provider timeout bounds the worst case). |

### Reliability

| ID | Description |
|----|-------------|
| NFR-REL-01 | DL verification provider calls must be wrapped in a timeout (configurable, default 5 seconds). On timeout the system must treat the result as `pending` and persist the pending state, not surface a 500 to the client. |
| NFR-REL-02 | The webhook handler must be idempotent: receiving the same `reference_id` with the same outcome more than once must not alter state or raise an error beyond `409 already_processed`. This applies to both the DL and RC webhooks. |
| NFR-REL-03 | RC provider calls must be wrapped in the `RC_PROVIDER_TIMEOUT_SECONDS` timeout (default 5). The provider call must not be made while holding an open database write transaction. On timeout the result is treated as pending (FR-36). With the flag OFF no RC provider call is made, so RC provider outages cannot affect onboarding. |

---

## Acceptance Criteria

| ID | Description | Verification | Priority |
|----|-------------|-------------|---------|
| AC-01 | Given an authenticated user with `onboarding_status = not_started`, when `GET /api/onboarding/status/` is called, then the response is `200` with `onboarding_status = "not_started"`, `active_role = null`, and `next_step = "role_selection"`. | Integration test: create user via OTP flow, call status endpoint, assert body. | must |
| AC-02 | Given an authenticated user in `not_started`, when `POST /api/onboarding/role/` is called with `role = "passenger"`, then the response is `200` with `active_role = "passenger"`, `onboarding_status = "role_selected"`, and `next_step = "profile"`. | Integration test. | must |
| AC-03 | Given a user with role already set, when `POST /api/onboarding/role/` is called again, then the response is `409 role_already_set`. | Integration test. | must |
| AC-04 | Given a user in `role_selected` with `role = "passenger"`, when `POST /api/onboarding/profile/` is called with valid `first_name`, `last_name`, `age`, `gender`, then the response is `200` with `onboarding_status = "complete"` and `next_step = "none"`. | Integration test. | must |
| AC-05 | Given a Passenger user who completed onboarding, when `GET /api/auth/me/` is called, then the response includes `onboarding_status = "complete"` and `active_role = "passenger"`. | Integration test. | must |
| AC-06 | Given a user in `role_selected` with `role = "driver"`, when `POST /api/onboarding/profile/` is called with valid fields, then the response is `200` with `onboarding_status = "awaiting_dl"` and `next_step = "dl_submission"`. | Integration test. | must |
| AC-07 | Given a Driver in `awaiting_dl`, when `POST /api/onboarding/driver/dl/` is called with a valid Indian DL number (e.g. `"MH01 20110012345"`) and the provider mock returns a synchronous verified result, then the response is `200` with `dl_verification_status = "verified"`, `onboarding_status = "awaiting_vehicle"`, and `next_step = "vehicle_registration"`. | Integration test with provider adapter mocked to return verified synchronously. | must |
| AC-08 | Given a Driver in `awaiting_dl`, when `POST /api/onboarding/driver/dl/` is called and the provider mock returns a pending result, then the response is `202` with `dl_verification_status = "pending"` and `onboarding_status = "pending_verification"`. | Integration test with provider adapter mocked to return pending. | must |
| AC-09 | Given a Driver in `pending_verification`, when the webhook endpoint receives a verified payload with a valid signature and the matching `reference_id`, then `dl_verification_status` is updated to `verified` and `onboarding_status` to `awaiting_vehicle`. The Driver must still complete vehicle registration before onboarding is fully complete. | Integration test: seed a DriverVerification row in pending state, POST to webhook, assert model fields. | must |
| AC-10 | Given a Driver in `pending_verification`, when the webhook endpoint receives a rejected payload, then `dl_verification_status` is set to `rejected`, `dl_rejection_reason` is stored, and `onboarding_status` remains `pending_verification` (not `complete`). | Integration test. | must |
| AC-11 | Given a DL number `"MH0120110012345"` (no separator), `"mh01 20110012345"` (lowercase), and `"MH01-20110012345"` (hyphen), when submitted to the format validator, then the first and third are accepted (uppercase enforced by normalisation or reject lowercase as per architect decision — see OQ-03), and a consistently invalid string such as `"ABCD1234"` is rejected `400 invalid_dl_format`. | Unit test of the DL format validation function with a parametrized set of inputs. | must |
| AC-12 | Given an `age` value of `17`, `81`, `0`, `-1`, or a non-integer string, when `POST /api/onboarding/profile/` is called, then the response is `400 invalid_age` and no profile row is created. | Unit + integration tests. | must |
| AC-13 | Given a `gender` value of `"attack_vector"`, when `POST /api/onboarding/profile/` is called, then the response is `400 invalid_gender`. | Unit test. | must |
| AC-14 | Given a Passenger user whose `onboarding_status` is not `complete`, when they call a protected non-onboarding endpoint (e.g. `GET /api/rides/`), then the response is `403 onboarding_incomplete` containing `onboarding_status` and `next_step`. | Integration test: call a stub protected endpoint with an onboarding-incomplete user token. | must |
| AC-15 | Given a Driver in `pending_verification`, when they call a ride-offer endpoint, then the response is `403 onboarding_incomplete`. | Integration test. | must |
| AC-16 | Given a user who completed role selection on device A, when they open the app on device B and call `GET /api/onboarding/status/`, then the response reflects `role_selected` state — not `not_started`. | Integration test: set role via API, call status with the same JWT (or a freshly issued one for the same user). | must |
| AC-17 | Given a Driver who has already reached `attempt_count = 3` (the default max), when they attempt another `POST /api/onboarding/driver/dl/`, then the response is `429 max_dl_attempts_exceeded`. | Integration test. | must |
| AC-18 | Given a webhook request with a missing or invalid signature, when `POST /api/onboarding/driver/dl/webhook/` is called, then the response is `403` and no database state is modified. | Integration test with and without a valid HMAC header. | must |
| AC-19 | Given the DL verification provider adapter raises a timeout exception, when `POST /api/onboarding/driver/dl/` is called, then the response is `202` with `dl_verification_status = "pending"` and a `DriverVerification` row exists in `pending` state. | Integration test with provider adapter mocked to raise a timeout. | must |
| AC-20 | Given a user with `active_role = "passenger"`, when `POST /api/onboarding/driver/dl/` is called, then the response is `403 not_a_driver`. | Integration test. | must |
| AC-21 | Given a user with an `onboarding_status` of `complete`, when `POST /api/onboarding/role/` or `POST /api/onboarding/profile/` is called, then the response is `409` with an appropriate error code and no state is mutated. | Integration test. | must |
| AC-22 | **(rewritten v8)** Given a fully onboarded Passenger (`onboarding_status = complete`) with no `DriverVerification` record, when `PATCH /api/profile/role/` is called with `role = "driver"` (RC flag ON or OFF), then the response is `200` with `active_role = "driver"`, `dl_verification_status = null`, `onboarding_status = "awaiting_dl"` and `next_step = "dl_submission"`; no `dl_required` or other error is returned; `GET /api/onboarding/status/` and `GET /api/auth/me/` then report `active_role = "driver"` and `onboarding_status = "awaiting_dl"`; and a following `POST /api/onboarding/driver/dl/` with a valid DL is accepted (not `403 not_a_driver`). The same holds for a `complete` user whose existing DL is `rejected` (`dl_verification_status = "rejected"` in the response; see AC-60 for the attempt limit). | Integration test run with the flag OFF and ON; assert the response body, the stored profile, and that the DL endpoint accepts the next call. | must |
| AC-23 | Given a fully onboarded user who registered as Passenger but has a `dl_verification_status = verified` (previously switched and submitted DL), when `PATCH /api/profile/role/` is called with `role = "driver"`, then the response is `200` with `active_role = "driver"`. **(v8)** The resulting `onboarding_status` is derived per FR-43 in both flag modes: `complete` (no `onboarding_status` key in the response) if the user has an active vehicle or `vehicle_step_exempt = true` (and, with the flag ON, a verified or legacy vehicle); otherwise `awaiting_vehicle` with `next_step = "vehicle_registration"`. See AC-64 for the full matrix. | Integration test. | must |
| AC-24 | Given a Driver with `dl_verification_status = verified` and `active_role = "driver"`, when `PATCH /api/profile/role/` is called with `role = "passenger"`, then the response is `200` with `active_role = "passenger"` and the `DriverVerification` record is preserved. | Integration test. | must |
| AC-25 | Given a user who switches back to driver after previously verifying their DL (AC-24), when `PATCH /api/profile/role/` is called with `role = "driver"` again, then the response is `200` — no re-submission of DL is required. **(v8)** The resulting status is derived from vehicle state per FR-43 (typically `complete` when the user still has their active vehicle; `awaiting_vehicle` if they have none and are not exempt), still without DL re-submission. | Integration test. | must |
| AC-26 | Given a user with `active_role = "passenger"`, when they call a driver-only ride endpoint, then the response is `403` even if their `dl_verification_status = verified`. Only `active_role = "driver"` AND `dl_verification_status = verified` unlocks driver actions. **(v8)** Likewise, a user with `active_role = "driver"` whose DL is not verified (for example just switched, `awaiting_dl`, or `pending_verification`) receives `403` on a driver-only ride endpoint (FR-25), and with the onboarding gate on, `403 onboarding_incomplete` on protected non-onboarding endpoints (AC-66). | Integration test. | must |
| AC-27 | Given a Driver in `awaiting_vehicle` state (DL verified) and `RC_VERIFICATION_ENABLED` OFF, when `POST /api/onboarding/driver/vehicle/` is called with a valid `registration_number` (e.g. `"MH01AB1234"`) and `vehicle_type` (e.g. `"sedan"`), then the response is `200` with `onboarding_status = "complete"`, `next_step = "none"`, and the vehicle details in the response body. | Integration test: create a Driver with verified DL, call vehicle endpoint, assert status is complete and Vehicle row exists. | must |
| AC-28 | Given a Driver in `awaiting_vehicle` state, when `POST /api/onboarding/driver/vehicle/` is called with an invalid `registration_number` (e.g. `"INVALID"`, `"12AB1234"`, `"MH01ABCDE12345"`), then the response is `400 invalid_registration_format` (flag ON or OFF), and no adapter call is made. **(v5)** With the flag OFF this depends on FR-51 (today the flag-off endpoint returns `400 invalid_request`); an invalid `vehicle_type` likewise returns `400 invalid_vehicle_type`. | Unit + integration test with parametrized invalid inputs, run with the flag OFF and ON. | must |
| AC-29 | Given a Passenger user, when `POST /api/onboarding/driver/vehicle/` is called, then the response is `403 not_a_driver`. **(v5)** Applies with the flag OFF and ON; with the flag OFF it depends on FR-51 (today the response is `403 permission_denied`). | Integration test, run with the flag OFF and ON. | must |
| AC-30 | Given a Driver whose DL is not yet verified (e.g. `onboarding_status = awaiting_dl` or `pending_verification`), when `POST /api/onboarding/driver/vehicle/` is called, then the response is `403 dl_not_verified`. | Integration test. | must |
| AC-31 | **Flag-off completion (first RC criterion).** Given `RC_VERIFICATION_ENABLED` is OFF (default), and a Driver in `awaiting_vehicle` with a verified DL, when `POST /api/onboarding/driver/vehicle/` is called with a valid `registration_number` and `vehicle_type`, then the response is `200` with `onboarding_status = "complete"` and `next_step = "none"`, a `Vehicle` row is created with `rc_verification_status = null` and `rc_attempt_count = 0`, the RC adapter is never invoked, and a subsequent `GET /api/auth/me/` shows `onboarding_status = "complete"` (so the client can redirect to the home page). This must hold even if the configured RC adapter would return rejected, time out, or raise a provider error. | Integration test with the flag OFF and the RC adapter patched to raise/reject; assert no adapter call, response body, DB state. | must |
| AC-32 | Given the flag is OFF, when `GET /api/onboarding/driver/vehicle/status/` is called by a Driver, then `rc_verification_status` and `rc_attempts_remaining` are `null`; and when the RC webhook receives a valid signed payload, no onboarding state changes and the response is `404 not_found` (FR-57). | Integration test. | must |
| AC-33 | Given the flag is ON and mock mode `sync_verified`, when a Driver in `awaiting_vehicle` submits a valid vehicle, then the response is `200` with `rc_verification_status = "verified"`, `onboarding_status = "complete"`, `next_step = "none"`, and `rc_name_match = match` is stored. | Integration test with flag ON, mock `sync_verified`. | must |
| AC-34 | Given the flag is ON and mock mode `async_pending`, when a Driver submits a valid vehicle, then the response is `202` with `rc_verification_status = "pending"`, `onboarding_status = "pending_rc_verification"`, `next_step = "awaiting_rc_verification"`, and `rc_attempt_count = 1`. | Integration test. | must |
| AC-35 | Given the flag is ON and mock mode `timeout`, when a Driver submits a valid vehicle, then the response is `202` (not 500) with `onboarding_status = "pending_rc_verification"` and the Vehicle row exists in `pending` state. | Integration test. | must |
| AC-36 | Given the flag is ON and mock mode `sync_verified_name_mismatch`, when a Driver submits a valid vehicle, then the vehicle is not rejected: the response is `202`, `onboarding_status = "pending_rc_verification"`, `rc_name_match` is `mismatch` (or `partial`), and the vehicle appears in the admin review list. The response body contains no owner name and no mismatch wording. | Integration test; assert response body does not contain the owner name. | must |
| AC-37 | Given the flag is ON and mock mode `sync_rejected`, when a Driver submits a valid vehicle, then the response is `422 rc_verification_rejected` with a sanitised reason, `next_step = "vehicle_registration"`, and the Driver remains in `awaiting_vehicle`. | Integration test. | must |
| AC-38 | Given a Driver whose vehicle was rejected (AC-37), when they resubmit a corrected registration number and the mock returns `sync_verified`, then the same `Vehicle` row (same primary key) is updated, no second row exists, `rc_attempt_count` is 2, and the Driver reaches `complete`. | Integration test; assert row count = 1 and same pk. | must |
| AC-39 | Given the flag is ON, `RC_MAX_ATTEMPTS = 3`, and a vehicle with `rc_attempt_count = 3`, when the Driver submits again, then the response is `429 max_rc_attempts_exceeded` and the adapter is not called. After a staff member resets attempts in admin, a further submission is accepted. | Integration test + admin action test. | must |
| AC-40 | Given the flag is ON and mock mode `provider_error`, when a Driver submits a valid vehicle, then the response is `422 rc_verification_provider_error` (not 500), the Driver remains in `awaiting_vehicle`, and `rc_attempt_count` is unchanged. | Integration test. | must |
| AC-41 | Given a Driver in `pending_rc_verification`, when `POST /api/onboarding/driver/vehicle/` is called again, then the response is `409 rc_verification_pending`; and when they call a protected non-onboarding or ride-offer endpoint, the response is `403 onboarding_incomplete` with `next_step = "awaiting_rc_verification"`. **(v5)** The gate response must carry `onboarding_status` and `next_step` inside `error` (FR-14), which depends on the additive error `extra` mechanism; a generic `permission_denied` does not satisfy this criterion. | Integration test; assert the `error` object keys. | must |
| AC-42 | Given a Driver in `pending_rc_verification`, when `GET /api/onboarding/driver/vehicle/status/` is called, then the response is `200` with `rc_verification_status = "pending"`, `next_step = "awaiting_rc_verification"`, and no owner data. | Integration test. | must |
| AC-43 | Given a pending vehicle with a known `rc_verification_ref`, when the RC webhook receives (a) a valid-signature `verified` payload, then the Driver becomes `complete` (subject to FR-38 name rules); (b) a valid-signature `rejected` payload, then the Driver returns to `awaiting_vehicle`; (c) the same payload again, then `409 already_processed` with no change; (d) a missing/invalid signature, then `403` with no state change; (e) an unknown reference, then `404 rc_reference_not_found` (FR-57). | Integration tests with and without a valid signature. | must |
| AC-44 | Given a vehicle flagged `pending` for review, when a staff user approves it in admin, then the Driver's `onboarding_status` becomes `complete` and `rc_verified_at` is set; when a staff user rejects it with a reason, then the Driver returns to `awaiting_vehicle`, the reason is stored, and both actions are audit-logged. A non-staff user cannot access these actions. | Admin action tests (or manual QA until admin tests exist). | should |
| AC-45 | Given the flag is ON, when a declared `vehicle_type = "car"` is submitted and the RC class returned is two-wheeler, then the vehicle is rejected (`422 rc_verification_rejected`); when the RC class is missing or unrecognised, then no class rejection occurs. | Unit test of the class-mapping function + integration test. | must |
| AC-46 | Given the flag is ON and a provider result with expired `fitness_valid_upto` or `insurance_valid_upto`, when the Driver is otherwise verified (name `match`, class compatible), then the vehicle is verified and the dates are stored; nothing is rejected on expiry. | Unit/integration test. | should |
| AC-47 | Given the flag is ON and a Driver who is `complete` with a legacy vehicle (`rc_verification_status = null`) or no vehicle, when any normal app endpoint is called, then the Driver is not moved from `complete`, no verification is forced, and no migration or deploy step alters their `onboarding_status`. | Integration + migration test with seeded legacy data. | must |
| AC-48 | Given the flag is ON and a user with a verified DL whose vehicle is `pending` or `rejected`, when `PATCH /api/profile/role/` is called with `role = "driver"`, then `onboarding_status` is NOT set to `complete`: it becomes `pending_rc_verification` (pending vehicle) or `awaiting_vehicle` (rejected vehicle), and the response carries the matching `next_step`. With a verified or legacy (`null`) vehicle it is `complete`. **(v6, supersedes the v5 U1 sentence)** Given the flag is ON and a non-grandfathered driver (`vehicle_step_exempt = false`) in `awaiting_vehicle` who never submitted a vehicle, when they switch to passenger (allowed, status `complete`, FR-52) and then back to driver, then `onboarding_status` is `awaiting_vehicle` and `next_step` is `vehicle_registration`, and they can still switch to passenger again. Given a driver marked grandfathered (`vehicle_step_exempt = true`) with no vehicle, the same sequence leaves them `complete` with `next_step` `none`. | Integration test matrix over vehicle states, including the non-grandfathered and the grandfathered no-vehicle sequences. | must |
| AC-49 | **(rewritten v8)** Given the flag is OFF and a `complete` user with a verified DL, when `PATCH /api/profile/role/` is called with `role = "driver"`, then no RC evaluation occurs and the result follows FR-43 (flag OFF): with an active vehicle or `vehicle_step_exempt = true` the response is `200` with `active_role = "driver"` and the status stays `complete` (same as v3 for these users); with no active vehicle and `vehicle_step_exempt = false` the response is `200` with `onboarding_status = "awaiting_vehicle"` and `next_step = "vehicle_registration"` (a deliberate change from v3, which returned `complete`). The initial onboarding happy path with the flag OFF is unchanged: Role -> Profile -> DL (verified) -> `POST /api/onboarding/driver/vehicle/` returns `200`, `onboarding_status = "complete"`, `next_step = "none"` (AC-27, AC-31). | Integration regression test for the unchanged cases (active vehicle, exempt, initial happy path) plus a test for the changed no-vehicle case. | must |
| AC-50 | Given two different Drivers submit the same `registration_number`, then both submissions are accepted (no uniqueness error), a WARNING log is written without personal data, and the admin view shows a count of other drivers for that number. | Integration test + manual admin check. | must |
| AC-51 | Given the settings, then `manage.py check` passes with no RC environment variables set, `RC_VERIFICATION_ENABLED` defaults to `False`, and starting with `DEBUG=False`, the flag ON, and the mock RC adapter configured is refused. | Settings test / manual check. | must |
| AC-52 | Given the RC adapter and service code, then no log line or Driver-facing response contains the RC owner name, and the raw provider payload is not persisted. | Log-capture test + code review (security review). | must |
| AC-53 | **(v5, U2)** Given the flag is OFF, then (a) a valid vehicle submission returns a `200` response with the same fields and values as before this change, with `vehicle_type` returned UPPERCASE per FR-53 (**v7**; v5 required the then-current casing to be preserved byte-for-byte); (b) an invalid registration number returns `400 invalid_registration_format`; (c) an invalid `vehicle_type` returns `400 invalid_vehicle_type`; (d) a Passenger receives `403 not_a_driver`; (e) a `complete` Driver posting a vehicle again receives `409 vehicle_already_registered`. | Integration tests with the flag OFF; (a) compared against a captured baseline response of the pre-change endpoint, allowing only the `vehicle_type` casing defined in FR-53. | must |
| AC-54 | **(v5, U3)** Given a user in `awaiting_vehicle` (for example, with a rejected vehicle and `rc_attempt_count` at `RC_MAX_ATTEMPTS`, flag ON, or with the flag OFF), when `PATCH /api/profile/role/` is called with `role = "passenger"`, then the response is `200` with `active_role = "passenger"`, the user is not gated out of the main app (a subsequent protected non-onboarding endpoint is not blocked with `onboarding_incomplete`), and the `DriverVerification` and `Vehicle` records are preserved. **(v6)** The `vehicle_step_exempt` marker is read-only in admin and is never written by application code (only by data migration 0004): switching roles, DL verification and vehicle actions never change it. **(v8)** The same holds for every in-progress driver state, not only `awaiting_vehicle`; the full matrix is AC-63. | Integration test over `awaiting_vehicle` states, including exhausted attempts; plus a check that `vehicle_step_exempt` is unchanged after these actions, that no application code path writes it (code review or search), and that it is read-only in admin. | must |
| AC-55 | **(v7, FR-53)** Given a Driver in `awaiting_vehicle`, when `POST /api/onboarding/driver/vehicle/` is called with `vehicle_type = "auto_rickshaw"` (lowercase), then the request is accepted and the response `vehicle.vehicle_type` is `"AUTO_RICKSHAW"`; and a subsequent `GET /api/onboarding/driver/vehicle/status/` returns `vehicle_type = "AUTO_RICKSHAW"`. The same holds for each of `car`/`CAR`, `suv`/`SUV`, `hatchback`/`HATCHBACK`, `sedan`/`SEDAN`, `bike`/`BIKE`, with the flag ON or OFF. | Parametrized integration test over all six values, flag OFF and ON. | must |
| AC-56 | **(v7, FR-54)** Given any onboarding, auth-me, DL status, vehicle, or role-switch response, then `onboarding_status`, `active_role` and `dl_verification_status` values are lowercase (for example `complete`, `driver`, `verified`), and no response example in this document contradicts this; `vehicle_type` is the only uppercase enum value. | Integration tests asserting the lowercase values on each endpoint; document review of the response examples. | must |
| AC-57 | **(rewritten v8, FR-55; v7 expected `400 invalid_onboarding_state`)** Given a user whose `onboarding_status` is `awaiting_vehicle` (flag ON or OFF), when `PATCH /api/profile/role/` is called with `role = "driver"`, then the response is `200` mirroring the current state (`active_role = "driver"`, `onboarding_status = "awaiting_vehicle"`, `next_step = "vehicle_registration"`), and nothing changes (`active_role`, `onboarding_status` and the `Vehicle` and `DriverVerification` records are unchanged, `vehicle_step_exempt` is unchanged). No `400 invalid_onboarding_state` is returned. Switching the same user to `passenger` still succeeds (AC-54). The same no-op holds for `awaiting_dl`, `pending_rc_verification` (`200`) and `pending_verification` (`202`); see AC-65. | Integration test with the flag OFF and ON. | must |
| AC-58 | **(v7, FR-56)** Given the flag is ON or OFF, when `POST /api/onboarding/driver/vehicle/` returns `200` or `202`, then `rejection_reason` is `null`. Given the flag is ON and mock mode `sync_rejected`, then the rejection arrives only as `422 rc_verification_rejected` with the sanitised reason in `error.detail`. | Integration tests over the `200`, `202` and `422` outcomes (extends AC-33, AC-34, AC-36, AC-37). | must |
| AC-59 | **(v7, FR-57)** Given the flag is OFF, when the RC webhook is called with any payload, then the response is `404` with `error.code = "not_found"` and no state changes. Given the flag is ON, when the RC webhook is called with a valid signature and an unknown `reference_id`, then the response is `404` with `error.code = "rc_reference_not_found"`. | Integration tests with the flag OFF and ON. | must |
| AC-60 | **(v8, FR-24(a), FR-13)** Given a `complete` user with a `rejected` DL whose `attempt_count` is below the maximum, when `PATCH /api/profile/role/` is called with `role = "driver"` (flag ON or OFF), then the response is `200` with `onboarding_status = "awaiting_dl"`, `next_step = "dl_submission"`, `dl_verification_status = "rejected"`, and `attempt_count` is unchanged; a following `POST /api/onboarding/driver/dl/` with a corrected DL is accepted and increments `attempt_count`. Given the same user with `attempt_count` at the maximum, the switch still returns `200` with `awaiting_dl`, a following DL submission returns `429 max_dl_attempts_exceeded`, and the user can still switch to `passenger` (`200`, `complete`, AC-63). | Integration tests with the flag OFF and ON, below and at the DL attempt limit. | must |
| AC-61 | **(v8, FR-24(b))** Given a `complete` user whose DL is `pending`, when `PATCH /api/profile/role/` is called with `role = "driver"` (flag ON or OFF), then the response is `202` with `active_role = "driver"`, `onboarding_status = "pending_verification"` and `dl_verification_status = "pending"` (unchanged existing behaviour), and a ride-offer or other protected endpoint is refused (`403`, FR-15, AC-15). | Integration test with the flag OFF and ON. | must |
| AC-62 | **(v8, end-to-end, FR-24)** Given a `complete` Passenger with no DL, when they switch to `driver` (`awaiting_dl`), submit a valid DL (provider mock returns verified; `awaiting_vehicle`), and then submit a valid vehicle, then with the flag OFF the vehicle response is `200`, `onboarding_status = "complete"`, `next_step = "none"`; with the flag ON and mock `sync_verified` it is `200`, `complete`, `rc_verification_status = "verified"`; with the flag ON and mock `async_pending` it is `202`, `pending_rc_verification`. In every case `active_role` is `driver` at the end, and a driver-only endpoint is accessible only once `complete` and the DL is verified. | Integration test of the full sequence with the flag OFF and ON (mock modes `sync_verified`, `async_pending`). | must |
| AC-63 | **(v8, FR-52, FR-23)** Given a user in each of `awaiting_dl`, `awaiting_vehicle`, `pending_verification` and `pending_rc_verification` (the last only with the flag ON, or seeded with the flag OFF per the rollback edge case), when `PATCH /api/profile/role/` is called with `role = "passenger"` with the flag ON and with the flag OFF, then the response is `200` with `active_role = "passenger"`, the stored `onboarding_status` is `complete`, the user is not gated out of a protected non-onboarding endpoint, and the `DriverVerification` and `Vehicle` records (including `attempt_count`, `rc_attempt_count` and `vehicle_step_exempt`) are unchanged. | Integration test matrix: 4 states x flag OFF/ON, asserting response, stored state, the gate, and unchanged records. | must |
| AC-64 | **(v8, FR-43)** Given a `complete` Passenger with a `verified` DL, when `PATCH /api/profile/role/` is called with `role = "driver"`, then the result is: **flag OFF** with an active vehicle -> `complete`; exempt and no active vehicle -> `complete`; not exempt and no active vehicle (including an inactive-only vehicle) -> `awaiting_vehicle` with `next_step = "vehicle_registration"`. **Flag ON** with a verified or legacy (`null`) vehicle -> `complete`; `pending` vehicle -> `pending_rc_verification`; `rejected` vehicle -> `awaiting_vehicle`; exempt and no active vehicle -> `complete`; not exempt and no active vehicle -> `awaiting_vehicle`. A Driver without an active vehicle who is not exempt is never `complete` after the switch, in either flag mode. | Integration test matrix over vehicle states x exempt marker x flag OFF/ON. | must |
| AC-65 | **(v8, FR-55)** Given a user already in an in-progress driver state (`awaiting_dl`, `awaiting_vehicle`, `pending_verification`, `pending_rc_verification`), when `PATCH /api/profile/role/` is called with `role = "driver"` (flag ON or OFF), then the response mirrors the current state (`200`; `202` for `pending_verification`), no field on the profile, `DriverVerification` or `Vehicle` changes, and no error is returned. Given a user in `not_started` or `role_selected`, the same request returns `403 onboarding_incomplete`. | Integration test over the four states x flag OFF/ON, plus the two ineligible states. | must |
| AC-66 | **(v8, gate, assumption A-v8-1)** Given `ONBOARDING_GATE_ENABLED` is on and a `complete` Passenger who switched to `driver` and is now `awaiting_dl`, when they call a protected non-onboarding endpoint, then the response is `403 onboarding_incomplete` with `onboarding_status = "awaiting_dl"` and `next_step = "dl_submission"` in `error`; `PATCH /api/profile/role/` and the DL and vehicle onboarding endpoints remain reachable; and after they switch back to `passenger` the same protected endpoint is no longer blocked. With the gate setting off, no `403 onboarding_incomplete` is produced by the gate. | Integration test with `ONBOARDING_GATE_ENABLED` on and off. | must |

## Edge Cases

- **Concurrent role submissions** — Two simultaneous `POST /api/onboarding/role/` calls for the same user must not create two `UserProfile` rows. Enforce with `get_or_create` plus a unique constraint on `UserProfile.user`.
- **UserProfile creation timing** — If the `UserProfile` row is not yet created when `GET /api/onboarding/status/` is called (race between OTP verify callback and first status poll), the endpoint must still return `200` with `not_started` rather than `404`. The row must be created lazily or as part of the OTP verify response.
- **Webhook delivered before client receives `202`** — The webhook may arrive and update state before the driver's `POST /api/onboarding/driver/dl/` response is delivered to the client. This is harmless: the client will call `GET /api/onboarding/driver/dl/status/` to confirm. State transitions must be idempotent. The same applies to the RC webhook and the RC status endpoint.
- **Duplicate webhook deliveries** — Providers commonly retry webhooks. The handler must be idempotent; re-processing a `reference_id` that is already in terminal state (`verified` or `rejected`) must return `409 already_processed` and not overwrite data.
- **DL number with mixed-case input** — The server must either normalise to uppercase before validation (preferred) or reject with a clear `400 invalid_dl_format`. Behaviour must be consistent and documented.
- **Provider returns an unrecognised status value** — The webhook handler must log the raw payload and treat the outcome as a transient error requiring manual review, not silently overwrite state. (For RC, the raw payload is logged only without owner data and is not persisted; see FR-47.)
- **User deletes and re-registers with the same phone number** — Out of scope for this feature (no delete flow exists per FEAT-001); noted for future handling.
- **Age boundary values** — `age = 18` and `age = 80` must be accepted. `age = 17` and `age = 81` must be rejected.
- **Role endpoint called before OTP verification completes** — All onboarding endpoints require a valid access token. If a token is not yet held, the request returns `401`. No special handling needed.
- **Provider API key misconfigured** — `POST /api/onboarding/driver/dl/` must return `422 dl_verification_provider_error` rather than a `500` crash. Operators must be alerted via logs. The same applies to RC (`422 rc_verification_provider_error`).
- **Duplicate vehicle registration number across users** — Two different Drivers may submit the same vehicle registration number (v1 decision R4, also with RC verification enabled). No uniqueness constraint is added. A non-unique index and an admin duplicate indicator are provided (FR-46) so reviewers can spot suspicious sharing. A future enhancement may enforce exclusivity (e.g. a partial unique constraint on verified, active vehicles) if product requires it.
- **Vehicle registration number with spaces, hyphens, or lowercase** — Input must be normalised: strip spaces and hyphens, convert to uppercase, then validate against the Indian format pattern. Example: `"mh 01-ab 1234"` is normalised to `"MH01AB1234"` before validation.
- **Driver attempts vehicle registration before DL is verified** — The `POST /api/onboarding/driver/vehicle/` endpoint must return `403 dl_not_verified`. The state machine enforces that `awaiting_vehicle` is only reachable after DL verification.
- **Driver calls vehicle endpoint after onboarding is already complete** — Must return `409 vehicle_already_registered` (the vehicle was already registered during onboarding). **(v5)** This applies with the flag OFF as well (FR-51); it must not surface as `403 dl_not_verified`.
- **Flag turned OFF while Drivers are in `pending_rc_verification`** — They must not be left stranded. Operations moves them (data patch or admin action) either to `awaiting_vehicle` (they resubmit under the self-declared flow) or to `complete` if product accepts. This is an operational rollback step, not an automatic behaviour. (Such a Driver may also switch to passenger, FR-52 / FR-43.)
- **Flag turned ON while Drivers are mid-onboarding** — Drivers in `awaiting_dl` / `pending_verification` follow the RC flow when they reach the vehicle step. Drivers already `complete` are untouched (FR-45).
- **Owner name differs because the vehicle is family- or fleet-owned, or financed** — Not an error. Goes to admin review (FR-38); no extra evidence is collected in v1.
- **Masked or missing owner name from the provider** — Classified `not_checked`; goes to admin review, never auto-verified, never rejected on that basis alone.
- **Provider returns a vehicle class that is unknown to the mapping** — Class check is skipped (no rejection).
- **Expired insurance or fitness** — Stored, informational, not blocking (FR-48).
- **Provider timeout on resubmission** — Consumes an attempt and moves the Driver to `pending_rc_verification` like a first submission.
- **Resubmission with a different vehicle type or registration number after rejection** — Allowed; the same `Vehicle` row is updated and the attempt count is retained so the limit cannot be bypassed by creating new rows.
- **Stale `pending_rc_verification`** — Not auto-rejected in v1. Operations must monitor pending age; a staff member resolves in admin. An ops owner for this queue is needed before the flag is enabled in production.
- **Grandfathered Driver with no vehicle row toggles role (flag ON)** — **(v6, replaces the v5 U1 and v4 wording)** "Grandfathered" is an explicit marker, not the absence of a vehicle row: only a Driver with `UserProfile.vehicle_step_exempt = true` (set solely by the one-time data migration, FR-43) who switches to passenger and back to driver stays `complete`. A missing or inactive-only vehicle record alone never implies exemption. A Driver without the marker and without an active vehicle record (for example one who reached `awaiting_vehicle`, never submitted a vehicle, switched to passenger via FR-52, and switched back) is derived to `awaiting_vehicle` with `next_step = "vehicle_registration"`, and can still switch to passenger again. This closes the earlier path by which such a Driver ended `complete` with no vehicle. Migration marking rule edge cases (see Data Model Changes): a `complete` Driver whose only vehicle is inactive is marked; a `complete` profile with a pending or rejected DL record is also marked (harmless, because switching to driver still requires a verified DL). A Driver whose DL is verified later and who has no vehicle row is in `awaiting_vehicle` (not `complete`) and is not affected by the marker. **(v8)** The same rule now applies with the flag OFF (FR-43).
- **Driver stuck in `awaiting_vehicle` (rejected vehicle, attempts exhausted)** — **(v5, U3)** Cannot submit further (`429 max_rc_attempts_exceeded`) until staff reset or approve, but may always switch to passenger (FR-52) so they are never locked out of the app.
- **User in `awaiting_vehicle` (or any in-progress driver state) requests a switch to `driver`** — **(v7, reconciled v8)** Now an idempotent no-op with `200` (`202` for `pending_verification`), flag ON or OFF; the v7 `400 invalid_onboarding_state` is retired (FR-55). This is distinct from the round trip above, where the user first switches to passenger (status `complete`) and the later switch back to driver is derived per FR-43 (for example `awaiting_vehicle` with `200`).
- **Rejection reason on a successful vehicle response (flag ON)** — **(v7)** A vehicle that was previously rejected and is then resubmitted successfully (`200` / `202`) returns `rejection_reason = null`; the earlier reason is not echoed (FR-56).
- **RC webhook with an unknown reference** — **(v7)** `404 rc_reference_not_found` when the flag is ON; `404 not_found` for any call while the flag is OFF (FR-57).
- **Old client that does not recognise `awaiting_rc_verification` / `vehicle_registration`** — Could strand in-flight Drivers. The flag must only be turned ON after a client that handles both `next_step` values (with a safe default for unknown values) is deployed.
- **Redirect to home when the flag is OFF** — The backend guarantees `onboarding_status = complete` and `next_step = "none"`; if the client does not redirect, that is a frontend defect, not a backend one.
- **Passenger who starts driver setup is gated while the onboarding gate is on** — **(v8, accepted)** While `ONBOARDING_GATE_ENABLED` is on, a `complete` Passenger who switches to `driver` becomes `awaiting_dl` (or `pending_verification`, `awaiting_vehicle`) and is therefore gated out of normal app features (including passenger features such as booking rides) with `403 onboarding_incomplete` until they finish driver setup or switch back to passenger (FR-14, FR-52, AC-66). This is an accepted product consequence of reusing the single `onboarding_status` for driver setup; no partial "passenger plus pending driver" state exists in v1. The role-switch endpoint stays reachable so the user can always return to passenger.
- **Frontend must handle the `awaiting_dl` result of a role switch** — **(v8)** The `PATCH /api/profile/role/` response can now carry `onboarding_status = "awaiting_dl"` and `next_step = "dl_submission"` (a status the switch never produced before). The client must route the user to DL submission and must not treat a `200` from the role switch as "switch complete". Clients that ignore `onboarding_status` / `next_step` on this response would leave the user gated.
- **Switch to driver after a rejected DL with the DL attempt limit reached** — **(v8)** Allowed (`awaiting_dl`), but the next DL submission returns `429 max_dl_attempts_exceeded` and manual review is required (FR-13); the user remains able to switch to passenger (FR-52). The switch does not reset `attempt_count`.
- **`pending_verification` with a webhook-rejected DL (AC-10)** — **(v8)** The user's status stays `pending_verification` after a DL rejection by webhook, so a switch to `driver` from that state is a no-op (FR-55) and does not re-open DL submission. The user can recover by switching to passenger and back to driver, which then yields `awaiting_dl` (rejected DL, FR-24(a)). See OQ-R16.
- **Flag-OFF role switch with a vehicle row left from the flag-ON period** — **(v8)** With the flag OFF, any active vehicle makes the derived status `complete` (FR-43), regardless of that row's `rc_verification_status` (`pending` or `rejected` rows created while the flag was ON are not evaluated while it is OFF). This matches the flag-OFF rule that no RC state is evaluated (FR-32).
- **Role switch from `awaiting_dl` to passenger** — **(v8)** `awaiting_dl` is only reachable after the profile (name, age, gender) has been submitted (FR-05) or after a switch by an already-profiled user, so the resulting `complete` passenger always has profile data.
- **Concurrent role switches** — **(v8)** Two simultaneous `PATCH /api/profile/role/` calls for the same user must not corrupt state: the final stored `active_role` and `onboarding_status` must be one consistent pair as defined by FR-24, FR-43 and FR-52 (the update is serialised per user).

## Non-Goals

- Frontend / Expo implementation of onboarding screens (a separate frontend feature). This includes the screen that redirects a Driver to the home page after completion; the backend delivers the API contract only. **(v8)** This includes the frontend handling of the `awaiting_dl` result of a role switch; the backend delivers the contract and flags it as a dependency.
- Profile photo / avatar upload.
- Multiple vehicles per driver (one vehicle per driver in v1; multi-vehicle support is a future feature).
- Background checks beyond DL verification.
- Document upload (Aadhar, PAN card, etc.) — not required in v1.
- Email collection or email verification at any stage.
- Admin tooling for manually approving or rejecting Driver accounts beyond the RC review actions in FR-44 (a broader DL/account admin workflow may be added in a follow-up).
- Push notifications to a Driver when their DL or RC verification status changes.
- Onboarding analytics funnel (drop-off tracking per step).
- Profile editing after onboarding is complete (a separate "edit profile" feature).
- Role switching UI/UX design (a frontend concern; backend contract is defined here).
- Multi-language / localisation of validation error messages.
- Age verification via government ID cross-check (DL format check only).
- **Real RC provider integration.** No real RC verification provider adapter is built in this version. Provider selection (pricing, contracts, credentials, sandbox) is deferred, mirroring DL, and is a separate follow-up. Only `MockRCVerificationAdapter` is built; the `RCVerificationAdapter` interface stays swappable. Turning RC verification on in production is a configuration change once a provider adapter exists.
- **Manual RC document upload** (photo of the RC, authorisation letter, ops-reviewed documents). Not in v1; a possible future exception path.
- Commercial / taxi permit verification (e.g. commercial permit, yellow/black plates) beyond the RC.
- Forcing already-onboarded Drivers to verify their vehicle, or moving them back to an earlier state. An optional later phase may add a post-onboarding verify prompt (`POST /api/driver/vehicle/verify/` plus a non-blocking banner); it is not part of this version.
- Auto-rejection or escalation of stale `pending_rc_verification` entries.
- Hard unique constraint on `registration_number`.
- Blocking on expired insurance or fitness.
- Fixing the DL module's wiring gaps (global adapter, missing DL settings, provider call inside a transaction); noted separately.
- **(v8)** A "passenger plus pending driver" dual state that would let a Passenger keep using passenger features while driver setup is in progress. Driver setup uses the single `onboarding_status`, so the gate applies (see Edge Cases).

## Constraints

- All endpoints must be prefixed `/api/` per project convention.
- The new Django app must be created via `python manage.py startapp profiles` (or an architect-approved alternative name).
- The DL verification provider is DigiLocker (Pull URI API). The adapter interface must still be designed to support both synchronous and asynchronous (webhook) response patterns without changing business logic, to allow future provider substitution.
- Environment variables for the DL provider must use `python-decouple` (`config(...)`) consistent with `backend/config/settings.py` and documented in `backend/.env.example`. The same applies to the RC settings.
- The onboarding gate (FR-14) must be implemented as a DRF permission class or middleware so it is applied consistently to all protected non-onboarding endpoints without per-view boilerplate.
- PostgreSQL is the only supported datastore.
- All API responses must conform to the unified envelope defined in DEC-011 (extended additively by the optional error `extra` mechanism, see API Contract).
- The `UserProfile` migration must declare a dependency on the `accounts` app migration that defines `AUTH_USER_MODEL`.
- DigiLocker sandbox environment (`https://sandbox.digitallocker.gov.in/`) must be used for all development and staging environments. The production DigiLocker API (`https://api.digitallocker.gov.in/`) requires formal partner registration with MeitY (Ministry of Electronics and Information Technology) and must only be used in production after registration is complete.
- RC verification must be behind the `RC_VERIFICATION_ENABLED` flag, default OFF. All RC schema changes must be additive and nullable/defaulted so existing rows and the flag-off path are unaffected.
- RC business rules (name matching, class mapping, state decisions) live in the service layer, not in adapters, so behaviour is identical across providers.
- New code must raise domain errors with stable error codes rather than relying on substring matching of exception messages (an existing weakness in the vehicle view).

## Dependencies

| Name | Type | Required |
|------|------|----------|
| FEAT-001 OTP authentication | Internal feature | true |
| `accounts.User` model (custom `AUTH_USER_MODEL`) | Internal model | true |
| DigiLocker Pull URI API (DL verification provider) | External service | true |
| DigiLocker OAuth 2.0 credentials (client_id / client_secret) | External credential | true |
| DigiLocker partner registration with MeitY (for production) | External process | true |
| PostgreSQL (already present) | Infrastructure | true |
| `python-decouple` (already present) | Python package | true |
| DRF (already present) | Python package | true |
| RC verification provider (aggregator) and contract | External service | false (deferred; mock only in v1; required only to enable the flag in production) |
| Frontend vehicle registration and RC pending screens, with safe handling of unknown `next_step` | Internal feature (frontend) | true before the flag is turned ON; not required for flag-off launch beyond the existing redirect on `complete` |
| Frontend handling of the `awaiting_dl` / `dl_submission` result of `PATCH /api/profile/role/` (route a switching Passenger to DL submission; do not treat the `200` as "switch complete") | Internal feature (frontend) | true before the v8 role-switch behaviour is exposed to users |
| `docs/plans/PLAN-003-vehicle-rc-verification.md` | Planning document | false (reference) |

## Assumptions

- A `UserProfile` row is created (with `onboarding_status = not_started`) the first time a user successfully completes OTP verification (`is_new_user = true` from FEAT-001). The mechanism for this trigger is an implementation decision (post-save signal, service layer call, or direct creation in the OTP verify view).
- The Indian DL format pattern `^[A-Z]{2}[0-9]{2}[ -]?[0-9]{4}[0-9]{7}$` covers all currently issued DL numbers. State code validity (e.g. `MH` is valid, `ZZ` is not) is not validated in v1; this is an open extension point.
- Age is collected as a self-reported integer (birth date is not required). The product team accepts the risk that users may enter inaccurate ages.
- Drivers are labeled "Rider" in all UI copy. Backend field values use `driver` and `passenger` for clarity. The UI label mapping is a frontend concern and does not affect API contracts.
- `active_role` is the single source of truth for a user's current role. There is no separate immutable "registered role" — the role chosen at onboarding simply becomes the initial value of `active_role`.
- The DL verification provider (DigiLocker) uses a synchronous Pull URI API. The primary flow completes DL verification in a single request-response cycle. The async/webhook/pending code paths are retained as fallback for timeout scenarios and for future-proofing if an async provider is ever substituted.
- A maximum of 3 DL resubmission attempts (default) is a configurable setting; product may adjust this without a code change.
- The webhook endpoint path is not secret; authentication relies solely on the provider's signature mechanism (HMAC-SHA256 if ever activated).
- DigiLocker provides a sandbox environment for development and testing. The mock adapter remains the default for local development (unit and integration tests use the mock adapter, not the DigiLocker sandbox). The DigiLocker sandbox is used for manual QA and staging environments where end-to-end verification flow testing is needed.
- DigiLocker DL verification is free for government-issued documents (DigiLocker is a government initiative under MeitY). No per-call cost is expected.
- DigiLocker API is subject to rate limits that vary by partner tier. The adapter must handle `429` responses from DigiLocker gracefully, mapping them to `422 dl_verification_provider_error` for the client.
- The Indian vehicle registration number format `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$` covers the standard format for most Indian vehicles. Older or special-format registrations (e.g., diplomatic, military) are not validated in v1.
- **(Revised in v4)** At launch RC verification is OFF and the platform relies on format validation and self-declaration by the Driver (the v3 behaviour). Third-party RC verification is built and exercised against the mock only; no real provider exists. Turning it on is a configuration change once a provider adapter exists.
- Provider-specific details for RC verification (field coverage, pricing, latency, masked owner names, async support) are unverified in PLAN-003 and must be confirmed during provider selection; all provider-derived fields in the adapter result are optional so a provider returning fewer fields still works.
- Drivers who share a vehicle (family, fleet, shifts) are common in India; hence name mismatch leads to review, not rejection, and duplicate registration numbers are allowed.
- The frontend ships support for `vehicle_registration` and `awaiting_rc_verification` `next_step` values (with a safe default for unknown values) before the flag is turned ON anywhere shared.
- Operations will own the admin review queue for pending RC vehicles before the flag is enabled in production; no review SLA is defined in v1.
- **(v5)** The flag-off error-contract conformance (FR-51) changes only error bodies of the vehicle endpoint; no existing client is known to depend on the previous generic error codes. The existing `vehicle_type` casing in the success response is preserved so that no client sees a changed success payload. **(v7)** The final sentence is superseded: the contract was refined to match the implementation, so `vehicle_type` is returned UPPERCASE in vehicle responses (FR-53). See OQ-R15 on whether this changes a payload any client already consumes.
- **(v6)** The v5 (U1) assumption and wording, that a `complete` Driver with no vehicle row is treated as grandfathered and stays `complete` on a role round trip, is superseded by this refinement. A missing vehicle record never implies exemption; exemption is the explicit `vehicle_step_exempt` marker, set only by the one-time data migration 0004 for profiles that were `complete`, had a `DriverVerification` record, and had no active `Vehicle` row at migration time. The fix applies with the flag ON; with the flag OFF nothing changes (v3 `switch_role` behaviour). **(v8)** The last clause is superseded: the vehicle-state derivation now applies with the flag OFF as well (FR-43).
- **(v8, A-v8-1)** While the onboarding gate (`ONBOARDING_GATE_ENABLED`) is on, a Passenger who starts driver setup is gated out of normal features until they finish driver setup or switch back to Passenger. This is accepted by product (see Edge Cases). The gate is a configurable setting (default off in the current settings), so this consequence only appears where the gate is enabled.
- **(v8)** The change to flag-OFF role-switch edge cases (a verified-DL switch to driver with no active vehicle and no exemption now yields `awaiting_vehicle` instead of `complete`) is deliberate and approved as part of this decision. The flag-OFF initial onboarding happy path is unchanged.
- **(v8)** The frontend must handle the `awaiting_dl` result of a role switch (route to DL submission). This is a dependency, not backend scope.
- **(v8)** No existing client relies on `400 dl_required` or on `400 invalid_onboarding_state` from `PATCH /api/profile/role/`; both codes are retired for this endpoint. Other documents (ARCH-002, the API docs and OpenAPI file, PLAN-002) and the implementation may still describe the retired behaviour and must be brought in line; this requirement does not edit them.
- **(v8)** The role-switch rules apply identically whether `RC_VERIFICATION_ENABLED` is ON or OFF, except that the vehicle-state derivation (FR-43) also evaluates the vehicle's RC status when the flag is ON.

## Open Questions

| ID | Question | Blocking | Resolution |
|----|----------|---------|------------|
| OQ-01 | Which DL verification provider will be used? Options in the Indian market include Digilocker API, Karza, IDfy, AuthBridge, and others. The provider choice affects the adapter interface design, webhook authentication mechanism, and what the `dl_rejection_reason` field can contain. | false | **Resolved (v2).** Provider is DigiLocker (Indian government digital document verification platform under MeitY). DigiLocker provides a Pull URI REST API authenticated via OAuth 2.0 (client_id + client_secret). It verifies DLs against the Sarathi/Vahan/Parivahan database maintained by the Ministry of Road Transport and Highways. Data returned includes: DL holder's name, date of birth, DL issue/expiry dates, vehicle classes, issuing authority, and current status (active/expired/suspended/revoked). The service is free for government-issued documents. |
| OQ-02 | Does the DL verification provider support both synchronous and asynchronous response modes, or only one? This determines whether the `202 pending` path is a required code path or an edge-case fallback. | false | **Resolved (v2).** DigiLocker's Pull URI API returns results synchronously in the same request cycle. The `202 pending` code path is retained as a fallback for timeout scenarios only (when the DigiLocker API call exceeds the configured timeout per NFR-REL-01, the result is treated as pending). It is not the primary flow. |
| OQ-03 | Should the DL number validator normalise lowercase input to uppercase before validation, or reject it outright? The user-facing experience differs: normalisation is more forgiving but may mask data entry errors. | false | |
| OQ-04 | What is the webhook authentication mechanism provided by the selected DL provider (HMAC-SHA256 header, shared secret, IP allowlist, mTLS)? Required to specify NFR-SEC-02 concretely. | false | **Resolved (v2).** DigiLocker uses synchronous responses; webhook is not the primary verification path. The webhook endpoint is retained for fallback/future-proofing only. If webhook authentication is ever needed, DigiLocker supports HMAC-SHA256 signature verification. |
| OQ-05 | Should `UserProfile` be created proactively at OTP-verify time (in the `accounts` app) or lazily on the first call to `/api/onboarding/status/`? The proactive approach couples `accounts` to `profiles`; the lazy approach requires careful handling of the first-call race. | false | |
| OQ-06 | What is the minimum age for Passengers? The requirement currently sets 18 for both roles. If the product intends to allow younger Passengers (e.g. students), the `age` validation range must be role-conditional. | false | **Resolved (v2).** Minimum age is 18 for both Drivers and Passengers. No role-conditional age validation is needed. The existing age range of 18-80 in FR-17 is confirmed as correct for all roles. |
| OQ-07 | Is there a requirement to collect the vehicle registration number or vehicle type as part of Driver onboarding in v1, or is that deferred to a separate feature? If required here, it expands scope significantly. | false | **Resolved (v3, amended v4).** Yes, vehicle registration is included in v1 Driver onboarding. A Driver must provide a vehicle registration number (Indian format: `^[A-Z]{2}[0-9]{2}[A-Z]{1,3}[0-9]{1,4}$`) and vehicle type (one of: `car`, `suv`, `hatchback`, `sedan`, `auto_rickshaw`, `bike`) after DL verification is complete. Exactly one vehicle per Driver in v1. Vehicle info is stored in a new `Vehicle` model linked to the user. The Driver onboarding flow is: Role selection -> Profile details -> DL submission -> Vehicle registration -> COMPLETE. This adds the `AWAITING_VEHICLE` onboarding status and `vehicle_registration` next step (FR-27 through FR-31). **v4 amendment:** the v3 statement "no third-party verification of vehicle registration in v1" is superseded: optional, feature-flagged RC verification is added (FR-32 to FR-50), but it ships OFF, so launch behaviour remains format validation + self-declaration. |
| OQ-08 | How should Drivers in `pending_verification` state be notified when their DL result arrives? Push notifications are listed as a non-goal; will the app poll on launch, or is a passive "check next time you open the app" model acceptable to the product team? | false | |
| OQ-09 | Should there be a time limit after which a `pending_verification` Driver is automatically rejected if no webhook is received (e.g. 48 hours)? This requires a periodic task and a policy decision. | false | |
| OQ-10 | Is the DL number to be stored encrypted at rest (requiring a key management strategy) or is hashing with last-4 display sufficient? This decision affects the data model and has compliance implications. | false | **Resolved (v3).** DL numbers are stored using Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) with the encryption key loaded from the `DL_ENCRYPTION_KEY` environment variable. The last 4 characters are stored in plaintext in `dl_number_display` for display/audit purposes. This approach is already implemented in the codebase. See FR-20 and NFR-SEC-01 for details. |
| OQ-R1 | Is RC verification a must-have for launch, or can the self-declared flow ship first with RC verification flagged off? | false | **Resolved (v4).** Ship with `RC_VERIFICATION_ENABLED` OFF; the self-declared flow stays the launch behaviour. RC verification is built and mocked only; turning it on is a config change once a provider exists. Flag-off completion is an explicit requirement (FR-32, AC-31). |
| OQ-R2 | Name-mismatch policy: flag-for-review, hard reject, or accept silently? What evidence for family/fleet-owned vehicles? | false | **Resolved (v4).** On owner-name mismatch (flag ON), flag the vehicle for admin review; do not reject. Objective failures (RC not found, blacklisted/blocked, vehicle class conflict) are rejected. Family- and fleet-owned vehicles use the review path; no extra evidence collection in v1. See FR-37, FR-38, FR-44. |
| OQ-R3 | Are expired insurance or fitness blocking rejections or informational? | false | **Resolved (v4).** Informational only in v1: stored, not blocking (FR-48). |
| OQ-R4 | Hard unique registration number per driver, or may several drivers share a vehicle? | false | **Resolved (v4).** Several Drivers may share one registration number in v1; no unique constraint. Add a non-unique index and an admin duplicate indicator (FR-46). |
| OQ-R5 | Are grandfathered (already onboarded) drivers required to verify? | false | **Resolved (v4).** No. Drivers who already completed onboarding are not moved back or forced to verify (FR-45). An optional later phase may add a post-onboarding verify prompt; it is a Non-Goal of this version. |
| OQ-R6 | Attempt limit, recovery, and stale-pending policy. | false | **Resolved (v4).** `RC_MAX_ATTEMPTS` default 3 (configurable). After that, a staff member resets attempts or manually approves in admin. No auto-reject of stale pending in v1 (FR-40). |
| OQ-R7 | Is storing the RC owner name acceptable under the DPDP Act, and for how long? | false | **Partially resolved (v4).** Store the owner name (needed for match and review), staff-only, minimal fields, no raw payload, not logged (FR-47, NFR-SEC-07). **OPEN, not blocking the flag-off launch (v5):** legal/compliance must decide the retention period for `rc_owner_name` and related RC data under the DPDP Act 2023, and whether/when it must be purged or nulled after resolution. It only becomes blocking for enabling the flag (`RC_VERIFICATION_ENABLED`) in production; no RC data is stored while the flag is OFF. |
| OQ-R8 | Which `vehicle_type` values map to which RC classes; is a mismatch a rejection? | false | **Resolved (v4).** Keep a documented mapping from `vehicle_type` (car, suv, hatchback, sedan, auto_rickshaw, bike) to RC vehicle classes; reject only on a clear class conflict (e.g. declared car but RC class two-wheeler). The exact mapping table goes in the architecture document (FR-39). |
| OQ-R9 | Manual RC photo upload as an exception path in v1? | false | **Resolved (v4).** No manual RC document upload in v1; a future exception path (Non-Goal). |
| OQ-R10 | Provider selection (budget, volume, data-processing terms). | false | **Resolved (v4).** Deferred, as for DL. Only `MockRCVerificationAdapter` is built; the adapter interface stays swappable (FR-33, Non-Goals). Provider selection is a separate follow-up. |
| OQ-R11 | Do commercial/taxi vehicles need additional proof (permits)? | false | **Resolved (v4).** Out of scope for v1 (Non-Goal). |
| OQ-R12 | **Architect to confirm:** (a) HTTP mapping of RC rejection: this document specifies `422 rc_verification_rejected` per the product decision; PLAN-003 suggested a `200` body with `rc_verification_status = rejected`, consistent with DL. (b) Whether a `complete` Driver with no vehicle row who switches role passenger -> driver should be derived to `awaiting_vehicle` (as FR-43 stated in v4) or stay `complete` as a grandfathered case (PLAN-003 D5 recommendation). (c) Whether the RC webhook while the flag is OFF returns `404` or an inert `200`. | false | **Resolved (v5).** (a) `422 rc_verification_rejected` retained, carried by the additive error `extra` mechanism (ADR Decision 16). (b) A `complete` Driver with no vehicle row stays `complete` (ADR Decision 20); FR-43, AC-48 and the edge case amended in v5 (U1). (c) The RC webhook returns `404` with no state change while the flag is OFF (ADR Decision 21); no state change was the product requirement in either case. **(v6) Refinement of (b):** a Driver with no vehicle row stays `complete` only when explicitly marked `vehicle_step_exempt` by the one-time data migration; otherwise the derivation is `awaiting_vehicle` (FR-43, AC-48). **(v7) Refinement of (c):** the flag-off `404` carries the error code `not_found`; with the flag ON an unknown reference returns `404 rc_reference_not_found` (FR-57). |
| OQ-R13 | Who owns the admin review queue for `pending_rc_verification` vehicles, and what review SLA applies, before the flag is enabled in production? | false | **OPEN (operations), not blocking the flag-off launch (v5).** Not needed while the flag is OFF; must be answered before the flag is enabled in production. Admin tooling is provided (ADR Decision 23); owner, SLA and queue monitoring are operations decisions. |
| OQ-R14 | **(v5, U4)** Operations/security item: staging with the mock RC adapter requires `DEBUG=True`, because the production guard refuses the mock adapter when `RC_VERIFICATION_ENABLED` is ON and `DEBUG=False` (NFR-SEC-08, AC-51). A staging environment run with `DEBUG=False` therefore cannot exercise the flag against the mock. Options: run that staging check with `DEBUG=True`, wait for a real provider adapter, or add an explicit, security-approved override (not designed). No override is approved or specified in this version. | false | **OPEN (operations / security), not blocking the flag-off launch (v5).** The guard stays as specified (NFR-SEC-08). A decision is needed before staging verification of the flag-on path; the flag-off launch does not depend on it. |
| OQ-R15 | **(v7)** (a) Request-side casing: FR-29 and FR-53 define lowercase as the accepted request form. Is an UPPERCASE (or mixed-case) `vehicle_type` in a request rejected `400 invalid_vehicle_type` or normalised to lowercase? Not specified by this amendment. (b) The v5 decision preserved the pre-change `vehicle_type` casing in the flag-off success response; FR-53 now returns UPPERCASE. Confirm that no existing client consumes the previous casing. (c) Does the GET `vehicle/status/` endpoint return the sanitised reason in `rejection_reason` for a vehicle in `rejected` state, or `null` (FR-56 covers the POST `200`/`202` responses only)? | false | **OPEN (product / architect), not blocking.** Current text: request values are lowercase (FR-29); `vehicle_type` is returned UPPERCASE (FR-53); `rejection_reason` on the status endpoint remains described as sanitised (unchanged from v4). |
| OQ-R16 | **(v8)** (a) A user in `pending_verification` whose DL was rejected by webhook (AC-10) stays in `pending_verification`, and the no-op rule (FR-55) means a switch to `driver` from that state does not re-open DL submission; recovery is a round trip through passenger (yielding `awaiting_dl`). Should a webhook DL rejection instead move the user to `awaiting_dl`, or should the no-op rule exclude this case? (b) Should starting driver setup be blocked up front (rather than failing at the next DL submission with `429`) when the user's DL attempts are already exhausted? (c) Should the passenger-visible gate (accepted for v1) later be relaxed with a "passenger plus pending driver" state? | false | **OPEN (product), not blocking.** Current text: (a) the round trip is the recovery path (FR-55, Edge Cases); (b) the switch is allowed and the `429` surfaces on DL submission (AC-60); (c) the single `onboarding_status` gate applies (A-v8-1, Non-Goals). |

## Success Metrics

| Metric | Target |
|--------|--------|
| Passenger onboarding completion rate (completed / started) | >= 80% within 24 hours of signup |
| Driver onboarding completion rate through DL submission | >= 60% within 48 hours of signup |
| Driver onboarding completion rate through vehicle registration | >= 55% within 48 hours of signup (applies with the flag OFF and, once enabled, with the flag ON) |
| Driver DL verification approval rate | >= 70% of submitted DLs verified on first attempt |
| Median time from role selection to profile complete (Passenger) | <= 3 minutes |
| `dl_verification_provider_error` rate | < 2% of DL submission calls |
| Onboarding gate bypass incidents (unapproved users accessing main app) | 0 |
| p95 latency for `GET /api/onboarding/status/` | <= 100 ms (NFR-PERF-01) |
| Flag-off regression: Drivers completing onboarding via the vehicle step while `RC_VERIFICATION_ENABLED` is OFF who are blocked by any RC logic | 0 |
| Paths to `complete` for a Driver with a pending or rejected vehicle (flag ON) | 0 |
| (v8) Paths to `complete` for a Driver with no active vehicle who is not grandfathered (flag ON or OFF) | 0 |
| (v8) Passengers who start driver setup via the role switch and reach `awaiting_dl` but can neither submit a DL nor return to passenger (users locked out) | 0 |
| (Flag ON only, after a real provider exists) RC first-attempt automatic verification rate | Baseline to be set after enablement; target to be defined with product |
| (Flag ON only) share of RC submissions routed to admin review | Tracked; target to be defined with product |
| (Flag ON only) median / p95 age of `pending_rc_verification` entries | Tracked; target to be defined once an ops owner and SLA exist (OQ-R13) |
