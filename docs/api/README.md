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
**Onboarding API** — User onboarding flow, role selection, and DL verification

**Endpoints:**
- `GET /api/onboarding/status/` — Get onboarding status and next step
- `POST /api/onboarding/role/` — Select role (driver or passenger)
- `POST /api/onboarding/profile/` — Submit personal details
- `POST /api/onboarding/driver/dl/` — Submit driving licence for verification
- `GET /api/onboarding/driver/dl/status/` — Poll DL verification status
- `POST /api/onboarding/driver/dl/webhook/` — DL verification webhook callback
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
