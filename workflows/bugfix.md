# Bugfix Workflow

## Trigger
Bug reported in production or staging.

## Steps

1. Reproduce the bug with a failing test.
2. `architect` (if systemic) — identify root cause.
3. `backend-engineer` / `frontend-engineer` — implement fix.
4. `test-engineer` — verify fix + regression coverage.
5. `code-reviewer` — review diff.
6. Merge to main, deploy hotfix.

## Gates
- Failing test must exist before fix is written.
- Review required before merge.
