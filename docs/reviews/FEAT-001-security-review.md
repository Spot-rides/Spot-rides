# Security Review: OTP Phone Authentication (FEAT-001)

**ID:** SEC-001
**Type:** security-review
**Feature:** FEAT-001
**Reviewer:** security-reviewer
**Status:** changes_requested

---

## Assets

- User account identity (phone number as primary identifier)
- OTP codes (short-lived authentication credentials)
- JWT access tokens (15-minute bearer credentials)
- JWT refresh tokens (30-day session credentials)
- User PII: phone numbers stored in DB, JWT claims, and logs

## Actors

- Anonymous public caller (OTP request/verify endpoints, no prior auth)
- Authenticated user (logout, /me/ endpoints)
- Attacker with valid access token (authenticated but potentially malicious)
- Attacker with access to stdout/log aggregation infrastructure
- Twilio (external SMS provider, outbound only)

## Trust Boundaries

- Internet -> Django API (TLS terminated at ALB; REMOTE_ADDR is set by load balancer)
- Django API -> PostgreSQL (credentials in env, ORM parameterised queries)
- Django API -> Redis (rate-limit counters; no auth required by default)
- Django API -> Twilio (outbound only, credentials in env)
- JWT token -> API (verified via HS256 signature; phone number claim is plaintext)

## Attack Surfaces

- POST /api/auth/otp/request/ — unauthenticated, accepts arbitrary phone strings
- POST /api/auth/otp/verify/ — unauthenticated, accepts phone + 6-digit code
- POST /api/auth/logout/ — authenticated, accepts arbitrary refresh token string in body
- GET /api/auth/me/ — authenticated read-only
- stdout / container log aggregation pipeline (receives print() output)

## Threats

| ID | Threat | Mitigation | Residual Risk |
|----|--------|-----------|--------------|
| T-01 | OTP code leaked via stdout in dev mode, captured by log aggregation | Remove print() call; use logging framework only | High until fixed |
| T-02 | Authenticated user logs out another user by blacklisting their refresh token | Add ownership check: token user_id must match request.user.id | Medium until fixed |
| T-03 | Phone number PII decoded from JWT Bearer token in infrastructure logs | Do not embed phone_number in JWT; use opaque user_id claim only | Medium until fixed |
| T-04 | Dev mode default OTP bypass code (000000) usable on externally reachable staging servers | Require explicit OTP_DEV_FIXED_CODE; remove default value | Medium — gated by DEBUG=True |
| T-05 | OTP brute force via distributed IPs | Per-phone attempt cap (5), per-IP verify limit (20/10m) | Low — OTP space is 10^6, each OTP capped at 5 attempts |

## OWASP Top 10 Checklist

- [x] A01 Broken Access Control — F-02: logout allows cross-user token blacklisting
- [x] A02 Cryptographic Failures — F-03: PII in JWT payload (signing, not encryption)
- [ ] A03 Injection — no findings; ORM used throughout, phone normalised via phonenumbers lib
- [ ] A04 Insecure Design — F-04: predictable default dev bypass code
- [ ] A05 Security Misconfiguration — CORS_ALLOW_ALL_ORIGINS=True present but tagged dev only
- [ ] A06 Vulnerable Components — out of scope per reviewer exclusions
- [ ] A07 Auth Failures — no auth bypass in prod path found; dev mode guard verified
- [ ] A08 Software/Data Integrity Failures — no findings
- [x] A09 Logging Failures — F-01: raw OTP written to stdout bypassing redaction filters
- [ ] A10 SSRF — no outbound URL construction from user input

## Findings

| ID | Severity | Title | Location | Description | Recommendation | Blocking |
|----|----------|-------|----------|-------------|---------------|---------|
| F-01 | high | Raw OTP code and phone number printed to stdout, bypassing all PII redaction | backend/accounts/services/twilio_client.py:86 | `print("OTP Dev Mode: ", phone_e164, code)` emits the raw 6-digit OTP and full E.164 phone number to stdout. Python's `PhoneRedactionFilter` only intercepts calls through the `logging` framework; `print()` is invisible to it. stdout is captured verbatim by Docker json-file and awslogs drivers, systemd journal, Heroku logplex, and any log shipping agent. This contradicts the explicit design note in the same file: "The raw code MUST NOT be logged." | Replace with `logger.info('otp_dev_dispatch_skipped', extra={'phone_number': phone_e164})` — the existing redaction filter will mask the phone. Never pass the code to any output function. | true |
| F-02 | medium | Logout endpoint blacklists any refresh token without verifying ownership | backend/accounts/views.py:199-210 | `LogoutView.post()` calls `RefreshToken(refresh).blacklist()` using a token value taken directly from the request body, after verifying only that the caller holds a valid access token. There is no check that the refresh token's embedded `user_id` claim matches `request.user.id`. An attacker who has obtained any victim's refresh token (e.g., from a shared device, a phishing page, or an API response cached elsewhere) can silently log that victim out without their knowledge. | Before blacklisting, decode the token, assert `token['user_id'] == request.user.id`, and raise `InvalidRefresh` on mismatch. | false |
| F-03 | medium | Phone number PII embedded in plaintext JWT claims (access + refresh) | backend/accounts/views.py:157-159 | `refresh['phone_number'] = user.phone_number` and `access['phone_number'] = user.phone_number` place the full E.164 phone number inside the JWT payload. HS256 is a signing scheme; the payload is only base64url-encoded and is trivially readable by any party. Access tokens are transmitted as Authorization: Bearer headers on every authenticated request. Infrastructure components — nginx/ALB access logs, Sentry/Datadog request capture, mobile analytics SDKs — commonly log or transmit these headers, exposing phone numbers at rest in systems outside the application's control. | Remove the `phone_number` claim from tokens. The `user_id` claim is already present and is sufficient for downstream service identification. If a service needs the phone number, fetch it from the DB using `user_id`. | false |
| F-04 | medium | Default OTP dev-mode bypass code is the predictable value `000000` | backend/config/settings.py:161 | `OTP_DEV_FIXED_CODE = config('OTP_DEV_FIXED_CODE', default='000000')`. When `OTP_DEV_MODE=True` and `DEBUG=True`, `otp.dev_mode_accepts()` accepts the fixed code as a valid OTP for any phone number that has an active OTP row. If a staging or CI environment is reachable from outside the organisation and has these flags set without explicitly overriding `OTP_DEV_FIXED_CODE`, `000000` authenticates as any user. | Remove the `default='000000'` argument; substitute `default=''`. The existing `if not fixed: return False` guard in `dev_mode_accepts()` will then disable the bypass unless a value is explicitly set. Document in the .env.example that a non-trivial random value must be chosen. | false |

## Residual Risk

- IP-based rate limiting on the verify endpoint uses `REMOTE_ADDR` only. Behind an ALB, all verify attempts share the load balancer's IP. The per-phone DB attempt counter (max 5) provides the binding control; IP limiting is effectively decorative in the described deployment topology. This should be addressed in a follow-up by introducing `django-ipware` or trusting `X-Forwarded-For` from a known proxy CIDR.
- `CORS_ALLOW_ALL_ORIGINS = True` is present in settings.py without a `DEBUG` guard. If this file is deployed to production without the guard, any origin can make credentialed cross-origin requests. This setting must be gated or replaced with an explicit `CORS_ALLOWED_ORIGINS` list before production deployment.
- JWT access tokens (15-minute lifetime) cannot be revoked after logout; only the refresh token is blacklisted. This is a known SimpleJWT limitation and is accepted by design, but means a stolen access token remains valid for up to 15 minutes post-logout.
