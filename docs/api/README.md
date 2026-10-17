# Spot Rides API Documentation

This directory contains OpenAPI 3.0 specifications for the Spot Rides platform API.

## Available Specs

### [openapi-accounts.yaml](./openapi-accounts.yaml)
**Auth API** — OTP-based phone authentication and JWT token management

**Endpoints:**
- `POST /api/auth/otp/request/` — Send OTP via SMS
- `POST /api/auth/otp/verify/` — Verify OTP and receive JWT tokens
- `POST /api/auth/token/refresh/` — Refresh JWT access token
- `POST /api/auth/logout/` — Blacklist refresh token
- `GET /api/auth/me/` — Get current user profile
- `GET /api/health/` — Health check

### [openapi-profiles.yaml](./openapi-profiles.yaml)
**Onboarding API** — User onboarding flow, role selection, DL verification, and vehicle registration

**Endpoints:**
- `GET /api/onboarding/status/` — Get onboarding status and next step
- `POST /api/onboarding/role/` — Select role (driver or passenger)
- `POST /api/onboarding/profile/` — Submit personal details
- `POST /api/onboarding/driver/dl/` — Submit driving licence for verification
- `GET /api/onboarding/driver/dl/status/` — Poll DL verification status
- `POST /api/onboarding/driver/dl/webhook/` — DL verification webhook callback
- `POST /api/onboarding/driver/vehicle/` — Register vehicle (registration number + type)
- `GET /api/onboarding/driver/vehicle/status/` — Poll vehicle RC verification status
- `POST /api/onboarding/driver/vehicle/rc/webhook/` — RC verification webhook (HMAC signature; `404` while the flag is off)
- `PATCH /api/profile/role/` — Switch active role

## Viewing the Specs

### Online Viewers
- **Swagger UI**: https://editor.swagger.io/ (paste the YAML content)
- **Redoc**: https://redocly.github.io/redoc/ (paste the YAML URL)

### Local Viewing

Install and run Swagger UI locally:
```bash
npm install -g swagger-ui-watcher
swagger-ui-watcher docs/api/openapi-accounts.yaml
swagger-ui-watcher docs/api/openapi-profiles.yaml
```

Or use Docker:
```bash
docker run -p 8080:8080 -e SWAGGER_JSON=/api/openapi-accounts.yaml -v $(pwd)/docs/api:/api swaggerapi/swagger-ui
```

## Response Envelope

All API responses use a unified JSON envelope:

```json
{
  "success": true | false,
  "message": "Human-readable summary",
  "data": { /* endpoint-specific payload */ } | null,
  "error": {
    "code": "machine_readable_code",
    "detail": "Human-readable detail",
    "fields": { /* per-field validation errors */ } | null,
    "retry_after": 30 | null
  } | null,
  "meta": {
    "request_id": "uuid",
    "timestamp": "2026-09-23T10:00:00Z"
  }
}
```

**Success responses**: `success: true`, `error: null`  
**Error responses**: `success: false`, `data: null`, `error: { ... }`

## Authentication

Most endpoints require JWT authentication via the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Obtain tokens via `POST /api/auth/otp/verify/`.

## Environments

| Environment | Base URL |
|-------------|----------|
| Local development | http://localhost:8000 |
| Production | https://api.spotrides.com |

## Feature Flag: Onboarding Gate

The onboarding gate requires `onboarding_status = COMPLETE` for all protected endpoints.

**Status**: Controlled by `ONBOARDING_GATE_ENABLED` environment variable (default: `false`)

When disabled, users can access protected endpoints without completing onboarding (useful during development/migration).

## Feature Flag: Vehicle RC Verification

**Status**: `RC_VERIFICATION_ENABLED` (default: `false`). Only a mock adapter exists; no real provider.

- **Off**: `POST /api/onboarding/driver/vehicle/` creates the vehicle and returns `200`, `onboarding_status = complete`, `next_step = none`. The additive response fields `rc_verification_status`, `rejection_reason` and `reference_id` are `null`.
- **On**: `200` complete, `202` `pending_rc_verification` (`next_step = awaiting_rc_verification`), `422 rc_verification_rejected`, `422 rc_verification_provider_error`, `429 max_rc_attempts_exceeded`, `409 rc_verification_pending` / `rc_already_verified`.
- `422 rc_verification_rejected` carries `onboarding_status`, `next_step`, `rc_verification_status` and `rc_attempts_remaining` as extra keys inside `error`. The `error` object may now carry additional flat keys (`code`, `detail`, `fields`, `retry_after` stay reserved); `403 onboarding_incomplete` carries `onboarding_status` and `next_step` when the gate is enabled.
- `PATCH /api/profile/role/` always returns `next_step`, and behaves the same with the flag on or off (except that `pending_rc_verification` is derived only with the flag on). Switching to `driver` without a verified DL (no record, or rejected) starts driver setup: `200`, `onboarding_status = awaiting_dl`, `next_step = dl_submission`; it no longer returns `400 dl_required`. A pending DL gives `202` / `pending_verification`; a verified DL gives `complete` only with an active vehicle (or a grandfathered driver), otherwise `awaiting_vehicle` / `vehicle_registration`. Switching to `passenger` is allowed from `complete`, `awaiting_dl`, `pending_verification`, `awaiting_vehicle` and `pending_rc_verification`, returns `complete` and keeps the DL and vehicle records. While the onboarding gate is enabled, a passenger who starts driver setup is gated (`403 onboarding_incomplete`) until they finish or switch back.
- Webhook signature: hex `HMAC-SHA256(RC_WEBHOOK_SECRET, raw body)` in the `X-RC-Signature` header (optional `sha256=` prefix).

Error codes corrected on the vehicle endpoint (flag on or off): invalid `registration_number` -> `400 invalid_registration_format`; invalid `vehicle_type` -> `400 invalid_vehicle_type`; passenger -> `403 not_a_driver`; `complete` driver -> `409 vehicle_already_registered`.
## Related Documentation

- **Requirements**: `../requirements/FEAT-001-otp-phone-authentication.md`, `../requirements/FEAT-002-user-onboarding.md`
- **Architecture**: `../architecture/ARCH-001-otp-phone-authentication.md`, `../architecture/ARCH-002-user-onboarding.md`
- **Decisions**: `../decisions/2026-09-15-unified-api-response-envelope.md`

## Changelog

| Date | Spec | Change |
|------|------|--------|
| 2026-09-15 | accounts | Initial OTP authentication endpoints |
| 2026-09-28 | accounts | Added `onboarding_status` and `active_role` to User schema |
| 2026-09-28 | profiles | Initial onboarding flow endpoints (FEAT-002) |
| 2026-10-10 | profiles | Added vehicle registration endpoint, `AWAITING_VEHICLE` state, DigiLocker as DL provider |
| 2026-10-15 | profiles | Flag-gated vehicle RC verification (`pending_rc_verification`, status and webhook endpoints, additive response fields); vehicle endpoint error-code fixes; envelope `error` accepts extra keys |
| 2026-10-17 | profiles | Role switch: driver without a verified DL starts driver setup (`awaiting_dl`, `next_step = dl_submission`) instead of `400 dl_required`; passenger exit from every non-initial status; `next_step` always returned |
