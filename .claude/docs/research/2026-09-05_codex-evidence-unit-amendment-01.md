# Evidence-unit replication amendment 01: explicit Alembic target

Status: **FROZEN BEFORE SAMPLE SELECTION OR OUTCOME INSPECTION**

Parent preregistration commit: `eeb63a1951acfa2a40f51ba5f67ffe476e31d866`

## Defect

The initial isolated-copy setup set `CALLOSUM_DB_URL` and invoked `python -m alembic upgrade head`. Repository
Alembic does not read that environment variable directly: `alembic/env.py` consumes the `sqlalchemy.url` value in
the Alembic `Config`. The command therefore upgraded the isolated worktree's default ignored validation database,
not `.local/evidence-unit-replication/study.sqlite`. The explicitly targeted H1a backfill then failed closed with
`sqlite3.OperationalError: no such table: chunk_structure`.

This is a research-harness targeting error, not evidence that migration 0079 fails when executed against its intended
database. No production or user database was written. No sample was selected, no sampled text was viewed, and no
reconstruction outcome was inspected.

## Amendment

Discard the two affected ignored scratch databases after resolving and checking their absolute paths remain inside
this dedicated worktree. Recreate `study.sqlite` from the pristine snapshot. Invoke Alembic programmatically with:

1. `Config("alembic.ini")`;
2. `config.set_main_option("sqlalchemy.url", exact_study_database_url)`;
3. `command.upgrade(config, "head")`.

Then verify both the `alembic_version` row and physical `chunk_structure` table before running the backfill. All
preregistered hypotheses, sampling, reconstruction strategies, metrics, and interpretation rules remain unchanged.

The mistakenly upgraded default validation database is audit-only scratch and is excluded from every study artifact
and denominator.
