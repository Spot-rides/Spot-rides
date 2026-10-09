# Requirement: User Onboarding Flow

**ID:** FEAT-002
**Type:** requirement
**Version:** 1
**Status:** ready
**Owner:** product-manager
**Date:** 2026-09-23
**Priority:** critical

---

## Summary

After a user completes OTP-based phone signup (FEAT-001), they must complete a
structured onboarding flow before accessing the main app. The flow captures
role selection (Driver or Passenger), personal details, and — for Drivers only
— driving licence (DL) verification via a third-party API. Onboarding state is
persisted server-side so a user can resume mid-flow on any device. The main app
experience is gated behind onboarding completion.

## Goal

Collect role, personal profile information, and (for Drivers) verified driving
licence status from every new user before granting access to the Spot Rides
main experience.

## Problem

After FEAT-001, a successfully authenticated user has only a phone number on
record. The app has no role signal to distinguish Drivers from Passengers, no
name or demographic data needed to populate ride interfaces, and no mechanism to
vet drivers' licence validity before they begin offering rides. Without this
layer, no functional ride experience can be launched safely or legally.

Additionally, there is no gate preventing a partially-registered user from
accessing the main app, which would produce undefined behaviour downstream.

## Users

| Role | Description |
|------|-------------|
| New Passenger | A user who completed OTP signup and is setting up their Passenger account for the first time. |
| New Driver | A user who completed OTP signup and intends to offer rides as a Driver (labeled "Rider" in the UI). |
| Returning partial user | A user who started onboarding on one device and resumes on another. |
| Operations / Trust & Safety | Internal team that reviews DL verification outcomes and may need to manually approve or reject Driver accounts. |

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
| FR-08 | The backend must call the configured DL verification provider after format validation. The integration must be implemented behind an adapter interface so the concrete provider can be swapped without modifying business logic. | must |
| FR-09 | If the DL verification provider responds synchronously with a verified result, `onboarding_status` must be set to `complete` and `dl_verification_status` to `verified` in the same request cycle. | must |
| FR-10 | If the DL verification provider responds asynchronously (deferred/pending result), `onboarding_status` must be set to `pending_verification` and `dl_verification_status` to `pending`. The provider must be able to deliver the final result via a webhook endpoint. | must |
| FR-11 | The backend must expose `POST /api/onboarding/driver/dl/webhook/` for inbound DL verification results from the provider. On receipt of a verified result, `dl_verification_status` is set to `verified` and `onboarding_status` to `complete`. On rejection, `dl_verification_status` is set to `rejected` and the Driver is notified (mechanism TBD — push notification is out of scope for this feature; the client must poll or the status must surface on next app open). | must |
| FR-12 | The backend must expose `GET /api/onboarding/driver/dl/status/` (authenticated, Drivers only) so the mobile client can poll for DL verification outcome. | must |
| FR-13 | A Driver whose DL was rejected must be allowed to resubmit via `POST /api/onboarding/driver/dl/` with a corrected DL number. The maximum number of resubmission attempts before manual review is required is a configurable setting (default: 3). | must |
| FR-14 | Any authenticated request to a protected non-onboarding endpoint by a user whose `onboarding_status` is not `complete` must return `403 onboarding_incomplete` with the current `onboarding_status` and `next_step` in the response body, enabling the client to redirect the user. | must |
| FR-15 | A Driver with `onboarding_status = pending_verification` must not be able to accept ride requests. The backend must enforce this even if the client attempts to bypass the gate. | must |
| FR-22 | The backend must expose `PATCH /api/profile/role/` (authenticated) to allow a fully onboarded user to switch their active role between `driver` and `passenger` at any time from within the app. | must |
| FR-23 | When a user switches to `passenger` via FR-22, the switch must take effect immediately regardless of DL status. The existing `DriverVerification` record (if any) is preserved so they can switch back to driver later without re-submitting their DL. | must |
| FR-24 | When a user switches to `driver` via FR-22, the backend must check `DriverVerification.dl_verification_status`. If `verified`, the switch takes effect immediately. If `pending`, the user enters `pending_verification` state and cannot offer rides until confirmed. If `rejected` or no DL record exists, the user must be directed to complete DL submission before the driver role is activated. | must |
| FR-25 | Only a user with `dl_verification_status = verified` may use driver-facing endpoints (e.g. posting a ride offer). The backend must enforce this independently of the `active_role` field — having `active_role = driver` alone is not sufficient. | must |
| FR-26 | The `GET /api/onboarding/status/` and `GET /api/auth/me/` responses must include `active_role`, reflecting the role the user is currently operating as. This is the single source of truth for role; there is no separate immutable "registered role" field. | must |
| FR-16 | Onboarding progress must be stored server-side and associated with the authenticated user so that resuming on a different device returns to the correct step. | must |
| FR-17 | Age must be validated as a positive integer between 18 and 80 inclusive. Any input outside this range must be rejected `400 invalid_age`. | must |
| FR-18 | Gender must be one of: `male`, `female`, `other`, `prefer_not_to_say`. Any other value must be rejected `400 invalid_gender`. | must |
| FR-19 | `first_name` and `last_name` must each be between 1 and 50 characters, contain only Unicode letters, spaces, hyphens, and apostrophes, and must not be blank or whitespace-only. | must |
| FR-20 | The DL number must be stored at rest. The storage strategy (plaintext, masked, or encrypted) is a decision for the architect but must be documented before implementation begins. The last four characters of the DL number must always be available in plaintext for display/audit purposes. | must |
| FR-21 | The `GET /api/auth/me/` response (from FEAT-001) must be extended to include `onboarding_status` and `active_role` (nullable until set) so the Expo client can determine gating on app launch in a single call. | must |

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
  "dl_verification_status": null
}
```

`onboarding_status` values: `not_started`, `role_selected`, `awaiting_dl`,
`pending_verification`, `complete`.

`next_step` values: `role_selection`, `profile`, `dl_submission`, `awaiting_verification`, `none`.

`dl_verification_status` values: `null` (not a driver or not yet submitted),
`pending`, `verified`, `rejected`.

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

**Request:**
```json
{ "dl_number": "MH01 20110012345" }
```

**Response `200 OK` (synchronous verified result):**
```json
{
  "dl_verification_status": "verified",
  "onboarding_status": "complete",
  "next_step": "none"
}
```

**Response `202 Accepted` (async / pending result):**
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

Called by the DL verification provider. Authentication mechanism is provider-
specific (HMAC signature, shared secret, or mTLS); the concrete approach is
decided when the provider is selected. The endpoint must reject unsigned or
unverifiable requests with `403`.

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

### `PATCH /api/profile/role/`

Requires: valid access token. User must have `onboarding_status = complete`.

**Request:**
```json
{ "role": "driver" }
```

**Response `200 OK` (switch to passenger, or switch to driver with verified DL):**
```json
{
  "active_role": "driver",
  "dl_verification_status": "verified"
}
```

**Response `202 Accepted` (switch to driver, DL is pending):**
```json
{
  "active_role": "driver",
  "onboarding_status": "pending_verification",
  "dl_verification_status": "pending"
}
```

**Response `400 dl_required` (switch to driver, no DL on file or DL rejected):**
```json
{
  "error": {
    "code": "dl_required",
    "detail": "Driving licence verification is required before acting as a driver.",
    "next_step": "dl_submission"
  }
}
```

**Errors:**
- `400 invalid_role` — value not in allowed set
- `400 dl_required` — switching to driver but no verified or pending DL exists
- `403 onboarding_incomplete` — user has not completed initial onboarding

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

---

## Data Model Changes

### New model: `UserProfile`

Proposed app: `profiles` (created via `python manage.py startapp profiles`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField | PK |
| `user` | OneToOneField → `accounts.User` | `on_delete=CASCADE`, `related_name="profile"` |
| `active_role` | CharField(10, choices) | `DRIVER`, `PASSENGER`; the role currently in use; set during onboarding and freely mutable afterwards via `PATCH /api/profile/role/`; nullable until onboarding step 1 |
| `first_name` | CharField(50) | nullable until step 2 |
| `last_name` | CharField(50) | nullable until step 2 |
| `age` | PositiveSmallIntegerField | nullable until step 2 |
| `gender` | CharField(20, choices) | `MALE`, `FEMALE`, `OTHER`, `PREFER_NOT_TO_SAY`; nullable until step 2 |
| `onboarding_status` | CharField(30, choices) | `NOT_STARTED`, `ROLE_SELECTED`, `AWAITING_DL`, `PENDING_VERIFICATION`, `COMPLETE` |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

A `UserProfile` row must be created automatically when a user completes OTP
verification for the first time (i.e., on first login / `is_new_user=true`
event from FEAT-001).

### New model: `DriverVerification`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigAutoField | PK |
| `user` | OneToOneField → `accounts.User` | `on_delete=CASCADE`, `related_name="driver_verification"` |
| `dl_number` | CharField(20) | Stored value; see FR-20 on storage strategy |
| `dl_number_display` | CharField(4) | Last 4 chars of DL number, always plaintext |
| `dl_verification_status` | CharField(20, choices) | `PENDING`, `VERIFIED`, `REJECTED` |
| `dl_verification_ref` | CharField(100, nullable) | Provider-issued reference ID for async lookup |
| `dl_submitted_at` | DateTimeField | Timestamp of most recent submission |
| `dl_verified_at` | DateTimeField(nullable) | Timestamp of verification confirmation |
| `dl_rejection_reason` | TextField(nullable) | Provider-supplied reason |
| `attempt_count` | PositiveSmallIntegerField(default=0) | Number of DL submissions; enforces FR-13 |
| `created_at` | DateTimeField(auto_now_add) | |
| `updated_at` | DateTimeField(auto_now) | |

### Migration dependency

`profiles` migrations must depend on `accounts` migrations (the custom
`AUTH_USER_MODEL` must exist before the FK is created).

### `accounts.User` model — no schema change required

`onboarding_status` and `role` are exposed on `GET /api/auth/me/` by joining
through `UserProfile`; the `User` table itself is not modified.

---

## Non-Functional Requirements

### Security

| ID | Description |
|----|-------------|
| NFR-SEC-01 | DL number storage strategy must be decided before implementation. Options are: symmetric encryption at rest, or storing only the last four digits for display and a one-way hash for deduplication. The choice must be documented in an ADR under `docs/decisions/`. |
| NFR-SEC-02 | The webhook endpoint (`POST /api/onboarding/driver/dl/webhook/`) must authenticate the inbound request using the mechanism provided by the DL verification provider (HMAC signature verification or equivalent). Unauthenticated requests must be rejected `403` before any database state is modified. |
| NFR-SEC-03 | Onboarding endpoints must require a valid JWT access token (standard DRF permission class `IsAuthenticated`). The webhook endpoint is authenticated by provider signature, not by a user token. |
| NFR-SEC-04 | The gating behaviour (FR-14) must be enforced server-side. The client-side redirect is a UX convenience only; it must not be the sole enforcement mechanism. |
| NFR-SEC-05 | The DL verification provider API key and any webhook shared secret must be loaded from environment variables via `python-decouple` and documented in `backend/.env.example` with placeholder values only. |
| NFR-SEC-06 | `first_name`, `last_name`, age, and gender are PII. Admin access must be restricted to staff users. |

### Performance

| ID | Description |
|----|-------------|
| NFR-PERF-01 | `GET /api/onboarding/status/` and `GET /api/onboarding/driver/dl/status/` must return within 100 ms at p95 under a load of 50 requests/second (reads against a single indexed row). |
| NFR-PERF-02 | `POST /api/onboarding/profile/` and `POST /api/onboarding/role/` must return within 200 ms at p95 (local DB writes only). |
| NFR-PERF-03 | `POST /api/onboarding/driver/dl/` must return within 3000 ms at p95 when the provider responds synchronously. If the provider is async the endpoint must return within 500 ms after dispatching the request. |

### Reliability

| ID | Description |
|----|-------------|
| NFR-REL-01 | DL verification provider calls must be wrapped in a timeout (configurable, default 5 seconds). On timeout the system must treat the result as `pending` and persist the pending state, not surface a 500 to the client. |
| NFR-REL-02 | The webhook handler must be idempotent: receiving the same `reference_id` with the same outcome more than once must not alter state or raise an error beyond `409 already_processed`. |

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
| AC-07 | Given a Driver in `awaiting_dl`, when `POST /api/onboarding/driver/dl/` is called with a valid Indian DL number (e.g. `"MH01 20110012345"`) and the provider mock returns a synchronous verified result, then the response is `200` with `dl_verification_status = "verified"` and `onboarding_status = "complete"`. | Integration test with provider adapter mocked to return verified synchronously. | must |
| AC-08 | Given a Driver in `awaiting_dl`, when `POST /api/onboarding/driver/dl/` is called and the provider mock returns a pending result, then the response is `202` with `dl_verification_status = "pending"` and `onboarding_status = "pending_verification"`. | Integration test with provider adapter mocked to return pending. | must |
| AC-09 | Given a Driver in `pending_verification`, when the webhook endpoint receives a verified payload with a valid signature and the matching `reference_id`, then `dl_verification_status` is updated to `verified` and `onboarding_status` to `complete`. | Integration test: seed a DriverVerification row in pending state, POST to webhook, assert model fields. | must |
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
| AC-22 | Given a fully onboarded Passenger, when `PATCH /api/profile/role/` is called with `role = "driver"` but no DL has been submitted, then the response is `400 dl_required` and `active_role` remains `passenger`. | Integration test. | must |
| AC-23 | Given a fully onboarded user who registered as Passenger but has a `dl_verification_status = verified` (previously switched and submitted DL), when `PATCH /api/profile/role/` is called with `role = "driver"`, then the response is `200` with `active_role = "driver"`. | Integration test. | must |
| AC-24 | Given a Driver with `dl_verification_status = verified` and `active_role = "driver"`, when `PATCH /api/profile/role/` is called with `role = "passenger"`, then the response is `200` with `active_role = "passenger"` and the `DriverVerification` record is preserved. | Integration test. | must |
| AC-25 | Given a user who switches back to driver after previously verifying their DL (AC-24), when `PATCH /api/profile/role/` is called with `role = "driver"` again, then the response is `200` — no re-submission of DL is required. | Integration test. | must |
| AC-26 | Given a user with `active_role = "passenger"`, when they call a driver-only ride endpoint, then the response is `403` even if their `dl_verification_status = verified`. Only `active_role = "driver"` AND `dl_verification_status = verified` unlocks driver actions. | Integration test. | must |

## Edge Cases

- **Concurrent role submissions** — Two simultaneous `POST /api/onboarding/role/` calls for the same user must not create two `UserProfile` rows. Enforce with `get_or_create` plus a unique constraint on `UserProfile.user`.
- **UserProfile creation timing** — If the `UserProfile` row is not yet created when `GET /api/onboarding/status/` is called (race between OTP verify callback and first status poll), the endpoint must still return `200` with `not_started` rather than `404`. The row must be created lazily or as part of the OTP verify response.
- **Webhook delivered before client receives `202`** — The webhook may arrive and update state before the driver's `POST /api/onboarding/driver/dl/` response is delivered to the client. This is harmless: the client will call `GET /api/onboarding/driver/dl/status/` to confirm. State transitions must be idempotent.
- **Duplicate webhook deliveries** — Providers commonly retry webhooks. The handler must be idempotent; re-processing a `reference_id` that is already in terminal state (`verified` or `rejected`) must return `409 already_processed` and not overwrite data.
- **DL number with mixed-case input** — The server must either normalise to uppercase before validation (preferred) or reject with a clear `400 invalid_dl_format`. Behaviour must be consistent and documented.
- **Provider returns an unrecognised status value** — The webhook handler must log the raw payload and treat the outcome as a transient error requiring manual review, not silently overwrite state.
- **User deletes and re-registers with the same phone number** — Out of scope for this feature (no delete flow exists per FEAT-001); noted for future handling.
- **Age boundary values** — `age = 18` and `age = 80` must be accepted. `age = 17` and `age = 81` must be rejected.
- **Role endpoint called before OTP verification completes** — All onboarding endpoints require a valid access token. If a token is not yet held, the request returns `401`. No special handling needed.
- **Provider API key misconfigured** — `POST /api/onboarding/driver/dl/` must return `422 dl_verification_provider_error` rather than a `500` crash. Operators must be alerted via logs.

## Non-Goals

- Frontend / Expo implementation of onboarding screens (a separate frontend feature).
- Profile photo / avatar upload.
- Vehicle registration details for Drivers (planned for a separate feature).
- Background checks beyond DL verification.
- Document upload (Aadhar, PAN card, etc.) — not required in v1.
- Email collection or email verification at any stage.
- Admin tooling for manually approving or rejecting Driver accounts (may be added in a follow-up; for now the webhook outcome is the only approval path).
- Push notifications to a Driver when their DL verification status changes.
- Onboarding analytics funnel (drop-off tracking per step).
- Profile editing after onboarding is complete (a separate "edit profile" feature).
- Role switching UI/UX design (a frontend concern; backend contract is defined here).
- Multi-language / localisation of validation error messages.
- Age verification via government ID cross-check (DL format check only).

## Constraints

- All endpoints must be prefixed `/api/` per project convention.
- The new Django app must be created via `python manage.py startapp profiles` (or an architect-approved alternative name).
- The DL verification provider is TBD; the adapter interface must be designed to support both synchronous and asynchronous (webhook) response patterns without changing business logic.
- Environment variables for the DL provider must use `python-decouple` (`config(...)`) consistent with `backend/config/settings.py` and documented in `backend/.env.example`.
- The onboarding gate (FR-14) must be implemented as a DRF permission class or middleware so it is applied consistently to all protected non-onboarding endpoints without per-view boilerplate.
- PostgreSQL is the only supported datastore.
- All API responses must conform to the unified envelope defined in DEC-011.
- The `UserProfile` migration must declare a dependency on the `accounts` app migration that defines `AUTH_USER_MODEL`.

## Dependencies

| Name | Type | Required |
|------|------|----------|
| FEAT-001 OTP authentication | Internal feature | true |
| `accounts.User` model (custom `AUTH_USER_MODEL`) | Internal model | true |
| DL verification third-party provider | External service | true (provider TBD — see OQ-01) |
| PostgreSQL (already present) | Infrastructure | true |
| `python-decouple` (already present) | Python package | true |
| DRF (already present) | Python package | true |

## Assumptions

- A `UserProfile` row is created (with `onboarding_status = not_started`) the first time a user successfully completes OTP verification (`is_new_user = true` from FEAT-001). The mechanism for this trigger is an implementation decision (post-save signal, service layer call, or direct creation in the OTP verify view).
- The Indian DL format pattern `^[A-Z]{2}[0-9]{2}[ -]?[0-9]{4}[0-9]{7}$` covers all currently issued DL numbers. State code validity (e.g. `MH` is valid, `ZZ` is not) is not validated in v1; this is an open extension point.
- Age is collected as a self-reported integer (birth date is not required). The product team accepts the risk that users may enter inaccurate ages.
- Drivers are labeled "Rider" in all UI copy. Backend field values use `driver` and `passenger` for clarity. The UI label mapping is a frontend concern and does not affect API contracts.
- `active_role` is the single source of truth for a user's current role. There is no separate immutable "registered role" — the role chosen at onboarding simply becomes the initial value of `active_role`.
- The DL verification provider will support at minimum one of: a synchronous REST API returning a definitive result immediately, or an asynchronous REST API that accepts a callback/webhook URL. The adapter interface must handle both.
- A maximum of 3 DL resubmission attempts (default) is a configurable setting; product may adjust this without a code change.
- The webhook endpoint path is not secret; authentication relies solely on the provider's signature mechanism.

## Open Questions

| ID | Question | Blocking |
|----|----------|---------|
| OQ-01 | Which DL verification provider will be used? Options in the Indian market include Digilocker API, Karza, IDfy, AuthBridge, and others. The provider choice affects the adapter interface design, webhook authentication mechanism, and what the `dl_rejection_reason` field can contain. | true |
| OQ-02 | Does the DL verification provider support both synchronous and asynchronous response modes, or only one? This determines whether the `202 pending` path is a required code path or an edge-case fallback. | true |
| OQ-03 | Should the DL number validator normalise lowercase input to uppercase before validation, or reject it outright? The user-facing experience differs: normalisation is more forgiving but may mask data entry errors. | false |
| OQ-04 | What is the webhook authentication mechanism provided by the selected DL provider (HMAC-SHA256 header, shared secret, IP allowlist, mTLS)? Required to specify NFR-SEC-02 concretely. | true |
| OQ-05 | Should `UserProfile` be created proactively at OTP-verify time (in the `accounts` app) or lazily on the first call to `/api/onboarding/status/`? The proactive approach couples `accounts` to `profiles`; the lazy approach requires careful handling of the first-call race. | false |
| OQ-06 | What is the minimum age for Passengers? The requirement currently sets 18 for both roles. If the product intends to allow younger Passengers (e.g. students), the `age` validation range must be role-conditional. | true |
| OQ-07 | Is there a requirement to collect the vehicle registration number or vehicle type as part of Driver onboarding in v1, or is that deferred to a separate feature? If required here, it expands scope significantly. | true |
| OQ-08 | How should Drivers in `pending_verification` state be notified when their DL result arrives? Push notifications are listed as a non-goal; will the app poll on launch, or is a passive "check next time you open the app" model acceptable to the product team? | false |
| OQ-09 | Should there be a time limit after which a `pending_verification` Driver is automatically rejected if no webhook is received (e.g. 48 hours)? This requires a periodic task and a policy decision. | false |
| OQ-10 | Is the DL number to be stored encrypted at rest (requiring a key management strategy) or is hashing with last-4 display sufficient? This decision affects the data model and has compliance implications. | true |

## Success Metrics

| Metric | Target |
|--------|--------|
| Passenger onboarding completion rate (completed / started) | >= 80% within 24 hours of signup |
| Driver onboarding completion rate through DL submission | >= 60% within 48 hours of signup |
| Driver DL verification approval rate | >= 70% of submitted DLs verified on first attempt |
| Median time from role selection to profile complete (Passenger) | <= 3 minutes |
| `dl_verification_provider_error` rate | < 2% of DL submission calls |
| Onboarding gate bypass incidents (unapproved users accessing main app) | 0 |
| p95 latency for `GET /api/onboarding/status/` | <= 100 ms (NFR-PERF-01) |
