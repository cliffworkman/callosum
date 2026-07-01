# Increment 235 — Library bundle SP2: syntheses (relayed, not re-verified)

Completes the collaboration track (B2). Syntheses now travel in a portable library bundle. The load-bearing
constraint: a synthesis is a **verification artifact** — its verified/contrasted/flagged statuses were computed
against the *sender's* chunks — so importing one must **not** present it as the recipient's verified synthesis
(invariant #1: external output is never authoritative citation evidence; #4: verification is the recipient's
substrate's job).

Maintainer forks (AskUserQuestion): **relay + flag** (a one-click "re-verify against my library" is a bigger,
separate feature → SP3); syntheses in **both** whole-library + selection exports.

## The honest design (the rule-#9 gate)

An imported synthesis is a **relayed artifact**:
- Stored as a **self-contained display blob** — `summaries.imported_json` (migration 0032, additive/guarded;
  `status="imported"`) — **never** written to `summary_sentences` / `citation_mappings` / `evidence_quotes`, so it
  can't be read as, or mistaken for, a locally-verified synthesis. This is the aligned alternative to the misaligned
  "import as a native verified synthesis" path (which would relay the sender's statuses through `citation_mappings`
  as if local).
- Flagged in the pane — `20_synthesis.jsx` shows **"Imported — the sender's assessment, not re-checked in your
  library"** (`.synth-imported`, `--flag` family), and the history list marks it (`imported: true`).
- **Region precision only** — every imported citation opens at the source paper's page, never a fabricated exact
  box (the sender's bbox is for the sender's PDF and isn't carried).
- **Evidence always shown** — each citation keeps its quote + page + the sender's status; a citation whose source
  paper the recipient lacks shows the quote + "Source not in your library" (no Open link — silence≠certificate).
- **Clean provenance** — only NATIVE syntheses (`imported_json IS NULL`) are exported; a bundle never re-relays a
  relayed artifact.

## Implemented

- **`metadata/library_bundle.py`** — `_synthesis_entries(conn, paper_ids)` (export; native only; a selection keeps
  only papers-scope syntheses **fully contained** in the selection; each citation resolved through the summaries.py
  chunks→papers join carries its **source by identity**, not chunk id) + `_import_syntheses(conn, entries, summary)`
  (resolve each source by identity → local `paper_id` else None; build the region-precision blob; insert one
  `summaries` row; **idempotent by content**; bounded `MAX_BUNDLE_SYNTHESES=2000` / `MAX_SYNTHESIS_SENTENCES=400` /
  `MAX_CITATIONS_PER_SENTENCE=50`; per-synthesis savepoint). `build_bundle` adds `syntheses` for both scopes;
  `import_bundle`'s summary gains `syntheses_imported`.
- **migration 0032 + `schema.py`** — `summaries.imported_json` (nullable JSON).
- **`summaries.py`** — `SummarizeJobResponse.imported` + `SummaryListItem.imported`; `SummaryCitationResponse`'s
  `mapping_id`/`evidence_quote_id`/`chunk_id`/`paper_id` → Optional; `_persisted_summary_response` branches on the
  blob → `_imported_summary_response` (region citations, `imported=True`); `_summary_list_item.imported`.
- **Frontend** — the `.synth-imported` banner + null-source ("Source not in your library") + `chunk_id`-null handling
  in `20_synthesis.jsx`; the modal copy + `syntheses_imported` count in `28b_bundle.jsx`; `.synth-imported` CSS
  (`--flag`, tokens only); `BundleImportSummary.syntheses_imported` (`routers/library.py`).

## Verification

`HF_HUB_OFFLINE=1 python -m pytest tests/test_library_bundle.py -q` → **14 passed** (8 SP1 + 6 SP2): export carries
the sentence + citation quote/status + **source-by-identity**; imported→relayed + **read via API** (`GET
/summaries/{id}` → `imported:true` + **region** citations from the blob, never in the tables; `GET /summaries` flags
it); re-import idempotent (dedup by content); a citation whose paper isn't present → `paper_id:null` + quote carried;
native-only never re-exports a relayed one; a selection carries a fully-contained papers-scope synthesis, excludes an
out-of-selection one. Full suite **848 passed, 1 skipped**. QA surface **172/172 API + 753/753 FE, 0 uncovered**
(`route_54` extended; the `imported` flags + `syntheses_imported` ride existing endpoints, the banner is in the
already-claimed `20_synthesis.jsx`). Migration head **0032** via `alembic_head()`. Audit **addendum** to
`2026-07-01_library-bundle.md` **PASS**. No egress, no PDFs, no new dependency, no new endpoint.

**Headed-verified, no egress** (`.local/visual/drive_inc235_syntheses.py`): a dest DB pre-loaded with a relayed
synthesis (a bundle carrying a native synthesis imported into it) — open THEORY → Synthesis → load it from history →
the **"Imported — the sender's assessment"** banner renders, the citation shows **REGION-LEVEL** precision (no exact
box) with its quote; 0 console/page errors, 0 off-machine requests.

## Deferred (SP3)

**Re-verify against my library** — a one-click action on an imported synthesis: re-run the local verification
pipeline (retrieval + NLI + quote-location) over the recipient's chunks for the same claims, turning the relayed
artifact into a native one. Bigger (touches the pipeline; needs the papers' chunks present). PDFs never travel.
