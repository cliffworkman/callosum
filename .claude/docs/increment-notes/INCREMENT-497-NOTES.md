# Increment 497 — Post-Merge Dependency and Runtime Hardening

## Implemented

- Upgraded Python security/tooling dependencies: cryptography 49.0.0 → 50.0.0 and pytest 8.4.2 → 9.1.1.
- Made app-scoped model and provider runtimes terminal after `close()`. Provider shutdown waits for active users
  without introducing an operation mutex that would serialize ordinary concurrent requests.
- Preserved batched NLI as the normal path, with original-order per-pair recovery only after an opaque batch failure;
  a pair that still fails receives no stance instead of suppressing all usable evidence.
- Added executable Node coverage for synthesis Overview age/stale-state logic and API error-status propagation.
- Removed the inert Critical Read `on_progress` callback from single and WIP call sites after confirming that all
  single, Set, and WIP browser surfaces use stage-aware status and no TUI/MCP consumer reads the raw field.
- Updated the latency contract with the concrete queueing, terminal-close, and exceptional NLI-recovery boundaries.

## Key technical detail

Runtime closure is a lifecycle boundary, not a cache miss. A closed runtime must never reconstruct a compatible
model or client. Local inference checks the terminal state after acquiring its inference lock; provider entries mark
themselves closed, reject new users, and wait on a condition for already-active users. This keeps close/use behavior
deterministic while retaining existing request concurrency.

The stance scorer still makes one batched model call in the healthy case. Only an exception from that opaque batch
causes the exact pairs to be retried individually, in original order. Persistent failures map to `None`; successful
pairs retain their predictions. This follows the evidence principle: absence of a model result is not evidence of a
scientific stance, and one unavailable pair is not a certificate that every sibling pair is unavailable.

## Dependency disposition

- Dependabot #18: cryptography fixed by 50.0.0.
- Dependabot #16: pytest fixed by 9.1.1; the previously documented PYSEC-2026-1845 risk acceptance is resolved.
- Dependabot #17: `glib` 0.18.5 remains open. Current published Tauri 2.11.5 depends on GTK 0.18.2, which requires
  `glib ^0.18`; forcing 0.20 is not a compatible lockfile-only change. The alert was neither dismissed nor hidden.

## Manual verification script

1. Run `uv sync --frozen` and confirm cryptography 50.0.0 and pytest 9.1.1 import from the project environment.
2. Run the runtime tests and confirm get/run after close cannot reload resources; confirm close waits for an active
   provider request while a second request is rejected and normal concurrent-request coverage still passes.
3. Run the length-aware NLI tests with the opaque-failure fake. Confirm the initial batched call is attempted once,
   fallback visits pairs in original order, and exactly the pathological pair maps to `None`.
4. Run the synthesis Overview UI tests and confirm boundary ages plus 409/500 response statuses are exercised by
   the exact extracted production functions.
5. Run single and WIP Critical Read tests; confirm stage-aware status remains and no raw progress callback is needed.
6. Inspect Dependabot: Python alerts should close; Rust glib remains explicitly open pending an upstream GTK/Tauri
   dependency-line change.

## Pytest and quality gates

- Final full root suite: **2461 passed, 3 skipped** in 16m13s.
- Focused receipts: runtime 32 passed; stance/Critical Read 72 passed; frontend/lifecycle 91 passed.
- Python dependency consumers: 44 passed; pytest-testmon smoke: 10 passed.
- Strict pip-audit: no known Python vulnerabilities.
- Ruff format/check, configured Bandit, Tach architecture checks, 562-file line budget, and `git diff --check`: pass.
- Dependency commit remote checks: GitHub CI (including e2e), CodeQL, and dependency graph: pass.
