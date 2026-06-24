# QA-POLICY.md — the callosum QA contract

This is the charter for callosum's automated QA mechanism. **CLAUDE.md rule #10 points here.**
Like `DESIGN.md` (CSS) and `PRINCIPLES.md` (claim/signal features), this file is the gate you read
before the relevant class of change — here, **anything that adds or alters an end-user surface.**

The mechanism has three moving parts:

1. **A computed surface map** (`tools/qa/build_surface_map.py`) — every API route + every interactive
   frontend element, extracted from source. Coverage is a *computed property*, not a discipline.
2. **QA routes** (`.claude/qa-routes/route_NN_*.md`) — self-contained scripts a headless agent (Codex
   `exec`) traverses, each declaring which surfaces it covers and asserting both behavior **and** the
   project's honesty invariants.
3. **A supervisor + a watched deposit inbox** (`tools/qa/supervisor.py` → `.claude/qa-inbox/`) — the
   supervisor dispatches routes to Codex with no human nudging; results (markdown + screenshots) land
   in the inbox, which a Claude Code session triages and acts on (Session-kickoff hook).

---

## Why callosum QA is not renovatr QA

renovatr QA is dominated by a production-safety contract (excluded real tenants, disposable `prodqa-*`
tenants, `PRODQA` sentinels, revert-after-mutate). **callosum has none of that to protect:** it is
local-only (`127.0.0.1`), single-user, no auth, and the library is disposable. So that whole layer is
**deleted**, not ported. Its only legitimate residue is the **fixture contract** below.

---

## The fixture contract (the one safety rule)

QA **never** runs against the real library (the user's Dropbox `library/` + their working
`validation.sqlite`). Every QA run:

- spins up the real `app.backend.api.app:app` against a **freshly migrated + seeded throwaway SQLite DB**
  on a **free port** (the exact pattern in `tests/e2e/test_smoke.py`: `command.upgrade(config, "head")`
  then `tests.api_helpers._seed_library`), and
- tears it down at the end.

"Disposable" means safe to *mutate* (delete-forever, empty-trash, purge — go ahead). A deterministic
seed is what makes findings *reproducible*. Both properties are required; they are not the same property.

**Pin the seed.** A change to `_seed_library` is a deliberate, reviewed event — QA reproducibility
depends on it.

---

## The coverage contract (the "no stone unturned" guarantee)

`python tools/qa/build_surface_map.py check` diffs the surfaces declared by the QA routes against the
surfaces that actually exist.

- **API surfaces are a hard gate.** An uncovered route fails `check` (and CI). Static extraction of the
  routers is authoritative (bare `APIRouter()`, absolute paths), so there is no excuse for an unmapped
  endpoint.
- **Frontend surfaces are a checklist.** Static JSX analysis can't resolve a handler to its behavior, so
  uncovered interactive elements are *reported* but don't fail the build unless `--strict-fe` is set. The
  point is that nothing is *invisible* — a new `<button onClick=…>` shows up in the report so a route
  author acknowledges it.

### When you MUST add or extend a QA route

Add a new route, or extend an existing one's `qa-coverage` block + steps, whenever you land:

- a **new API endpoint** or a changed request/response contract,
- a **new interactive control** (button, editable field, dropdown, toggle, drag affordance),
- a **new view-state** (a new filter/mode/panel/tab the user can reach),
- a **new async job** (synthesis, score, suggest, dedup, scan, import, recheck, domains, summary, …) —
  these are the highest-value adversarial targets (navigate away mid-job, double-submit).

This belongs in the **same increment** as the feature, exactly like CLAUDE.md rule #6 (keep CLAUDE.md
current) and rule #8 (read DESIGN.md). Shipping a surface without a route is the QA analogue of drift.

---

## The honesty-invariant assertions (what makes this QA worth running)

Generic QA asks "does the button work." callosum exists to keep a set of **honesty invariants**, and QA
must test *those*, because a build can pass every click check while quietly violating them. Every route
that touches the relevant surface MUST assert:

- **Egress gate (Core invariant #3).** Run with `CALLOSUM_ALLOW_DATA_EGRESS` **unset**. Capture all
  outbound network requests (Playwright `page.on("request")`). **Any** request to a Gemini/`generativelanguage`/
  genai host with egress off is a **Critical** finding. This converts "egress is off by default" from a
  hope into a per-run test.
- **Coordinate honesty (Core invariant #2).** A citation labeled `exact` draws a bbox rect; `region`
  scrolls + shows the approximate note; `null` opens the page (if known) and draws nothing. An approximate
  or absent location rendered as an exact highlight is **Critical**.
- **Verification always shown (Core invariant #4) / signal-not-verdict (PRINCIPLES #2, #7).** Confidence,
  quote, and page are visible on every citation; no surface presents a hidden composite "reproducibility
  score" or a "bad papers" verdict (statcheck/axes are filters + counts, never ranks). A hidden composite
  or an accusation is a **High/Critical** finding against the no-accusation veto.

A QA finding of a security class (a reachable server-side folder read, an egress leak, a file-path
traversal) does **not** get fixed ad hoc — it opens a `.claude/security-audits/YYYY-MM-DD_<feature>.md`
stub per the existing audit gate. QA feeds the audit discipline; it doesn't duplicate it.

---

## Severity rubric (reused from renovatr — it's good)

- **Critical** — data loss, an invariant violated (egress leak, fake-exact highlight), a crash, a control
  that cannot be completed through the UI, a 500.
- **High** — a core flow broken or silently failing, a wrong result shown as correct.
- **Medium** — a confusing flow, missing feedback after an action, a recoverable error with a bad message.
- **Low** — minor UX papercut, inconsistent terminology.
- **Visual** — misalignment, overflow, truncation, contrast, responsive break.

**Console-error budget is zero** on every route (the `tests/e2e` norm, generalized). A console error is at
least Medium; a page error is High.

---

## The deposit + triage loop (how dev monitoring drops)

- The supervisor writes each route's result to `.claude/qa-inbox/<run-id>/route_NN_<name>.md` plus
  `screenshots/`, and a `run-summary.md` that **leads with Critical/High only** (everything else collapsed),
  so the inbox never trains you to ignore it.
- `.claude/qa-inbox/` is **gitignored, local-only** (a dropzone, like `future-tracks-import/`).
- **Session-kickoff (CLAUDE.md):** glance at `.claude/qa-inbox/`. For each unprocessed run: triage by
  severity; fix Critical/High in-session; file Medium/Low into `INCREMENT-BACKLOG.md`; open audit stubs for
  security-class findings; then move the run to `.claude/qa-inbox/_processed/`.

---

## Run cadence (keep it cheap; escalate deliberately)

- **Tier 0 — read-only smoke** (every surface renders, every control is clickable, 0 console errors): cheap,
  zero-noise, pass/fail. CI cadence + before any release.
- **Tier 1 — local stateful flows** (no egress): the bulk of the routes. On demand / weekly / when a
  feature lands in that area.
- **Tier 2 — egress-gated + external-fetch flows** (synthesis, My Publications, acquisition, help assistant):
  run hermetic by default (inject a fake generator/Crossref client — the app already supports
  `create_app(...)` injection); reserve a real-provider pass for explicit integration checks.

The route number `NN` encodes complexity order; the supervisor runs ascending and lets Tier 0 gate the rest.

---

## The anti-goal

The failure mode is **noise + spend**, not under-coverage. A supervisor that files 40 Low/Visual findings a
pass defeats the "reduce dev monitoring" goal. Keep Tier 0 as the default loop; make deep passes occasional;
keep the summary Critical/High-first. The durable value is the **coverage gate + the catch-and-escalate
reflex**, not the size of the report.
