# Increment 163 — "Coming soon" accordion placeholders (a visible roadmap)

**What the user asked for:** preemptively scaffold the planned THEORY/METHODS accordion sections + subsection tabs
into the GUI as placeholders — "mostly to keep me psyched about all of the stuff we're gonna build." Done honestly:
each stub names a **real, backlog-tracked** capability, placed by the DESIGN §5 cognitive-task rubric, with the
principle framing it'll ship with baked in, and **inert** (no controls/data — "silence is not a certificate").

## Implemented (frontend-only)

New chunk **`app/frontend/js/09_placeholders.jsx`** (loads after the registry at 05 + the METHODS sections at
06–08, so it can append a tab to the shipped Statistics check):

- A small **`<ComingSoon title body builds/>`** component (an `--accent-soft` "Coming soon" badge + title + body +
  a "builds on / Backlog #…" line).
- **THEORY → Discover** *(new section, `order: 30`)* with three coming-soon **tabs** — **Beyond library** (#30 SP2:
  cites/cited-by + topic-related via OpenAlex/Semantic-Scholar, explainable reasons, ranked by relevance not raw
  citations), **Feed** + **Search** (#28 Feed/Search track). Demonstrates the subsection-tab pattern.
- **METHODS** *(new sections after Review @40, ordered by cognitive task)* — **Mixed-model reporting** (`50`, #23),
  **Bayesian statistics** (`60`, #24), **Meta-analysis** (`70`, #37 — extract/structure, never pool), **Citation
  equity** (`80`, #25 — identity-agnostic, descriptive, never an accusation).
- **METHODS → Statistics check** gains a **"More checks"** tab (#27: more NHST forms + p-curve) — appended to the
  **shipped** `statcheck` section via `registerPaneTab` (find-or-create by id), **without editing
  `06_methods_statcheck.jsx`**. The section now shows a `[Statistics check | More checks]` strip.

CSS: a `.coming-soon*` recipe in `styles.css` (tokens only — `--accent-soft` badge + muted body; rule #8).
DESIGN.md §5 gained a "Coming soon placeholders" convention note (the 4 honesty requirements + the recipe).

**Deliberately NOT stubbed:** the where-to-submit tool (#40) — it's authoring-support, not "evaluating how a paper
was studied," so it'd break the DESIGN §5 placement rubric; the Word/Google-Docs adapters — those are external,
not accordion sections.

## Gates

- **Principles (rule #9):** non-triggering — the stubs produce no claim/signal (inert roadmap UI). But they
  *advertise* future signal-producing features, so each description bakes in the charter framing
  (signal-not-verdict; "never a 'BF > 3' verdict"; "descriptive, never an accusation"; "extracts, never pools") so
  the roadmap can't promise something misaligned. On rule #5 (no dead code): these are **intentional, labeled
  roadmap UI**, not accidental dead code, and DESIGN §5 mandates removing each stub in the increment its real
  feature lands.
- **DESIGN (rule #8):** tokens-only `.coming-soon*`; placement by the cognitive-task rubric; convention documented.
- **QA (rule #10):** the stubs are inert (no interactive controls; the accordion headers/tabs are PaneAccordion's,
  covered by route_00) → **no new QA surface** (surface **113/113 API + 597/597 FE, 0 uncovered**, unchanged).
- **Experience (rule #11):** the point *is* the experience — a visible roadmap that's honest about what's stubbed.

## Manual verification

**Headed, no egress** (`.local/visual/drive_inc163_placeholders.py`): THEORY → Discover shows
`[Beyond library | Feed | Search]` tabs (Feed tab content confirmed); METHODS → Bayesian shows a "Coming soon"
badge + title; Statistics check shows the `[Statistics check | More checks]` strip (the shipped statcheck intact);
0 console/page/genai.

## Pytest

**601** unchanged (frontend-only; `test_frontend_assembly.py` confirms the new chunk is in the build + the build
is in sync). `ruff` clean; build + assembly green; no migration; no new dependency.

## Next
The user's roadmap: **Word add-in (Office.js)** → then **Google Docs via an authenticated clffwrkmn.net relay**
(its own design-led increment: a tunnel + auth/rate-limiting on callosum + the add-on). Plus the carried
`40_app.jsx` 630/600 split (rule #1). (And the user may name more placeholder sections to add.)
