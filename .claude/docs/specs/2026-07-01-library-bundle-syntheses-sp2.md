# Portable Library Bundle — B2 SP2: syntheses (relayed, not re-verified)

**Status:** approved (brainstorm 2026-07-01) → this spec → build. Extends SP1 (`library_bundle.py`, inc 234).
**Maintainer forks (AskUserQuestion):** **relay + flag** (re-verify against the recipient's library is a bigger,
separate feature → SP3); syntheses in **both whole-library + selection** exports.

## Goal

Carry the sender's **syntheses** in a library bundle. A synthesis is a **verification artifact** — its
verified/weak/contradicted statuses were computed against the *sender's* chunks — so importing it must **not** present
it as the recipient's verified synthesis (that would violate invariant #1: external output is never authoritative
citation evidence; and #4: verification is the recipient's substrate's job). SP2 imports a synthesis as a **clearly-
flagged relayed artifact**, at region precision, structurally separate from a native synthesis.

## The honesty design (rule #9 — this touches the claim/verification gate)

- **Relayed, not re-verified.** An imported synthesis is flagged **"Imported — the sender's assessment, not
  re-checked in your library."** Its per-citation status (verified/weak/contradicted) is shown as *the sender's*
  reading, never re-computed locally.
- **Region precision only (invariant #2).** Each citation opens at the source paper's **page** (region), never a
  fabricated exact box — the sender's bbox is for the sender's PDF. Save-as-highlight (inc-36, exact-only) stays
  disabled for imported citations.
- **Evidence always shown (#4).** Each citation still carries its **quote + page + the sender's status**; a citation
  whose source paper the recipient doesn't have shows the quote + "source not in your library" (evidence stays
  visible — silence is not a certificate), no "Open source" link.
- **Never in the local verification tables.** An imported synthesis is stored as a **self-contained display blob**
  (`summaries.imported_json`), so it can *never* be read as, or mistaken for, a locally-verified synthesis. The
  aligned alternative to the misaligned "import as a native synthesis" path (which would relay the sender's statuses
  through `citation_mappings` as if local).
- **Provenance.** Only **native** syntheses are exported (`imported_json IS NULL`) — a bundle never re-relays a
  relayed artifact (keeps provenance clean).

## Storage — `summaries.imported_json` (migration 0032, additive/guarded)

One nullable JSON column on `summaries`. An imported synthesis row: `status="imported"`, `imported_json = <the
resolved display blob>`, the NOT-NULL version columns (`chunk_version_verified_against` etc.) set to the sentinel
`"imported"`. Native syntheses leave `imported_json` NULL (unchanged). No rows are written to
`summary_sentences`/`citation_mappings`/`evidence_quotes` for an imported synthesis — the blob is self-contained.

The blob (the display shape, resolved on import):
```jsonc
{
  "generated_by": "…", "scope_label": "3 papers",
  "overview": [ { "text": "…", "claim_ordinals": [0,2] } ],
  "sentences": [
    { "ordinal": 0, "text": "…", "flagged": false,
      "citations": [
        { "paper_id": 12|null, "paper_title": "…", "quote": "…", "page_start": 3, "page_end": 3,
          "status": "verified", "retrieval_confidence": 0.8, "quote_confidence": 1.0, "support_confidence": 0.7,
          "coordinate_precision": "region" }
      ] }
  ]
}
```

## Bundle format — a top-level `syntheses: [...]`

Whole-library: every native synthesis. Selection: only **papers-scope** syntheses whose scope `paper_ids` are **all
in the selection** (fully contained — so the recipient has every cited paper); query/cluster-scope syntheses only in
whole-library. Each entry (resolved from the native tables via the existing read join, which already resolves
`paper_id` + `paper_title` + quote + page + status per citation):
```jsonc
{
  "scope_type": "papers"|"query"|"cluster_node",
  "scope_identities": [ {identity} ],   // papers-scope: the scope papers' identities
  "scope_ref": { "query": "…" },        // the raw non-paper scope bits (query text)
  "content": "…", "overview_json": [...], "generated_by": "…",
  "sentences": [
    { "ordinal": 0, "text": "…",
      "citations": [
        { "quote_text": "…", "page_start": 3, "page_end": 3, "status": "verified",
          "retrieval_confidence": 0.8, "quote_confidence": 1.0, "support_confidence": 0.7,
          "source": {identity} } ] } ]
}
```

## Export (`library_bundle.py`)

`_synthesis_entries(conn, *, paper_ids=None)`: iterate native summaries (`imported_json IS NULL`); for a selection,
keep a papers-scope summary only if its scope `paper_ids ⊆ paper_ids`. Per summary, read its sentences + per-citation
`{quote_text, page_start, page_end, status, confidences, source-paper identity}` (reuse the `_summary_citation_rows`
join that resolves `chunks.paper_id → papers`; map `paper_id → _identity(paper_row)`). `build_bundle` adds
`bundle["syntheses"] = _synthesis_entries(...)` for **both** scopes (selection passes the selected ids).

## Import (`library_bundle.py`)

`_import_syntheses(conn, entries, summary)`: per entry, in a `begin_nested()` savepoint:
- **Dedup / idempotency:** skip if an imported summary with the same `content` already exists (a query over
  `summaries WHERE imported_json IS NOT NULL AND content = :c`) → re-import is idempotent.
- Resolve each citation's `source` identity → local `paper_id` (via `find_existing_paper_by_identity`, else None) +
  `paper_title` (from the resolved row, else the sender's — carry it in the entry). Build the display blob (region
  precision; `flagged` = a sentence has citations and none are `verified` — mirrors the native rule).
- Insert one `summaries` row (`status="imported"`, `imported_json=blob`, `scope_type`, `scope_ref_json` = the raw
  scope with paper_ids translated to local ids where resolvable [else omitted], version columns = `"imported"`).
- Count `syntheses_imported`. (No embedding needed — a synthesis creates no new papers/chunks.)

`import_bundle`'s summary gains `syntheses_imported`; the router `BundleImportSummary` + the modal add it.

## Read (`summaries.py`)

- `SummarizeJobResponse` gains **`imported: bool = False`**; `SummaryCitationResponse`'s `mapping_id`,
  `evidence_quote_id`, `chunk_id`, `paper_id` become **Optional** (an imported citation has no local
  mapping/evidence/chunk id, and a paper it may not resolve). Native responses are unchanged (fields populated).
- `_persisted_summary_response(conn, summary_id, …)`: if the summary has `imported_json`, **build the response from
  the blob** (sentences + citations at region precision, `imported=True`) instead of the tables.
- `SummaryListItem` gains **`imported: bool`**; `_summary_list_item` reads it (`imported_json IS NOT NULL`) so the
  history list flags imported syntheses. `list_summaries` includes them.

## Frontend (`20_synthesis.jsx`)

When a loaded synthesis (`SummarizeJobResponse`) is `imported`, render a distinct **banner**: "Imported — the
sender's assessment, not re-checked in your library" (an `--flag` note, tokens only). Citations render as today at
region precision (the pane already handles region: "Open source" scrolls to the page, no exact box); a citation with
`paper_id == null` shows its quote + "source not in your library" (no link). The synthesis-history list marks imported
items. One CSS recipe `.synth-imported` (DESIGN rule #8). No new claim/score.

## Gates

- **Security audit** — addendum to `2026-07-01_library-bundle.md`: no new endpoint/egress/dependency (rides the SP1
  bundle endpoints); the migration is additive/guarded; imported citations are bound-param inserts; no PDF; still no
  egress. **Principles gate — this touches #1/#4** (a verification artifact): the aligned relay-not-re-verify design
  above is the finding; the misaligned "import as native verified" path is declined.
- **Rule #10 (QA):** extend `route_54_library_bundle.md` — the `syntheses` in the bundle, the imported-synthesis
  banner + region precision + "not re-verified" assertion, the `imported` response flag.
- **Rule #1:** `library_bundle.py` gains the synthesis export/import (re-measure; split `_synthesis_*` to a helper
  module if it crosses 600); `summaries.py` the read branch (re-measure); `20_synthesis.jsx` a banner.
- Migration head via `alembic_head()`.

## Verification

- **pytest** (extend `tests/test_library_bundle.py`, hermetic): seed a papers-scope synthesis with a verified + a
  flagged citation; export → the `syntheses` entry carries the sentences + per-citation quote/page/status/source-
  identity; import into a fresh DB → an `imported` summary row with a blob whose citations resolve to local paper ids
  at region precision; **re-import idempotent** (no duplicate synthesis); a citation whose paper isn't present →
  `paper_id null`, quote still carried; selection export includes a fully-contained papers-scope synthesis, excludes a
  query-scope one; a bundle from an already-imported synthesis does **not** re-export it. Plus `tests/test_summaries.py`:
  `GET /summaries/{id}` for an imported summary returns `imported: true` + region citations from the blob;
  `GET /summaries` flags it.
- **Headed, no egress** (extend/clone the inc-234 driver): seed a native synthesis → export → import → the history
  shows the imported synthesis flagged, opening it shows the banner + region citations; 0 console/page/off-machine.
- Full suite green; `ruff` + `format`; `build_frontend` (+ assembly); QA `check` 0-uncovered; help corpus's "Sharing a
  library" section notes syntheses now travel (relayed, flagged); commit (excl. `www/`), push, CI.

## Deferred (SP3)

**Re-verify against my library** — a one-click action on an imported synthesis: re-run the local verification
pipeline (retrieval + NLI + quote-location) over the recipient's chunks for the same claims, turning the relayed
artifact into a native one. Bigger (touches the pipeline; needs the papers' chunks present). PDFs never travel.
