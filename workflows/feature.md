version: 1

workflow:

id: feature-development

name: Feature Development

description: >
End-to-end development workflow for implementing a new feature
using requirements, architecture, planning, implementation,
testing, code review, and security review.

trigger:

```
type: user_request

examples:
  - "Build Google OAuth login"
  - "Add dark mode"
  - "Implement team invitations"
```

state:
file: .ai/state.yaml

artifact\_root: .ai/features/${feature\_id}

stages:

```
- id: requirements
  name: Requirements
  agent: product-manager

  input:
    - user_request
    - repository
    - existing_documentation

  output:
    artifact: docs/requirements/${feature_id}.md
    schema: schemas/requirement.schema.yaml

  gate:
    id: requirements-gate

    conditions:

      - expression: "artifact.status == 'approved'"
        message: "Requirements must be approved."

      - expression: "artifact.goal != null"
        message: "Feature goal is required."

      - expression: "size(artifact.acceptance_criteria) > 0"
        message: "At least one acceptance criterion is required."

      - expression: "size(artifact.open_questions[?blocking == true]) == 0"
        message: "Blocking product questions remain."

    on_failure:
      action: return_to_agent

- id: architecture
  name: Architecture
  agent: architect

  depends_on:
    - requirements

  input:
    - docs/requirements/${feature_id}.md
    - repository
    - existing_architecture
    - existing_adrs

  output:
    artifact: docs/architecture/${feature_id}.md
    schema: schemas/architecture.schema.yaml

  gate:
    id: architecture-gate

    conditions:
      - expression: "artifact.status == 'approved'"
        message: "Architecture must be approved."
      - expression: "size(artifact.components) > 0"
        message: "Affected components must be identified."
      - expression: "artifact.proposed_solution != null"
        message: "Proposed solution is required."
      - expression: "size(artifact.risks) >= 0"
        message: "Architecture risk assessment must exist."
    on_failure:
      action: return_to_agent

- id: planning
  name: Planning
  agent: planner

  depends_on:
    - architecture

  input:
    - docs/requirements/${feature_id}.md
    - docs/architecture/${feature_id}.md
    - repository

  output:
    artifact: docs/plans/${feature_id}.md
    schema: schemas/plan.schema.yaml

  gate:
    id: plan-gate

    conditions:
      - expression: "artifact.status == 'approved'"
        message: "Plan must be approved."
      - expression: "size(artifact.tasks) > 0"
        message: "Plan must contain tasks."
      - expression: "all(artifact.tasks, task.owner != null)"
        message: "Every task requires an owner."

    on_failure:
      action: return_to_agent

- id: implementation
  name: Implementation

  depends_on:
    - planning

  strategy:
    type: dependency_graph
    task_source: docs/plans/${feature_id}.md
    scheduling:
      max_parallel_tasks: 4
      rules:
        - "dependencies must be complete"
        - "blocked tasks cannot start"
        - "only tasks with status='ready' may start"
  agents:
    frontend:
      agent: frontend-engineer
      task_filter:
        owner: frontend-engineer
    backend:
      agent: backend-engineer
      task_filter:
        owner: backend-engineer
  task_completion:
    required:
      - implementation
      - tests
      - verification

    statuses:
      success:
        - complete
      retryable:
        - failed
      blocked:
        - blocked
  gate:
    id: implementation-gate
    conditions:
      - expression: "all(tasks, task.status == 'complete')"
        message: "All implementation tasks must be complete."
    on_failure:
      action: resume_pending_tasks
- id: testing
  name: Testing
  agent: test-engineer

  depends_on:
    - implementation

  input:
    - docs/requirements/${feature_id}.md
    - docs/architecture/${feature_id}.md
    - docs/plans/${feature_id}.md
    - repository
    - git_diff

  output:
    artifact: docs/reviews/${feature_id}-testing.md
    schema: schemas/review.schema.yaml

  gate:
    id: testing-gate

    conditions:
      - expression: "testing.status == 'passed'"
        message: "Testing must pass."
      - expression: "critical_test_failures == 0"
        message: "Critical test failures exist."
    on_failure:
      action: create_fix_tasks
      return_to: implementation

- id: code_review
  name: Code Review
  agent: code-reviewer

  depends_on:
    - testing

  input:
    - docs/requirements/${feature_id}.md
    - docs/architecture/${feature_id}.md
    - docs/plans/${feature_id}.md
    - repository
    - git_diff
    - test_results

  output:
    artifact: docs/reviews/${feature_id}-code-review.md
    schema: schemas/review.schema.yaml

  gate:
    id: code-review-gate

    conditions:
      - expression: "review.status == 'approved'"
        message: "Code review must be approved."
      - expression: "blocking_findings == 0"
        message: "Blocking review findings exist."

    on_failure:
      action: create_fix_tasks
      return_to: implementation

- id: security
  name: Security Review
  agent: security-reviewer

  depends_on:
    - code_review

  input:
    - docs/requirements/${feature_id}.md
    - docs/architecture/${feature_id}.md
    - repository
    - git_diff
    - test_results
    - docs/reviews/${feature_id}-code-review.md

  output:
    artifact: docs/reviews/${feature_id}-security-review.md
    schema: schemas/security-review.schema.yaml

  gate:
    id: security-gate

    conditions:
      - expression: "security.status == 'approved'"
        message: "Security review must be approved."
      - expression: "critical_findings == 0"
        message: "Critical security findings exist."
      - expression: "high_findings == 0"
        message: "High severity security findings exist."

    on_failure:
      action: create_fix_tasks
      return_to: implementation

- id: final
  name: Final Gate
  agent: workflow-controller

  depends_on:
    - requirements
    - architecture
    - planning
    - implementation
    - testing
    - code_review
    - security

  gate:
    id: final-gate
    conditions:
      - expression: "requirements.status == 'passed'"
      - expression: "architecture.status == 'passed'"
      - expression: "planning.status == 'passed'"
      - expression: "implementation.status == 'passed'"
      - expression: "testing.status == 'passed'"
      - expression: "code_review.status == 'approved'"
      - expression: "security.status == 'approved'"

  on_success:
    update_state:
      status: ready
    message: >
      Feature passed all engineering gates and is ready.
  on_failure:
    update_state:
      status: blocked
```
