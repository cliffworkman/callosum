# Increment 579 — H1b.1: source-representation completeness and provenance hardening

**Not H1c.** No reconstruction, no retrieval change, no assembled evidence unit. This closes the one
blocker an independent audit found in H1b, plus the two provenance gaps that would have made H1c
unsafe to build on, and stops.

---

## Why this increment exists

An independent Codex audit of H1b ran on branch `codex/h1b-source-component-audit-20260905`
(preregistered `955c606`, findings frozen `7f9e4fc` *before* reading any of H1b's own notes, post-hoc
comparison `6f3839e`; report at
`.claude/docs/research/2026-09-05_codex-h1b-source-component-audit.md`). Its verdict on H1b's central
representation was strong and is **not reopened here**:

| Measure | Result |
|---|---|
| Live PDF attachments covered | 114 / 114 |
| Pages matching fresh production extraction | 1,628 / 1,628 exact |
| Components matching | 1,089,546 / 1,089,546 exact |
| Independent raw-PyMuPDF reread (31 adversarial pages) | 29,405 / 29,405 exact |
| chunks / embeddings / attachments / sqlite-vec identities and vectors | unchanged |
| Ten fixed-vector retrieval queries, ordered top-20 + distances | identical before and after |

It found **one concrete defect**. With the component cap lowered inside the harness, replacing a
two-page attachment returned `{pages: 1, components: 0, truncated: 1}` — and because that persisted
page carried a matching `source_checksum` and `derivation_version`, which was everything H1b checked,
`attachments_with_current_source()` classified the partial graph as **current**. A later ordinary
backfill would have skipped it forever.

The production corpus never hit the cap, and nothing on the retrieval path reads these rows, so this
was never a live regression. It was a substrate correctness defect, and it failed the approved H1c
gate. Two further findings had to be closed with it: durable provenance had only **surrogate primary
keys**, which the audit proved change on every forced rebuild; and **malformed raster geometry** (363
inverted bboxes, one out-of-page) was faithfully preserved with no signal that it is unusable.

---

## Implemented

### Schema — migration `0081_source_representations`

One additive sibling table and two additive columns. No column on `chunks`, `attachments` or
`source_pages` was added or altered, and no existing H1b row changed meaning.

`source_representations` — one row per attachment:

```
attachment_id (UNIQUE, CASCADE)     source_checksum
extraction_tool                     extraction_version        derivation_version
expected_pages   written_pages   skipped_pages   written_components
state       complete | truncated | incomplete | failed
state_reason    component_cap | degenerate_pages | page_gap | persistence_error:<class> | extraction_error:<class>
created_at      updated_at
```

`source_components` gains `component_path` (the stable logical locator) and `geometry_state`
(`valid`/`invalid`/`unknown`), both nullable so pre-H1b.1 rows stay legal. SQLite's
`ALTER TABLE ADD COLUMN` with no default is metadata-only, so both adds are O(1) even at ~1.09M rows.

**Deliberately no `expected_components` column.** Production cannot know a component count reliably
before persistence, and inventing one would manufacture precision that does not exist. Page
completeness is the invariant; `written_components` is instead cross-checked against the rows
actually present, which is a fact rather than a prediction.

**Deliberately no new index.** `ix_source_components_page_kind` already has `source_page_id`
leftmost, so a locator resolves with one index seek plus a ~670-row in-page filter.

### The currentness contract

`current` now **requires** `complete`. Identity is necessary but no longer sufficient
(`source_representation_repo._current_source_stmt`, one inspectable statement):

```
state = 'complete'
AND derivation_version matches
AND attachment checksum present and equal to source_checksum
AND expected_pages > 0
AND written_pages = expected_pages
AND skipped_pages = 0
AND (source_pages rows present)      = written_pages
AND (source_components rows present) = written_components
```

The last two clauses are not decoration. A status row can outlive the graph it describes — the audit
deleted an attachment's rows and reran — and without the cross-check that combination reads as
current. The **component** count is checked as well as the page count because the invariant is about
the completeness of the graph, not of its envelope: an intact page envelope with missing component
rows is not a complete source graph.

> **No code path may infer currentness from the mere existence of `source_pages` /
> `source_components` rows.**

### State transitions and finalization

Finalization order is the whole point. Inside the one transaction the caller already owns:

1. the completeness record is destroyed **first** — before the graph it describes;
2. pages and components are written;
3. the record is written **last**, with the computed state.

So a complete marker can never outlive an interrupted write, and an interruption at any point leaves
either the previous committed representation or nothing.

| Situation | State | Reason |
|---|---|---|
| Every extracted page written, none skipped, no bound hit | `complete` | — |
| Component cap reached | `truncated` | `component_cap` |
| A page the schema cannot represent (`width`/`height` ≤ 0) | `incomplete` | `degenerate_pages` |
| Fewer pages written than extraction produced | `incomplete` | `page_gap` |
| The derivation raised | `failed` | `persistence_error:…` / `extraction_error:…` |

Two corrections to the cap path. The check now runs **before** the page row is inserted, and the page
whose components would be dropped is removed with them — so no orphan page-with-zero-components row
claims coverage it does not have (the exact shape the audit caught). And the truncation flag decides
**independently of the page arithmetic**: if the cap trips on the *last* page,
`written_pages == expected_pages` would otherwise still read as complete. That is the subtle half of
the fix, and it has its own regression test.

**A skipped page fails closed.** A degenerate page is deterministic, so a rerun keeps producing it and
the developer backfill keeps retrying — that is the honest cost. Counting it toward completeness would
make `current` mean "everything representable happened to be written" rather than "the representation
is complete", which is precisely the weakening this increment exists to prevent. Zero incidence in the
live corpus.

**A failed attempt never corrupts a surviving valid representation.** The state of the persisted
representation and the outcome of the latest attempt are different facts, and only the first decides
currentness. When a rebuild fails and its savepoint rolls back, a previously committed complete
representation for the same file is restored intact; marking that row `failed` would destroy a good
representation because a *later* attempt went wrong. `record_source_failure` checks first and
declines, returning `False` so the caller logs the failed attempt through ordinary logging. No attempt
history is kept — that would be a job framework, which this deliberately is not.

### The stable logical locator

`SourceLocator` (`source_representation_repo`) is the durable identity a future assembled unit must
use:

```
source checksum + extraction tool + extraction version + derivation version + page + component_path
```

`component_path` is materialized by the pure builder as `b{sorted_order}[/l{child_order}[/s{child_order}]]`.
It is unique within a page by construction: a block's `sorted_order` is its enumerate index over the
already-sorted block list, and `child_order` is the extractor's own line/span index within its parent,
so skipped nodes leave gaps but never duplicates. `extraction_version` is an explicit constituent
rather than folded into the tool name, because a PyMuPDF upgrade can change what is observed from the
same bytes and a locator blind to that would silently resolve to a different component.

`resolve_locator` **fails closed** on any drift — live attachment checksum, stored page's extractor or
derivation identity, page number, or path. `locator_for_component` is the audit direction. Every
constituent stays inspectable; `as_key()` is a rendering of them, never an opaque digest.

**A sharper hazard than the audit reported, found while writing the regression tests.** Surrogate ids
are not merely unstable — they are *reused*. `_flatten` allocates from `max(id) + 1`, so when the
attachment being rebuilt holds the top of the id space, its old ids are handed straight back to
different content. A stale reference to component 7 then resolves **successfully, to the wrong
thing**, with no error anywhere. That is strictly worse than an id simply moving, and it is now its
own test (`test_a_rebuild_can_silently_reuse_a_previous_surrogate_id`). It also explains a fixture
subtlety worth recording: in a database holding a single attachment, a forced rebuild reuses every id
exactly, so id movement is only observable with a co-resident attachment holding the top of the id
space — as in the real 114-attachment corpus.

### Geometry validity

Raw coordinates are **never** normalized, clamped, swapped or repaired. A separate explicit judgment
is recorded beside them, by a pure classifier testable from literals:

| Condition | State | Reason |
|---|---|---|
| any coordinate absent | `unknown` | `missing` |
| `x1 < x0` or `y1 < y0` | `invalid` | `inverted` |
| outside `[0 − tol, dim + tol]` on any edge | `invalid` | `out_of_page` |
| otherwise | `valid` | — |

**`GEOMETRY_PAGE_TOLERANCE_PT = 2.0`, frozen before corpus validation and justified on mechanism, not
on the count it produces.** A MediaBox/CropBox difference, a glyph outline overshooting its advance
width, and float rounding through the coordinate transform all routinely put an edge a fraction of a
point outside the page rectangle; none is a malformed observation. 2.0pt (~0.7 mm) is larger than all
three and far smaller than any region a spatial association could meaningfully use. Tuning it after
seeing which historical rasters it classifies would be choosing a threshold for a desired corpus
count.

`geometry_state` is materialized so a future association query can `WHERE geometry_state = 'valid'`
and fail closed by default without remembering to join and re-derive the rule. The reason string is
returned for inspection and reporting but is not stored, keeping this to exactly two new columns on
the large table.

Zero-area bboxes are **reported but not gated on**: degenerate is not self-contradictory, and whether
to exclude them is an H1c call to make against measurement.

### Ingest

`_persist_source_components` keeps its SAVEPOINT isolation and gains failure bookkeeping in a
**second** savepoint, so even the bookkeeping cannot escalate into a chunk failure. A non-complete
receipt is logged at WARNING with its state, reason and counts — honest, non-silent, non-current, and
repaired by an ordinary backfill rerun. Current chunks remain authoritative and unaffected.

### Backfill / repair

Only an attachment recorded `complete` **and** current is skipped. `truncated`, `incomplete`,
`failed`, stale-checksum, stale-derivation and entirely absent representations are all reprocessed by
an ordinary rerun with no extra flag. A per-attachment `try/except` records `failed` on an extraction
error so one bad PDF neither aborts the run nor vanishes from the report. `--summary` now prints the
`complete/truncated/incomplete/failed/absent` breakdown plus geometry-validity counts;
`--inspect-page` prints the representation state and flags each non-valid bbox inline beside its
locator path. Still local, offline, resumable, idempotent, per-attachment bounded, checksum-aware, no
API, no JobStore, no UI.

### Migration posture for existing H1b libraries

**`0081` promotes nothing.** No pre-existing attachment is labelled `complete` merely because rows
exist; absent status → not current → repaired by the ordinary developer backfill, which establishes
`complete` only after passing the same checks a new write passes.

This is free rather than costly, and the reason is worth recording: `component_path` and
`geometry_state` are NULL on every pre-H1b.1 row, so a full re-derivation is required regardless. The
conservative choice and the necessary choice coincide.

---

## Key technical detail

The defect was not that H1b wrote a partial graph — a bounded write is a legitimate safety mechanism,
and the cap stays. The defect was that **the representation had no way to say so**. Checksum and
derivation version answer "is this derived from the current file by the current code?", which is a
question about *identity*; nothing answered "is this derived graph whole?", which is a question about
*completeness*. H1b conflated them because in the happy path they coincide.

The fix is therefore not a bigger cap or a better error path. It is a separate record whose whole job
is to carry the completeness answer, written last so it cannot lie, and cross-checked against the rows
actually present so it cannot go stale in place.

---

## Corpus validation

Run on a coherent SQLite online-backup snapshot of the real 114-PDF validation library
(`.local/validation-summarize/validation.sqlite`, 496 MB), migrated to `0081` and backfilled from
scratch. The five before-hashes were taken before the migration.

### Representation state (R.3–R.7)

| Measure | Result |
|---|---|
| Live PDF attachments | 114 |
| `complete` | **114** |
| `truncated` / `incomplete` / `failed` / `absent` | **0 / 0 / 0 / 0** |
| Satisfying the **full** currentness predicate | **114** |
| Representations whose page rows disagree with `written_pages` | 0 |
| Source pages | 1,628 |
| Source components | 1,089,546 |
| Soft-deleted PDF attachments | 1, with no representation row — **outside live coverage by design** |

Pages and components match the independent audit's counts exactly. Immediately after migration and
before the backfill, all 114 read `absent` — confirming the migration promotes nothing.

### Interruption, on the real corpus (R / §F)

The serial backfill was killed mid-attachment at 35 completed. The interrupted attachment left
**no page rows, no component rows and no representation row**; `PRAGMA integrity_check` returned
`ok`; the rerun picked it up and converged. Because the completeness marker is written last, there
was no window in which it could have survived the half-written graph.

The remaining attachments were then driven by three sharded worker processes against the same
database (a validation-run accelerator only — production ingest and the ordinary single-process
backfill are unchanged). Per-attachment transactions plus WAL and the engine's 5 s `busy_timeout`
absorbed the overlap: 114/114 complete, zero lost or duplicated.

### Forced rebuild and locator stability (R.8, R.9)

Three attachments spanning the size range were force-rebuilt:

| Attachment | Components | Surrogate ids changed | Logical tree | Locator resolves | Still current |
|---|---:|---:|---|---|---|
| 92 | 1 | 1 / 1 | identical | ✓ same content | ✓ |
| 71 | 8,487 | 8,487 / 8,487 | identical | ✓ same content | ✓ |
| 88 | 37,045 | 37,045 / 37,045 | identical | ✓ same content | ✓ |

**Every** surrogate id moved; **no** logical locator did.

### Locator collisions (R.10) — a real finding, precisely characterised

Grouped on the **durable identity fields** (source checksum + extraction tool + extraction version +
derivation version + page + `component_path`) — *not* on `source_page_id`, which is itself
replaceable and therefore not a provenance test:

| Measure | Result |
|---|---:|
| Components | 1,089,546 |
| `component_path` NULL | 0 |
| Durable-key groups with more than one row | 3,342 |
| ...of which name **different content** | **0** |
| Collisions within any single attachment | **0** |

All 3,342 are attachments 83 and 84: **the same PDF attached twice to paper 114**, whose logical
trees hash identically. That is the locator working correctly — two byte-identical documents *are*
the same document — and the property that matters holds exactly: **no durable key ever names
different content.** It does establish that the key is not by itself a globally unique row address,
so provenance carries `attachment_id` beside it, which `resolve_locator` already requires and the
`evidence_form` contract already specifies. Regression test:
`test_the_same_file_attached_twice_shares_one_durable_identity`.

### Geometry validity (R.11) — reported at the frozen tolerance, not tuned to it

| State | Components | Share |
|---|---:|---:|
| `valid` | 1,088,070 | 99.865% |
| `invalid` | 1,476 | 0.135% |
| `unknown` | 0 | — |

Of the invalid: **363 inverted** — matching the independent audit's count exactly — and **1,113
out-of-page**. By kind: 364 image, 469 span, 453 line, 190 text_block.

The audit reported only *one* out-of-page case because it audited raster geometry specifically; this
classifier applies to every component kind, so the extra 1,112 are text lines, spans and blocks. The
audit's known image case remains `invalid`, as required.

The overflow distribution is what shows the frozen 2.0pt tolerance is not doing the work:

| Distance beyond the page rect | Components |
|---|---:|
| 2–5 pt | 91 |
| 5–20 pt | 56 |
| 20–100 pt | 460 |
| > 100 pt (max 144.0 pt) | 506 |

966 of 1,113 are more than **20 pt** outside the page. These are real overflows, not tolerance noise:
moving the threshold from 2 pt to 20 pt would change the count only from 1,113 to 966. The tolerance
was frozen on mechanism before measurement and is reported, not adjusted. Whether to treat
far-outside text as unusable is an H1c question with its own preregistered criterion.

3 zero-area bboxes exist and are **reported but deliberately not gated on**.

### Raw chunk / embedding / vector invariants (R.12)

| Data | Rows | Result |
|---|---:|---|
| `chunks` (complete rows, including text) | 23,875 | **identical** |
| `embeddings` metadata | 24,134 | **identical** |
| `attachments` | 115 | **identical** |
| sqlite-vec row-id map | 24,032 | **identical** |
| sqlite-vec vector blobs | 26 | **identical** |

All five byte-identical across migration, full backfill and three forced rebuilds.

### Retrieval identity (R.13)

Ten pre-existing stored vectors used verbatim as query vectors (no model loaded, so the comparison is
exact), ordered top-20 with hexadecimal float distances, run against the **untouched original** and
the **migrated + backfilled copy**:

```
original (untouched)      : 5cb20a949f4301807df6d7f4d3552d4f891e2108b845dd781ba455222e1c8ed6
copy (migrated+backfilled): 5cb20a949f4301807df6d7f4d3552d4f891e2108b845dd781ba455222e1c8ed6
```

### Cost attributable specifically to H1b.1 (R.10 / deliverable 15)

A/B against the H1b commit over the same real page dicts, so shared extraction cost is excluded:

| Component | Cost |
|---|---:|
| `build_page` (locator paths + geometry classification) | **+65 ms/paper** |
| Persistence (two extra TEXT columns per row + one status row) | **+298 ms/paper** |
| **Total H1b.1** | **≈ +0.36 s/paper** |
| For comparison, H1b's own source-component capture | +2.57 s/paper |
| ...on an ingest baseline of | 20.5 s/paper |

H1b.1 is **+14% on top of H1b's capture cost and ≈ +1.8% of total ingest** — status bookkeeping, not
a material regression. The full currentness query, which runs once per backfill invocation, measures
**90 ms** at 306k components (~320 ms extrapolated to the full 1.09M); the component cross-check was
measured rather than optimised away.

---

## Non-load-bearing invariant

H1b.1 must remain unread by production. `tests/test_source_representation.py` asserts that nine
retrieval/generation modules — the summarization pipeline and verifier, the embedding pipeline,
retrieval and vector store, citation suggest and section scope, the full-text repo and the provider
seam — reference none of `source_representations`, `source_representation_repo`, `component_path`,
`geometry_state` or `SourceLocator`. Completeness state, logical locators and geometry validity are
**not** wired into retrieval. They exist so H1c is safe to study.

---

## Explicitly deferred (recorded as decisions, not oversights)

- **Character offsets.** H1b components carry none, and defining them requires settling a canonical
  page-text serialization — which text a component's offsets index into, and how spans, lines and
  blocks compose. That is a design question in its own right, not a bookkeeping addition. Stable
  *component* identity is what H1c needs now; exact sub-span provenance stays an H1c/future question.
- **Every GROBID gap the audit found**: table `<note>` preservation, cell roles and attributes,
  multi-page figure/table regions (currently unioned onto the first page), persisted grid-truncation
  markers, and richer checksum/parser/TEI provenance on `paper_figures`. Real findings, but none
  caused the H1c gate failure, and folding them in would have turned H1b.1 into H1b.5.
- **Table reconstruction**, vector-rule persistence, caption↔table association, heading/body
  association, multi-page tables, assembled `EvidenceUnit` rows, assembled retrieval or verification,
  re-embedding, eligibility changes.
- **Unrelated CI/Ruff/CRLF repair.** The pre-existing Ruff baseline in `tools/evidence_hygiene/*.py`
  and the CRLF freeze-battery failures are untouched by scope.

---

## Manual verification script

```powershell
# 1. migrate a COPY of a real library (never the live one)
python -c "import sqlite3; s=sqlite3.connect('file:.local/validation-summarize/validation.sqlite?mode=ro',uri=True); d=sqlite3.connect('.local/h1b1-validation/validation.sqlite'); s.backup(d)"
alembic -x url=sqlite:///.local/h1b1-validation/validation.sqlite upgrade head

# 2. everything should be ABSENT, not silently promoted
python tools/backfill_source_components.py --db-url sqlite:///.local/h1b1-validation/validation.sqlite --summary

# 3. repair, then confirm complete == current
python tools/backfill_source_components.py --db-url sqlite:///.local/h1b1-validation/validation.sqlite
python tools/backfill_source_components.py --db-url sqlite:///.local/h1b1-validation/validation.sqlite --summary

# 4. a rerun must write nothing
python tools/backfill_source_components.py --db-url sqlite:///.local/h1b1-validation/validation.sqlite

# 5. inspect one page: locator paths, representation state, any [INVALID] geometry
python tools/backfill_source_components.py --db-url sqlite:///.local/h1b1-validation/validation.sqlite --inspect-page 3 1
```

## Pytest

**2,933 passed, 4 skipped, 6 failed** (`pytest -n 4 -q`, 11m04s).

The 6 failures are the **pre-existing CRLF freeze-battery failures**, verified by mechanism rather
than assumed: the qualification battery compares SHA-256 digests of 10 frozen files, the single
mismatching file is `app/backend/llm/providers.py`, that file is **not in this increment's diff**,
and its content normalized CRLF→LF matches the frozen manifest digest **exactly** — so the content is
correct and only its working-tree line endings differ. Repairing that is out of scope here (it would
require a maintainer decision to re-freeze a preregistered profile, per CLAUDE.md).

Focused suites, all green:

| Suite | Result |
|---|---|
| `tests/test_source_representation.py` (new) | 37 passed |
| `tests/test_source_components.py` (H1b) | 45 passed |
| `tests/test_migrations.py` | 12 passed |
| `tests/test_pdf_processing.py`, `test_chunk_structure.py`, `test_grobid_pipeline.py`, `test_grobid_tei_parse.py`, `test_chunk_filtering.py` | 81 passed |

Gates: `python -m tach check` OK; `tools/check_line_budget.py` OK (593 files within the 600 cap —
`extraction.py` untouched at 593); `ruff format` + `ruff check` clean on every file this increment
touches.
