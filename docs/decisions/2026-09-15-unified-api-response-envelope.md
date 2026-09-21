# DEC-011 — Unified API response envelope

**Date:** 2026-09-15
**Status:** approved
**Supersedes:** ARCH-001 §API Contracts error envelope
**Applies to:** every endpoint under `/api/` in this project

## Context

ARCH-001 defined an error envelope (`{error, detail, retry_after}`) for the
`accounts` endpoints only, and success payloads were returned bare and shaped
per endpoint. That means the Expo client needs a different unwrapping rule for
every call, and each new backend app is free to invent its own error shape.

## Decision

All `/api/` responses share one envelope:

```json
{
  "success": true,
  "message": "OTP sent successfully.",
  "data": {},
  "error": null,
  "meta": { "request_id": "…", "timestamp": "…", "pagination": {} }
}
```

On failure `success` is `false`, `data` is `null`, and `error` carries
`{code, detail, fields, retry_after}`. `204`/`205` responses stay bodyless.

The envelope is applied centrally, not at call sites:

| Concern | Owner |
|---------|-------|
| Wrapping success payloads, attaching `meta` | `core.renderers.EnvelopeJSONRenderer` (`DEFAULT_RENDERER_CLASSES`) |
| Wrapping every error | `core.exceptions.envelope_exception_handler` (`EXCEPTION_HANDLER`) |
| `meta.pagination` | `core.pagination.EnvelopePageNumberPagination` (`DEFAULT_PAGINATION_CLASS`) |
| Optional `message` on success | `core.response.ApiResponse` |

Views keep returning their bare payload. Feature apps declare errors by
subclassing `core.exceptions.ApiError` with a `status_code`, `error_code` and
`default_detail`; `accounts.exceptions.AuthDomainError` now does exactly this,
and the per-code taxonomy from ARCH-001 is unchanged.

`core` is a plain package under `backend/` rather than an installed app — it
has no models, and nothing in it may import a feature app.

## Consequences

- Error codes from ARCH-001 are preserved but moved from the top-level `error`
  key to `error.code`, so `docs/api/openapi-accounts.yaml` was updated and any
  existing client parsing the flat shape must be migrated. No frontend consumes
  these endpoints yet, so this is a free rename.
- Validation failures now expose per-field messages under `error.fields`
  instead of collapsing to a single `detail` string.
- Every response carries `meta.request_id`, matching the `X-Request-ID` header
  set by `accounts.middleware.RequestIDMiddleware`, so a client bug report maps
  straight onto a log line.
- Django-level responses that never reach DRF (admin, URLconf 404s, static)
  are not enveloped. Acceptable: they are not `/api/` JSON contracts.

## Alternatives considered

- **Per-view wrapper helpers** — rejected; the envelope would be optional in
  practice and would drift the moment someone returns a plain `Response`.
- **Middleware that rewrites the response body** — rejected; it would have to
  re-parse already-rendered JSON and would also catch non-API responses.
- **Keeping the ARCH-001 flat shape and only standardising errors** — rejected;
  the client still needs per-endpoint unwrapping for success payloads, which is
  the larger half of the problem.
