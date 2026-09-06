# Cross-agent adversarial H1b.2 gate review

> **This is a cross-agent adversarial review, not a fully independent audit**, because Claude
> participated in the initial H1b.2 implementation before Codex inherited the uncommitted work,
> completed validation and documentation, and made the final commit. The two production hunks under
> review were written by Claude and kept verbatim by Codex. Weight this accordingly: the adversarial
> *state construction* below is fresh and was written against the committed artifact, but the author
> of the code and the author of these attacks are the same agent. For future increments the
> implementation and audit roles are to be separated from the start.

| Item | Value |
|---|---|
| Target commit | `aab95f27f50fbcff1c12ffacb234424553fe9734` |
| Parent | `d6a83870710bbe75abd0276020f62c5ffaac0215` |
| H1b.1 baseline | `1f65f8e90c92263d80c0991601a5b805dca568e2` |
| Migration head | `0081_source_representations` (unchanged — no new migration) |
| Date | 2026-09-05 |

---

## 1. Diff audit

`git show --stat aab95f27`: six files, **two production**.

| File | Delta |
|---|---|
| `app/backend/pdf_processing/source_components.py` | +15 (one `import math`, one 2-line guard, docstring) |
| `app/backend/persistence/source_representation_repo.py` | +42/−5 (one subquery, one outerjoin, one WHERE clause, docstring) |
| `tests/test_source_representation.py` | +228 |
| `.claude/CLAUDE.md`, `.claude/changes.md`, `INCREMENT-580-NOTES.md` | docs |

Confirmed absent: migration, retrieval/prompt/provider/verifier change, locator redesign, state-model
redesign, reconstruction work, unrelated cleanup. The production delta is narrowly the two blockers.

## 2. Currentness identity coherence — 6/6 adversarial cases closed

Fresh adversarial states built against the committed code on throwaway migrated databases
(harness: `.claude/research/claude_h1b2_gate_review.py`).

| Case | Mutation | Result |
|---|---|---|
| G (control) | none | **CURRENT** ✓ |
| A | representation `extraction_tool` | non-current ✓ |
| B | representation `extraction_version` | non-current ✓ |
| C | page `source_checksum` | non-current ✓ |
| D | page `derivation_version` | non-current ✓ |
| E | page `extraction_tool` | non-current ✓ |
| F | page `extraction_version` | non-current ✓ |
| H | 1 of 5 pages `extraction_version` | non-current ✓ |

Cases C–F mutate exactly **one page of three** and leave all three page rows intact, so they are
coherence failures rather than count failures. Universality was checked separately by drifting the
**first, middle and last** page of a five-page graph one at a time — each invalidates the whole
attachment. The H1b.1 checks are not weakened: `state`, `skipped_pages`, `written_pages` and
`written_components` mutations are still rejected, and restoring a healthy envelope makes the
representation current again.

**32/32 adversarial assertions passed.**

## 3. SQL / NULL semantics — verified, not assumed

The docstring's claim that the identity columns are NOT NULL was checked against the **live DDL** in
the migrated corpus, not the ORM model:

- `source_pages`: `source_checksum`, `extraction_tool`, `extraction_version`, `derivation_version`
  all `NOT NULL`; `UNIQUE (attachment_id, page_number)`.
- `source_representations`: same four `NOT NULL`; `UNIQUE (attachment_id)`.

So `!=` can never evaluate to NULL and silently admit a mismatch, and duplicate page rows for one
`(attachment, page)` are structurally impossible. No new requirement is warranted — the schema
already prevents these states.

**The one real risk in this construction was auto-correlation**: `source_representations` appears
both in the outer query and inside the new subquery. The compiled SQL shows the subquery carries its
**own** `FROM source_pages JOIN source_representations`, aliased `anon_3` — self-contained, not
correlated to the enclosing FROM:

```sql
LEFT OUTER JOIN (SELECT source_pages.attachment_id AS aid, count(*) AS n
  FROM source_pages JOIN source_representations
       ON source_representations.attachment_id = source_pages.attachment_id
  WHERE source_pages.source_checksum      != source_representations.source_checksum
     OR source_pages.extraction_tool      != source_representations.extraction_tool
     OR source_pages.extraction_version   != source_representations.extraction_version
     OR source_pages.derivation_version   != source_representations.derivation_version
  GROUP BY source_pages.attachment_id) AS anon_3 ON anon_3.aid = source_representations.attachment_id
... AND coalesce(anon_3.n, 0) = 0
```

Outer-join behaviour is correct in both directions: an attachment with no incoherent pages produces
no `anon_3` row → `coalesce(…, 0) = 0` → eligible; one or more → excluded. Orphan pages (pages with
no envelope) are dropped by the inner join but their attachment never enters the outer `FROM rep`,
so it cannot be current either. Zero orphan pages exist in the corpus.

## 4. NaN / non-finite classification — closed

| Input | Result |
|---|---|
| NaN in x0 / y0 / x1 / y1 (each) | `invalid` / `non_finite` ✓ |
| all-NaN bbox | `invalid` / `non_finite` ✓ |
| `+inf`, `-inf` | `invalid` / `non_finite` ✓ |
| partial bbox with `None` (x0, y1, whole bbox) | `unknown` / `missing`, **no TypeError** ✓ |
| `None` **and** NaN together | `unknown` / `missing`, no raise ✓ |

Guard ordering verified by execution, not by reading: the missing/partial check precedes
`math.isfinite`, so it is never handed a `None`; the finiteness check precedes every numeric
comparison. The mixed `None`+NaN case — the nastiest ordering probe — fails closed on the missing
branch.

## 5. NaN persistence seam — closed

SQLite's actual behaviour, measured rather than assumed: `NaN` binds to **NULL** (`typeof = null`);
`inf` is stored as `inf`.

Persisting a page containing a NaN raster bbox through the real write path:

```
persisted image: x0=10.0  y0=None  x1=100.0  y1=50.0   state=invalid
persisted image: x0=None  y0=None  x1=None   y1=None   state=invalid
```

- pre-persistence classification: `invalid` ✓
- persisted rows never `geometry_state='valid'` ✓
- **forbidden condition (NULL coordinate AND `state='valid'`): count = 0** ✓
- surviving finite coordinates untouched — no coordinate manufactured to preserve the NaN ✓

The prior failure class is unreachable. A qualification worth recording: because SQLite cannot store
NaN, re-deriving state from the *persisted* row would yield `unknown` where the stored judgment says
`invalid`. Both are fail-closed and the stored one is stricter, so this is a documentation point, not
a defect — but H1c must read `geometry_state`, not re-derive it from stored coordinates.

## 6. Finite geometry — unchanged

Ordinary → `valid`; inverted → `invalid`; out-of-page → `invalid`; inside 2.0pt → `valid`; just past
2.0pt → `invalid`; zero-area → `valid`. Tolerance still exactly `2.0`. Zero-area is **not** treated as
an H1b.2 failure; the H1c qualification stands — algorithms needing rectangle-area/overlap semantics
must additionally require non-zero area.

## 7-8. Live corpus

| Check | Result |
|---|---|
| Live PDF attachments current under the H1b.2 rule | **114 / 114** |
| Falsely non-current | **0** |
| Trashed PDFs outside live coverage | 1 (no representation row) |
| Pages compared to their envelope | **1,628** |
| Pages disagreeing | **0** |
| Pages with no envelope | 0 |
| Distinct `(tool, version, derivation)` across all pages | 1 |
| Components represented | **1,089,546** |
| Recomputed with the committed classifier vs stored | **0 disagreements** |
| Non-finite stored geometry | **0** |
| NULL coordinate + `state='valid'` | **0** |
| Inverted | **363** (expected 363) |
| Out-of-page beyond 2.0pt | **1,113** (expected 1,113) |
| Zero-area (all images) | 3, measured separately |

No geometry was rewritten; every stored coordinate is unchanged.

## 9. Data and retrieval invariants

Reproduced with **Codex's own harness and serialization**, not a re-implementation:

| Data | Rows | SHA-256 vs frozen H1b.1 receipt |
|---|---:|---|
| `chunks` | 23,875 | `c0b4d848…fa6e97` IDENTICAL |
| `embeddings` | 24,134 | `f91de983…6ec56` IDENTICAL |
| `attachments` | 115 | `6ee7c192…edef84` IDENTICAL |
| vec row-id map | 24,032 | `d9ef3266…f3955c3b9` IDENTICAL |
| vec vector blobs | 26 | `ab474f04…dd35db` IDENTICAL |

Fixed-vector retrieval probe (query ids 14353–14362, top-20, hex distances), untouched original vs
H1b.2 target:

```
before : 884470634b09f8bbb8938a08788107c7a064e920290f9e8667e05ab4eb426025
after  : 884470634b09f8bbb8938a08788107c7a064e920290f9e8667e05ab4eb426025
frozen : 884470634b09f8bbb8938a08788107c7a064e920290f9e8667e05ab4eb426025
exactly_equal: True
```

**Receipt-hash provenance note.** An earlier Claude-side harness reported `5cb20a94…` for "the same
probe". That is not a conflict and not a second anchor: it was a `repr()`-of-tuples encoding of the
same ordered ids and distances, whereas the frozen receipt is Codex's canonical
`json.dumps(sort_keys=True, separators=(",",":"))` encoding. Re-run here under the **frozen**
serialization, the target reproduces `8844706…` exactly. The Claude-side value should not be treated
as a provenance anchor.

## 10. Non-load-bearing

Independent grep across `app/` and `integrations/` for every substrate token
(`source_representations`, `source_representation_repo`, `incoherent_pages`, `geometry_state`,
`component_path`, `SourceLocator`, `attachments_with_current_source`, `is_source_current`,
`record_source_failure`) returns 13 files, all sanctioned: persistence/schema/migration,
`pdf_processing` (`source_components.py`, `ingest.py`), the developer backfill, tests, and the two
research harnesses.

**Zero** references in `summarization/`, `embeddings/`, `llm/`, `citations/`, `api/routers/`, or
`fulltext_repo.py`. The repo's own 20 guard tests also pass. H1b.2 affects ingest, backfill and
currentness inspection only.

## 11. Currentness performance

Absolute run on this machine: min 187.08 / median 206.59 / max 220.06 ms — above the frozen H1b.1
baseline (162.66 / 169.72 / 192.42), but the machine was loaded. A **paired, interleaved**
measurement isolates the clause itself:

```
H1b.1 statement (no coherence) : median 168.80 ms -> 114 current
H1b.2 statement (committed)    : median 167.63 ms -> 114 current
paired median overhead         : -1.16 ms (-0.69%)
```

Indistinguishable from zero, consistent with the implementer's reported +1.10 ms / +0.65% (also
noise). Expected: the clause scans 1,628 page rows beside an aggregate over 1,089,546 components. **No
operational regression.**

## 12. Tests

162 passed across `test_source_representation`, `test_source_components`, `test_migrations`,
`test_pdf_processing`, `test_chunk_structure`, `test_grobid_pipeline`. 20 non-coupling guards passed.

H1b.2 cannot have caused the 6 reported pre-existing failures: the intersection of its changed-file
set with the 10 frozen qualification files is **empty**, and the sole mismatching frozen file is
`app/backend/llm/providers.py` — absent from the diff, with content whose CRLF→LF normalization
matches the frozen digest exactly (line-ending drift, not content drift).

## 13. Residual qualifications for H1c (none blocking)

1. **Read `geometry_state`, do not re-derive it.** For a NaN observation the stored judgment
   (`invalid`) is stricter than what re-deriving from the persisted NULL coordinates would give
   (`unknown`). Both fail closed; the stored one carries more information.
2. **Zero-area regions.** 3 image components have zero area and are `valid`. Any algorithm relying on
   rectangle-area or overlap semantics must additionally require non-zero area. Unchanged H1c
   qualification.
3. **Coherence is internal only, by design.** Nothing compares either side against the currently
   installed PyMuPDF. A global extractor-upgrade invalidation policy remains a separate, deliberate
   architectural decision, correctly not made here.
4. **Review independence.** Per the header, this is cross-agent, not fully independent.

---

## Gate decision

All fifteen conditions hold: six identity-drift cases non-current (1); coherent graph current (2);
one incoherent page invalidates a multi-page representation (3); SQL/NULL/outer-join/duplicate
semantics cannot bypass the check, verified against live DDL and compiled SQL (4); NaN in any
coordinate invalid (5); ±infinity invalid (6); partial/None safely handled with no raise (7); NaN
cannot persist as partial geometry marked valid (8); finite geometry unchanged (9); 114/114 live
representations current (10); 1,628/1,628 pages envelope-coherent (11); no live non-finite or
partial-valid geometry (12); chunks/embeddings/vectors/retrieval byte-identical to the frozen
receipts (13); non-load-bearing (14); no new blocker relevant to bounded H1c association research
(15).

**H1c GATE = OPEN**

H1c was not started.
