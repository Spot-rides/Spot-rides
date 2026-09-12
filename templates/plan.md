# Plan: [Feature Name]

**ID:** PLAN-001
**Type:** plan
**Feature:** FEAT-001
**Architecture:** ARCH-001
**Version:** 1
**Status:** draft
**Date:** YYYY-MM-DD

---

## Tasks

| ID | Title | Owner | Depends On | Risk | Status |
|----|-------|-------|-----------|------|--------|
| TASK-001 | [Create Django model + migration] | backend-engineer | — | low | pending |
| TASK-002 | [Create API endpoint] | backend-engineer | TASK-001 | low | pending |
| TASK-003 | [Create frontend screen] | frontend-engineer | TASK-001 | low | pending |
| TASK-004 | [Write integration tests] | test-engineer | TASK-002, TASK-003 | low | pending |

---

## Task Details

### TASK-001 — [Title]

- **Owner:** backend-engineer
- **Goal:** [What this task achieves]
- **Rationale:** [Why this task is needed]
- **Dependencies:** none
- **Affected Files:**
  - `backend/[app]/models.py`
  - `backend/[app]/migrations/`
- **Implementation Notes:** [Key implementation details]
- **Acceptance Criteria:**
  - [ ] [Specific, verifiable criterion]
- **Tests Required:**
  - [ ] [Test description]
- **Risk:** low
- **Status:** pending

---

### TASK-002 — [Title]

- **Owner:** backend-engineer
- **Goal:**
- **Rationale:**
- **Dependencies:** TASK-001
- **Affected Files:**
  - `backend/[app]/views.py`
  - `backend/[app]/serializers.py`
  - `backend/[app]/urls.py`
- **Implementation Notes:**
- **Acceptance Criteria:**
  - [ ]
- **Tests Required:**
  - [ ]
- **Risk:** low
- **Status:** pending

---

### TASK-003 — [Title]

- **Owner:** frontend-engineer
- **Goal:**
- **Rationale:**
- **Dependencies:** TASK-001
- **Affected Files:**
  - `frontend/screens/[ScreenName].tsx`
  - `frontend/components/[Component].tsx`
- **Implementation Notes:**
- **Acceptance Criteria:**
  - [ ]
- **Tests Required:**
  - [ ]
- **Risk:** low
- **Status:** pending

---

### TASK-004 — [Title]

- **Owner:** test-engineer
- **Goal:**
- **Rationale:**
- **Dependencies:** TASK-002, TASK-003
- **Affected Files:**
  - `backend/tests/`
- **Implementation Notes:**
- **Acceptance Criteria:**
  - [ ]
- **Tests Required:**
  - [ ]
- **Risk:** low
- **Status:** pending

---

## Critical Path

TASK-001 → TASK-002 → TASK-004

## Parallel Groups

| Group | Tasks | Notes |
|-------|-------|-------|
| Group A | TASK-002, TASK-003 | Both depend only on TASK-001 — can run in parallel |
