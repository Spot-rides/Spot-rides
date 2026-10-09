"""Service layer for user onboarding and DL verification.

This package contains the business logic for the onboarding flow:
- validators.py: Input validation (DL format, age, name)
- onboarding.py: Onboarding state machine (role selection, profile details, role switching)
- dl_verification.py: DL verification logic (submission, webhook processing)
"""
