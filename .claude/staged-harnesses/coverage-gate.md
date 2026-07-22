# Staged harness: coverage gate (threshold or changed-lines)

**Checks:** test-coverage percentage, either an overall floor or a changed-lines-only threshold on new code.

**Why deferred:** "report first, gate later" (the harness-hardening plan's own correction to an earlier,
over-eager coverage-gate proposal) — a blunt high bar punishes legitimate untested surfaces (thin adapters,
generated code, defensive branches) as much as it catches real gaps, and this project's suite has never run
coverage at all yet, so there's no baseline to set a sane threshold from.

**Activation trigger:** coverage *reporting* (non-gating — `pytest --cov` in CI, uploaded as an artifact or a
PR comment, never failing the build) has run for a few cycles and the number stabilizes enough to pick a
sane floor (or, more precisely, a changed-lines threshold so new code is held to a bar without demanding a
retroactive sweep of the whole tree).

## Draft config (moves into `pyproject.toml`'s `[tool.coverage.*]` + a CI step on activation)

```toml
[tool.coverage.run]
source = ["app", "integrations"]
omit = ["app/frontend/*"]  # frontend is JS, not measured by Python coverage

[tool.coverage.report]
# No `fail_under` yet — reporting phase only. Add one once a baseline stabilizes.
show_missing = true
skip_covered = false
```

```yaml
# Draft CI step (report-only; add to ci.yml's lint-and-test job on activation)
- name: Coverage report (informational — not gated yet)
  run: uv run pytest --cov --cov-report=term-missing -q
```

## Activation steps
1. Add `pytest-cov` to the `dev` dependency group.
2. Move the `[tool.coverage.*]` draft into `pyproject.toml`; add the CI step above (report-only).
3. After a few cycles of stable reporting, pick a floor (or a changed-lines threshold via `diff-cover` or
   similar) and flip the CI step to fail below it.
4. Update this registry's status to `active` and remove this file (or mark it superseded).
