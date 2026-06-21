# Increment 99 — Tests derive the Alembic head, not a hardcoded revision

A small dev-infra cleanup that kills a recurring failure class: a migration bumps the head revision, but two
test files hardcode the old revision string, so the suite only goes red on the *full* run (it bit inc 91 and
inc 98 — each time, the targeted subset passed and the full suite caught a stale constant).

## Implemented
- **`tests/api_helpers.py`** — new `alembic_head()`: reads the current head from the migration scripts via
  `ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()`. (Assumes the single linear head the
  project maintains.)
- **`tests/test_health.py`** — a module-level `HEAD = alembic_head()` replaces the three hardcoded
  `"00NN_…"` literals in the at-head + behind-DB health assertions.
- **`tests/test_startup_migration.py`** — `HEAD = alembic_head()` replaces the hardcoded constant.

Now a new migration needs **zero** test edits for the head revision — the assertions follow the scripts. The
`db_revision == HEAD` check in `test_health` (against a freshly-migrated DB) doubles as the wiring proof: if
`alembic_head()` were wrong, that test fails.

## Key technical detail
Tests-only change (`tests/` is exempt from the 600-line rule and is dev infra). No app code, no migration, no
behavior change — the assertions are refactored, not added. **Convention going forward:** never hardcode the
Alembic head revision in a test; use `alembic_head()`.

## Pytest
**410 passed, 1 skipped** — unchanged (no new test; the head literals became `alembic_head()`). `ruff` clean.
