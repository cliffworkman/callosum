# Increment 332 — Backlog #30: wire beyond-library suggest into the LibreOffice adapter, fix doc drift

## Context
The user asked to tackle backlog #30 ("Track C SP2/Stage-3 — beyond-library suggest," framed as "the highest-
value unbuilt novel capability in the backlog"). Research before writing any code found this framing itself
was wrong: `app/backend/citations/beyond_library.py` already implements the entire capability — OpenAlex
`referenced_works`/`related_works`/citing-works graph expansion anchored on top in-library matches, plus
Crossref/PubMed/OpenAlex keyword search, every candidate carrying an explainable `reason`/`relationship_label`
(never a bare/citation-count score) — wired into `POST /citations/suggest` and the web Cite pane, and already
security-audited PASS (`.claude/security-audits/2026-07-11_beyond-library-citation-suggest.md`). It shipped inc
271/272 (2026-07-14/15) as one large uncredited Codex commit with no increment notes of its own, which is why
it never got folded back into `INCREMENT-BACKLOG.md`'s status line — a real doc-drift bug, not reality.

Given this, the user chose the "cleanup + LibreOffice wiring" path over building something already built. This
increment: (1) wires the already-shipped engine into the LibreOffice adapter, whose "Suggest citations" macro
had never called the beyond-library path at all, and (2) fixes the doc drift this discovery surfaced.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`fetch_suggestions`** signature/return changed: gained `include_beyond_library: bool = False`,
  `beyond_top_k: int = 5`; now returns `{"suggestions": [...], "beyond_library_suggestions": [...]}` (was a bare
  in-library list). Matches the same opt-in-each-time consent model the web Cite pane's checkbox already
  established — `include_beyond_library` defaults False and is never silently turned on or persisted.
- **`build_beyond_suggest_rows(items)`** (new): one pick-list row per beyond-library candidate — author/year/
  title plus its `relationship_label` (preferred) or `reason`, prefixed `[beyond library]` so it's never
  confused with an in-library row.
- **`save_beyond_library_item(base, item)`** (new): `POST /discovery/save` — the exact same write path the web
  app's own "Add to library" button uses (metadata-only, server-deduped, safe to call twice).
- **`_suggest_dialog`** (new, replaces `_suggest_listbox` — deleted, its only caller): a pick-list with an
  "Also search beyond my library" checkbox, unchecked by default. Checking it triggers a live re-fetch
  (`XItemListener`, the same live-toggle mechanism Phase 5a's text listener established) that merges in
  beyond-library rows. Returns `(kind, item)` — `"library"` inserts directly; `"beyond"` saves-then-cites.
- **`suggest_and_insert`** rewritten around `_suggest_dialog`; no longer short-circuits on an empty in-library
  list before the user gets a chance to opt into searching further (a user with no in-library matches yet can
  still find something via the checkbox — a real behavior improvement, not just a refactor).

## A genuine empirical finding
Unlike Phase 5a's `edit_ctrl.setText()` reliably firing `XTextListener.textChanged`, a programmatic
`checkbox.setState()` does **NOT** fire `XItemListener.itemStateChanged` in this LibreOffice version — standard
UNO/AWT behavior (fires on a real user click, not a scripted mutation), not a bug, and not headlessly
synthesizable. This applies **retroactively** to the already-shipped Phase 5b/5c Options dialog's suppress-
author/author-only mutex checkboxes, which rely on the identical mechanism and were never spike-verified for
exactly this reason — folded into the standing "composer needs a real human in real Writer" caveat.

## Tests
- **`tests/test_libreoffice_adapter.py`** (+5): `fetch_suggestions` posts the new fields and returns both
  lists, defensive-on-bad-shape updated for the new return shape; `build_beyond_suggest_rows` prefers
  `relationship_label` over `reason` and falls back sensibly; `save_beyond_library_item` posts the expected
  `/discovery/save` fields and defaults missing ones.
- **`selftest_uno.py::spike_beyond_library_checkbox_listener`** (new): `cc._post_json` monkeypatched to a
  deterministic fake response (never hits real Crossref/PubMed/OpenAlex — this offline-by-design harness must
  not depend on live third-party availability); proves the refresh-and-merge callback logic is correct by
  invoking it directly (the real click-to-callback wiring is the one thing this can't prove — see above).
- **`selftest_uno.py::spike_save_beyond_library_item_and_cite`** (new): a hand-built fake beyond-library item →
  real `/discovery/save` (local, no internet needed for a bare metadata-only save) → real `insert_citation` →
  confirmed rendered as `(Velickovic, 2018)`.
- One pre-existing regression caught and fixed: `main()`'s original inc-157 suggest→insert check called
  `fetch_suggestions` expecting the old bare-list return; updated to read `["suggestions"]`.
- 47 pytest passed (42 prior + 5 new). Real-UNO roundtrip: `SELFTEST OK`.

## Documentation/hygiene fixes (same increment, per rule #6)
- **`INCREMENT-BACKLOG.md`**: #30 marked closed with the correction explained; two stale cross-references
  fixed (#21's "when Track C SP2 lands" → "Stage-4"; the SP1 shipped-breadcrumb's "SP2 remains" → SP2 shipped
  too); a follow-up note added to the 2026-07-19 audit-pass header flagging this as the SAME class of drift
  that pass found elsewhere, with the root cause named (a commit with no increment notes of its own).
- **`integrations/README.md`**: was badly stale — listed the real, in-use `openalex`/`semantic_scholar`
  adapters as "planned, not yet implemented," and never mentioned `arxiv`/`biorxiv`/`core`/`doaj`/`europepmc`/
  `osf`/`retraction_watch` at all. Rewritten to describe what's actually implemented.
- **Removed `integrations/semantic-scholar/`** (hyphen, README-only stub) — confirmed unreferenced anywhere in
  code; a genuinely dead, confusing duplicate of the real `integrations/semantic_scholar/` (underscore).
  `grobid/`/`mendeley/` left alone — they're legitimately still-unbuilt placeholders, not stale duplicates.
- **`.claude/qa-routes/route_42_cite.md`**: confirmed via `build_surface_map.py check` that `37_cite.jsx` was
  already mechanically "covered" (file-level attribution), but the route's own steps never once exercised the
  beyond-library checkbox/cards — a real gap in what a QA run would actually catch, despite the gate passing.
  Added standing assertions (the egress-boundary distinction, reason/relationship-label requirement),
  adversarial cases (toggle-then-adversarial-input, rapid toggle), and steps walking through checking the box,
  reading a `BeyondSuggestionCard`, and using "Add to library."

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_composer.py tests/test_libreoffice_install.py
   tests/test_libreoffice_oxt.py -q` — 47 passed.
2. `python adapters/libreoffice/run_roundtrip.py` — `SELFTEST OK` (one transient soffice-startup retry, the
   known unrelated flake), all prior spikes plus both new backlog-#30 spikes.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. **NOT verified — flagged, not assumed**: the beyond-library checkbox has never been clicked by a real human
   in real Writer (see the empirical finding above — this is now explicitly true of BOTH the new checkbox and
   the Phase 5b/5c Options dialog's mutex checkboxes). Folded into the standing composer manual-verification debt.

## Gates
- **Security audit:** not a new stub — this reuses the ALREADY-audited `beyond_library.py`/`include_beyond_library`
  path and the already-audited `/discovery/save` write boundary exactly as designed; the LibreOffice adapter is
  just a new, consistent client of both, with the identical opt-in-each-time consent posture. No new endpoint,
  no new provider, no new egress channel.
- **Principles/A-A (rule #9):** unchanged — reuses the existing signal-not-verdict/candidates-not-auto-insert
  design wholesale; the checkbox default-off + per-call opt-in (never a persisted setting) was a deliberate
  choice to match the audited web behavior rather than invent a laxer standing-consent model for this client.
- **README:** `adapters/libreoffice/README.md`'s Suggest-citation item updated to describe the checkbox +
  save-then-cite flow.

## Next
Genuinely open for Track C: Semantic Scholar recommendations (new external fetch, audit-gated), a persistent
cache+dismiss surface (structurally different from what's shipped — a real design choice, not yet made),
Stage-4 section-scoping (needs GROBID + the plugin). The standing composer manual-verification debt (Phase
5a/5b/5c + this increment's checkbox) is still the most overdue open item across the whole LibreOffice adapter line.
