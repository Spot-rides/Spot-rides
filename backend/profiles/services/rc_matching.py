"""Pure RC verification rules: owner-name match, vehicle-class check and outcome decision.

No database access and no provider knowledge, so the policy is identical for every adapter.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

NAME_MATCH = 'match'
NAME_PARTIAL = 'partial'
NAME_MISMATCH = 'mismatch'
NAME_NOT_CHECKED = 'not_checked'

OUTCOME_VERIFIED = 'verified'
OUTCOME_PENDING = 'pending'
OUTCOME_REJECTED = 'rejected'

DEFAULT_REJECTION_REASON = 'The vehicle could not be verified.'
CLASS_CONFLICT_REASON = 'The vehicle type does not match the registration certificate.'

_RELATION_RE = re.compile(
    r'(?<!\w)(?:s\s*/\s*o|d\s*/\s*o|w\s*/\s*o|c\s*/\s*o|son\s+of|daughter\s+of|wife\s+of)(?!\w)'
)
_MASKED_RUN_RE = re.compile(r'x{3,}', re.IGNORECASE)
# "MD" is deliberately absent: it is a common given-name prefix.
_HONORIFICS = frozenset({'mr', 'mrs', 'ms', 'miss', 'shri', 'smt', 'sri', 'shree', 'kumari', 'dr'})


def _tokens(text: Optional[str]) -> List[str]:
    if not text:
        return []
    text = unicodedata.normalize('NFKC', text).casefold()
    cut = _RELATION_RE.search(text)
    if cut:
        text = text[:cut.start()]
    tokens, current = [], []
    for ch in text:
        if unicodedata.category(ch)[0] in ('L', 'M'):
            current.append(ch)
        elif current:
            tokens.append(''.join(current))
            current = []
    if current:
        tokens.append(''.join(current))
    return [t for t in tokens if t not in _HONORIFICS]


def classify_owner_match(profile_first: Optional[str], profile_last: Optional[str], rc_owner: Optional[str]) -> str:
    """Return 'match' | 'partial' | 'mismatch' | 'not_checked'."""
    if not rc_owner or not rc_owner.strip() or '*' in rc_owner or _MASKED_RUN_RE.search(rc_owner):
        return NAME_NOT_CHECKED

    profile_tokens = _tokens(profile_first) + _tokens(profile_last)
    rc_tokens = _tokens(rc_owner)
    if not profile_tokens or not rc_tokens:
        return NAME_NOT_CHECKED

    available = list(rc_tokens)
    unmatched = []
    full = 0
    for token in profile_tokens:
        if token in available:
            available.remove(token)
            full += 1
        else:
            unmatched.append(token)

    initial = 0
    still_unmatched = 0
    for token in unmatched:
        hit = next(
            (rc for rc in available if (len(token) == 1 and rc.startswith(token)) or (len(rc) == 1 and token.startswith(rc))),
            None,
        )
        if hit is None:
            still_unmatched += 1
        else:
            available.remove(hit)
            initial += 1

    if full + initial == 0:
        return NAME_MISMATCH
    if still_unmatched == 0 and initial <= 1 and full >= 1:
        return NAME_MATCH
    return NAME_PARTIAL


_NON_PASSENGER = 'NON_PASSENGER'
_THREE_WHEELER = 'THREE_WHEELER'
_TWO_WHEELER = 'TWO_WHEELER'
_FOUR_WHEELER = 'FOUR_WHEELER'

# Order matters: first category with a whole-word/phrase hit wins.
_CLASS_KEYWORDS = (
    (_NON_PASSENGER, (
        'GOODS', 'TRUCK', 'LORRY', 'TRACTOR', 'TRAILER', 'TIPPER', 'BUS', 'OMNIBUS',
        'HMV', 'HGV', 'LGV', 'EARTH MOVING', 'CONSTRUCTION EQUIPMENT',
    )),
    (_THREE_WHEELER, (
        'THREE WHEELER', '3 WHEELER', '3W', 'E RICKSHAW', 'ERICKSHAW',
        'AUTO RICKSHAW', 'AUTORICKSHAW', 'RICKSHAW',
    )),
    (_TWO_WHEELER, (
        'M CYCLE', 'MCYCLE', 'MOTOR CYCLE', 'MOTORCYCLE', 'SCOOTER', 'MOPED', 'TWO WHEELER', '2 WHEELER', '2W',
    )),
    (_FOUR_WHEELER, (
        'MOTOR CAR', 'LMV', 'LIGHT MOTOR VEHICLE', 'MOTOR CAB', 'MAXI CAB', 'CAB', 'TAXI', 'JEEP', 'CAR',
    )),
)

_COMPATIBLE_CLASS = {
    'car': _FOUR_WHEELER,
    'suv': _FOUR_WHEELER,
    'hatchback': _FOUR_WHEELER,
    'sedan': _FOUR_WHEELER,
    'auto_rickshaw': _THREE_WHEELER,
    'bike': _TWO_WHEELER,
}


def _normalise_class(text: str) -> str:
    return ' ' + re.sub(r'\s+', ' ', re.sub(r'[^A-Z0-9]', ' ', text.upper())).strip() + ' '


def _rc_category(rc_vehicle_class: Optional[str]) -> Optional[str]:
    if not rc_vehicle_class:
        return None
    padded = _normalise_class(rc_vehicle_class)
    for category, keywords in _CLASS_KEYWORDS:
        if any(f' {kw} ' in padded for kw in keywords):
            return category
    return None


def check_vehicle_class(declared_vehicle_type: str, rc_vehicle_class: Optional[str]) -> Optional[bool]:
    """True = compatible, False = clear conflict, None = unknown/missing class (skip, never rejects)."""
    category = _rc_category(rc_vehicle_class)
    expected = _COMPATIBLE_CLASS.get((declared_vehicle_type or '').lower())
    if category is None or expected is None:
        return None
    return category == expected


@dataclass(frozen=True)
class Decision:
    outcome: str
    reason: Optional[str] = None


def decide_rc_outcome(result, name_match: str, class_ok: Optional[bool]) -> Decision:
    """Verified / pending (review) / rejected, evaluated in the architected order."""
    if result.status == 'rejected':
        return Decision(OUTCOME_REJECTED, result.rejection_reason or DEFAULT_REJECTION_REASON)
    if class_ok is False:
        return Decision(OUTCOME_REJECTED, CLASS_CONFLICT_REASON)
    if result.status == 'pending':
        return Decision(OUTCOME_PENDING)
    if result.status == 'verified' and name_match == NAME_MATCH:
        return Decision(OUTCOME_VERIFIED)
    return Decision(OUTCOME_PENDING)
