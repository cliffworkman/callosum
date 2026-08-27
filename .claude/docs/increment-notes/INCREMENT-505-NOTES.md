# Increment 505 — Feed-suggestion bug fixes + Title-Case/control-height retrospective sweeps (backlog #59/#60)

## Implemented

### Two Feed-suggestion bugs (found live right after inc 504 shipped)

- **My Publications axis suggested as a followable topic.** `FeedSuggestModal`'s `GET /axes` fetch
  (`app/frontend/js/30g_feed_suggest.jsx`) now filters `a.kind !== "my_publications"` before the list reaches
  either the bioRxiv/medRxiv Categories tab or the PubMed Search tab — the My Publications axis tracks the
  user's own papers, not a research topic to match a category against or follow as a search query.
- **"others"/"et al." suggested as a followable author.** Real CSL-JSON author data sometimes contains a
  placeholder literal instead of a real name (an upstream-metadata artifact, not something Callosum invents).
  `suggest_authors_to_follow` (`app/backend/clustering/followed_authors.py`) gained a small denylist
  (`_NON_NAME_AUTHOR_TOKENS = {"others", "et al", "et al.", "and others", "anonymous"}`) checked in the same
  per-name loop as the existing self/already-followed exclusions. `tests/test_feed.py`'s
  `test_suggest_authors_endpoint_ranks_by_frequency_excludes_self_and_followed` extended with a seeded paper
  whose `csl_json.author` includes `{"literal": "others"}`/`{"literal": "Et al."}` and an assertion neither
  ever appears in the response.

### Backlog #59 — Title-Case retrospective (DESIGN.md rule, 2026-08-27)

Swept every `<button>`/`<option>`/toggle-label/standalone `.btn-link`-styled `<a>` control across
`app/frontend/js/*.jsx` for Title Case compliance, following the rule DESIGN.md gained in inc 504 ("Mark All
Read," not "Mark all read" — control labels only, prose untouched). ~60 individual strings across ~50 files.
Two entire files had been missed by inc 504's own partial pass and got a first-time sweep here:
`10k_wip_checks.jsx` (6 WIP-checklist action buttons — "Create Checkpoint," "Check Transparency," "Audit LMM
Reporting," etc. — plus 3 `labels={{first, again}}` pairs and 2 "Open Source File" links) and
`35d_citation_styles.jsx` (5 buttons — "Edit Source," "Duplicate to Edit," "Use as Application Default," "Check
for Updates," and the "View Source" link).

Representative fixes across the rest of the sweep: dropdown option text (`10_pdf_layer.jsx`'s field/type/sort
selects, `10h_wip_filters.jsx`'s ~18 filter options, `30d_discover.jsx`'s "Recent Searches"/"Clear History"/"All
Sources"/"Saved for Later"), single-word `.axis-link`/`.btn-link` action buttons that had escaped every prior
pass ("save"→"Save," "open"→"Open," "delete"→"Delete," "merge"→"Merge," "clear"→"Clear," "cancel"→"Cancel,"
"remove"→"Remove," "reprocess"→"Reprocess," "summarize"→"Summarize," across `08x_methods_critical.jsx`,
`10_pdf_layer.jsx`, `15_axes.jsx`, `19_duplicates.jsx`, `25c_urls.jsx`, `26_wanted.jsx`, `26b_text_health.jsx`,
`27_scan.jsx`, `31_mypubs_dashboard.jsx`, `33_mypubs_pubs.jsx`, `45_workbench.jsx`), and status-styled-but-live
buttons the user explicitly asked to include (e.g. `05_method_credit.jsx`'s disabled/terminal
"✓ Added to Library," not just its active "+ Add Missing to Library" sibling).

**Two deliberate, documented exceptions** (both confirmed live, not silently applied):
1. **Fixed-stylization domain terms** keep their own established casing rather than being force-capitalized:
   `p-curve` (lowercase p, matches CLAUDE.md's own usage), `statcheck` (all lowercase — its own tool name,
   same treatment as `bioRxiv`/`medRxiv`), `metafor` (the R package's own lowercase name, `45_workbench.jsx`'s
   export button), `RevMan`/`CSV` (already correctly cased acronyms, untouched), `Z-curve` (capital Z, matches
   CLAUDE.md's "Z-curve 2.0").
2. **Long, sentence-like toggle/checkbox labels** stay as prose — a user-confirmed call (asked via
   AskUserQuestion) after finding ~8 candidates like "Let an AI agent edit your library" and
   "Expand beyond expected sections when bounded search is weak": these read as explanatory sentences, not
   click targets, so recasing them would fight the DESIGN.md rule's own prose carve-out. The user separately
   confirmed the *opposite* call for status-styled action buttons/spans (recase all of them, including
   disabled/terminal states) — a distinct category from long-sentence labels.

Inline metadata-line links (e.g. a lowercase "source"/"notice" mention inside a `· label: value` provenance
row in `08j_reference_integrity.jsx`/`08m_funding_results.jsx`) were left as prose — distinct from a standalone
`.btn-link`-styled action link at the end of a card (which *was* recased, e.g. `08x_methods_critical.jsx`'s
"Notice" link), the same reception-context judgment DESIGN.md already applies elsewhere.

### Backlog #60 — Control-height retrospective (DESIGN.md `--control-h` token, 2026-08-27)

Extended the `--control-h: 32px` fix inc 504 applied only to `.searchbar` to four more input+button row
containers with the identical box-sizing/padding mismatch bug, each with a scoped rule (never the shared
`.btn-primary`/`.btn-ghost`/`.lib-sort` base classes, which are reused in dozens of unrelated contexts):

- `.wip-root-form` (`10f_wip.jsx`)
- `.mypubs-pubs-controls` (`33_mypubs_pubs.jsx`)
- `.grim-form` (`07_methods_grim.jsx`)
- `.es-form` (`08i_methods_effectsize.jsx`)

Each got `<container> <input-class>, <container> .btn { height: var(--control-h); box-sizing: border-box; }`
plus a `.btn` flex-center rule, scoped so the base input classes' *other* reuse sites stay untouched.

**Two candidate containers audited and deliberately left unfixed:**
- `.credit-author-head` (`38_credit.jsx`) — pairs a text input with a compact `.btn-icon` remove button,
  already one of DESIGN.md §3 #5's documented intentional compact variants; forcing alignment would fight
  established precedent rather than fix a bug.
- `.scan-row` (`28_import.jsx`, `28b_bundle.jsx`) — a native `<input type="file">` paired with a `.btn`. A
  browser's own file-picker chrome isn't reliably restylable to a fixed height across browsers, and the row's
  own `align-items: center` already keeps it visually sane despite the height difference — this is native
  control chrome, not the CSS-controllable mismatch `--control-h` exists to fix.

## Key technical detail

The sweep repeatedly surfaced the same failure mode: `pytest tests/test_frontend_assembly.py` asserts literal
control-text strings, so every genuine rename broke its own matching assertion. Rather than a mechanical
find-replace across the test file, each failure was individually confirmed as either (a) a correct rename with
a stale test string (fixed the test) or (b) a genuine sweep gap the earlier pass had missed (fixed the source,
then the test) — this is how `10k_wip_checks.jsx` and `35d_citation_styles.jsx` were discovered as entirely
missed files: their button text was still lowercase in the source, but no test asserted the *old* text either,
so a first grep-based audit (`>[a-z][a-zA-Z]*(\s...)?</button>` etc. across `app/frontend/js`) was needed to
find them, rather than relying on test failures alone.

## Manual verification script

1. `python tools/build_frontend.py`, start the app.
2. Discover → Feed → Suggest → PubMed Search tab: confirm "My Publications" is absent from suggested queries.
3. Discover → Feed → Suggest → Author tab: confirm "others"/"et al." never appears; top suggestion is a real
   author name.
4. WIP → any manuscript → Checks tab: confirm all 6 action buttons read in Title Case ("Create Checkpoint,"
   "Check Transparency," etc.) and "Open Source File" links are Title Case.
5. Settings → Citation Styles: confirm "Edit Source," "Duplicate to Edit," "Use as Application Default," "Check
   for Updates," "View Source" are all Title Case.
6. WIP → any manuscript's root form, My Publications → Publications tab, Methods → GRIM, Methods → Effect Size:
   confirm the input/select/button row in each sits at one consistent height (no visible step between
   controls).
7. CRediT tab: confirm the compact author-name-field + remove-icon row is unchanged (intentionally not
   height-unified).

## Pytest

`pytest tests/test_frontend_assembly.py -q` → 79 passed.
`pytest tests/test_feed.py -q` → 19 passed (incl. the extended author-exclusion test).
`pytest tests/test_funding_discovery.py -q` → 28 passed (one stale Title-Case string assertion fixed).
Full suite `pytest -n 4 -q` → 2531 passed, 3 skipped (one pre-existing flaky-worker rerun aside; see the
`pytest-xdist-worker-crash-flakiness` memory note).
