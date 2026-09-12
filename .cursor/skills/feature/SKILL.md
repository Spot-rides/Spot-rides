# Feature Skill

## Purpose
End-to-end guide for delivering a new feature using the AI dev team.

## Steps

1. **Requirements** — Invoke `product-manager` agent. Output: `docs/requirements/<feature>.md`
2. **Architecture** — Invoke `architect` agent with requirements doc. Output: `docs/architecture/<feature>.md`
3. **Planning** — Invoke `planner` agent with architecture doc. Output: `docs/plans/<feature>.md`
4. **Implementation** — Invoke `frontend-engineer` and/or `backend-engineer` per plan tasks.
5. **Testing** — Invoke `test-engineer` to write and run tests.
6. **Review** — Invoke `code-reviewer` on the diff. Output: `docs/reviews/<feature>-review.md`
7. **Security** — If applicable, invoke `security-reviewer`. Output: `docs/reviews/<feature>-security.md`
8. **Merge** — All gates green → merge to main.
