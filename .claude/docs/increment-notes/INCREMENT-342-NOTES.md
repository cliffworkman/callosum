# Increment 342 — Backlog #20 remainder: uv, pre-commit, CI gates one at a time, staged-harnesses registry

## Context
Next in the 12-item decision queue after #15 (sync_server hardening). Executes the harness-hardening plan
(`.claude/docs/future-tracks/opus4.8_future-tracks_harnesshardening.md`, itself a council-reviewed roadmap
written earlier and filed as backlog #20) Phases 1-4 in full, plus the staged-harnesses registry mechanism
(Phase "B" of that plan's two-bucket split). Branch protection (that plan's Phase 5) is deliberately **not**
applied in this increment — Cliff gets shown the exact ruleset first (see Next, below), per a standing
commitment made earlier in this session before any of this work started.

## Implemented (four commits, each pushed and confirmed green on GitHub Actions before the next landed —
the "ratchet: one gate at a time" discipline the plan itself names as a standing constraint)

**1. `chore(#20): adopt uv + migrate to the pre-commit framework`** — `pyproject.toml` becomes the single
source of truth for dependencies (normalized to match `requirements.txt`'s real pins, which had drifted ahead
of it), gains a `[dependency-groups].dev` mirroring `requirements-dev.txt`, and a committed `uv.lock` (151→158
packages resolved as dev tools were added across the sequence). CI's install step switches from
`pip install -r requirements-dev.txt` to `astral-sh/setup-uv` + `uv sync --locked` (fails outright if the lock
drifts from `pyproject.toml` — this **is** the "`uv lock --check`" gate the plan named, folded into `--locked`
rather than a separate step). `requirements.txt`/`requirements-dev.txt` remain as a hand-synced pip fallback.
Replaces the hand-rolled `tools/git-hooks/pre-commit` + `core.hooksPath` mechanism with the standard
**pre-commit framework** (`.pre-commit-config.yaml`): the same ruff format/check + the 600-line budget script,
plus `trailing-whitespace`/`end-of-file-fixer`/`check-merge-conflict`/`check-added-large-files`/`check-yaml`/
`check-toml`. A one-time `pre-commit run --all-files` sweep fixed the whitespace/EOF violations it found across
31 files (mostly docs, four frontend `.jsx` chunks) — content-identical, and the rebuilt `callosum-app.html` is
byte-identical (esbuild already strips this whitespace).

**2. `feat(ci): CI gate — alembic migration check`** — new `tests/test_migrations.py`: a fresh temp SQLite DB
must reach `alembic upgrade head` cleanly (catches broken migration execution) and then `alembic check` must
report zero autogenerate drift against the SQLAlchemy models (catches model/migration mismatch) — neither is
exercised by the rest of the suite, which seeds DBs via `metadata.create_all()`, never the real migration
chain. Required one real fix: `alembic/env.py` gained an `include_object` filter excluding `chunks_fts*` —
the FTS5 virtual table (migration 0026, raw `CREATE VIRTUAL TABLE ... USING fts5`) and its four SQLite-generated
shadow tables have no SQLAlchemy `Table` equivalent, so without the exclusion `alembic check` reported them as
permanent, un-fixable drift on every run. Also cleared an unrelated alembic deprecation warning
(`path_separator = os` in `alembic.ini`) and bumped `actions/setup-node` v4→v7 in both workflows (cleared a
Node-20-deprecated warning noticed on the first CI run).

**3. `feat(ci): CI gate — pip-audit + enable Dependabot`** — `pip-audit -r requirements.txt --strict` runs
blocking (clean today — the `transformers`/`urllib3` findings the 2026-06-20 pre-GitHub audit flagged have
since self-resolved via the existing version ranges, exactly as that audit predicted). `pip-audit -r
requirements-dev.txt` runs report-only (`|| true`): one accepted finding remains, **pytest 8.4.2 →
PYSEC-2026-1845 (fixed 9.0.3)** — deferred as its own future compatibility pass (a major-version bump across a
1396-test suite + xdist/testmon/playwright plugins deserves dedicated attention, not a drive-by pin change);
documented at the point of use (`requirements-dev.txt`, `pyproject.toml`) and in a new addendum to
`.claude/security-audits/2026-06-20_pre-github-fullsweep.md` (which had named "wire pip-audit into CI" as its
own follow-up — this closes it). `.github/dependabot.yml` enables weekly updates for `uv`, `npm`, and
`github-actions` ecosystems.

**4. `docs(#20): staged-harnesses registry`** — `.claude/staged-harnesses/REGISTRY.md` + 7 draft files
(Pyright, tach, a coverage gate, Hypothesis property tests, an embedding/vector-drift harness, performance
monitoring, bandit) implementing the plan's bucket-B split: expensive or judgment-heavy checks drafted with an
explicit activation trigger rather than turned on now (which would mean either false-positive noise or a
big-bang retrofit against code that predates the check). CLAUDE.md gets a one-line session-kickoff item
("glance at the registry — has any trigger fired?") and a reference-docs table row.

## Key technical detail
The `alembic check` gate's one real finding — `chunks_fts` and its four FTS5 shadow tables aren't expressible
as SQLAlchemy `Table` objects — is a **permanent, correct** exception, not a bug to fix. Teaching
`include_object` to skip `chunks_fts*` by name keeps the check meaningful everywhere else (a real drift on any
ORM-backed table still fails the gate) while not perpetually flagging an intentional, unfixable gap.

A YAML gotcha worth remembering: an unquoted step `name:` containing `text: more text` (a bare colon-space) is
invalid YAML per spec — GitHub's workflow parser rejected it outright ("error in your yaml syntax on line 32")
even though a permissive local `yaml.safe_load()` check didn't catch it. Quote any step name containing a
colon. (Separately, and unrelated: a step name containing `word #1 …` gets silently truncated at the `#` by
strict YAML comment rules — cosmetic only, pre-existing since inc 264, not fixed here.)

## Principles/A-A gate (rule #9)
Dev-infra/CI tooling — doesn't produce a claim/signal/judgment about the literature, so the primary gate
doesn't trigger. No security-audit stub opened for the `pre-commit`/`pip-audit` dev-tool additions themselves
(consistent with how `ruff`/`pytest-xdist`/`playwright` were added previously — dev-only tooling never ships,
never touches user data, never executes against the running app). The pip-audit gate itself directly extends
an existing security audit rather than opening a new one, since it's literally that audit's own named
follow-up action.

## Tests
- `tests/test_migrations.py` (+2, new): upgrade-head-succeeds + check-reports-no-drift.
- Full suite re-run twice under the new uv-managed `.venv` before `test_migrations.py` existed (once right
  after `uv sync`, once after the whitespace sweep + frontend rebuild): **1396 passed, 1 skipped** both times —
  no regression from the uv/pre-commit migration itself. **1398 passed, 1 skipped** once the two new migration
  tests are included (confirmed both locally and via CI's own full `pytest -n auto -q` step on the gate-2 push).
- Each of the four commits confirmed **green on GitHub Actions** (both `lint-and-test` and `e2e-smoke`) before
  the next was pushed — see the ratchet discipline above.
- Line budget: unaffected (351/351; `sync_server/`-adjacent files not in scope this increment).

## Gates
- **Security audit:** extended `.claude/security-audits/2026-06-20_pre-github-fullsweep.md` with a
  2026-07-22 addendum (pip-audit wired into CI; the one accepted dev-only finding documented) — **PASS**.

## Backlog
**#20 fully closed**: uv adoption, the pre-commit framework migration, all three named CI gates (alembic,
pip-audit, Dependabot), the staged-harnesses registry, and branch protection (with Cliff's explicit sign-off
on the exact ruleset — see below) are all done.

## Branch protection — applied, with Cliff's sign-off
The repo already had an active ruleset ("Callosum Rules", set up 2026-07-06/08 outside any Claude Code
session, discovered mid-increment while investigating a `git push` message) enforcing
`deletion`/`non_fast_forward` (force-push already blocked), `code_scanning` (CodeQL), `code_quality`, and
`copilot_code_review` — with Cliff's admin role bypassing all of it always. Presented Cliff three options
(status-checks-only / status-checks-plus-required-PR / hold off); he chose **status-checks-only**. Added a
`required_status_checks` rule (`lint-and-test` + `e2e-smoke`, `strict_required_status_checks_policy: true`) to
the existing ruleset via `PUT /repos/cliffworkman/callosum/rulesets/18586133` (note: this endpoint is `PUT`,
not `PATCH` — the latter 404s despite `gh api`'s docs suggesting otherwise). Everything else on the ruleset
(deletion/force-push/CodeQL/code-quality/Copilot-review, both bypass actors) carried over unchanged; Cliff's
admin bypass means this changes nothing about his own direct-push workflow — it only binds a future
non-admin contributor or low-privilege token to green CI before a merge/direct-update lands. A PR-required
rule + a real approval count stay explicitly deferred until a second contributor is actually active.

## Next
All four planned CI-gate commits plus branch protection are done. Nothing left open in backlog #20.
