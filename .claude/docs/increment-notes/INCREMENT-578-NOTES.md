# Increment 578 — H1b: source-component preservation

**Substrate increment. No reconstruction, no retrieval change, no evidence assembly.**

Predecessors: increment 577 (H1a, `chunk_structure`, migration `0079`), and two independently-run
studies that converged on the same architectural conclusion —
`.claude/docs/research/2026-09-05_proposition-preserving-evidence-units.md` and
`.claude/docs/research/2026-09-05_codex-evidence-unit-replication.md` (the latter merged onto `main`
in this increment, with its full preregistration → amendment → freeze history preserved).

Both studies found that **current PDF chunks are extraction units, not reliably evidence units**,
and that **general adjacent-chunk merging is unsafe** (59.1% false-join rate; 27.0% even after H1a
hygiene). H1b therefore preserves richer deterministic source structure *without letting it affect
retrieval*.

---

## Implemented

### Schema / migration

`alembic/versions/0080_source_components.py` (head: `0079_chunk_structure` → `0080_source_components`).
Three sibling tables in the 0074/0079 mould — additive, never a retrofit. **No column was added to
or altered on `chunks`**, so no `op.batch_alter_table` was needed.

`app/backend/persistence/schema_source_components.py`:

| Table | Purpose |
|---|---|
| `source_pages` | attachment, page number, width, height, **rotation**, coordinate system, extractor name/version, derivation version, source checksum |
| `source_components` | self-parenting hierarchy (`span → line → text_block`/`heading`), kind, **`native_order`**, **`sorted_order`**, `child_order`, bbox, exact text, font, size, flags, `dir_x`/`dir_y`/`wmode` |
| `paper_figures` | GROBID figure/table records: `xml_id`, GROBID's own `@type`, label, head, `figDesc`, its supplied row/cell grid, and a region where the build located one |

`derivation_version = "source-components-v1"`. Bumping it invalidates every row and the next
backfill re-derives, with no migration.

Two indexes only on `source_components` (`parent_id`, and a composite `source_page_id, kind` whose
leftmost column serves page-scoped reads). Deliberately **no** index on text/font/geometry and **no**
full-text index over spans — neither is justified until a study asks for it.

### Native vs sorted order — the correctness requirement

`extract_pdf` calls `get_text("dict", sort=True)`. Verified in PyMuPDF's own source
(`extractDICT`): sorting is `blocks.sort(key=lambda b: (b["bbox"][3], b["bbox"][0]))` and
**`b["number"]` is not renumbered**. So:

- `chunks.bbox_json["block"]` is the **post-sort enumerate ordinal**, and because the `type != 0`
  skip happens *inside* the loop, it counts image blocks that are then dropped — it has gaps.
- `quote_matching.py` separately stores MuPDF's **native** number from `get_text("words")`.
- The same key name `"block"` therefore denotes two different numbering spaces today.

H1b stores them as **separate columns** (`native_order`, `sorted_order`) and a migration test pins
that split. Neither is labelled "reading order"; neither establishes paragraph continuity.

**Measured, this increment:** across the **whole 114-PDF / 1,628-page validation library** the two
orders are out of sequence on **1,356 of 1,628 pages (83.3%)** — higher than the 63.6% seen on a
12-PDF probe and higher than the predecessor study's 70%, so the case for separate columns is
stronger than the research assumed. The very first row of the inspection output for the first
library PDF is `native_order 14, sorted_order 0` — an image block MuPDF numbered 14th appearing
first in geometric order.

### Structural capture

`app/backend/pdf_processing/source_components.py` — **pure** (the H1a contract): no DB connection,
no client, no network call, never opens a PDF. It takes the page dict `extract_pdf` has already
built plus geometry it has already measured, and returns records. Testable entirely from literals.

Kept in its own module rather than enriching `extract_pdf`'s own loop: that loop feeds `chunks`, and
the premise of H1b is that chunk behaviour must not change. `extraction.py` gained one call, one
import and one additive `ExtractionResult.source_pages` field (**574 → 593 lines**).

Preserved, all of which the pipeline computed and discarded before:

- page width/height (computed at `extraction.py`, dropped in `make_chunk_drafts`, **zero readers anywhere**)
- **page rotation** (never read in the extraction path at all)
- block bbox (previously survived only long enough to associate link annotations)
- the full line/span hierarchy with per-line `dir`/`wmode`
- **exact per-span text**, un-normalized — `chunks.text` is whitespace-collapsed
- per-span font name, size and flags (only *size* was read before, transiently, for spacing)
- **pure headings** — `make_chunk_drafts` recognizes a single-line heading block, advances its
  section tracker, and emits **no chunk**; that text was lost outright
- raster image block bounds (all 13 image fields were dropped wholesale)

`sections.py` gained a shared pure `scan_block_heading()` so the builder can recognize a pure
heading **without** mutating a `SectionTracker` (calling `observe_block` again would double-advance
the section). `observe_block` now delegates to it — behaviour-identical.

### Written at ingest *and* backfillable

Per the maintainer's decision, source components are recorded during normal PDF ingest
(`attach_pdf_to_paper` and `reprocess_pdf_attachment`), not backfill-only — otherwise every newly
imported paper would sit structurally incomplete until someone ran a research tool.

**The write is isolated in a SAVEPOINT** (`conn.begin_nested()`). Source components are
observational substrate; the chunks in the same transaction are authoritative product state, so a
failure here rolls back only to the savepoint and never the chunks. The failure is logged at
WARNING with the attachment id — **not swallowed silently**, which is how inc 577 lost every
geometry rule to a broad `except` — and the backfill repairs it, since the write is
replace-per-attachment. A regression test injects a failure and asserts the chunks survive.

`tools/backfill_source_components.py` covers existing libraries: no API endpoint, no UI, no
JobStore, local PDFs only, no network, per-paper/per-attachment bounded, resumable via
per-attachment commit, idempotent, derivation-versioned, and checksum-aware (an attachment whose
file no longer matches its stored checksum is **skipped and counted**, not recorded under the old
identity — that is inc-576 PDF-recovery territory). `--inspect-page <attachment> <page>` and
`--summary` are the inspection surface; `--include-trashed` is an explicit debugging opt-in.

### GROBID figures

- `integrations/grobid/client.py`: `teiCoordinates` is now `["div", "head", "p", "figure"]`.
- `integrations/grobid/tei_parse.py`: new `parse_figures()` + `FigureRecord`. `<figure>` elements
  are **siblings of `<div>` under `<body>`**, which is exactly why `parse_tei`'s
  `.//tei:text/tei:body/tei:div` never saw them. Extracts `xml:id`, GROBID's own `@type`, `<label>`,
  `<head>`, `<figDesc>`, and GROBID's supplied `<table><row><cell>` grid. Same DOCTYPE/NUL guard.
- `grobid_pipeline.py` persists them; `parse_tei` and the section mapping are untouched.

**Compatibility, as directed:** an existing parse that lacks figure coordinates stays valid. A
missing bbox is an **honest permanent NULL**, never a staleness or error state, and H1b does **not**
auto-reparse the library merely because it can now preserve more. Verified against the real
fixture: 3 figures, the bitmap one located via its nested `<graphic>`, and both `type="table"`
figures correctly carrying `bbox=None`.

### Boilerplate follow-up (§L) — experimental, offline, unqualified

`guarded_digit_masked_key()` added to `tools/evidence_hygiene/structure.py`, beside the existing
offline `repetition_key`. It is **not referenced by production**; `chunk_filtering.py::_repetition_key`
is untouched, and a test asserts both facts.

**A real flaw was found by testing the guard rather than assuming it.** The first implementation
counted any digit-free token as a "real word", so `M = 3.41, SD = 1.02` reached 4 (`M`, `=`, `SD`,
`=`) and passed — masking a genuine reported result into a key it would share with every other
numeric result. That is precisely the numerical casualty the rule exists to avoid. A real word now
requires **two alphabetic characters**, which leaves that case with one (`SD`) and correctly
declines it. Verified: 6 numeric cases decline, 3 running-head cases mask, and two issues of one
running head share a key.

Before it may influence anything a user sees it must clear the same held-out gate H1a used: **≥95%
precision with adequate sample size**. The research sample is not qualification.

---

## Validation

| Check | Result |
|---|---|
| **Full suite** (`pytest -n 4 -q`) | **2895 passed, 4 skipped, 6 failed** — all 6 pre-existing, see below |
| `tests/test_source_components.py` | **45 passed** (new) |
| `tests/test_grobid_tei_parse.py` | **19 passed** (7 new) |
| `tests/test_grobid_pipeline.py` | **10 passed** (1 new; 4 assertions updated for `figures_recorded`) |
| `tests/test_migrations.py` | **11 passed** (1 new: the three tables + the native/sorted split) |
| Fresh DB `alembic upgrade head` | OK |
| `alembic check` | **no model drift** |
| `python -m tach check` | **All modules validated** |
| `ruff check` / `ruff format --check` on every touched file | clean |
| `tools/check_line_budget.py` | all 592 application-source files within the 600-line cap |
| Migrate + backfill a copy of the populated validation DB | **114/114 live attachments, 1,089,546 components** |
| `chunks.text` sha256 before/after | **unchanged** (`0cb7d01a…`) |
| `chunks.bbox_json` sha256 before/after | **unchanged** (`d6b2a93d…`) |
| Embedding identities sha256 | **unchanged** (`bf279156…`, 24,134 rows) |
| sqlite-vec vector blobs + rowid map sha256 | **unchanged** (`d5cf03b1…` / `dd816c2e…`) |
| Retrieval/generation modules referencing the substrate | **none** (11 modules asserted) |

### The 6 pre-existing failures

All six are the qualification-battery freeze tests, and the cause was verified rather than assumed:
the sole mismatching frozen input is **`app/backend/llm/providers.py`, which carries CRLF on disk
while `freeze.json` holds the LF-normalized digest**. This is the issue documented in the
predecessor report §0 — `.gitattributes` gained `eol=lf` in inc 575 and git never applies that
retroactively (186 of 850 tracked `.py` files still carry CRLF). **This increment touches zero
frozen files** (verified by set-intersecting the 18 frozen paths against the diff, and by
`git status` reporting the qualification tree clean). The repair is a repo-wide
`git add --renormalize` that would collide with parallel work, and `providers.py` is a frozen input
whose re-freezing is explicitly a maintainer decision — so it is reported, not fixed here.

### Real-library structural outcomes (114 PDFs, 1,628 pages)

| | |
|---|---|
| Pages where native order ≠ sorted sequence | **1,356 / 1,628 (83.3%)** |
| Spans carrying font + flags | 910,764 |
| Pure headings recovered (text ingest discards entirely) | 598 — real section names (`Procedure`, `2.1. Participants`, `References`) |
| Image bounds preserved | 7,413 |
| **Rotated pages recorded** | **10 at 90°** — rotation the extraction path never read at all |

The 83.3% disagreement rate is *higher* than the 63.6% my 12-PDF probe measured and higher than the
70% the predecessor study reported, which strengthens rather than weakens the case for keeping the
two orders in separate columns.

### Measured cost of writing at ingest

| | |
|---|---|
| Baseline ingest (5 real PDFs) | 20.50 s/paper |
| Structural walk (`build_page`) | **0.15 s/paper** |
| Persistence | **2.42 s/paper** |
| **Total H1b overhead** | **≈2.57 s/paper, +12.5%** |
| Storage | **≈2.1 MB/paper** (~250 MB for a 114-PDF library) |

Proportionate rather than surprising, on an operation already dominated by PDF extraction. Reported
rather than optimized, per the instruction not to optimize speculatively. Span rows dominate at
**89.7%** of components (measured 655.7 spans/page).

### Soft-delete accounting

`--summary` reports live coverage and trashed attachments **separately**. A trashed paper without
source rows is not a coverage gap — this is the same fact that explained H1a's 93 "unclassified"
chunks (paper 2, trashed 2026-08-28; correct behaviour, not a defect). A regression test pins that
`--include-trashed` is the only way to reach them.

---

## Deliberately not done

Adjacent-chunk merging · prose reunification · heading/body reconstruction · caption↔table
activation · table-row assembly · multi-page tables · table footnotes · evidence-unit retrieval ·
re-embedding · adaptive top_k · eligibility gates · plot understanding · chart digitization · vision
inference · **any `assembled` evidence unit** · assembled verifier support · model/provider
experiments · prompt engine · query planner.

`app/backend/document_tables.py` was **not** touched: its PyMuPDF `find_tables()` row evidence stays
ephemeral-per-request and unpersisted, exactly as before. GROBID's own supplied grid is a different
thing — GROBID states it, we do not reconstruct it.

`evidence_form = verbatim | assembled` is **specified, not instantiated**:
`.claude/docs/specs/2026-09-05-evidence-unit-contract.md`. Its load-bearing rule is that
`canonical_text_contains` must never be relaxed to accept an assembled string — an assembled unit
requires per-component verification plus separate verification of the assembly recipe.

---

## H1c prerequisites

1. **Caption↔table association precision.** The rate is known (41% associable, median gap 6.9pt);
   whether an associated caption is the *right* one has never been adjudicated. Cheapest first task.
2. **Table-row reconstruction** limited to where PyMuPDF's `lines` strategy already fires with a
   detected header (100% header recall over 34 tables).
3. **Per-component verification** before any multi-region display exists.
4. **Hygiene precedes reconstruction** — measured: 12/12 correct joins survive hygiene, and it
   removes 38% of boilerplate-caused false joins. An ordering constraint, not a licence to join.

## What changed for H1c's design

- Native order is now **recoverable without a second extraction pass** — `block["number"]` is
  present in the sorted dict. H1c does not need a re-read arm for reading order.
- Per-span geometry is queryable in SQL, so "which rectangle contains `p = .761`" is a query rather
  than a PDF reparse.
- Table figures from GROBID arrive with a caption and a grid but frequently **no coordinates**; a
  caption↔table geometry study must therefore source regions from PyMuPDF, not GROBID, or re-parse
  with the new `teiCoordinates` request first.

## Watch items

- `app/backend/pdf_processing/extraction.py` is at **593/600** and `app/backend/persistence/schema.py`
  at **594/600**. Both are the next split candidates; run
  `python tools/check_line_budget.py --list` before adding to either.
- `tools/check_line_budget.py --list` crashes on Windows (`UnicodeEncodeError` on `≤` under cp1252).
  The plain check path is unaffected and CI is unaffected. Pre-existing, not fixed here.
