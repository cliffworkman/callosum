# Increment 339 — Backlog #26: CRediT builder UX follow-ups (role presets + "and" formatting + discoverability)

## Context
Next in the 12-item decision queue. Three follow-ups from the inc-261 experience pass: (a) per-author role
presets — highest-value, but flagged as needing a principles beat first; (b) an opt-in "and" before the last
by-role name; (c) discoverability (CRediT was hard to stumble on). Cliff's answer for (a) was explicit: "build
presets anyway, skip the discussion" — with my own commitment at decision time to still run a quick internal
Principles check while designing them, even without a separate discussion round.

## Principles check (rule #9), run as committed
**Principle touched:** #3 (facts vs. candidates never conflated), #5 (the human is the filter), #9 (defaults
are the user's) — plus `methods/credit.py`'s own load-bearing boundary ("build, never infer... the human is the
source of truth; Callosum only formats"). **Misaligned path:** a preset that reads as Callosum *asserting* a
role bundle — e.g. auto-applying a guess at "who's probably the PI" from author order, a dimmed/pending visual
state implying a suggestion to accept/reject, or persisting a "preset-sourced" marker that would make a
preset-derived role look more authoritative than a hand-clicked one. **Aligned design (built):** a preset button
produces the byte-for-byte SAME `roles` object state a manual multi-click would — no new field, no visual
distinction from a hand-toggled chip, always an explicit click (never auto-triggered, never pre-selected for
any author), and immediately as editable/removable as any chip. It's pure client-side convenience — the
backend's `format_statement`/`NO_INFERENCE` boundary is completely untouched by this feature.

## Implemented
- **(a) Role presets** — `app/frontend/js/38_credit.jsx`: `CREDIT_PRESETS` (First author / PI / Collaborator,
  the three names the backlog itself specified) + `applyPreset(i, roles)` — toggle-all-or-fill-gaps semantics
  (if every bundled role is already assigned, clicking removes them all; otherwise it adds only the missing
  ones, leaving already-set roles/degrees untouched). Zero backend change — role assignment was already 100%
  client-side, so this couldn't touch the audited "build never infer" boundary even if it tried to.
- **(b) "and" formatting** — `app/backend/methods/credit.py`: `_join_names(names, *, use_and)` (Oxford-comma
  join for 3+, plain "and" for exactly 2, unchanged `, `.join for the default-off case), wired into
  `format_statement`'s **by-role** contributor-name join only (the by-author per-author role-list join is a
  different join entirely and is untouched — matches the backlog's own scoping to "by-role lines"). New
  `use_and: bool = False` request field (`routers/credit.py`), opt-in, default off. Frontend: a checkbox shown
  only in the By-role view (it has no effect on By-author), persisted as a global `localStorage` preference
  (`callosum.credit.useAnd` — a formatting choice, not per-paper content unlike the authors×roles grid).
- **(c) Discoverability** — a jump-link from Discover → Journals ("Where to submit") to Work → CRediT.
  `40_app.jsx`: `openCreditBuilder` (mirrors the existing `openReferenceWarnings`/`openSynthesisWorkspace`
  jump-callback pattern exactly — `requestWorkspaceTab("work", "credit")` + `selectWorkspace("work")`), exposed
  on `workspaceCtx` (both Discover's `PublishersPanel` and Work's `CreditSection` already receive the same
  shared ctx object, so no new plumbing was needed). `08e_methods_publishers.jsx`: one link line, gated on
  `ctx.onOpenCreditBuilder` being present.

## Key technical detail
The backlog's "item ~5 in the accordion" framing for (c) was stale — a later reorg (inc 280) moved both CRediT
and PUBLISHERS out of the old THEORY/METHODS accordion entirely, into top-level workspace sub-tabs (Work →
CRediT; Discover → Journals). The actual jump is cross-workspace, not cross-accordion-section — caught by
reading the current registration code rather than trusting the backlog's description, avoiding designing a
mechanism for a UI structure that no longer exists.

## Tests
- `tests/test_credit.py` (+3): `_join_names`'s two/three+-name cases and the default-off/opt-in split; the
  by-role-only scoping (by-author output identical whether `use_and` is on or off); the endpoint's `use_and`
  field end-to-end.
- `tests/test_frontend_assembly.py`: 46 passed unchanged after the preset/checkbox/jump-link JSX landed.
- **Live browser verification** (Playwright, against the maintainer's real day-to-day testing instance — a
  standing permission, not a scratch fixture): confirmed the three preset buttons render and toggle correctly
  end-to-end (a real POST to `/credit/statement` producing "Ada Lovelace: Conceptualization, Formal analysis,
  Investigation, Methodology, Writing – original draft."); confirmed the "and" checkbox only appears in By-role
  view; confirmed the Journals → CRediT jump-link actually switches workspace + tab. One real finding along the
  way: the `use_and` backend logic initially appeared not to work live — turned out to be a stale long-running
  uvicorn process (Python doesn't hot-reload; the pytest suite, which imports fresh code, already confirmed the
  logic correct) — resolved by a server restart, not a code fix.

## A process note, not a code one
While cleaning up test data from the live-browser pass, an over-broad `localStorage` clear
(`key.startsWith('callosum.credit.')`) removed every CRediT scratchpad key, not just the one created during
this verification — risking the user's own saved drafts for other papers, not just the test entry. Confirmed
harmless this time (the instance is testing-only, nothing load-bearing), but flagged immediately and recorded
as a standing lesson: scope any test-data cleanup to the exact item(s) created, never a prefix/pattern match.

## Manual verification script
`.claude/qa-routes/route_66_credit.md` steps 9-11 (role-bundle toggle-all/fill-gaps behavior; the "and" checkbox
scoped to By-role and its two/three+-name formatting; the Journals→CRediT jump-link).

## Gates
- **Security audit:** not triggered — no new endpoint (one existing endpoint gained one optional bool field),
  no new persistence, no new external fetch. `use_and` is validated by Pydantic's `bool` type coercion (rule #4
  is satisfied by construction — no free-form input).
- **QA coverage:** `tools/qa/build_surface_map.py check` — unaffected (no new API surface); `route_66_credit.md`
  extended for the three new FE controls.

## Backlog
**#26 closed** (`INCREMENT-BACKLOG-DONE.md`).

## Next
Remaining in the 12-item queue: #14 (permanent-delete + on-disk PDF removal, security-audited), #15 (sync_server
hardening code), #20 remainder (pre-commit/uv/CI/branch protection), #21 (packaging/distribution exploration).
