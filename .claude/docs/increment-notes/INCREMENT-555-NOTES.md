# Increment 555 Notes — changelog-driven drift gate for the demo/showcase + whole-demo currency audit

## Outcome

Two related deliverables, both explicitly requested by Cliff in the same message: (1) a mechanism that
uses callosum's own increment numbering to catch the online demo and showcase website drifting out of sync
with real app functionality, as a **hard CI gate** with an **explicit-decline** escape hatch; and (2) a
thorough, all-6-stage currency audit of the online demo (Discover/Read/Evaluate/Synthesize/Write/Audit),
fixing what was cheap in-session and backlogging the rest with evidence.

## 1. The changelog-driven drift gate (`tools/qa/changelog_drift.py`)

A new shared module gives both existing coverage tools (`check_website_coverage.py`,
`check_demo_experience_coverage.py`) increment-number-aware staleness detection, on top of their existing
content-hash fingerprinting:

- `latest_increment_number()` — the max of the topmost `## YYYY-MM-DD — Increment N:` header in
  `.claude/changes.md` and the highest `INCREMENT-N-NOTES.md` filename in `.claude/docs/increment-notes/`.
  `changes.md` is confirmed to lag the real increment count in practice, so trusting it alone would
  understate drift.
- `staleness_errors(review, *, label, current_fingerprint, grace_increments=1)` — the demo tool's
  grace-windowed check: passes if the fingerprint hasn't moved, or an active decline covers the current
  increment, or the increment delta since the last review is within the grace window (tolerates one
  increment's worth of same-session drift so a push that lands both a source change and an increment bump
  doesn't fail against itself). Fails closed if no `reviewed_increment` baseline exists at all.
- `decline_covers(review)` — a standalone primitive (`declined_increment is not None and
  latest_increment_number() <= declined_increment`), used **directly** by the website tool so its original
  zero-grace "any fingerprint drift fails instantly" posture is preserved exactly, with decline-awareness
  layered on top rather than routed through the coarser delta logic.
- `decline_banner(review, *, label)` — printed whenever an active decline is the reason a check is passing,
  so a decline can never go quietly missing from CI output.

**Explicit decline, not a silent bypass** (added mid-design per Cliff's own requirement: *"we should build in
the ability to bypass the gate in the event it's needed, but this should be an explicit decline... we should
err on the side of trying to keep the showcase and demo up-to-date, forcing an explicit decline otherwise"*):
both tools gain `--decline --note "<reason>"`, writing `declined_at`/`declined_rev`/`declined_increment`/
`decline_note` **alongside** (never instead of) the last real `reviewed_*` fields — modeled on the existing
`excluded_qa_routes` pattern in `showcase-coverage.json` (mandatory reason, auditable, never silent). A
decline only covers drift up to the increment it was declined at; the next new increment reopens the gate.

**Asymmetric posture, by design:** the website tool keeps its pre-existing zero-grace instant-fail-on-any-
fingerprint-drift check over a narrow, human-curated glob (`app/frontend/{index.html,styles.css,js/*.jsx}`,
`help_content.md`, the word-processor adapters, `tui/`, `mcp_server/`) — just decline-aware now. The demo
tool gets **only** the coarser grace-windowed increment check, over a deliberately different, broader glob
(`app/backend/api/routers/*.py` + `tools/demo/*.py`) that a zero-grace gate would fail on almost every push.

**A real pre-existing bug fixed alongside this**: `check_website_coverage._source_files()`'s glob was
`adapters/google_docs/**/*` — the real directory is `adapters/googledocs/`, so Google Docs adapter edits had
never once contributed to the website fingerprint. Fixed.

**No new CI step needed.** `tools/demo/build_demo.py` already calls `check_demo_experience_coverage.validate()`
uncaught (line ~150) and is already wired into `ci.yml`'s `lint-and-test` job (`Build static demo artifact`
step, which runs before pytest) — so the new staleness check inside `validate()` is automatically a hard CI
gate with zero workflow changes. The website tool's own CI step was already present. Both registries needed a
bootstrap `--refresh` in this same increment (below) since neither had a `reviewed_increment` baseline yet.

## 2. Whole-demo currency audit (all 6 stages)

Per Cliff's own explicit choice ("Audit all 6 stages now"), dispatched parallel research passes across
Discover, Read, Evaluate, Synthesize, Write, and Audit, cross-referencing every real frontend fetch call
against `demo/demo-runtime.js`'s route table and `demo/experience-coverage-v1.json`'s classifications.

### Fixed in this increment

- **`GET /feed/suggest-authors`** (Discover, backlog #66): a real route since inc 455/506 with a real
  frontend call (`30g_feed_suggest.jsx`) had no matching demo route at all — Feed → Suggest → Author spun
  forever (a permanent loading state, not even a 404, since the frontend's `isDemoMode()` guard returned
  early before ever attempting the fetch). Fixed with a new capture step in `capture_demo_prospection.py`
  (a real `GET /feed/suggest-authors` call against the demo sandbox) + a new `demo-runtime.js` route + a new
  `suggested_authors` field on `DemoDiscoverState` (schema v3→v4) + removing the frontend's `isDemoMode()`
  early-return.
- **`missing_works`/`dismissed_works`** (Discover, backlog #66): the Indexed-Works review panel was hardcoded
  to `[]` in `capture_demo_prospection.py` instead of reading the real dashboard job's own computed values —
  fixed to read `live_dashboard.missing_works`/`.dismissed_works`.
- **The "three-paper" stale-copy sweep** (backlog #67): the demo corpus grew 3→5 papers in inc 548, and a
  recurring "hardcoded old count" pattern was found spread across ~15 locations: `demo/README.md` (5
  paragraphs), `demo/coverage-v1.json` (5 entries), `app/frontend/js/{08e_methods_publishers,10_pdf_layer,
  31_mypubs_dashboard}.jsx`, `demo/demo-runtime.js`, `www/{index,showcase,how-it-works}.html`, and
  `tools/demo/generate_demo_wip_state.py`. All fixed to the correct 5-paper/4-Workman-authored/4-bundled-PDF
  counts. Two files were checked and correctly left alone: `generate_demo_synthesis_state.py` and one
  `coverage-v1.json`/`demo/README.md` line each genuinely describe a separate, legitimately-3-paper Critique
  sandbox — not a stale count.
- **The Meta-Preregistration crosswalk's "Open Registration/Publication Evidence" buttons silently served the
  wrong PDF for 10 of 12 rows** (Synthesize audit finding): every saved crosswalk row's
  `registration_source_locator.attachment_id` is `4201`, but the demo's only real attachment for that paper is
  id `42` — `demo-runtime.js`'s pdf route ignored the `attachment_id` query param entirely and always served
  paper 42's own manuscript, mislabeled as registration evidence. Fixed: the route now validates
  `attachment_id` against the paper's real attachments and returns an honest blocked message on mismatch
  instead of silently substituting the wrong file. The 2 page-less rows' permanent "loading stored
  registration…" dead end (`openSource`'s `page == null` branch called `setShowRaw(true)` without ever
  fetching) is also fixed, now calling the real `inspectRaw()` fetch-and-toggle.
- **The Citation Styles panel auto-fired a live preview POST on every mount in demo mode and rendered a raw
  error box** (Write audit finding): `35d_citation_styles.jsx`'s preview effect now checks `isDemoMode()` and
  shows an explanatory note instead; `demo-runtime.js` gained bespoke `/citations/styles/*` messages instead
  of falling through to the fully generic block/missing-read text.
- **`cap-fulltext` reclassified** `saved-inspectable` → `missing-snapshot` in `experience-coverage-v1.json`
  (Read audit finding): `/papers/fulltext` (library-wide full-text search) has zero route or captured data in
  the demo — it was misclassified as working.
- **`demo-runtime.js`'s `/usage/summary` stub incorrectly hardcoded `enabled: false`** (Audit-stage finding);
  the real backend default is `usage_events_enabled: True`. Fixed, and contradicted the frontend's own "On by
  default" copy.
- **The demo settings payload was missing most of `SettingsStatus`'s real fields, including the required
  `account` field** (Audit-stage finding) — `export_demo_snapshot.py` now builds a real `SettingsStatus(...)`
  instance instead of a hand-typed 4-key dict, and `demo_snapshot.py`'s schema-drift guard now checks against
  `set(SettingsStatus.model_fields)` instead of a hardcoded 4-key allowlist that couldn't have caught this.
- Several bespoke `mutationBlockedMessage()` entries added for previously-generic-fallback paths
  (`/methods/pcurve/run`, `/methods/zcurve/run`, `/methods/effect-size`, `/critical-read/set`).
- Reconciled two near-duplicate "read state/priority" lock-explanation strings (`16b_readmark.jsx` vs.
  `demo-runtime.js`) into one shared wording.

### Backlogged (`INCREMENT-BACKLOG.md` #70)

Findings needing a new capture job or a product decision, not a cheap inline fix: `cap-cite-stance` (every
saved Cite suggestion is "support" — no contrast/mention example exists), `cap-csl` breadth (only one
hardcoded style is ever servable), `cap-bibliography` breadth (saved renderings cover 3 of 5 papers), the
Synthesize-stage cluster (`cap-contrasts` — zero contradicted-citation example; `cap-extraction-candidates` —
the workbench capture bypasses the real `/propose` endpoint entirely; `cap-extraction-anchors` — no
exact-precision anchored cell exists; `cap-staleness`/`cap-registration-correction` — no stale-comparison or
rejected-link example; `cap-registration-review` — all rows are `unreviewed` by deliberate privacy design;
`cap-raw-registration` — a genuine OSF licensing constraint, not a data gap).

## 3. Direct request: `www/how-it-works.html` updated for Local AI (inc 547)

Cliff separately asked to update the pipeline-explainer page now, given Local AI's addition. Added a 5th
provider card ("Local AI" — managed on-device Qwen model, zero setup/zero egress) to the provider grid
(widened `repeat(4,1fr)` → `repeat(5,1fr)`), and updated the two accompanying prose mentions of the provider
list to name it alongside Gemini/OpenAI/Anthropic/custom/loopback.

## 4. Backlogged (not built): #68, #69

Per Cliff's own request, filed but not built this increment: **#68** a release-tag-triggered CI gate on the
in-app "what's new" notification banner (needs a design decision on where the registry lives); **#69** a
changelog-driven drift gate for `README.md` and `www/how-it-works.html`, extending `changelog_drift.py` with
per-doc source globs.

## Key technical detail

The website tool's zero-grace Condition A was **not** rewritten to call `staleness_errors(...,
grace_increments=0)` — that would have silently weakened its original guarantee (any fingerprint drift fails,
regardless of increment count) into a delta-based check that could pass on same-increment drift. Instead it
stays a direct fingerprint comparison, with `decline_covers()` layered on as the only new escape hatch — a
new primitive built specifically so the website tool's existing behavior is preserved exactly rather than
routed through the demo tool's coarser logic.

## Manual verification script

1. `python tools/qa/check_website_coverage.py` — should FAIL before the bootstrap refresh (frontend source
   changed since the last review), confirming the gate fires; then `--refresh --note "..."` and re-run clean.
2. `python tools/qa/check_demo_experience_coverage.py` — same pattern; confirms `cap-fulltext` now reports
   under `missing-snapshot` in the printed counts.
3. Load the demo, open Discover → Feed → Suggest → Author: the tab now resolves to 3 real suggested authors
   instead of spinning forever.
4. Open Synthesize → Meta-Preregistration, click "Open Registration Evidence" on any row whose locator
   doesn't match the paper's real attachment: confirm an honest blocked message instead of the paper's own
   manuscript opening mislabeled as registration evidence.
5. Open Settings → Citation styles in the demo: confirm an explanatory note renders instead of a raw
   "Preview unavailable: HTTP 404" error box.

## Pytest

`tests/test_frontend_assembly.py` (86 passed, after updating two assertions to the corrected demo-mode copy),
`tests/test_check_website_coverage.py` (5 passed), `tests/test_usage_events.py` (14 passed);
`tests/test_demo_snapshot.py`/`tests/test_demo_experience_coverage.py` confirmed correctly fail-closed before
the bootstrap `--refresh` (no `reviewed_increment` baseline yet) and pass after.
