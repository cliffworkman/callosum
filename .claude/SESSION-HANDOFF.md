# Session handoff — 2026-07-19 → next session (Claude → Claude)

**Goal for the next stretch: work down the backlog.** This is a self-handoff. Point me at this file at kickoff
(or I'll spot it in `.claude/`). Written after a 5-increment session; everything below is committed + CI-green on
`main`.

---

## ⚡ First actions (do these before anything else)
1. **Restart the dev server.** inc 306–308 are backend/frontend changes the running uvicorn won't have loaded.
   Nothing is visible (the new keyword tags, the read-only fixes) until the restart. No DB migration needed.
   Rebuild the frontend if you edited `app/frontend/` since (`python tools/build_frontend.py`).
2. **Read `.claude/CLAUDE.md` in full**, then skim increment notes **304–308** (`.claude/docs/increment-notes/`)
   + the top of `.claude/changes.md`. That's the current state.
3. **Confirm the plan below still matches the backlog** — grep `INCREMENT-BACKLOG.md`; it drifts (items marked
   open are sometimes already shipped — verify before building, mark drift DONE as you go).

## Where we are
- **At inc 308 on `main`, CI green, 1283 pytest passing / 1 skipped.** This session landed:
  - **304** per-item import progress titles · **305** web-stack CVE migration (fastapi 0.139.2 + starlette 1.3.1;
    14 Dependabot alerts → 0) · **306** richer keyword tags (OpenAlex topics + PubMed MeSH into enrichment) ·
    **307** keyword tags everywhere (Feed/Search-save bg-enrich + 🔎 re-resolve) · **308** QA-pass fixes
    (read-only credit 403s, mobile Help, Clear-× guard) · **+ QA inbox triage** (Codex pass, processed + filed).

## Operational notes carried from this session (important)
- **The local harness intermittently KILLS the ~13-min full `pytest -n auto` run** (resource pressure — the machine
  wasn't OOM). It killed 3 in a row at one point. **Lean on CI as the authoritative full-suite gate** — CI ran clean
  every push this session. Locally, run **targeted** tests (`pytest tests/test_<area>.py -q`) during dev; push and
  watch CI (`gh run watch <id> --exit-status`) for the full gate. Don't burn 30 min retrying killed full runs.
- **`integrations/openalex/adapter.py` is at 599/600** (inc 306). **Split it before the next OpenAlex edit** — peel
  the module-level work-mapping helpers (`_meta_from_work`/`_csl_from_work`/`_meta_with_abstract`/
  `_reconstruct_abstract`/`_OA_TYPE_TO_CSL`) → a new `integrations/openalex/work_mapping.py` leaf (inc-137 pattern;
  `work_keywords.py` joins it). `python tools/check_line_budget.py --list` shows the live closest-to-cap files.
- **Codex-verify skepticism** (memory): Codex over-claims self-audits — full pytest (or CI), both ruff gates, read
  against invariants. Its QA reports also get trust-but-verify (I re-checked every 2026-07-19 finding vs the code).
- End-of-session: **commit + push** by default (off-machine backup). `ruff format` (not just check) before pushing.

---

## 🔜 Start here — immediate follow-ups from this session

1. **inc 308 frontend fixes are UNVERIFIED (no Playwright this session).** They build clean + `test_frontend_assembly`
   passes, but the read-only credit gating / mobile Help collapse / Clear-× cancel were **not** browser-checked.
   **Confirm them** — run a Codex QA re-run (`tools/qa/supervisor.py`) on route_43/48 + the read-only companion +
   the mobile visual pass, OR eyeball with Playwright. See `INCREMENT-308-NOTES.md` → "Manual verification".
2. **"QA 2026-07-19 (Codex pass)" backlog batch — remaining (all need a browser):** in `INCREMENT-BACKLOG.md`
   (top of AUTONOMOUS). **[Medium] metadata-only paper opened as a PDF tab → `/papers/2/pdf` 404** (trace the
   selected-but-unopened cue; may be a fixture artifact); **[Low ×4] mobile CSS spacing** (Feed filter widths,
   whatsnew-notice height, Settings provider-row collision, Work provenance alignment); **route_00 steps 4–5**
   rewrite to the workspace IA. These were left filed because pixel-tuning blind risks making them look worse.

---

## The backlog — what I can build SOLO (AUTONOMOUS section, `INCREMENT-BACKLOG.md` §52–274)
Most of this section is already shipped/drift. The genuinely-open, autonomous-safe threads:
- **httpx→httpx2 TestClient migration** (inc-305 tech-debt) — dev-only deprecation; migrate before it becomes a
  removal. Small, self-contained.
- **SQLite residual snapshot-upgrade BUSY fix** — the LONG-JOB half is complete (inc 273–278); what remains is the
  **short SELECT-then-write request-path retry** (the deferred pre-public concurrency increment). Was scoped once:
  candidate approaches = scoped `BEGIN IMMEDIATE` vs extending `run_write` coverage vs a hybrid. Real reliability work.
- **Workspaces-nav UX follow-up** (inc 280) — returning-user re-learning cost for moved tools; an experience-pass item.
- **per-attachment PDF serving** (#5 G-deferred) — Files currently opens the *primary* PDF; serve a chosen attachment.
- The **QA 2026-07-19 batch** above (browser-equipped).

## The backlog — what needs YOU (⛔ NEEDS CLIFF, §275–409) — plan WITH me, don't build unattended
- **#12 Critical-review supplement (multi-paper)** [gated — its own design; the #13 auditability bar is ratified].
- **#14 Permanent delete removes the on-disk PDF** [destructive — needs a confirmation flow + security audit].
- **Sync UI (SP3c)** — the accounts/sync arc (194–202) shipped the crypto+engine+server; the Settings→Sync setup/
  enable/conflict-review UI is the open slice [outward-facing].
- **#9 Tag-provenance design-level sub-tasks** [design] · **#11 README front-door expansion** [outward-facing] ·
  **#19 Tags↔findings retraction-surfacing** [blocked+design] · **#20 harness hardening (adopt `uv`)** [infra] ·
  **#21 packaging/distribution (Tauri shell)** [exploratory] · **superuser capabilities** [maintainer-deferred].

## Longer-horizon (only if the near-term clears)
- **Future tracks** (§410–786) — the 7 track docs in `.claude/docs/future-tracks/`.
- **Competitive-benchmark revisions** (§787–899).

---

## Suggested next-session opening move
If you want autonomous progress: **(a)** confirm inc 308 via a Codex QA re-run, then **(b)** pick the
**httpx→httpx2** migration or the **SQLite short-write BUSY fix** (both self-contained, high-value, no gate). If you
want a bigger feature: plan **Sync UI (SP3c)** or **#12 critical-review** *with me* (they're gated). Either way:
run the Principles alignment gate for any claim/signal feature, add a QA route + experience pass per surface, and
push → let CI be the full-suite gate.
