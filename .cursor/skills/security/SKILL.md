# Security Review Skill

## Purpose
Identify security issues before they reach production.

## Steps

1. Read the diff and architecture doc for the feature.
2. Run OWASP Top 10 checklist.
3. Check: input validation, auth/authz, secrets exposure, SQL injection, XSS.
4. Scan dependencies for known CVEs.
5. Validate against `schemas/security-review.schema.yaml`.
6. Save report to `docs/reviews/YYYY-MM-DD-<slug>-security.md`.
7. Return verdict: `PASS`, `WARN`, or `BLOCK`.
