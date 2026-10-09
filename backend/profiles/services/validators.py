"""Validation functions for onboarding inputs.

All validators return (is_valid, error_message) tuples.
"""

import re
from typing import Tuple

# Indian DL format: XX00 0000 0000000 or XX000000000000
# Two state letters + two RTO digits + four year digits + seven serial digits
DL_PATTERN = re.compile(r'^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$')


def validate_dl_format(dl_number: str) -> Tuple[bool, str]:
    """Validate Indian DL number format.

    Args:
        dl_number: Normalized DL number (already uppercased, no spaces)

    Returns:
        (is_valid, error_message)
    """
    if not DL_PATTERN.match(dl_number):
        return False, "Invalid DL format. Expected: XX00 0000 0000000 (13 digits after state code)"
    return True, ""


def validate_age(age: int) -> Tuple[bool, str]:
    """Validate age range.

    Args:
        age: User-provided age

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(age, int) or age < 18 or age > 80:
        return False, "Age must be between 18 and 80"
    return True, ""


def validate_name(name: str, field_name: str) -> Tuple[bool, str]:
    """Validate first/last name.

    Args:
        name: Name string
        field_name: "first_name" or "last_name" for error messages

    Returns:
        (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, f"{field_name} cannot be blank"
    if len(name) > 50:
        return False, f"{field_name} must be 50 characters or less"
    # Allow Unicode letters, spaces, hyphens, apostrophes
    if not re.match(r"^[\w\s'-]+$", name, re.UNICODE):
        return False, f"{field_name} contains invalid characters"
    return True, ""
