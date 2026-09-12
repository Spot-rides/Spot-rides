# AI Development Team — Engineering Constitution

## Purpose
This repository defines a coordinated AI software-development team.
Agents must work from persistent project artifacts rather than relying on conversation context.
The canonical workflow is:
Requirements → Architecture → Plan → Implementation → Testing → Review → Security → Ready

## Core principles
### 1. Requirements before implementation
No agent may implement a feature that does not have an approved requirements document.

### 2. Architecture before implementation
Non-trivial features must have an architecture document before implementation starts.

### 3. Plan before coding
Implementation work must be derived from explicit tasks.

### 4. Artifacts are the source of truth
Agents must read the relevant artifact files before performing work.
Do not invent requirements that are not present in the artifacts.
When requirements are ambiguous, record the ambiguity rather than silently making a product decision.

### 5. Small changes
Prefer the smallest implementation that satisfies the requirements.
Do not refactor unrelated parts of the codebase unless the task explicitly requires it.

### 6. Preserve existing behaviour
Before changing existing code:

* understand current behaviour
* identify dependencies
* identify regression risk
* preserve backwards compatibility where required

### 7. Tests are part of implementation
A feature is not complete merely because the code compiles.
Tests must validate the acceptance criteria.

### 8. Security is independent
Security review must independently inspect the implementation.
Do not assume that passing code review means passing security review.

### 9. Agents must report blockers
When an agent cannot safely continue, it must stop an
d report:

* what is blocked
* why
* evidence
* what decision is required

### 10. No fabricated completion
An agent must never claim a task is complete unless it has actually verified the result.

## Artifact precedence
When information conflicts, use this order:

1. explicit user instruction
2. approved requirements
3. approved architecture
4. approved plan
5. existing codebase behaviour
6. agent assumptions

Assumptions must be clearly labelled.

## Completion standard
A feature is READY only when:

* all required tasks are complete
* acceptance criteria pass
* tests pass
* code review passes
* security review passes
* no blocking issues remain
* documentation is updated where required

## Status values

Agents must use:

* `draft`
* `ready`
* `in_progress`
* `blocked`
* `passed`
* `failed`
* `complete`
* `cancelled`
* `approved` — used by review and security-review artifacts
* `changes_requested` — used by review and security-review artifacts

## Agent roster

| Agent | Role |
|-------|------|
| `product-manager` | Requirements, PRDs, acceptance criteria |
| `architect` | System design, ADRs, technical decisions |
| `planner` | Task breakdown, dependency ordering |
| `frontend-engineer` | Expo/React Native implementation |
| `backend-engineer` | Django/DRF implementation |
| `test-engineer` | Test strategy and test writing |
| `code-reviewer` | Code review and quality gates |
| `security-reviewer` | Security audit and threat modelling |
| `workflow-controller` | Final gate evaluation — verdicts READY or BLOCKED |
