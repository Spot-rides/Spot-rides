"""Redis-backed rate limiter for OTP request / verify endpoints.

Implements PLAN-001 TASK-012 / ARCH-001 COMP-006.

Design:
- Fixed-window ``INCR + EXPIRE NX`` executed atomically in a single Lua
  script (one round trip).
- Phone numbers are SHA-256 hashed before use as Redis key material so a
  Redis snapshot never leaks PII (ARCH-001 §Rate Limiting).
- Composed windows per ARCH:
    request:  phone 30s (limit 1), 1h (limit 5), 24h (limit 10),
              ip 1h (limit 30)
    verify:   ip 10m (limit 20)
- ``compensate_request`` reverses the counters on Twilio failure so the
  caller isn't penalised for infrastructure faults (FR-15).
- Fail-closed: any Redis error surfaces as :class:`AuthUnavailable` (DEC-010).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from django.core.cache import caches

from ..exceptions import AuthUnavailable


logger = logging.getLogger('accounts')


# ---------------------------------------------------------------------------
# Window definitions (see ARCH-001 §Rate Limiting)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Window:
    label: str
    key_template: str
    ttl: int
    limit: int


_REQUEST_PHONE_WINDOWS: tuple[_Window, ...] = (
    _Window('phone_30s', 'rl:otp_req:phone:{phone_hash}:30s', 30, 1),
    _Window('phone_1h', 'rl:otp_req:phone:{phone_hash}:1h', 3600, 5),
    _Window('phone_24h', 'rl:otp_req:phone:{phone_hash}:24h', 86400, 10),
)

_REQUEST_IP_WINDOW = _Window('ip_1h', 'rl:otp_req:ip:{ip}:1h', 3600, 30)

_VERIFY_IP_WINDOW = _Window('verify_ip_10m', 'rl:otp_verify:ip:{ip}:10m', 600, 20)

_COOLDOWN_KEY_TEMPLATE = 'rl:otp_req:phone:{phone_hash}:cooldown'
_COOLDOWN_TTL = 30


# ---------------------------------------------------------------------------
# Lua script — atomic INCR + EXPIRE NX; returns (count, ttl_seconds).
# ---------------------------------------------------------------------------


_LUA_INCR_EXPIRE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def hash_phone(phone_e164: str) -> str:
    return hashlib.sha256(phone_e164.encode('utf-8')).hexdigest()


def _redis():
    """Return the low-level Redis client, or raise :class:`AuthUnavailable`.

    ``django_redis.get_redis_connection`` is imported lazily so the module
    can be imported without a Redis at boot (settings still need it, but
    unit tests can patch this function).
    """
    try:
        from django_redis import get_redis_connection
        return get_redis_connection('default')
    except Exception as exc:  # noqa: BLE001 — connection failures are fail-closed.
        logger.error('rate_limit.redis_unavailable', extra={'error': str(exc)})
        raise AuthUnavailable('Rate limiter is temporarily unavailable.')


def _incr(client, key: str, ttl: int) -> Tuple[int, int]:
    try:
        result = client.eval(_LUA_INCR_EXPIRE, 1, key, ttl)
    except Exception as exc:  # noqa: BLE001
        logger.error('rate_limit.eval_failed', extra={'error': str(exc), 'key': key})
        raise AuthUnavailable('Rate limiter is temporarily unavailable.')
    count = int(result[0])
    remaining_ttl = int(result[1])
    if remaining_ttl < 0:
        # Key missing or with no expire — normalise to the window ttl.
        remaining_ttl = ttl
    return count, remaining_ttl


def _decr(client, key: str) -> None:
    try:
        current = client.decr(key)
        # Never leave a negative counter; a compensating call must not
        # accidentally credit future requests.
        if current is not None and int(current) < 0:
            client.delete(key)
    except Exception as exc:  # noqa: BLE001 — compensation is best-effort.
        logger.warning('rate_limit.decr_failed', extra={'error': str(exc), 'key': key})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_otp_request(phone_hash: str, ip: str) -> Tuple[bool, Optional[int]]:
    """Check request-side windows. Returns ``(ok, retry_after)``.

    On limit hit, returns the largest ``retry_after`` among tripped windows,
    or the cooldown key's remaining TTL if the 30s cooldown is active.
    """
    client = _redis()

    # Cooldown check (set on last successful request) short-circuits.
    cooldown_key = _COOLDOWN_KEY_TEMPLATE.format(phone_hash=phone_hash)
    try:
        cooldown_ttl = client.ttl(cooldown_key)
    except Exception as exc:  # noqa: BLE001
        logger.error('rate_limit.ttl_failed', extra={'error': str(exc)})
        raise AuthUnavailable('Rate limiter is temporarily unavailable.')
    if cooldown_ttl and cooldown_ttl > 0:
        return False, int(cooldown_ttl)

    tripped: list[int] = []
    incremented: list[tuple[_Window, str]] = []

    for window in _REQUEST_PHONE_WINDOWS:
        key = window.key_template.format(phone_hash=phone_hash)
        count, ttl = _incr(client, key, window.ttl)
        incremented.append((window, key))
        if count > window.limit:
            tripped.append(ttl)

    ip_key = _REQUEST_IP_WINDOW.key_template.format(ip=ip)
    count, ttl = _incr(client, ip_key, _REQUEST_IP_WINDOW.ttl)
    incremented.append((_REQUEST_IP_WINDOW, ip_key))
    if count > _REQUEST_IP_WINDOW.limit:
        tripped.append(ttl)

    if tripped:
        # Roll back counters for this attempt so we don't compound-penalise
        # legitimate users who retry after the retry_after window elapses.
        for _, key in incremented:
            _decr(client, key)
        return False, max(tripped)
    return True, None


def check_otp_verify(phone_hash: str, ip: str) -> Tuple[bool, Optional[int]]:
    """Per-IP verify limiter (NFR-SEC-08).

    ``phone_hash`` is currently unused for the limit itself but is included
    in the signature so callers pass it consistently (the ARCH mirror-of-DB
    attempts counter can be added later without a signature change).
    """
    client = _redis()
    key = _VERIFY_IP_WINDOW.key_template.format(ip=ip)
    count, ttl = _incr(client, key, _VERIFY_IP_WINDOW.ttl)
    if count > _VERIFY_IP_WINDOW.limit:
        _decr(client, key)
        return False, ttl
    return True, None


def record_success_cooldown(phone_hash: str) -> None:
    """Set the 30s post-success cooldown for ``phone_hash``."""
    client = _redis()
    key = _COOLDOWN_KEY_TEMPLATE.format(phone_hash=phone_hash)
    try:
        client.set(key, '1', ex=_COOLDOWN_TTL)
    except Exception as exc:  # noqa: BLE001
        logger.error('rate_limit.cooldown_set_failed', extra={'error': str(exc)})
        raise AuthUnavailable('Rate limiter is temporarily unavailable.')


def compensate_request(phone_hash: str, ip: str) -> None:
    """Reverse the counters set by :func:`check_otp_request` after Twilio failure.

    Idempotent: DECR on a missing / already-zero key is a no-op (and we
    clean up any negative values). The cooldown key is deleted as well
    since the send never actually landed.
    """
    try:
        client = _redis()
    except AuthUnavailable:
        # Compensation must never mask the original error path; log and drop.
        logger.warning('rate_limit.compensate_skipped_redis_down')
        return

    for window in _REQUEST_PHONE_WINDOWS:
        _decr(client, window.key_template.format(phone_hash=phone_hash))
    _decr(client, _REQUEST_IP_WINDOW.key_template.format(ip=ip))
    try:
        client.delete(_COOLDOWN_KEY_TEMPLATE.format(phone_hash=phone_hash))
    except Exception as exc:  # noqa: BLE001
        logger.warning('rate_limit.cooldown_delete_failed', extra={'error': str(exc)})


def ping() -> bool:
    """Boot / health check helper. Raises :class:`AuthUnavailable` on failure."""
    client = _redis()
    try:
        client.ping()
    except Exception as exc:  # noqa: BLE001
        logger.error('rate_limit.ping_failed', extra={'error': str(exc)})
        raise AuthUnavailable('Rate limiter is temporarily unavailable.')
    return True


# Retain a symbolic reference so ``caches['default']`` is initialised eagerly
# when this module is imported (matches ARCH's Redis-via-CACHES wiring).
_ = caches
