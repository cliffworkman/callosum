# Harness hardening plan (post-git) — corrected per council review

**Disposition for CC:** this is the **post-git hardening roadmap**. Execute it **after** the git baseline +
private GitHub push are done (that ordering is fixed). Work the phases in order. **Turn ON** the cheap checks
now; **STAGE** the expensive/judgment ones as dormant drafts with activation triggers; scaffold the activation
registry. Run any claim/signal/egress-touching work through the Principles gate as usual. **Do not activate a
staged harness until its trigger fires.**

---

## Nomenclature corrections (apply in every doc you write)
- **"Architectural fitness function" = automated, executable checks only** (tests, lint, types, import rules,
  `alembic check`). The **principles gate, the core invariants, the security review are governance / guardrails
  — not fitness functions.** Use the terms precisely; the distinction matters for onboarding Jeff.
- **Lockfile:** use **uv** (`uv.lock`). pip-tools is the fallback; not Poetry.
- **Type checker:** **Pyright**, not mypy, in *warn → baseline → ratchet* mode. **Do not use the deprecated
  SQLAlchemy mypy plugin.**
- **Dependency security:** **Dependabot *and* pip-audit** (complementary, not either/or).
- **"AGPL compatibility check" was mis-specified** — there is no such button. Implement a **license inventory +
  a policy allowlist + a human exception process + SPDX metadata** (pip-licenses or liccheck; an SPDX
  expression `AGPL-3.0-or-later` in `pyproject.toml`).
- **`alembic check`** catches model/migration drift; **also** run a temp-DB `alembic upgrade head` to catch
  broken migration *execution*.
- **Coverage:** report first, gate later (low or changed-lines threshold); never a blunt high bar.
- **Architecture lint:** **tach** slightly favored over import-linter for module-boundary rules (your
  "file-containment" rule is closer to boundary enforcement than layer imports); either is fine; **after** the
  substrate exists.

---

## Two buckets (Fork 2 resolution)

### A. TURN ON NOW — cheap, unanimous keep, wire into pre-commit + CI as you build them
Their value is catching drift **as it happens**; staging them would only create an activation-day cleanup
backlog.
- **ruff** — both `ruff format --check` and `ruff check`; pre-commit (with `--fix` locally) + CI.
- **pytest** — CI.
- **`alembic check` + a temp-DB migration test** — CI.
- **pip-audit** — CI (scheduled or per-PR); enable **Dependabot** on the repo.
- **600-line size-budget script** — pre-commit (this is the automated form of the manual cap).

### B. STAGE AS DORMANT DRAFTS — expensive/judgment; draft the config, do NOT wire, record a trigger
- **Pyright strict config** — trigger: a type-clean baseline of the core app exists / before Jeff's first
  typed module.
- **tach (or import-linter) boundary contracts** — trigger: Jeff begins contributing, or module
  count/coupling crosses a threshold.
- **Coverage gate (threshold)** — trigger: suite stabilizes after a few cycles of coverage *reporting*.
- **Hypothesis property tests** — trigger: per target, when touching the gnarly pure functions
  (`paper_edits` merge, dedup union-find, citation export, quote-matching).
- **Embedding/vector-drift harness** — trigger: **before changing the embedding model.** (Vector schema
  versioning + a re-index path; you have partial text-versioning, not model-migration coverage — Gemini's
  catch.)
- **Performance/resource monitoring** (query latency, storage growth) — trigger: a real library crosses
  ~1–2k PDFs.
- **bandit (security static analysis)** — trigger: before public exposure, or when adding a network or
  file-write surface.

### The staging mechanism
- Create **`.claude/staged-harnesses/`** (dev-only, already outside shipped code and excludable from
  optimization passes). Each staged harness = a **draft config** + a short header: *what it checks, why it's
  deferred, its ACTIVATION TRIGGER, and the activation steps* (where the config moves when live —
  `pyproject.toml` / `.pre-commit-config.yaml` / `.github/workflows`).
- Add **`.claude/staged-harnesses/REGISTRY.md`** listing each staged harness, its trigger, and status
  (drafted / active).
- **Activation check:** add **one line** to the session-kickoff checklist — "scan
  `staged-harnesses/REGISTRY.md`; has any trigger fired?" Keep it a single glance, not a ritual (the
  recursion risk — a check that something remembers to check — is real; do not let it grow into ceremony).
- Treat staged harnesses as **drafts** (updatable, reactivatable), not maintained final products — the same
  "build the plan, defer the implementation" pattern used for big future features.

---

## Fork 1 — the principles/values gate
- **Keep it.** Reclassify it accurately: **governance, not a fitness function.**
- Its **contributor-facing form**: distill the gate into a **CONTRIBUTING.md section + a PR-template
  checklist**, so external pushes (Jeff's) are checked against the principles/values at review time. This is
  the value-alignment instrument for onboarding — and it answers the asymmetry that the gate scrutinizes an
  external contributor more neutrally than it scrutinizes the AI-plus-Cliff loop.

---

## The sequence (after git baseline + private GitHub, which precede everything here)

**Phase 1 — reproducible setup.** Adopt uv; normalize `pyproject.toml`; add dev/test/e2e dependency groups;
generate `uv.lock`; create one canonical check command (Makefile / justfile / `scripts/check`).

**Phase 2 — wire existing checks locally.** ruff + pytest in the check command; `alembic upgrade head` on a
temp SQLite DB.

**Phase 3 — pre-commit** (fast checks: ruff format/check, trailing whitespace, EOF fixer, YAML/TOML check,
large-file guard, the 600-line script). CI is the authority; pre-commit is bypassable with `--no-verify`.

**Phase 4 — GitHub Actions CI, gates added ONE AT A TIME** (green, then required): install + `uv lock --check`
→ ruff → pytest; then `alembic check` + temp-DB migration; then pip-audit. (Pyright / coverage / arch lint are
bucket B — staged, not added here yet.)

**Phase 5 — branch protection AFTER CI is green:** require PR before merge, require status checks, block
force-push on main, require one review once Jeff is active.

**Phase 6 — convert manual conventions:** 600-line → script (in pre-commit); file-containment → staged tach
config; security-review → PR template + `SECURITY_REVIEW.md`; principles → CONTRIBUTING + PR template.

**Phase 7 — contributor + research furniture:** the front-door README (see the separate README prompt),
CONTRIBUTING.md, a PR template, two issue templates (bug; feature/design proposal), SECURITY.md, `.env.example`,
CITATION.cff (research software), SemVer `0.y.z`, a curated Keep-a-Changelog `CHANGELOG.md`, and the SPDX
license expression in `pyproject.toml`. (Optional later: REUSE/SPDX file headers, SBOM via uv, OpenSSF
Scorecard, CODE_OF_CONDUCT when fully public.)

---

## Standing constraints
- **Never turn multiple new blocking gates on in one PR — ratchet.** One gate, green, required, next.
- **Apply Grok's filter at each rung:** does this catch a mistake you actually make, or is it here because
  serious projects have it? Subtraction is the default tie-breaker.
- **The cheap bucket runs continuously; the expensive bucket waits for its trigger.** That is the whole point
  of the split — don't collapse it back into "turn everything on."
