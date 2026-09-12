# Code Review Skill

## Purpose
Gate code quality before merge.

## Steps

1. Read the diff (branch vs main).
2. Check: correctness, edge cases, error handling, naming, duplication.
3. Verify tests exist and cover the change.
4. Check for performance issues (N+1 queries, large payloads).
5. Validate against `schemas/review.schema.yaml`.
6. Save review to `docs/reviews/YYYY-MM-DD-<slug>-review.md`.
7. Return verdict: `APPROVE`, `REQUEST_CHANGES`, or `BLOCK`.
