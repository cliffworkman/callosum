# Increment 552 Notes — Resume Axis Suggest from Status

## Outcome

Clicking an **Axis suggest** row in the Status popover now opens Theory → Axes, reopens the Suggested axes modal,
and polls the exact job represented by that row. Closing the modal no longer strands a running or completed suggestion
job, and reopening it from Status does not create a second scan or duplicate Status receipt.

## Implementation

- `axis_suggest_jobs` publishes the bounded `suggest-axes` modal destination in its existing Status navigation
  descriptor.
- The Status dispatcher attaches the clicked job id to the existing pane-tab request. `AxesPanel` consumes that
  request and keeps the modal's open state local to the pane, avoiding another top-level app-shell branch.
- `SuggestAxesModalBody` accepts an optional resume job id. A Status reopen polls `GET /axes/suggest/{job_id}`
  directly; an ordinary ✨ click and the onboarding flow continue to create a fresh job through `POST /axes/suggest`.
- QA route 76 now explicitly checks running and completed Axis Suggest resume behavior and forbids a second POST or
  duplicate Status row.

## Verification

- Status, Status-timing, Axes API, and frontend-assembly suite after rebuilding `callosum-app.html`: **142 passed**.
- Ruff format/check, Bandit, Tach, the 600-line budget, and `git diff --check`: pass.
- No provider, egress, persistence, migration, dependency, or scientific-semantics change.
