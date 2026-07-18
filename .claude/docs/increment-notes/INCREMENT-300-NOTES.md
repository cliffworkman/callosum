# Increment 300 — Fast pytest: targeted dev runs + parallelism + change-based selection

Running the whole ~1261-test suite (~45 min serial) after every localized change was a waste of wall-clock. This
makes the test loop fast without weakening coverage — CI still runs the full suite (now parallel).

## Implemented (tooling + docs only — no application code changed)

- **`requirements-dev.txt`:** add **`pytest-xdist>=3`** (parallel runner) + **`pytest-testmon>=2`** (change-based
  selection).
- **`.gitignore`:** ignore testmon's `.testmondata` / `.testmondata-journal`.
- **`.github/workflows/ci.yml`:** the offline suite `pytest -q` → **`pytest -n auto -q`** (parallel; the opt-in
  browser e2e job is unchanged — it's gated on `CALLOSUM_RUN_E2E=1`).
- **`.claude/CLAUDE.md`:** the Verification protocol §1 now prescribes **targeted dev runs** as the default
  (`pytest tests/test_<area>.py -q`, or `pytest --testmon -q`), with the **full parallel run (`pytest -n auto -q`)
  only before merge** (CI covers it). The Commands table lists the four run modes.

## The three layers (how to use it)

1. **Targeted (default dev loop):** the suite is split per-resource, so run only the changed area's file(s) —
   e.g. `pytest tests/test_feed.py -q` — plus `tests/test_frontend_assembly.py -q` for any `app/frontend/` edit.
   Finishes in **seconds**.
2. **Parallel full run:** `pytest -n auto -q` (one worker per core) for the pre-merge gate — the tests are hermetic
   (`temp_db_url` uses a per-test `tmp_path` DB; the autouse fixture isolates settings/library/keychain), so they run
   safely in parallel.
3. **Automatic change-selection:** `pytest --testmon -q` runs only tests whose covered code changed since the last
   run — the first run builds `.testmondata` (gitignored), later runs are targeted with no thought required.

## Key technical detail

Parallel-safety was the only risk; it holds because every DB-touching test gets its own migrated SQLite file under
`tmp_path` (`tests/conftest.py`), and the autouse fixture points settings / library dir / keychain at per-test temp
paths — so workers never share state. `-n auto` therefore matches the serial pass count exactly. (Deeper future win,
if needed: the `temp_db_url` fixture re-runs all Alembic migrations per test; a schema-template-copy could cut that —
measure with `pytest --durations=25` first.)

## Manual verification

- Targeted: `pytest tests/test_feed.py -q` → passes in seconds.
- Parallel parity: `pytest -n auto -q` → **1261 passed, 1 skipped** (exact parity with serial, parallel-safe
  confirmed), in **~13 min vs ~45 min serial** (~3.5× faster on this machine).
- testmon: `pytest --testmon -q` builds `.testmondata`; a follow-up run after editing one module selects only the
  affected tests.

## Pytest

No new tests (tooling/docs increment). Full suite unchanged at **1261 passed, 1 skipped** — now runnable in parallel.
