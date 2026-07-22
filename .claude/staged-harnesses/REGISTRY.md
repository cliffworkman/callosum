# Staged-harnesses registry

Backlog #20 (the harness-hardening ratchet, `.claude/docs/future-tracks/opus4.8_future-tracks_harnesshardening.md`)
splits fitness-function candidates into two buckets: **cheap + unanimous-keep** ones are turned on immediately
(ruff, pytest, the 600-line budget, `alembic check`, pip-audit — see `.pre-commit-config.yaml` +
`.github/workflows/ci.yml`), and **expensive or judgment-heavy** ones are drafted here as dormant configs with
an explicit activation trigger, so they don't create day-one noise or an activation-day cleanup backlog.

**Session-kickoff check (CLAUDE.md item #9-adjacent):** glance down this table — has any trigger fired? Keep it
a single glance, not a ritual. A harness stays a **draft** (updatable, reactivatable) until its trigger fires;
activating it means moving its config into the live location named in its own file and wiring it into
`.pre-commit-config.yaml` / `.github/workflows/ci.yml` / `pyproject.toml` as appropriate.

| Harness | Checks | Trigger | Status |
|---|---|---|---|
| [`pyright.md`](pyright.md) | Static type checking (strict, ratcheted) | A type-clean baseline exists across the core app, or before the first outside contributor's first typed module | drafted |
| [`tach.md`](tach.md) | Module-boundary / import-layering rules | An outside contributor begins pushing code, or module count/coupling crosses a threshold that makes the file-containment rule (CLAUDE.md #1) hard to eyeball | drafted |
| [`coverage-gate.md`](coverage-gate.md) | Coverage threshold (or changed-lines) gate | The suite's coverage *reporting* (not gating) has run a few cycles and stabilizes | drafted |
| [`hypothesis.md`](hypothesis.md) | Property-based tests on gnarly pure functions | Per-target: next time `paper_edits` merge, the dedup union-find, citation export, or quote-matching is touched | drafted |
| [`embedding-drift.md`](embedding-drift.md) | Vector-schema versioning + re-index path | Before changing the embedding model (`all-MiniLM-L6-v2` / `bge-base-en-v1.5`) | drafted |
| [`performance-monitoring.md`](performance-monitoring.md) | Query latency + storage growth | A real library crosses ~1-2k PDFs | drafted |
| [`bandit.md`](bandit.md) | Security static analysis (Python) | Before any public/hosted exposure, or when adding a new network or file-write surface | drafted |

## Why these stayed dormant instead of turning on now

Grok's filter (from the harness-hardening plan): *does this catch a mistake you actually make, or is it here
because serious projects have it?* Subtraction is the default tie-breaker. Every harness above is either
expensive to run continuously, requires a baseline that doesn't exist yet, or only pays for itself once a
specific condition (a contributor, a model change, a library-size threshold, a public deploy) is real — turning
any of them on today would mean living with either false-positive noise or a check nobody's watching.
