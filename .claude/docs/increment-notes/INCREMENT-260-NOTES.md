# Increment 260 — Citation-equity no-DOI hints made actionable (+ backlog reconciliation)

## Context — the finding that reshaped the task

The open backlog carried a *Medium* item (QA run 20260702, `route_51`): *"Citation-equity: the 'Find
overlooked work' control shows on a no-DOI paper but 422s"* — asking to hide/disable the audit +
overlooked-work controls on a no-DOI paper with an honest "needs a DOI" hint.

Investigating before changing (rule #7) showed **the functional gating already shipped.** The QA run that
filed the item ran on **2026-07-02**; the fix landed the next day in **inc 257's close-out sweep**
(`9b24076`, 2026-07-03 — "a no-DOI paper in Citation concentration now hides **both** run controls behind
an honest 'needs a DOI' hint"). The `08c` "How it's cited" tab had gated on `hasDoi` even earlier (inc 232,
`9ba8ef5`). So on current HEAD **all three DOI-dependent controls are already suppressed** on a no-DOI
paper, each behind an honest hint — the 422-on-click gap the backlog described no longer reproduces. The
backlog entry was simply never reconciled after inc 257.

The genuine remaining delta was an **experience gap (rule #11)**: the shipped hints explained the *why*
("…so OpenAlex can't resolve its references") but **dead-ended** — they told the user the tool couldn't run
without telling them what to *do* about it. That matched the exact refinement confirmed in the plan preview:
make the hint actionable ("Add one in the Detail pane to enable"). A correct signal with no path to the
action it implies is precisely the failure mode rule #11 exists to catch.

## Implemented

Made the three no-DOI hints **actionable** — each keeps its honest, service-specific *why* and appends the
forward path in the app's own vocabulary (the DOI field lives **"under Identifiers"** in the Detail pane —
matching the existing `25_detail.jsx:420` "Add its DOI under Identifiers…" copy):

- `app/frontend/js/08b_methods_citation_equity.jsx`
  - **Citation concentration / Run audit** (no-DOI state): *"This paper has no DOI, so OpenAlex can't
    resolve its references. **Add one under Identifiers in the Detail pane to enable this audit.**"*
  - **Find overlooked work** (no-DOI state): *"This paper has no DOI, so OpenAlex can't relate work to it.
    **Add one under Identifiers in the Detail pane to enable the overlooked-work search.**"*
- `app/frontend/js/08c_methods_citation_context.jsx`
  - **How it's cited** (no-DOI state): *"This paper has no DOI, so Semantic Scholar can't look up its
    citation graph. **Add one under Identifiers in the Detail pane to enable it.**"*

Docs / hygiene:
- `.claude/qa-routes/route_51_methods_citation_equity.md` + `route_53_citation_context.md` — updated the
  quoted hint strings to the new actionable copy (the routes assert the exact hint text).
- Removed two stray atomic-write temp artifacts left by an interrupted prior edit
  (`route_51_…md.tmp.16084.*`, `route_65_…md.tmp.16084.*` — both stale pre-update copies; the real routes
  are current).
- `.claude/docs/INCREMENT-BACKLOG.md` — removed the stale "Find overlooked work … 422s" item (shipped inc
  257, actionable-hint polish inc 260). The DONE ledger was maintained only through inc 152, so the
  "what landed / which increment" record for this item lives here + in `changes.md` (per that file's own
  header) rather than forcing a lone new section into the stale DONE file.

Rebuilt `callosum-app.html` via esbuild (all three new strings verified present in the bundle).

## Key technical detail

No behavior/logic change — this is copy only. The gating conditions were already correct:
- `08b` shares one `meta = { title, hasDoi }` fetch (`GET /papers/{id}`) from `CitationEquitySection` down
  to both `CitationEquityPaper` (audit) and `OverlookedWork`, so both controls gate off a single source of
  truth; the run buttons render only under `meta.hasDoi` / `hasDoi`.
- `08c` fetches its own `meta` and renders the Fetch button only under `meta.hasDoi`.

The hints reuse the existing `.tag-suggest-empty` class verbatim — **no CSS/token change**, so rule #8 is
not triggered. The DOI is a real editable field (`25_detail.jsx:445` `IdentifierRow fieldKey="doi"`;
backend `metadata/paper_edits.py:88` accepts `doi` edits), so the "add one in the Detail pane" guidance
points somewhere the user can actually act — verified before writing the copy.

## Gate summary

- **DESIGN (rule #8):** not triggered — no CSS/inline-style change (existing empty-state class reused).
- **Principles (rule #9):** aligned. This does not add a claim/signal; it makes an honest *limitation*
  disclosure actionable. "Silence is not a certificate" / "defaults are the user's" — the tool says what it
  can't do **and** how to make it possible, rather than dead-ending. No misaligned path (the easy version
  was to leave the hint as-is).
- **QA (rule #10):** no new surface (existing no-DOI view-states, already covered by `route_51`/`route_53`);
  surface-map `check` clean (203/203 API + 965/965 FE, 0 uncovered). Route quoted-string assertions updated.
- **EXPERIENCE (rule #11):** this change *is* the experience-pass fix — a dead-ending correct signal made to
  point at the action it implies. No further persona dispatch needed for a copy-level nudge.
- **Help corpus:** no impact (polish to an existing hint, not a new/renamed control or workflow) — same
  class as the inc-257 gating entry; no `HELP-DOCS-SYNCED` marker moved.

## Manual verification script (port 8888)

1. Start the app; open a paper that has **no DOI** (or clear a paper's DOI under Detail → Identifiers).
2. THEORY pane → **Cite** section → **Citation concentration** tab. Confirm: **no Run audit button**; the
   hint reads *"…can't resolve its references. Add one under Identifiers in the Detail pane to enable this
   audit."* Scroll to **Overlooked work**: **no Find overlooked work button**; hint ends *"…Add one under
   Identifiers in the Detail pane to enable the overlooked-work search."*
3. **How it's cited** tab: **no Fetch button**; hint ends *"…Add one under Identifiers in the Detail pane to
   enable it."*
4. Add a DOI under Detail → Identifiers (🔎 to resolve). Return to the Cite tabs → the **Run audit** /
   **Find overlooked work** / **Fetch** buttons now render (the hint is gone). The path the hint promised
   works end-to-end.

## Pytest

`pytest --ignore=tests/test_mcp_server.py` → **1032 passed, 1 skipped** (unchanged from inc 259 — a
frontend copy change touches no Python; the optional `mcp` suite is not installed).
