# Evidence-unit replication amendment 02: correct the default target identity

Status: **FROZEN BEFORE SAMPLE SELECTION OR OUTCOME INSPECTION**

Parent amendment commit: `413add64fb80514c7f1529b557d220ad493b5b12`

Amendment 01 correctly identified the causal defect—repository Alembic ignored `CALLOSUM_DB_URL` because no
`sqlalchemy.url` override was placed in its `Config`—but incorrectly called the accidental target the worktree's
"default ignored validation database." The literal `alembic.ini` value at H1a is `sqlite:///callosum.db`, so the
accidental target was the ignored repository-root `callosum.db` inside this dedicated worktree.

Replace that phrase in the audit interpretation with **ignored repository-root `callosum.db`**. The file remains
isolated scratch, contains no source-library content, and is excluded from all study artifacts and denominators.
All other statements and every scientific rule in the preregistration and Amendment 01 remain unchanged.
