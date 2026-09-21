# Requirement: OTP-Based Phone Authentication (Backend)

**ID:** FEAT-001
**Type:** requirement
**Version:** 1
**Status:** ready
**Owner:** product-manager
**Date:** 2026-09-12
**Priority:** high

---

## Summary

Introduce a passwordless authentication layer for the Spot Rides Django/DRF
backend. Users identify themselves with a phone number and prove possession
via a one-time password (OTP) delivered by Twilio SMS. Upon successful
verification, the backend issues a JSON Web Token pair (access + refresh) via
`djangorestframework-simplejwt` so subsequent `/api/` requests can be
authenticated. The feature covers new-user sign-up and returning-user sign-in
through a single unified flow.

## Goal

Enable a user to authenticate against the Spot Rides backend by proving
control of a phone number through a Twilio-delivered OTP, and receive a JWT
access/refresh token pair for authenticated `/api/` access.

## Problem

The Spot Rides backend currently has no authentication mechanism beyond the
default Django admin. There is no user model tailored to the product's
identifier (a phone number), no way for a mobile client to register or sign
in, and no token issuance to authorize API calls. Without this layer, no
protected product functionality (rides, profiles, bookings) can be built.

Passwords are undesirable for a mobile-first ride-hailing product because:

* users on mobile dislike managing passwords
* phone numbers are the natural identity for ride-hailing
* OTP flows align with regional norms for on-demand mobility apps
* proving possession of a number reduces fraudulent sign-ups

## Users

| Role | Description |
|------|-------------|
| Unregistered rider | A person opening the app for the first time who has never authenticated with Spot Rides. |
| Returning rider | A person with a previously verified phone number returning to the app on the same or a new device. |
| Backend engineer | Engineer who consumes the endpoints from server-side integrations, tests, and support tooling. |
| Mobile client (Expo app) | The React Native app in `frontend/` that will consume these endpoints in a later feature. |

## User Stories

| ID | Statement | Priority |
|----|-----------|---------|
| US-01 | As an unregistered rider, I want to enter my phone number and receive an SMS code, so that I can create an account without a password. | must |
| US-02 | As a rider who received an SMS code, I want to submit that code and be logged in, so that I can start using the app. | must |
| US-03 | As a returning rider, I want the same phone-number-plus-OTP flow to sign me in on any device, so that I don't need a separate login path. | must |
| US-04 | As an authenticated rider, I want my session to persist across app restarts via a refresh token, so that I am not asked for an OTP on every launch. | must |
| US-05 | As a rider whose access token has expired, I want to refresh it silently using my refresh token, so that I stay signed in. | must |
| US-06 | As a rider, I want to log out and have my refresh token invalidated, so that a stolen device cannot continue my session. | should |
| US-07 | As a rider who did not receive the SMS, I want to request the code be resent after a short cooldown, so that transient SMS failures do not lock me out. | must |
| US-08 | As the operator, I want abusive request patterns (rapid OTP requests or brute-force verification) to be rate-limited, so that Twilio spend and account takeover risk are bounded. | must |

## Functional Requirements

| ID | Description | Priority |
|----|-------------|---------|
| FR-01 | The backend must expose `POST /api/auth/otp/request/` accepting a `phone_number` field. It normalizes the value to E.164 format, validates it, and, when valid, generates and stores an OTP and dispatches it via Twilio SMS. | must |
| FR-02 | The backend must expose `POST /api/auth/otp/verify/` accepting `phone_number` and `code`. On success, it returns a JWT access token, a refresh token, and a boolean `is_new_user` flag. | must |
| FR-03 | The backend must expose `POST /api/auth/token/refresh/` conforming to `djangorestframework-simplejwt`'s standard refresh contract, returning a new access token (and rotated refresh token if rotation is enabled). | must |
| FR-04 | The backend must expose `POST /api/auth/logout/` accepting a refresh token and blacklisting it so it can no longer be exchanged for an access token. | should |
| FR-05 | The backend must expose `GET /api/auth/me/` that returns the authenticated user's minimal profile (id, phone_number, is_new_user hint if useful, date_joined). Requires a valid access token. | must |
| FR-06 | OTP codes must be exactly 6 numeric digits, generated from a cryptographically secure random source. | must |
| FR-07 | OTP codes must expire no more than 5 minutes after issuance. Verifying an expired code must fail with a distinct error code. | must |
| FR-08 | A given phone number must be limited to at most 1 OTP request every 30 seconds, at most 5 OTP requests per rolling hour, and at most 10 per rolling 24 hours. Requests exceeding this must return HTTP 429 with a `retry_after` seconds value. | must |
| FR-09 | A given phone number must allow at most 5 verification attempts per active OTP. On the 5th failed attempt the OTP must be invalidated and a new OTP must be requested. | must |
| FR-10 | Requesting a new OTP for a phone number must invalidate any prior un-consumed OTP for that number. Only the latest OTP is valid at any time. | must |
| FR-11 | Successful verification must upsert a user record keyed on the normalized E.164 phone number. If the number has never been seen, a new user is created and `is_new_user=true` is returned. | must |
| FR-12 | Phone numbers must be validated and stored in E.164 form (e.g. `+14155552671`). Inputs that cannot be parsed to E.164 must be rejected with HTTP 400. | must |
| FR-13 | The system must support international phone numbers (any valid E.164 number Twilio can deliver to). Country restrictions, if any, are configured via settings and not hardcoded. | must |
| FR-14 | Twilio credentials (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` or Messaging Service SID) must be read from environment via `python-decouple`, matching the existing pattern in `backend/config/settings.py`. They must never be hardcoded or committed. | must |
| FR-15 | When Twilio dispatch fails, the OTP record must not be committed (or must be rolled back), and the endpoint must return HTTP 502 with a stable error code so the client can retry. The phone number's rate-limit counter must not be incremented for a Twilio-side failure. | must |
| FR-16 | The system must log every OTP request, verification attempt (success/failure), and token issuance with a request id, hashed phone number, and outcome. Raw OTP codes and full phone numbers must never appear in application logs. | must |
| FR-17 | JWT access tokens must have a lifetime of 15 minutes; refresh tokens 30 days. Rotation on refresh must be enabled, and rotated refresh tokens must be blacklisted. | must |
| FR-18 | The system must provide a development-mode override (`OTP_DEV_MODE=True`) where a fixed OTP (e.g. `000000`) is accepted and Twilio dispatch is skipped. This override must be a no-op when `DEBUG=False`. | should |

## API Contract Sketch

Endpoints (final shapes to be confirmed by architect):

### `POST /api/auth/otp/request/`

Request:
```json
{ "phone_number": "+14155552671" }
```

Success `200 OK`:
```json
{ "detail": "otp_sent", "expires_in": 300, "resend_available_in": 30 }
```

Errors:
* `400` `invalid_phone_number`
* `429` `rate_limited` (with `retry_after`)
* `502` `sms_dispatch_failed`

### `POST /api/auth/otp/verify/`

Request:
```json
{ "phone_number": "+14155552671", "code": "123456" }
```

Success `200 OK`:
```json
{
  "access": "<jwt>",
  "refresh": "<jwt>",
  "is_new_user": true,
  "user": { "id": 42, "phone_number": "+14155552671" }
}
```

Errors:
* `400` `invalid_code`, `code_expired`, `no_active_otp`
* `429` `too_many_attempts` (OTP invalidated; client must request a new one)

### `POST /api/auth/token/refresh/`

Standard SimpleJWT contract:
```json
{ "refresh": "<jwt>" }
```
Response includes new `access` (and rotated `refresh` if enabled).

### `POST /api/auth/logout/`

Request:
```json
{ "refresh": "<jwt>" }
```
Response `205 Reset Content` on success. Blacklists the refresh token.

### `GET /api/auth/me/`

Authenticated. Returns:
```json
{ "id": 42, "phone_number": "+14155552671", "date_joined": "2026-09-12T10:00:00Z" }
```

## Data Model Implications

* **Custom `User` model** (or extension of `AbstractBaseUser`) whose primary
  identifier is `phone_number` (E.164, unique, indexed). `USERNAME_FIELD =
  "phone_number"`. No password required (may keep the field unusable via
  `set_unusable_password()`). Django's `AUTH_USER_MODEL` must be set before
  the first migration in this project.
* **`OtpCode` table** (or equivalent) storing: id, phone_number (E.164,
  indexed), code_hash (never the raw code), created_at, expires_at,
  consumed_at (nullable), attempts (int), invalidated (bool), request_ip
  (nullable, for abuse analytics), request_id.
* **Rate-limit counters** — may be stored in-DB alongside `OtpCode` or in a
  cache (final choice deferred to architect; the requirement is behavioural,
  see FR-08).
* **Refresh token blacklist** — provided by
  `rest_framework_simplejwt.token_blacklist`, requires its own migration.
* Persistent OTP storage is required (transient/cache-only is acceptable only
  if audit logging captures attempt outcomes independently, per FR-16).

## Non-Functional Requirements

### Security

| ID | Description |
|----|-------------|
| NFR-SEC-01 | OTP codes must be stored hashed (e.g. HMAC-SHA256 with a server-side pepper from settings), never in plaintext. |
| NFR-SEC-02 | Verification must be constant-time against the hash to avoid timing side channels. |
| NFR-SEC-03 | Twilio credentials and the OTP pepper must be loaded from environment variables via `python-decouple` and documented in `backend/.env.example` with placeholder values only. |
| NFR-SEC-04 | Phone numbers logged for observability must be hashed or masked (e.g. last 4 digits). Raw OTPs must never be logged, even at DEBUG level. |
| NFR-SEC-05 | Enumeration must be mitigated: `POST /api/auth/otp/request/` must not disclose whether a phone number is already registered. The response is the same for new and returning users. |
| NFR-SEC-06 | JWT signing key must be distinct from `SECRET_KEY` or must be rotated independently; document the choice. Refresh tokens must be blacklistable. |
| NFR-SEC-07 | All auth endpoints must be served over HTTPS in production (enforcement at deploy layer; documented as a deployment constraint). |
| NFR-SEC-08 | Brute-force verification must be bounded per FR-09 and additionally per-IP (max 20 verify attempts per IP per 10 minutes across all phone numbers). |

### Performance

| ID | Description |
|----|-------------|
| NFR-PERF-01 | `POST /api/auth/otp/request/` must return within 2000 ms at p95 under a load of 20 requests/second sustained for 60 seconds (Twilio latency dominates; the endpoint may return before Twilio confirms delivery, but before returning it must have persisted the OTP). |
| NFR-PERF-02 | `POST /api/auth/otp/verify/` must return within 300 ms at p95 under the same workload. |
| NFR-PERF-03 | Token refresh must return within 150 ms at p95. |

### Observability

| ID | Description |
|----|-------------|
| NFR-OBS-01 | Each auth request must emit a structured log entry with request id, endpoint, outcome code, masked phone identifier, and duration. |
| NFR-OBS-02 | Counters must be exposed (or at minimum log-derivable) for: otp_requests_total, otp_verify_success_total, otp_verify_failure_total (by reason), sms_dispatch_failure_total, rate_limit_hits_total. |
| NFR-OBS-03 | Twilio dispatch errors must include the Twilio error code in logs (but not customer-visible responses). |

### Privacy

| ID | Description |
|----|-------------|
| NFR-PRIV-01 | Phone number is PII. Access to it in the admin must be restricted to staff users and audited via Django admin's log. |
| NFR-PRIV-02 | Consumed and expired OTP records must be purged (or code_hash nulled) no later than 24 hours after expiry via a periodic task. Attempt outcome counters may be retained in aggregate. |

## Acceptance Criteria

| ID | Description | Verification | Priority |
|----|-------------|-------------|---------|
| AC-01 | Given a valid E.164 phone number, when `POST /api/auth/otp/request/` is called, then the API responds `200` with `expires_in=300` and an SMS containing a 6-digit code is dispatched to Twilio. | Integration test with Twilio client mocked; assert response body and mock call args. | must |
| AC-02 | Given a malformed phone number ("12345", "abc", missing `+`), when the request endpoint is called, then the API responds `400 invalid_phone_number` and no OTP is created and no SMS is dispatched. | Unit + integration tests with parametrized invalid inputs. | must |
| AC-03 | Given an active OTP, when the correct code is submitted to `POST /api/auth/otp/verify/`, then the API responds `200` with `access`, `refresh`, `is_new_user`, and `user` fields; a `User` row exists for that phone number. | Integration test: request OTP, extract stored hash via test hook, submit matching code, assert token pair present and user created. | must |
| AC-04 | Given a returning user (User row already exists for phone), when they complete the OTP flow, then the response includes `is_new_user=false` and the same user id as before. | Integration test seeding an existing user, then executing the flow. | must |
| AC-05 | Given an OTP older than 5 minutes, when verification is attempted, then the API responds `400 code_expired`. | Test with frozen/advanced time (`freezegun` or Django's `override_settings` + injected clock). | must |
| AC-06 | Given an OTP with 5 prior failed attempts, when a 6th verification is attempted (even with the correct code), then the API responds `429 too_many_attempts` and the OTP is marked invalidated. | Integration test looping incorrect submissions then a correct one. | must |
| AC-07 | Given a phone number that just received an OTP, when `POST /api/auth/otp/request/` is called again within 30 seconds, then the API responds `429 rate_limited` with `retry_after` > 0 and no new SMS is dispatched. | Integration test with two rapid requests and Twilio mock call count assertion. | must |
| AC-08 | Given a valid refresh token, when `POST /api/auth/token/refresh/` is called, then the API returns a new access token; when the old refresh token is reused after rotation, it is rejected. | Integration test issuing tokens, refreshing, then attempting reuse. | must |
| AC-09 | Given a valid refresh token, when `POST /api/auth/logout/` is called, then subsequent refresh attempts with that token return 401 and the token appears in the blacklist table. | Integration test. | should |
| AC-10 | Given `GET /api/auth/me/` is called without an `Authorization: Bearer <access>` header, then the API responds `401`. Given a valid access token, then it responds `200` with the correct user data. | Integration test with and without token. | must |
| AC-11 | Given the Twilio client raises an exception during dispatch, when `POST /api/auth/otp/request/` is called, then the API responds `502 sms_dispatch_failed`, no `OtpCode` row is persisted, and the phone number's rate-limit counter is unchanged. | Integration test with Twilio mock raising. | must |
| AC-12 | Given application logs across the full lifecycle, when inspected, then no log line contains the raw OTP code and no log line contains an unhashed/unmasked full phone number. | Test captures logs via `caplog` and asserts absence via regex. | must |
| AC-13 | Given `OTP_DEV_MODE=True` and `DEBUG=True`, when `POST /api/auth/otp/verify/` is called with code `000000` for a phone that has requested an OTP, then verification succeeds and no real Twilio dispatch occurs on the prior request call. Given `DEBUG=False`, the override has no effect regardless of `OTP_DEV_MODE`. | Two integration tests, one per config combination. | should |
| AC-14 | Given input phone number `"(415) 555-2671"` with a US country context, when normalized, then it is stored as `+14155552671`. Given a valid E.164 international number (e.g. `+919812345678`), then it is stored unchanged. | Unit tests over the normalization utility. | must |
| AC-15 | Given a settings misconfiguration where Twilio credentials are missing, when the Django app starts, then it logs a clear warning and (in production) fails health check for the auth subsystem. `/api/auth/otp/request/` must return `503 auth_unavailable` rather than crashing. | System check + integration test with unset env. | should |

## Edge Cases

* **Phone number reuse after account deletion** — Out of scope for this feature; no delete endpoint is being built. Documented as a follow-up concern.
* **Number porting** — A user who changes SIMs but keeps the number is transparently the same user. A user who changes their number cannot currently migrate their account through this API; noted as a future feature.
* **Concurrent OTP requests** — Two simultaneous `otp/request/` calls for the same number must not both dispatch SMS. Enforce with `select_for_update` or a unique-per-active-OTP constraint (implementation choice for architect).
* **Concurrent verify races** — Two simultaneous `verify/` calls where one succeeds must not allow the second to also succeed (consume-once semantics).
* **International SMS delivery failure** — Some numbers/regions have poor SMS delivery. Handled by generic `sms_dispatch_failed` plus resend logic; no special-casing per country in this feature.
* **Case where OTP arrives after user requests resend** — The new request invalidates the prior OTP; the user must use the latest received code. This must be documented in the response for the frontend team.
* **Clock skew** — Expiry is server-side; no client clock trust needed.
* **Twilio account suspension / total outage** — Behaviour matches AC-11 and AC-15.
* **Bot/scraper hitting request endpoint** — Bounded by FR-08 per-number limits and NFR-SEC-08 per-IP limits. Global caps (system-wide requests/minute) are out of scope but the architect should note the extension point.
* **Long phone numbers or Unicode input** — Rejected by E.164 validator (FR-12).
* **Access token used after user logout** — Access token remains valid until its 15-minute expiry (documented trade-off of stateless JWT). Refresh token is blacklisted immediately.

## Non-Goals

- Frontend/Expo integration (a separate feature will consume these endpoints).
- Email-based authentication or email fallback.
- Social login (Google, Apple, Facebook).
- Password-based authentication or password-reset flows.
- Multi-factor authentication beyond the single OTP factor.
- Voice-call OTP delivery (SMS only in v1).
- WhatsApp OTP delivery.
- Silent/passive verification (SMS retriever, magic links).
- Account recovery flows for lost phone numbers.
- User profile fields beyond phone number and Django defaults (name, avatar, etc. handled by a later feature).
- Admin tooling for manually issuing OTPs or impersonating users.
- Device binding, device fingerprinting, or per-device token management.
- Suspicious-login notifications.
- SMS cost dashboards or Twilio billing controls (observability counters only).
- Session revocation across all devices from a single action (only per-refresh-token logout).

## Constraints

- Django 6.1 + DRF; add `djangorestframework-simplejwt` and `twilio` (and a phone-number library, e.g. `phonenumbers`) as dependencies.
- PostgreSQL is the only supported datastore.
- Backend app must be created via `python manage.py startapp <name>` (suggested app name: `accounts` or `auth_otp` — architect to finalize).
- All endpoints must live under `/api/auth/` to match the project's `/api/` prefix convention.
- Environment configuration must use `python-decouple` (`config(...)`) consistent with `backend/config/settings.py`.
- Custom `AUTH_USER_MODEL` must be introduced before other feature-specific migrations depend on the user table.
- `.env` must not be committed; `backend/.env.example` must be updated with new keys.

## Dependencies

| Name | Type | Required |
|------|------|----------|
| `djangorestframework-simplejwt` | Python package | true |
| `twilio` (Twilio Python SDK) | Python package | true |
| `phonenumbers` (or equivalent E.164 parser) | Python package | true |
| Twilio account with SMS-enabled number or Messaging Service | External service | true |
| PostgreSQL (already present) | Infrastructure | true |
| Redis or equivalent cache | Infrastructure | false (only if architect chooses cache-backed rate limiting; DB-backed is acceptable) |

## Assumptions

- The product supports international riders from day one; no whitelist of countries is required for v1 (see FR-13). If regulatory constraints later require it, a settings-driven allowlist can be added.
- Twilio is the sole SMS provider for v1; no provider abstraction layer is required beyond a thin internal service wrapper for testability.
- The Expo mobile app is the only first-party client; server-to-server tokens are not needed in this feature.
- Users authenticate one phone number to one account. Multiple accounts per number are disallowed.
- 6-digit numeric OTPs are acceptable (industry norm) despite lower entropy than alphanumeric; brute-force is mitigated by attempt caps (FR-09) and expiry (FR-07).
- The 15-minute access / 30-day refresh token lifetimes are a reasonable default; may be tuned in ops without a schema change.
- Rate-limit windows may be implemented via DB counters or a cache; the architect decides based on deployment topology.
- Development mode (`DEBUG=True`) may accept a fixed OTP to enable frontend/backend dev without SMS cost.
- The health endpoint at `/api/health/` should not be gated by auth; only new `/api/auth/*` and future protected endpoints require tokens.

## Open Questions

| ID | Question | Blocking |
|----|----------|---------|
| OQ-01 | Should the OTP length or expiry be configurable per environment via settings, or hardcoded per FR-06/FR-07? | false |
| OQ-02 | Is Redis available in the target deployment, or should rate limiting be DB-backed? Affects architecture and NFR-PERF-01. | false |
| OQ-03 | Should refresh-token rotation be enabled from day one (recommended) and, if so, is a token-blacklist table acceptable given operational overhead? | false |
| OQ-04 | Do we need a country allowlist for SMS destinations to bound Twilio spend and fraud (e.g. restrict to specific launch markets)? | true |
| OQ-05 | Should `is_new_user=true` responses trigger a downstream event (analytics, welcome hook)? If yes, which event bus? Otherwise deferred. | false |
| OQ-06 | Do we need admin-side impersonation or "sign in as user" tooling for support? Currently listed as non-goal; confirm. | false |
| OQ-07 | What is the intended production hosting environment (needed to confirm HTTPS termination and secret management approach for NFR-SEC-03, NFR-SEC-07)? | false |
| OQ-08 | Is a voice-call OTP fallback required for accessibility/regulatory reasons in any launch market? Currently listed as non-goal. | false |
| OQ-09 | What is the expected concurrent OTP-request load at launch? Confirms whether NFR-PERF-01's 20 rps target is right-sized. | false |
| OQ-10 | Should we capture the requesting IP address on OTP records for abuse analytics and retain it under our privacy posture? | false |

## Success Metrics

| Metric | Target |
|--------|--------|
| OTP verify success rate (successful verifies / OTP requests) | >= 75% |
| Median time from OTP request to successful verify | <= 60 seconds |
| Rate of `sms_dispatch_failed` responses | < 1% of otp/request calls |
| Auth endpoint p95 latencies | Meet NFR-PERF-01/02/03 |
| Auth-related security incidents in first 90 days | 0 |
| Zero occurrences of raw OTP or full phone number in production logs | 0 (audited quarterly) |
