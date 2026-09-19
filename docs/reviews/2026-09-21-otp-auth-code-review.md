# Code Review: OTP Phone Authentication (FEAT-001)

**ID:** REVIEW-001
**Type:** code-review
**Feature:** FEAT-001
**Reviewer:** code-reviewer
**Date:** 2026-09-21
**Branch:** OTP-and-login-flow
**Status:** changes_requested

---

## Requirements Status: pass

The core OTP lifecycle (request → SMS dispatch → verify → JWT issue → logout) is correctly implemented end-to-end. All ARCH-001 API contract shapes, error codes, and HTTP status codes appear to be honoured. Rate limiting, HMAC hashing, attempt counting, and token blacklisting are present and functional.

## Architecture Status: pass

The layering is clean and follows the described ARCH-001 decomposition: serializers validate input, service modules own domain logic, views are thin orchestrators, and all errors flow through the central exception handler. The core envelope is consistently applied.

## Testing Status: unknown

Test files were excluded from this review per the task brief.

---

## Findings

| ID | Severity | Title | Location | Description | Recommendation | Blocking |
|----|----------|-------|----------|-------------|----------------|---------|
| F-01 | high | Raw OTP code printed to stdout in dev mode | `backend/accounts/services/twilio_client.py:86` | `print("OTP Dev Mode: ", phone_e164, code)` unconditionally writes the raw OTP code and phone number to stdout when dev mode is active. This directly contradicts the stated invariant in `otp.py` ("The raw code never enters a log record or exception message"). In environments where stdout is forwarded to a log aggregator — including many local dev setups with Docker or CI — this leaks a live secret. | Remove the `print` call. If the OTP is needed in dev, use a dedicated `logger.debug` call that emits only the OTP ID and relies on the `PhoneRedactionFilter` to strip six-digit sequences. | true |
| F-02 | high | `CORS_ALLOW_ALL_ORIGINS = True` is unconditional | `backend/config/settings.py:105` | The comment says "dev only" but there is no `if DEBUG:` guard. As written, this setting ships to production and allows any origin to make credentialed cross-origin requests to the API. | Wrap the line: `if DEBUG: CORS_ALLOW_ALL_ORIGINS = True`. For production, populate `CORS_ALLOWED_ORIGINS` from an env var with the explicit mobile/web origins. | true |
| F-03 | high | OTP consumption and user creation span two separate transactions | `backend/accounts/views.py:149-152` | `otp_service.verify()` is decorated `@transaction.atomic` and commits the OTP row as consumed before returning. The view then opens a second `transaction.atomic()` block to call `User.objects.get_or_create`. If any error occurs between these two commits (process crash, DB error, unhandled exception in the JWT-minting code), the OTP is permanently consumed but no session is established. On the next attempt the user receives `no_active_otp` and must request a fresh OTP to recover. This is especially problematic for new users who cannot log in at all without a working retry. | Restructure so both the OTP consumption and the user get-or-create execute in a single atomic block. One approach: keep `verify()` as the integrity check only (raise on failure, do not save `consumed_at`), and then have the view own a single outer transaction that (1) re-locks and marks the OTP consumed, and (2) gets or creates the user. Alternatively, pass a `save=False` flag to `verify()` and let the caller commit. | true |
| F-04 | medium | Redundant single-column index on `OtpCode.phone_number` | `backend/accounts/models.py:48` | `phone_number = models.CharField(max_length=16, db_index=True)` creates a standalone B-tree index. The `Meta.indexes` block then defines a composite index on `(phone_number, invalidated, consumed_at)`. PostgreSQL can use the composite index for phone-only lookups (it is the leftmost column), so the single-column index duplicates storage and maintenance overhead for every write. | Remove `db_index=True` from the field definition. The composite index is more useful for all query patterns in `create_for_phone` and `verify`. | false |
| F-05 | medium | Inactive users receive valid JWTs after OTP verification | `backend/accounts/views.py:152` | `User.objects.get_or_create(phone_number=phone_e164)` returns an existing user regardless of their `is_active` status. Tokens are then minted for that user. Subsequent requests with those tokens fail `JWTAuthentication` because `is_active=False` users are rejected by the default DRF auth backend — but the verify endpoint returns `HTTP 200` with tokens, giving the caller the impression that authentication succeeded. | Decide the intended policy and make it explicit. If a deactivated user should be denied at verify time, add `if not user.is_active: raise AuthDomainError(...)` after `get_or_create`. If reactivation on OTP is desired, set `user.is_active = True; user.save()`. | false |
| F-06 | medium | Cooldown TTL check is not atomic with rate-limit INCR operations | `backend/accounts/services/rate_limit.py:139-162` | `check_otp_request` first reads the cooldown key TTL with a plain `client.ttl()`, then proceeds to run the INCR Lua script on each window key. These two Redis operations are not grouped into a single pipeline or Lua script. In a highly concurrent scenario two requests can both observe `cooldown_ttl <= 0` and both proceed to the INCR phase before either sets the cooldown (cooldown is only set post-send in `record_success_cooldown`). The practical impact is low because the 30s phone window (limit=1) will catch the second concurrent request anyway, but the invariant the cooldown is meant to enforce is weakened. | Either pipeline the TTL check with the first INCR in the Lua script, or accept and document the known TOCTOU and rely on the 30s fixed-window as the authoritative backstop. | false |
| F-07 | low | `_client` Twilio singleton is not thread-safe during initialization | `backend/accounts/services/twilio_client.py:44-61` | `_get_client()` reads and writes the module-level `_client` without a lock. Under a WSGI server with threads, two threads can both observe `_client is None` and each construct a new `Client` object. The second assignment wins silently. Constructing two clients is not catastrophic, but it is wasteful and makes the `reset_client_for_tests()` helper unreliable under concurrency. | Protect the lazy init with `threading.Lock`, or initialize the client at application startup (e.g. `AppConfig.ready()`). | false |
| F-08 | low | `is_active` check missing in `create_user` manager | `backend/accounts/managers.py:27-31` | `create_user` silently drops any `password` argument passed by the caller (`password=None` is hardcoded in the `_create_user` call). If a caller inadvertently passes a password when creating a regular user (e.g. a management command), it is silently discarded. The omission is documented as intentional for the passwordless flow, but there is no assertion or warning that alerts the developer. | Add a `warnings.warn` or a `raise ValueError` if `password` is not `None` in `create_user`, so callers are informed that the argument is ignored. | false |
| F-09 | low | `_ = caches` eager side effect at module import | `backend/accounts/services/rate_limit.py:236` | Importing `rate_limit` causes `caches['default']` to be evaluated, which initialises the django-redis backend. If Redis is unavailable at boot (e.g. in a migration-only container or during unit tests without a Redis fixture), this triggers a connection attempt that may log noisy errors or raise. | Remove the `_ = caches` line. The comment says it ensures eager init, but `_redis()` already handles the lazy connection. If an eager health-check is needed, call `rate_limit.ping()` inside `AppConfig.ready()` instead. | false |
| F-10 | nit | `dev_mode_accepts` compares raw codes, real `verify` compares hashes | `backend/accounts/services/otp.py:80` | `hmac.compare_digest(code, fixed)` compares two plaintext strings. The constant-time guarantee of `compare_digest` is meaningless here since both sides are equal-length plaintext. This is dev-only so there is no security issue, but the inconsistency is worth noting for clarity. | Document the rationale in a comment, or hash both sides for consistency: `hmac.compare_digest(hash_code(code), hash_code(fixed))`. | false |
| F-11 | nit | Missing `DEFAULT_AUTO_FIELD` in settings | `backend/config/settings.py` | Django 3.2+ emits a system check warning when `DEFAULT_AUTO_FIELD` is not set. The warning does not surface as an error today but will clutter logs. | Add `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` to settings. | false |

---

## Positives

- Constant-time HMAC comparison throughout OTP verification correctly prevents timing-based side-channel attacks.
- The `PhoneRedactionFilter` and `RequestIdFilter` pipeline is thorough and well-structured; phone numbers are masked before they reach any log sink and the six-digit scrub on OTP-context records is a solid defence-in-depth measure.
- The Lua INCR+EXPIRE script in `rate_limit.py` correctly ensures atomicity for the core counter operation, avoiding the classic `GET/INCR` race condition.
- `compensate_request` on Twilio failure (FR-15) is correctly implemented: counters are decremented best-effort inside a try/except so a Redis failure during compensation does not mask the original SMS error.
- The `select_for_update` in both `create_for_phone` and `verify` prevents race conditions between concurrent OTP requests for the same phone number.
- Domain exceptions cleanly separate error signalling from HTTP rendering; no view hand-rolls an error envelope.
- The `OTP_DEV_MODE` guard refusing to activate when `DEBUG=False` is a good production safety rail.
- The `_MESSAGE_TEMPLATE` in `twilio_client.py` never interpolates the raw code into any log record — only the `body` variable (ephemeral, never logged) carries it.
- The `EnvelopeJSONRenderer` correctly short-circuits on 204/205 status codes, ensuring the logout `205 Reset Content` response has no body.

## Scope Assessment

The implementation is correctly scoped to FEAT-001. No unrelated models, views, or migrations were introduced. The `core/` package (envelope, exceptions, renderers, pagination) is generic infrastructure that correctly supports the feature without leaking auth-specific logic. The requirements.txt additions (twilio, phonenumbers, django-redis, djangorestframework-simplejwt) are all directly required by the feature.
