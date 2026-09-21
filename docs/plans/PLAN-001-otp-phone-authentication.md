# Plan: OTP-Based Phone Authentication (Backend)

**ID:** PLAN-001
**Type:** plan
**Feature:** FEAT-001
**Architecture:** ARCH-001
**Version:** 1
**Status:** ready
**Date:** 2026-09-12

---

## Assumed Defaults (user-authorised)

1. **`purge_expired_otps` scheduler** — delivered as a Django management command only. Wiring it into cron / EventBridge / Celery-beat is an **ops handoff**, not code in this feature.
2. **Logging + `X-Request-ID` middleware** — minimal, self-contained JSON formatter and middleware scoped to the `accounts` app's needs. A broader observability feature can supersede later.
3. **Managed Redis (ElastiCache)** — treated as an **ops precondition**. This plan wires configuration only; infra provisioning is out of scope.

## Prerequisites (ops, not blockers for code)

- Redis reachable at `REDIS_URL` (dev: local; prod: ElastiCache multi-AZ).
- Twilio account with SMS-enabled sender (or Messaging Service SID) and DLT registration for Indian carriers.
- HTTPS termination at ALB, `X-Forwarded-Proto` forwarded to Django.
- Secrets available via env (`JWT_SIGNING_KEY`, `OTP_PEPPER`, Twilio creds) — AWS Secrets Manager -> task env.

---

## Task Table

| ID | Title | Owner | Depends On | Satisfies | Size | Risk | Status |
|----|-------|-------|-----------|-----------|------|------|--------|
| TASK-001 | Add Python dependencies (SimpleJWT, twilio, phonenumbers, django-redis, redis) | backend-engineer | — | ARCH-Deps | S | low | complete |
| TASK-002 | Extend `backend/.env.example` with new keys | backend-engineer | — | FR-14, NFR-SEC-03, COMP-011 | S | low | complete |
| TASK-003 | Scaffold `accounts` Django app | backend-engineer | TASK-001 | COMP-001 | S | low | complete |
| TASK-004 | Wire `settings.py`: INSTALLED_APPS, AUTH_USER_MODEL, DRF defaults, SIMPLE_JWT, CACHES, env reads | backend-engineer | TASK-001, TASK-002, TASK-003 | FR-14, FR-17, NFR-SEC-06, COMP-011 | M | medium | complete |
| TASK-005 | Custom `User` model + `PhoneUserManager` | backend-engineer | TASK-003, TASK-004 | FR-11, COMP-002 | M | medium | complete |
| TASK-006 | `OtpCode` model with indexes | backend-engineer | TASK-003, TASK-004 | FR-06, FR-07, FR-09, FR-10, NFR-SEC-01, COMP-003 | M | medium | complete |
| TASK-007 | Generate initial migrations (`accounts` + `token_blacklist`) | backend-engineer | TASK-005, TASK-006 | ARCH-Migration | S | medium | complete |
| TASK-008 | Django admin registrations (User staff-only, OtpCode read-only) | backend-engineer | TASK-005, TASK-006 | NFR-PRIV-01 | S | low | complete |
| TASK-009 | `services/phone.py` — E.164 normalization + country allowlist | backend-engineer | TASK-004 | FR-12, FR-13, AC-14, COMP-007 | S | low | complete |
| TASK-010 | `services/otp.py` — generate, HMAC-hash, constant-time verify, dev-mode | backend-engineer | TASK-006 | FR-06, FR-07, FR-09, FR-10, FR-18, NFR-SEC-01, NFR-SEC-02, COMP-004 | M | medium | complete |
| TASK-011 | `services/twilio_client.py` — sync wrapper, timeouts, error mapping, dev-mode | backend-engineer | TASK-004 | FR-14, FR-15, FR-18, NFR-OBS-03, COMP-005 | M | high | complete |
| TASK-012 | `services/rate_limit.py` — Redis limiter with Lua INCR+EXPIRE, composed windows | backend-engineer | TASK-004 | FR-08, NFR-SEC-08, COMP-006 | M | high | complete |
| TASK-013 | `logging.py` — JSON formatter + phone-mask/hash filter + PII redaction | backend-engineer | TASK-004 | FR-16, NFR-SEC-04, NFR-OBS-01 | S | medium | complete |
| TASK-014 | `X-Request-ID` middleware | backend-engineer | TASK-004 | NFR-OBS-01 | S | low | complete |
| TASK-015 | `exceptions.py` — domain exceptions + DRF exception handler (error envelope) | backend-engineer | TASK-004 | ARCH-Error-Envelope | S | low | complete |
| TASK-016 | `serializers.py` — Otp request/verify/logout/user serializers | backend-engineer | TASK-009 | FR-01, FR-02, FR-12, FR-13 | S | low | complete |
| TASK-017 | `OtpRequestView` — validate, rate-limit, atomic OTP+dispatch, compensate on failure | backend-engineer | TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016 | FR-01, FR-08, FR-10, FR-13, FR-15, NFR-SEC-05, COMP-008 | L | high | complete |
| TASK-018 | `OtpVerifyView` — verify, mint JWT, upsert user, consume-once semantics | backend-engineer | TASK-010, TASK-012, TASK-015, TASK-016 | FR-02, FR-09, FR-11, FR-17, COMP-008 | L | high | complete |
| TASK-019 | `LogoutView` — blacklist refresh token | backend-engineer | TASK-004, TASK-015 | FR-04, COMP-008 | S | low | complete |
| TASK-020 | `MeView` — authenticated profile echo | backend-engineer | TASK-005, TASK-015 | FR-05, COMP-008 | S | low | complete |
| TASK-021 | Wire `accounts/urls.py` and include under `/api/auth/` in `config/urls.py` | backend-engineer | TASK-017, TASK-018, TASK-019, TASK-020 | FR-03, COMP-009, COMP-012 | S | low | complete |
| TASK-022 | System check for Twilio + Redis creds → `503 auth_unavailable` | backend-engineer | TASK-011, TASK-012 | AC-15 | S | medium | pending |
| TASK-023 | `purge_expired_otps` management command | backend-engineer | TASK-006, TASK-007 | NFR-PRIV-02, COMP-013 | S | low | pending |
| TASK-024 | Unit tests: `services/phone.py` normalization + allowlist | test-engineer | TASK-009 | AC-14, FR-12, FR-13 | S | low | pending |
| TASK-025 | Unit tests: `services/otp.py` hashing / verify / dev-mode | test-engineer | TASK-010 | FR-06, FR-07, FR-09, NFR-SEC-01, NFR-SEC-02, AC-13 | M | medium | pending |
| TASK-026 | Unit tests: `services/twilio_client.py` (mocked SDK, dev-mode, prod guard) | test-engineer | TASK-011 | FR-14, FR-15, FR-18, AC-11 | S | low | pending |
| TASK-027 | Unit tests: `services/rate_limit.py` (fakeredis; composed windows, decrement) | test-engineer | TASK-012 | FR-08, NFR-SEC-08, AC-07 | M | medium | pending |
| TASK-028 | Integration tests: `/otp/request/` happy path + rate-limit + Twilio failure | test-engineer | TASK-021, TASK-022 | AC-01, AC-02, AC-07, AC-11, AC-15 | M | medium | pending |
| TASK-029 | Integration tests: `/otp/verify/` happy + edge cases (new/returning, expiry, attempts, dev-mode) | test-engineer | TASK-021 | AC-03, AC-04, AC-05, AC-06, AC-13 | M | medium | pending |
| TASK-030 | Integration tests: `/token/refresh/` rotation + reuse rejection | test-engineer | TASK-021 | AC-08, FR-03, FR-17 | S | low | pending |
| TASK-031 | Integration tests: `/logout/` blacklist + `/me/` auth gating | test-engineer | TASK-021 | AC-09, AC-10, FR-04, FR-05 | S | low | pending |
| TASK-032 | Log-content tests: no raw OTP / no full phone in logs (caplog regex) | test-engineer | TASK-021 | AC-12, NFR-SEC-04, FR-16 | S | low | pending |
| TASK-033 | Migration smoke test (`migrate` from zero, then `migrate accounts zero` rollback) | test-engineer | TASK-007 | ARCH-Migration | S | low | pending |
| TASK-034 | README + ops runbook: env var reference, ElastiCache precondition, purge scheduler handoff | backend-engineer | TASK-002, TASK-023 | Ops-Handoff | S | low | pending |

---

## Task Details

### TASK-001 — Add Python dependencies

- **Owner:** backend-engineer
- **Goal:** Add all runtime packages required by ARCH-001 to `backend/requirements.txt` at pinned versions.
- **Rationale:** All subsequent code paths depend on SimpleJWT, twilio, phonenumbers, django-redis, redis.
- **Dependencies:** none
- **Affected Files:** `backend/requirements.txt`
- **Implementation Notes:** Pins per ARCH §Dependencies: `djangorestframework-simplejwt==5.3.1`, `twilio==9.3.0`, `phonenumbers==8.13.50`, `django-redis==5.4.0`, `redis==5.0.8`.
- **Acceptance Criteria:**
  - [ ] `pip install -r backend/requirements.txt` succeeds in a clean venv
  - [ ] All five packages appear pinned
- **Tests Required:**
  - [ ] Manual install verification (no test task)
- **Risk:** low
- **Status:** complete

---

### TASK-002 — Extend `backend/.env.example`

- **Owner:** backend-engineer
- **Goal:** Document every new env key needed by the feature.
- **Rationale:** FR-14 / NFR-SEC-03 require `python-decouple` config discoverability without leaking secrets.
- **Dependencies:** none
- **Affected Files:** `backend/.env.example`
- **Implementation Notes:** Keys per ARCH §Settings Changes: `JWT_SIGNING_KEY`, `OTP_PEPPER`, `OTP_DEV_MODE`, `OTP_DEV_FIXED_CODE`, `OTP_COUNTRY_ALLOWLIST`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `TWILIO_MESSAGING_SERVICE_SID`, `REDIS_URL`. Use placeholders only.
- **Acceptance Criteria:**
  - [ ] All 10 keys present with placeholder values
  - [ ] No real secrets committed
- **Tests Required:**
  - [ ] Grep check for placeholder markers
- **Risk:** low
- **Status:** complete

---

### TASK-003 — Scaffold `accounts` Django app

- **Owner:** backend-engineer
- **Goal:** Create the app skeleton via `python manage.py startapp accounts` inside `backend/`.
- **Rationale:** All feature code lives here (COMP-001).
- **Dependencies:** TASK-001
- **Affected Files:** `backend/accounts/*` (generated)
- **Implementation Notes:** Add subpackage `services/` with `__init__.py`. Add `management/commands/` skeleton.
- **Acceptance Criteria:**
  - [ ] `backend/accounts/apps.py` present with `AccountsConfig`
  - [ ] `services/` and `management/commands/` directories exist
- **Tests Required:** none
- **Risk:** low
- **Status:** complete

---

### TASK-004 — Wire `settings.py`

- **Owner:** backend-engineer
- **Goal:** Add INSTALLED_APPS entries, `AUTH_USER_MODEL`, DRF defaults, `SIMPLE_JWT`, `CACHES` (Redis), env reads, prod hardening block.
- **Rationale:** COMP-011; unlocks all downstream work. Must happen BEFORE first migration (ARCH §Migration).
- **Dependencies:** TASK-001, TASK-002, TASK-003
- **Affected Files:** `backend/config/settings.py`
- **Implementation Notes:** Copy the ARCH §Settings Changes block verbatim. Add `rest_framework_simplejwt`, `rest_framework_simplejwt.token_blacklist`, `accounts` to INSTALLED_APPS. Set global DRF default permission to `IsAuthenticated` (per-view AllowAny where public). Add `MIDDLEWARE` entry for the request-id middleware placeholder (implemented in TASK-014). Register logging config with the JSON formatter placeholder (implemented in TASK-013). Register `accounts.exceptions.auth_exception_handler` as `EXCEPTION_HANDLER` (implemented in TASK-015).
- **Acceptance Criteria:**
  - [ ] `python manage.py check` passes
  - [ ] Missing `JWT_SIGNING_KEY` / `OTP_PEPPER` fails fast at import time in prod
  - [ ] Existing `/api/health/` still reachable without auth
- **Tests Required:**
  - [ ] `manage.py check`
- **Risk:** medium
- **Status:** complete

---

### TASK-005 — Custom `User` model + manager

- **Owner:** backend-engineer
- **Goal:** Implement `accounts.models.User` (AbstractBaseUser + PermissionsMixin) and `PhoneUserManager`.
- **Rationale:** COMP-002; FR-11 identity semantics.
- **Dependencies:** TASK-003, TASK-004
- **Affected Files:** `backend/accounts/models.py`, `backend/accounts/managers.py`
- **Implementation Notes:** `USERNAME_FIELD = "phone_number"`, `REQUIRED_FIELDS = []`, unique/indexed phone_number VARCHAR(16), `set_unusable_password()` in `create_user`; superuser retains password. Standard `is_staff` / `is_superuser` / `is_active` / `date_joined` / `last_login`.
- **Acceptance Criteria:**
  - [ ] `User.objects.create_user("+919812345678")` succeeds without a password
  - [ ] `create_superuser` requires password
  - [ ] Phone uniqueness enforced at DB level
- **Tests Required:**
  - [ ] Covered by TASK-029 integration path
- **Risk:** medium
- **Status:** complete

---

### TASK-006 — `OtpCode` model

- **Owner:** backend-engineer
- **Goal:** Persistent hashed-OTP table per ARCH data model.
- **Rationale:** COMP-003; FR-06/07/09/10 lifecycle, NFR-SEC-01 hashed storage.
- **Dependencies:** TASK-003, TASK-004
- **Affected Files:** `backend/accounts/models.py`
- **Implementation Notes:** Columns: `phone_number` (indexed), `code_hash` (VARCHAR 64), `created_at`, `expires_at`, `consumed_at nullable`, `attempts SMALLINT default 0`, `invalidated BOOLEAN default False`, `request_ip INET null`, `request_id VARCHAR(40)`. Composite index `(phone_number, invalidated, consumed_at)`; single index on `expires_at`.
- **Acceptance Criteria:**
  - [ ] Fields exactly match ARCH §Data Model
  - [ ] No plaintext `code` column exists
- **Tests Required:**
  - [ ] Covered by TASK-025, TASK-029
- **Risk:** medium
- **Status:** complete

---

### TASK-007 — Initial migrations

- **Owner:** backend-engineer
- **Goal:** Produce `accounts/migrations/0001_initial.py` and run `token_blacklist` migrations end-to-end.
- **Rationale:** ARCH §Migration order; must run before any other feature depends on user.
- **Dependencies:** TASK-005, TASK-006
- **Affected Files:** `backend/accounts/migrations/0001_initial.py`
- **Implementation Notes:** `python manage.py makemigrations accounts` then `migrate`. Verify token_blacklist tables created.
- **Acceptance Criteria:**
  - [ ] `migrate` from empty DB succeeds
  - [ ] `migrate accounts zero` and `migrate token_blacklist zero` cleanly reverse
- **Tests Required:**
  - [ ] TASK-033 exercises rollback
- **Risk:** medium
- **Status:** complete

---

### TASK-008 — Django admin registrations

- **Owner:** backend-engineer
- **Goal:** Minimal admin: `UserAdmin` (staff-only, list phone), `OtpCodeAdmin` read-only (no create/edit; hash visible, never raw code — raw is never stored).
- **Rationale:** NFR-PRIV-01 staff-restricted PII access.
- **Dependencies:** TASK-005, TASK-006
- **Affected Files:** `backend/accounts/admin.py`
- **Acceptance Criteria:**
  - [ ] `OtpCode` admin `has_add_permission` / `has_change_permission` return False
  - [ ] User list restricted to staff
- **Tests Required:** none (visual)
- **Risk:** low
- **Status:** complete

---

### TASK-009 — `services/phone.py`

- **Owner:** backend-engineer
- **Goal:** `normalize_to_e164(raw, default_region="IN") -> str` and `country_allowed(e164) -> bool` using `phonenumbers`.
- **Rationale:** COMP-007; FR-12, FR-13, AC-14; enforces `OTP_COUNTRY_ALLOWLIST`.
- **Dependencies:** TASK-004
- **Affected Files:** `backend/accounts/services/phone.py`
- **Implementation Notes:** Use `phonenumbers.parse`, `is_valid_number`, `format_number(..., E164)`, `region_code_for_number`. Empty allowlist == no restriction (log warning in prod).
- **Acceptance Criteria:**
  - [ ] `"(415) 555-2671"` with US region → `+14155552671`
  - [ ] `"+919812345678"` unchanged
  - [ ] Non-E.164 garbage raises domain error
- **Tests Required:** TASK-024
- **Risk:** low
- **Status:** complete

---

### TASK-010 — `services/otp.py`

- **Owner:** backend-engineer
- **Goal:** Generate + hash + verify OTP with attempt tracking + dev-mode short-circuit.
- **Rationale:** COMP-004; FR-06/07/09/10, NFR-SEC-01/02, FR-18.
- **Dependencies:** TASK-006
- **Affected Files:** `backend/accounts/services/otp.py`
- **Implementation Notes:** `generate() -> str` via `secrets.randbelow(10**6)` zero-padded. `hash_code(code)` via `hmac.new(pepper, code.encode(), sha256).hexdigest()`. `verify(phone, submitted)` loads latest active OTP with `select_for_update`, compares via `hmac.compare_digest`, increments attempts, marks invalidated at ≥5, marks consumed_at on success. `dev_mode_accepts(code)` returns True only when `DEBUG=True AND OTP_DEV_MODE=True AND code == OTP_DEV_FIXED_CODE`; raises `RuntimeError` if `OTP_DEV_MODE` while `DEBUG=False`. Never logs the raw code.
- **Acceptance Criteria:**
  - [ ] Constant-time verify path
  - [ ] Attempts increment; 5th failure invalidates
  - [ ] Expired OTP returns distinct error, not consumed
  - [ ] Supersede prior active on new request in same transaction
- **Tests Required:** TASK-025
- **Risk:** medium
- **Status:** complete

---

### TASK-011 — `services/twilio_client.py`

- **Owner:** backend-engineer
- **Goal:** `send_otp_sms(phone_e164, code)` synchronous wrapper.
- **Rationale:** COMP-005; FR-14/15/18, NFR-OBS-03.
- **Dependencies:** TASK-004
- **Affected Files:** `backend/accounts/services/twilio_client.py`
- **Implementation Notes:** Construct `Client(sid, token, http_client=TwilioHttpClient(timeout=5))`. Prefer `TWILIO_MESSAGING_SERVICE_SID` if set. Raise `SmsDispatchError` on any Twilio exception; log Twilio error_code but never return it. Dev-mode: no-op + log `otp_dev_dispatch_skipped`. Prod guard: raise `RuntimeError` if `OTP_DEV_MODE` and `DEBUG=False`.
- **Acceptance Criteria:**
  - [ ] Twilio client constructed lazily (module import must not fail if creds unset in dev)
  - [ ] SDK exceptions surface as `SmsDispatchError`
  - [ ] Message body: `"Your Spot Rides code is {code}. It expires in 5 minutes."`
- **Tests Required:** TASK-026
- **Risk:** high
- **Status:** complete

---

### TASK-012 — `services/rate_limit.py`

- **Owner:** backend-engineer
- **Goal:** Redis limiter with composed windows and compensating decrement.
- **Rationale:** COMP-006; FR-08, NFR-SEC-08.
- **Dependencies:** TASK-004
- **Affected Files:** `backend/accounts/services/rate_limit.py`
- **Implementation Notes:** Use `django_redis.get_redis_connection("default")`. Atomic Lua: `INCR key; EXPIRE key ttl NX`. Key schema per ARCH §Rate Limiting (phones hashed via SHA-256). Public methods: `check_otp_request(phone_hash, ip) -> (ok, retry_after)`, `check_otp_verify(phone_hash, ip) -> (ok, retry_after)`, `record_success_cooldown(phone_hash)` sets 30 s key, `compensate_request(phone_hash)` DECRs 30s/1h/24h buckets and deletes cooldown key. If Redis unreachable → raise `AuthUnavailable` (fail-closed).
- **Acceptance Criteria:**
  - [ ] Lua script single round-trip
  - [ ] Correct TTLs (30, 3600, 86400, 600 for verify-ip)
  - [ ] Compensation is idempotent
- **Tests Required:** TASK-027
- **Risk:** high
- **Status:** complete

---

### TASK-013 — Logging (JSON formatter + PII redaction filter)

- **Owner:** backend-engineer
- **Goal:** Minimal JSON stdout formatter; `PhoneRedactionFilter` masks phone numbers and strips OTP-like tokens.
- **Rationale:** FR-16, NFR-SEC-04, NFR-OBS-01. Kept minimal per user default #2.
- **Dependencies:** TASK-004
- **Affected Files:** `backend/accounts/logging.py`; `LOGGING` dict in `settings.py`.
- **Implementation Notes:** `mask_phone("+919812345678") -> "+91********78"`. `hash_phone_for_logs(phone) -> sha256(phone).hexdigest()[:16]`. Formatter emits `{ts, level, msg, request_id, phone_masked?, phone_hash?, ...extras}`. Filter attached to `accounts` logger.
- **Acceptance Criteria:**
  - [ ] Log lines are valid JSON on one line
  - [ ] Filter rejects any log record containing a 6-digit sequence flagged as OTP context
- **Tests Required:** TASK-032
- **Risk:** medium
- **Status:** complete

---

### TASK-014 — `X-Request-ID` middleware

- **Owner:** backend-engineer
- **Goal:** Read/generate `X-Request-ID`, attach to a thread-local/logging context, echo in response header.
- **Rationale:** NFR-OBS-01; correlates DB `OtpCode.request_id` with log lines.
- **Dependencies:** TASK-004
- **Affected Files:** `backend/accounts/middleware.py`, `settings.MIDDLEWARE`
- **Implementation Notes:** Use `uuid4().hex` when absent. Stash on `request.request_id`; inject into logging via a filter or contextvar.
- **Acceptance Criteria:**
  - [ ] Response includes `X-Request-ID`
  - [ ] Log records carry the same id
- **Tests Required:** covered by TASK-032
- **Risk:** low
- **Status:** complete

---

### TASK-015 — `exceptions.py` and DRF exception handler

- **Owner:** backend-engineer
- **Goal:** Domain exceptions + stable JSON error envelope.
- **Rationale:** ARCH error shape `{error, detail, retry_after?}`.
- **Dependencies:** TASK-004
- **Affected Files:** `backend/accounts/exceptions.py`
- **Implementation Notes:** Classes: `AuthDomainError`, `SmsDispatchError`, `RateLimited(retry_after)`, `OtpExpired`, `OtpInvalidated`, `NoActiveOtp`, `InvalidCode`, `TooManyAttempts`, `AuthUnavailable`, `CountryNotAllowed`, `InvalidPhoneNumber`. `auth_exception_handler(exc, ctx)` maps each to the ARCH-defined HTTP status + error code, includes `retry_after` when set. Delegates to `drf.views.exception_handler` for auth/validation defaults.
- **Acceptance Criteria:**
  - [ ] All ARCH error codes mapped
  - [ ] Response body shape identical for all errors
- **Tests Required:** exercised by TASK-028 through TASK-031
- **Risk:** low
- **Status:** complete

---

### TASK-016 — `serializers.py`

- **Owner:** backend-engineer
- **Goal:** `OtpRequestSerializer` (phone), `OtpVerifySerializer` (phone+code), `LogoutSerializer` (refresh), `UserSerializer` (id, phone, date_joined).
- **Rationale:** FR-01/02/12/13.
- **Dependencies:** TASK-009
- **Affected Files:** `backend/accounts/serializers.py`
- **Implementation Notes:** `OtpRequestSerializer.validate_phone_number` calls `normalize_to_e164` then `country_allowed`; raises `InvalidPhoneNumber` / `CountryNotAllowed`. `OtpVerifySerializer.validate_code` enforces `^\d{6}$`.
- **Acceptance Criteria:**
  - [ ] Normalized phone is what downstream code sees
  - [ ] Malformed input → 400 before any DB/Redis work
- **Tests Required:** TASK-024, TASK-028
- **Risk:** low
- **Status:** complete

---

### TASK-017 — `OtpRequestView`

- **Owner:** backend-engineer
- **Goal:** Endpoint `POST /api/auth/otp/request/`.
- **Rationale:** FR-01/08/10/13/15, NFR-SEC-05.
- **Dependencies:** TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015, TASK-016
- **Affected Files:** `backend/accounts/views.py`
- **Implementation Notes:** Flow: serializer → `rate_limit.check_otp_request` → `transaction.atomic` block: supersede prior active OTP (`select_for_update`), insert new OTP row, `twilio_client.send_otp_sms`. On Twilio error → transaction rolls back, `rate_limit.compensate_request`, return 502. On success set 30 s cooldown, respond with `{detail: "otp_sent", expires_in: 300, resend_available_in: 30}`. Never leaks user existence.
- **Acceptance Criteria:** covers AC-01, AC-02, AC-07, AC-11
- **Tests Required:** TASK-028
- **Risk:** high
- **Status:** complete

---

### TASK-018 — `OtpVerifyView`

- **Owner:** backend-engineer
- **Goal:** Endpoint `POST /api/auth/otp/verify/`.
- **Rationale:** FR-02/09/11/17.
- **Dependencies:** TASK-010, TASK-012, TASK-015, TASK-016
- **Affected Files:** `backend/accounts/views.py`
- **Implementation Notes:** Flow: serializer → per-IP verify rate-limit → `transaction.atomic` + `select_for_update` on latest active OTP → verify → on success `User.objects.get_or_create(phone_number=...)`, mint `RefreshToken.for_user(user)` with `phone_number` custom claim, respond `{access, refresh, is_new_user, user}`. Dev-mode override applied inside verify.
- **Acceptance Criteria:** covers AC-03, AC-04, AC-05, AC-06, AC-13
- **Tests Required:** TASK-029
- **Risk:** high
- **Status:** complete

---

### TASK-019 — `LogoutView`

- **Owner:** backend-engineer
- **Goal:** Endpoint `POST /api/auth/logout/` (blacklist refresh, 205).
- **Rationale:** FR-04.
- **Dependencies:** TASK-004, TASK-015
- **Affected Files:** `backend/accounts/views.py`
- **Implementation Notes:** Parse `RefreshToken(body["refresh"])`, call `.blacklist()`, return 205. Malformed → 400 `invalid_refresh`.
- **Acceptance Criteria:** covers AC-09
- **Tests Required:** TASK-031
- **Risk:** low
- **Status:** complete

---

### TASK-020 — `MeView`

- **Owner:** backend-engineer
- **Goal:** Authenticated `GET /api/auth/me/` returning `{id, phone_number, date_joined}`.
- **Rationale:** FR-05.
- **Dependencies:** TASK-005, TASK-015
- **Affected Files:** `backend/accounts/views.py`
- **Implementation Notes:** `permission_classes = [IsAuthenticated]`; serialize via `UserSerializer`.
- **Acceptance Criteria:** covers AC-10
- **Tests Required:** TASK-031
- **Risk:** low
- **Status:** complete

---

### TASK-021 — URL wiring

- **Owner:** backend-engineer
- **Goal:** `accounts/urls.py` and include under `/api/auth/` in project urls.
- **Rationale:** COMP-012, FR-03 (mount `TokenRefreshView`).
- **Dependencies:** TASK-017, TASK-018, TASK-019, TASK-020
- **Affected Files:** `backend/accounts/urls.py`, `backend/config/urls.py`
- **Implementation Notes:** Preserve `/api/health/` public. Mount SimpleJWT `TokenRefreshView` at `token/refresh/`.
- **Acceptance Criteria:**
  - [ ] All 5 endpoints resolve
  - [ ] `/api/health/` still 200 without auth
- **Tests Required:** covered by TASK-028-031
- **Risk:** low
- **Status:** complete

---

### TASK-022 — System check for creds → `503 auth_unavailable`

- **Owner:** backend-engineer
- **Goal:** Django `system check` emits warnings (dev) / errors (prod); `OtpRequestView` returns 503 when creds missing.
- **Rationale:** AC-15.
- **Dependencies:** TASK-011, TASK-012
- **Affected Files:** `backend/accounts/apps.py`, `backend/accounts/checks.py`
- **Implementation Notes:** Register a check reading `TWILIO_*`, `OTP_PEPPER`, `JWT_SIGNING_KEY`, `REDIS_URL`. View catches `AuthUnavailable`.
- **Acceptance Criteria:**
  - [ ] Missing Twilio in prod → check error
  - [ ] View returns 503 with stable code
- **Tests Required:** TASK-028
- **Risk:** medium
- **Status:** pending

---

### TASK-023 — `purge_expired_otps` management command

- **Owner:** backend-engineer
- **Goal:** Delete or null-out `code_hash` on OTP rows older than 24 h post-expiry.
- **Rationale:** NFR-PRIV-02; COMP-013.
- **Dependencies:** TASK-006, TASK-007
- **Affected Files:** `backend/accounts/management/commands/purge_expired_otps.py`
- **Implementation Notes:** `OtpCode.objects.filter(expires_at__lt=now - 24h).delete()`. Emit summary log. Idempotent.
- **Acceptance Criteria:**
  - [ ] `python manage.py purge_expired_otps` runs cleanly
  - [ ] Only rows past retention removed
- **Tests Required:**
  - [ ] Unit test asserting only expired-24h rows are affected (add to TASK-025 suite)
- **Risk:** low
- **Status:** pending

---

### TASK-024 — Unit tests: `services/phone.py`

- **Owner:** test-engineer
- **Goal:** Parametrized tests over normalization + allowlist behavior.
- **Rationale:** AC-14, FR-12, FR-13.
- **Dependencies:** TASK-009
- **Affected Files:** `backend/accounts/tests/test_phone.py`
- **Acceptance Criteria:**
  - [ ] `"(415) 555-2671"` (US) → `+14155552671`
  - [ ] `"+919812345678"` unchanged
  - [ ] `"12345"`, `"abc"`, `""` → InvalidPhoneNumber
  - [ ] Non-IN number with default allowlist → CountryNotAllowed
  - [ ] Empty allowlist admits any valid E.164
- **Tests Required:** self
- **Risk:** low
- **Status:** pending

---

### TASK-025 — Unit tests: `services/otp.py`

- **Owner:** test-engineer
- **Goal:** OTP generate/hash/verify/attempts/expiry/dev-mode/purge coverage.
- **Rationale:** FR-06/07/09, NFR-SEC-01/02, FR-18, AC-13, NFR-PRIV-02.
- **Dependencies:** TASK-010
- **Affected Files:** `backend/accounts/tests/test_otp_service.py`
- **Implementation Notes:** Use `freezegun` (or Django's clock override) for expiry. Assert `hmac.compare_digest` path via monkeypatch that only accepts equal-length hex.
- **Acceptance Criteria:**
  - [ ] Generated codes are 6 digits, uniformly random
  - [ ] Storage never contains raw code
  - [ ] 5 wrong attempts invalidate the OTP; a 6th (even correct) raises TooManyAttempts
  - [ ] Expired OTP → OtpExpired, row remains for audit
  - [ ] New request supersedes prior active OTP
  - [ ] `dev_mode_accepts` respects `DEBUG` + `OTP_DEV_MODE` guard
- **Tests Required:** self
- **Risk:** medium
- **Status:** pending

---

### TASK-026 — Unit tests: `services/twilio_client.py`

- **Owner:** test-engineer
- **Goal:** Mocked SDK behavior + dev-mode + prod-guard.
- **Rationale:** FR-14/15/18, AC-11.
- **Dependencies:** TASK-011
- **Affected Files:** `backend/accounts/tests/test_twilio_client.py`
- **Acceptance Criteria:**
  - [ ] SDK exception → `SmsDispatchError`
  - [ ] Twilio error code logged, not returned
  - [ ] Dev-mode no-ops when `DEBUG=True`
  - [ ] `OTP_DEV_MODE=True` with `DEBUG=False` raises `RuntimeError`
- **Tests Required:** self
- **Risk:** low
- **Status:** pending

---

### TASK-027 — Unit tests: `services/rate_limit.py`

- **Owner:** test-engineer
- **Goal:** Composed windows + compensation using `fakeredis`.
- **Rationale:** FR-08, NFR-SEC-08, AC-07.
- **Dependencies:** TASK-012
- **Affected Files:** `backend/accounts/tests/test_rate_limit.py`
- **Acceptance Criteria:**
  - [ ] 2nd request within 30 s → rate_limited with retry_after > 0
  - [ ] 6th request in 1h → rate_limited
  - [ ] 11th in 24h → rate_limited
  - [ ] Per-IP verify limit trips at 21st attempt in 10 min
  - [ ] `compensate_request` restores counters
  - [ ] Redis unreachable → `AuthUnavailable`
- **Tests Required:** self
- **Risk:** medium
- **Status:** pending

---

### TASK-028 — Integration tests: `/otp/request/`

- **Owner:** test-engineer
- **Goal:** Happy path, invalid inputs, rate-limit, Twilio failure, 503 auth_unavailable.
- **Rationale:** AC-01, AC-02, AC-07, AC-11, AC-15.
- **Dependencies:** TASK-021, TASK-022
- **Affected Files:** `backend/accounts/tests/test_view_request.py`
- **Implementation Notes:** Twilio client patched at module boundary. `fakeredis` for cache. Assert response envelope for each error.
- **Acceptance Criteria:**
  - [ ] AC-01 body + mocked SDK call args
  - [ ] AC-02 parametrized invalid inputs, no DB row, no SDK call
  - [ ] AC-07 rapid 2nd request → 429 + retry_after
  - [ ] AC-11 Twilio raises → 502, no OTP row, counters intact
  - [ ] AC-15 unset Twilio creds → 503 auth_unavailable
- **Tests Required:** self
- **Risk:** medium
- **Status:** pending

---

### TASK-029 — Integration tests: `/otp/verify/`

- **Owner:** test-engineer
- **Goal:** Happy path (new+returning), expiry, attempt cap, dev-mode.
- **Rationale:** AC-03, AC-04, AC-05, AC-06, AC-13.
- **Dependencies:** TASK-021
- **Affected Files:** `backend/accounts/tests/test_view_verify.py`
- **Implementation Notes:** Use a test hook to fetch the freshly persisted `OtpCode` and reconstruct the plaintext via a fixture-generated deterministic path (either by patching `secrets.randbelow` to return a fixed int during the request, or by exposing the raw code only in-test via a monkeypatched `otp.generate`).
- **Acceptance Criteria:**
  - [ ] AC-03: 200 + tokens + user exists
  - [ ] AC-04: returning user reuses id, `is_new_user=false`
  - [ ] AC-05: expired → 400 code_expired
  - [ ] AC-06: 5 wrong then correct → 429 too_many_attempts + invalidated
  - [ ] AC-13a: dev-mode `000000` accepted with `DEBUG=True`
  - [ ] AC-13b: dev-mode ignored when `DEBUG=False`
- **Tests Required:** self
- **Risk:** medium
- **Status:** pending

---

### TASK-030 — Integration tests: `/token/refresh/`

- **Owner:** test-engineer
- **Goal:** Rotation + reuse detection.
- **Rationale:** AC-08, FR-03, FR-17.
- **Dependencies:** TASK-021
- **Affected Files:** `backend/accounts/tests/test_view_refresh.py`
- **Acceptance Criteria:**
  - [ ] Refresh returns new access + rotated refresh
  - [ ] Reusing the old refresh → 401
  - [ ] Access lifetime 15 min, refresh 30 d (assert on decoded exp)
- **Tests Required:** self
- **Risk:** low
- **Status:** pending

---

### TASK-031 — Integration tests: `/logout/` + `/me/`

- **Owner:** test-engineer
- **Goal:** Blacklist behavior + auth gating.
- **Rationale:** AC-09, AC-10.
- **Dependencies:** TASK-021
- **Affected Files:** `backend/accounts/tests/test_view_logout_me.py`
- **Acceptance Criteria:**
  - [ ] Logout returns 205; refresh becomes 401
  - [ ] `/me/` without header → 401
  - [ ] `/me/` with valid Bearer → 200 correct payload
- **Tests Required:** self
- **Risk:** low
- **Status:** pending

---

### TASK-032 — Log-content tests

- **Owner:** test-engineer
- **Goal:** Assert no raw OTP or full phone in any log line across the flow.
- **Rationale:** AC-12, NFR-SEC-04, FR-16.
- **Dependencies:** TASK-021
- **Affected Files:** `backend/accounts/tests/test_logging.py`
- **Implementation Notes:** Use `pytest`'s `caplog` or a memory handler attached to the `accounts` logger; run request→verify→refresh→logout end-to-end; regex `r"\+\d{10,15}"` and `r"\b\d{6}\b"` (contextual) must not match.
- **Acceptance Criteria:**
  - [ ] No matches for either regex
  - [ ] Every log record has `request_id`
- **Tests Required:** self
- **Risk:** low
- **Status:** pending

---

### TASK-033 — Migration smoke test

- **Owner:** test-engineer
- **Goal:** Ensure migrations apply and reverse cleanly on a fresh DB.
- **Rationale:** ARCH §Migration + Rollback.
- **Dependencies:** TASK-007
- **Affected Files:** `backend/accounts/tests/test_migrations.py` or CI step
- **Acceptance Criteria:**
  - [ ] `migrate` from empty DB succeeds
  - [ ] `migrate accounts zero` then `migrate token_blacklist zero` reverses without errors
- **Tests Required:** self
- **Risk:** low
- **Status:** pending

---

### TASK-034 — README + ops runbook additions

- **Owner:** backend-engineer
- **Goal:** Document env vars, ElastiCache precondition, and scheduling handoff for `purge_expired_otps`.
- **Rationale:** Ops handoff (user defaults #1, #3).
- **Dependencies:** TASK-002, TASK-023
- **Affected Files:** `backend/README.md` (create if missing) or `docs/ops/auth-runbook.md`
- **Implementation Notes:** Table of env keys with purpose + example, note "Redis (ElastiCache multi-AZ) is a deploy prerequisite", note "Schedule `python manage.py purge_expired_otps` hourly (cron / EventBridge / Celery-beat) — not wired in this feature".
- **Acceptance Criteria:**
  - [ ] All env keys documented
  - [ ] Purge command scheduling explicitly deferred to ops
- **Tests Required:** none
- **Risk:** low
- **Status:** pending

---

## Critical Path

TASK-001 → TASK-003 → TASK-004 → TASK-006 → TASK-010 → TASK-017 → TASK-021 → TASK-028
(8 hops; verify-flow path TASK-018/029 is one hop shorter and can proceed in parallel after TASK-010.)

## Parallel Groups

| Group | Tasks | Notes |
|-------|-------|-------|
| P-A | TASK-001, TASK-002 | Deps and env docs are independent. |
| P-B | TASK-005, TASK-006 | Both wait on TASK-003/004; independent models. |
| P-C | TASK-009, TASK-010, TASK-011, TASK-012, TASK-013, TASK-014, TASK-015 | All service/support modules; only TASK-010 needs TASK-006. Otherwise parallelisable after TASK-004. |
| P-D | TASK-017, TASK-018, TASK-019, TASK-020 | Views can be built concurrently after their service deps land. |
| P-E | TASK-024, TASK-025, TASK-026, TASK-027 | Unit-test tasks independent of each other once their services exist. |
| P-F | TASK-028, TASK-029, TASK-030, TASK-031, TASK-032, TASK-033 | Integration tests run in parallel after TASK-021. |

## Rollout

- **Feature flag:** false (no user-visible feature yet).
- **Migration:** true (custom User + OtpCode + token_blacklist).
- **Order:** deps + settings → models + migrations → services → views/urls → tests → ops docs → deploy → set Twilio env → smoke test with a real Indian phone.
- **Rollback:** `migrate accounts zero` and `migrate token_blacklist zero`; revert deploy; remove `AUTH_USER_MODEL` from settings. Safe because no other feature depends on `accounts.User` yet.

## Owner / Size / Status Summary

- Total tasks: 34 (backend-engineer: 23; test-engineer: 11)
- Sizes: S ≈ 20; M ≈ 11; L ≈ 3
- All tasks start in `pending`.

## Blockers

None. All ARCH-001 open questions are resolved; the three residual items (scheduler wiring, minimal observability scope, ElastiCache provisioning) are covered by the user-authorised defaults recorded above.
