# Planning Skill

## Purpose
Break an architecture doc into an ordered, dependency-aware task list.

## Steps

1. Read architecture doc from `docs/architecture/`.
2. List all implementation units (models, serializers, views, screens, tests).
3. Assign each unit to an agent role (`[frontend]`, `[backend]`, `[test]`).
4. Order tasks by dependency (migrations before views, views before screens).
5. Estimate effort (S/M/L).
6. Validate against `schemas/plan.schema.yaml`.
7. Save to `docs/plans/YYYY-MM-DD-<slug>.md`.
