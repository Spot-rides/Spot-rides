# Refactor Workflow

## Trigger
Technical debt identified, performance issue, or structural improvement needed.

## Steps

1. `architect` — document current state and target state → `docs/decisions/`
2. `planner` — break refactor into atomic, safe steps.
3. Engineer — implement one step at a time, tests green after each step.
4. `test-engineer` — confirm no regressions.
5. `code-reviewer` — review diff.
6. Merge.

## Gates
- All existing tests must remain green throughout.
- No feature changes bundled with refactor.
