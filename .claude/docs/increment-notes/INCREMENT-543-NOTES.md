# Increment 543 — Demo Ask example now shows a real verified+flagged mix (Phase 3 slice)

**Date:** 2026-08-30
**Scope:** Continuation of the website/demo improvement plan
(`.claude/backups/plans/2026-08-30_website-demo-improvements.md`), Phase 3 — the demo's own data gaps.
Cliff explicitly asked me to verify his recollection that a real Synthesize > Ask snapshot already exists in
the public demo (it does) and investigate it further.

## The finding

Direct inspection of the promoted demo summary (`demo/snapshot-v1.json`'s `api.summaries["1"]`) confirmed two
real, concrete issues, neither a fabrication risk — both present in the underlying sandbox-generated content
before promotion, not introduced by the promotion pipeline itself:

1. **Every citation was `verified`.** The app's real citation-status vocabulary is `verified`/`weak`/
   `unverified`/`contradicted` at the DB layer, collapsing in the frontend
   (`app/frontend/js/20_synthesis.jsx:4`) to three visible states: verified (green), flagged (amber — covers
   `weak` and `unverified`), and "⚠ source disagrees" (red — `contradicted`). The previously-promoted demo
   summary showed only the green state, ever — the one feature the whole project is built around never
   demonstrated the thing verification actually catches.
2. **Two sentences (ordinals 0 and 4) were byte-identical text.** Confirmed present already in the original
   sandbox-generated content (`.local/demo-synthesis-run-20260813.sqlite`, summary id 5), not a promotion
   artifact.

`tools/demo/promote_verified_demo_synthesis.py` structurally could not have promoted anything but an all-green
result — it hard-rejected any summary containing a non-`"verified"` citation. Surveying all 9 real sandbox
generation attempts across `.local/demo-synthesis-run-20260813.sqlite` and its 3 `-audit-` siblings found no
single attempt that was simultaneously (a) fully spanning all three curated papers and (b) a mix of verified
and flagged citations and (c) free of duplicate text — so a real fix required a judgment call, not just a bug
fix. Relaxing the gate to show a real flagged citation against a real, identifiable published paper is squarely
"the AI's own output wasn't quite right" (never a claim about the cited paper), but adjacent enough to the
project's no-accusation-of-individuals territory that it went to Cliff explicitly before any code changed.
**Cliff's decision: relax the gate and use it.**

## Implemented

- **`tools/demo/promote_verified_demo_synthesis.py`**: the promotion gate now accepts any real citation status
  the app itself displays (`verified`/`weak`/`unverified`/`contradicted`, not only `verified`), and the summary
  top-level status check accepts `verified` or `flagged`. It never fabricates or upgrades a status — the real
  one travels through unchanged — and every non-verified sentence/status pair it accepts is printed as an
  explicit `NOTE`, so a mixed-status promotion is a visible, informed choice at the call site, never a silent
  default. The Overview `claim_ordinals` validation now checks against `verified_ordinals` (non-flagged
  sentences only) rather than all sentence ordinals, and the `verified_claims_sha256` fingerprint computation
  is now filtered to only verified sentences — both changes make the tool match
  `app/backend/demo_ask_overview.py::verified_claims_sha256()`'s own `if not sentence.flagged` filter exactly,
  which is load-bearing: a fingerprint computed over the wrong claim set would be one the live app could never
  itself reproduce.
- **Promoted sandbox summary 4** (`.local/demo-synthesis-run-20260813.sqlite`) in place of summary 5 — a real,
  already-generated-and-independently-verified synthesis with 1 `verified` sentence (paper 42) + 4 `weak`
  (flagged) sentences (papers 67, 67, 67, 88), no duplicate text, and an Overview whose single `claim_ordinals:
  [0]` already correctly referenced only the verified sentence. The `weak` status here comes specifically from
  `retrieval_confidence` (~0.65–0.69) falling under the 0.7 threshold while `quote_confidence`/
  `support_confidence` both stay at ~1.0 — a real, meaningful "the passage-to-claim semantic match wasn't quite
  strong enough" case, not a fabricated or low-quality contrast (`app/backend/summarization/verification.py`'s
  `_status()`).
- **`demo/snapshot-v1.json` + `demo/ask-overview-v1.json`** regenerated via the project's own documented
  pipeline (`promote_verified_demo_synthesis.py` → `export_demo_snapshot.py`, per `demo/README.md`'s "Curate
  and export" section) — no hand-edited JSON.
- **`demo/README.md`'s coverage table** updated to describe what actually changed: the Synthesize row now
  states the Ask spans all three curated papers with a genuine verified+flagged mix, and narrows the "open
  findings" cell to what's still actually missing (a single sentence citing more than one paper at once, a
  real `contradicted` example, the registration inspector, a stronger Critique example) rather than the
  stale, broader "source diversity... open finding" wording.
- **`tests/test_demo_snapshot.py`**: two tests encoded the old all-verified assumption and needed updating to
  match the new, intentional contract (not a regression — the old assertions were exactly the thing this
  increment deliberately changed):
  - `test_saved_demo_synthesis_includes_traceable_generated_overview`'s Overview-length lower bound relaxed
    from `2` to `1` (only 1 sentence is verified now, so the Overview can only ever narrate that one claim).
  - `test_saved_demo_synthesis_is_the_verified_three_paper_sandbox_run` renamed to
    `test_saved_demo_synthesis_is_the_verified_and_flagged_three_paper_sandbox_run` and rewritten to assert the
    real mixed shape explicitly (exactly 1 verified + 4 weak citations, `summary_status == "flagged"`, still
    all three curated papers represented, quote/support confidence still ~1.0 on every citation including the
    flagged ones) rather than a blanket "everything is verified."

## Verification

- `python tools/demo/promote_verified_demo_synthesis.py --source-db .local/demo-synthesis-run-20260813.sqlite
  --source-summary-id 4 --target-db .local/nli-01-anomalous/good-beautiful-export-v2.sqlite
  --confirm-dedicated-demo-target --confirm-public-source` → printed the expected mixed-status NOTE (4 of 5
  sentences flagged) and promoted 5 claims / 5 citations. Pre-promotion backup taken at
  `.local/nli-01-anomalous/good-beautiful-export-v2-before-summary4-20260830.sqlite`.
- `python tools/demo/export_demo_snapshot.py --source-db .local/nli-01-anomalous/good-beautiful-export-v2.sqlite
  --confirm-public-demo-source` → validated snapshot written; direct read confirmed the new sentence/citation
  mix (1 verified/paper 42, 4 weak/papers 67×3+88) and the Overview correctly tracing only ordinal 0.
- `python tools/qa/check_demo_experience_coverage.py` → passed (exit 0); bucket counts:
  `{"browser-local": 5, "external-surface": 13, "homepage_links": 12, "missing-snapshot": 6,
  "saved-inspectable": 43, "saved-partial": 38, "scientifically-inapplicable": 1, "total": 120,
  "visible-live-only": 14}` — the Ask capability stays in its existing `saved-partial` bucket (the coverage
  ledger tracks capability *presence*, not citation-status diversity), so this fix improves what the saved
  example actually demonstrates without changing its coverage classification.
- `pytest tests/test_demo_snapshot.py tests/test_demo_experience_coverage.py -q` → **27 passed** (was 2 failing
  before the two test updates above — both failures were the stale all-verified assumption, confirmed by
  reading the assertions, not just re-running until green).
- `python tools/demo/build_demo.py` → succeeded, `dist-demo` artifact built against `snapshot_schema: 9`.

## Deferred (not an oversight — concurrent-edit safety)

Codex is concurrently active in this same working tree on backlog #57 Phase 6B (the EndNote managed-bootstrap
executor, inc 542, uncommitted at the time of this work) with live, uncommitted edits to `.claude/CLAUDE.md`
(the increment counter itself, currently mid-bump to 542) and `.claude/changes.md`. Editing either file right
now risks colliding with Codex's own in-progress edit to the exact same lines. This increment's own CLAUDE.md
counter bump (→ 543) and `changes.md` entry are deliberately deferred to a follow-up pass once Codex's inc 542
lands, rather than risking a corrupted concurrent write to shared documentation files. No code, test, or demo
content in this increment is affected by the deferral — only the bookkeeping.

## Next

Phase 3's remaining named gaps (Discover's 0/11 saved-inspectable capabilities, the fully-missing capabilities
like `cap-pdf-search`) are still open, plus the still-flagged `app_current.png`/hotspot recapture from inc 540.
See the plan doc for full scope.
