"""Sanitisation of provider- or staff-supplied free text before it is stored or returned."""

import re
import unicodedata
from typing import Iterable, Optional

_TAG_RE = re.compile(r'<[^>]*>')
_WS_RE = re.compile(r'\s+')


def sanitise_reason(text: Optional[str], *, redact: Iterable[Optional[str]] = (), max_len: int = 500) -> str:
    """Strip markup and control characters, redact given strings, collapse whitespace, truncate."""
    if not text:
        return ''
    cleaned = _TAG_RE.sub(' ', str(text))
    cleaned = ''.join(
        ch if (ch in '\t\n\r' or unicodedata.category(ch)[0] != 'C') else ' '
        for ch in cleaned
    )
    for value in redact:
        if value and value.strip():
            cleaned = re.sub(re.escape(value.strip()), '[redacted]', cleaned, flags=re.IGNORECASE)
    cleaned = _WS_RE.sub(' ', cleaned).strip()
    return cleaned[:max_len]
