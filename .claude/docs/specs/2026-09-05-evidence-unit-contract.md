# The EvidenceUnit contract — `evidence_form = verbatim | assembled`

**Status: design only. Nothing in this document is implemented.** No `EvidenceUnit` type, table,
column, or retrieval surface exists as of increment 578 (H1b). This spec exists so the distinction
is settled *before* the first assembled unit does — because an assembled string reaching today's
verifier would correctly fail to verify, and the failure would look like a bug rather than a
category error.

**Date:** 2026-09-05
**Increment:** 578 (H1b, source-component preservation)
**Predecessors:** `.claude/docs/research/2026-09-05_proposition-preserving-evidence-units.md` §8/§9,
`.claude/docs/research/2026-09-05_codex-evidence-unit-replication.md` §10

---

## 1. Why this contract has to exist before the code does

Two independent studies converged on the finding that a current chunk is an *extraction* unit, not
an *evidence* unit. A large class of units cannot be repaired by any eligibility setting: `p = .146`
is a real reported statistic that has lost its referent. Excluding it discards real evidence;
keeping it yields a unit that can never verify. Only reconstruction resolves that.

But reconstruction produces a string that **never existed contiguously in the document**. A table
fact assembled from caption + row label + column header + cell —

```
Table 6 > PCC > DKEFS > p = .761
```

— is a genuinely useful representation and is *not a quotation*. Presenting it as one would violate
core invariant #2 (the coordinate honesty contract) directly, and would do so invisibly: the string
looks like a quote, carries a page number, and would render with a highlight.

The fix is not to forbid assembly. It is to make the distinction **structural**, so that an
assembled unit cannot be displayed or verified as a verbatim one by accident.

---

## 2. The two forms

### `verbatim`

- Exactly one contiguous source region.
- Current quote semantics apply unchanged: `exact` / `region` / `null` coordinate precision, one
  highlight, the existing `canonical_text_contains` check.
- This is what every unit in callosum is today.

### `assembled`

- **N ordered components**, each retaining its own `(attachment, page, bbox, char range)`.
- Each component carries a **role**: `body`, `heading_context`, `table_caption`, `row_header`,
  `column_header`, `value`, `footnote`.
- Displayed as **multiple highlights**, never as a single quotation, and never inside quotation
  marks.
- Carries an explicit `assembly_basis` (`adjacency` | `caption_table` | `table_row`) and a
  `confidence_in_assembly` that is **measured, never assumed**.

This **extends** invariant #2 rather than bending it. Region-level or absent coordinates are still
never presented as exact highlights; an assembled unit simply has more than one of them.

---

## 3. The verifier implication (the part that must not be gotten wrong)

`canonical_text_contains` would correctly **fail** an assembled string, because that string appears
nowhere in the source.

**This is not a defect to be worked around.** The rule that follows from it:

> **`canonical_text_contains` must never be relaxed to accept an assembled string.**

An assembled unit requires **per-component verification plus separate verification of the assembly
recipe**:

1. Each component is verified verbatim against its own coordinates and the attachment checksum.
2. The *assembly* — the claim that these components belong together — is a separate assertion with
   its own evidence and its own confidence, and it is what a reader is being asked to trust.

Meaning is not established by string concatenation. A unit whose components all verify individually
can still be a wrong assembly, and the display must make that distinguishable.

---

## 4. Sketch (not a schema)

```
EvidenceUnit
  attachment_id
  evidence_form        : verbatim | assembled
  components           : [ (source_component_id | chunk_id, page, bbox, char_range, role) ]
  reading_order_key    : (page, native_block, native_line, native_word)
  proposition_state    : bearing | not_bearing | unresolved
  assembly_basis       : null | adjacency | caption_table | table_row
  assembly_confidence  : measured, never assumed
  derivation_version
```

Two deliberate omissions, both inherited from H1a's reasoning:

- **No `scientific_claim_eligible` flag.** Eligibility is task-relative — a reference entry is not
  evidence for a scientific claim but *is* evidence for "what did this paper cite?" — so it must be
  computed per question, never frozen into a column.
- **No overall quality or trust score.** Composite scores are declined by PRINCIPLES.md #7.

`reading_order_key` uses **native** MuPDF order, which H1b now preserves separately from the
post-sort ordinal (`source_components.native_order` vs `sorted_order`). Neither is a claim about
semantic continuity.

---

## 5. What H1b deliberately did not build

H1b preserves the source structure an assembled unit would be built *from*, and stops there. It
does **not** implement: adjacent-chunk merging, prose reunification, heading/body reconstruction,
caption↔table association, table-row assembly, evidence-unit retrieval, re-embedding, or any
`assembled` record.

The measurements are the reason, not caution for its own sake:

| Measure | Result |
|---|---|
| Bounded one-neighbour join, genuine recovery | ≈ 6.7% of units |
| Same joiner, false-join rate | **59.1%** [44%, 72%] |
| After applying H1a hygiene first | 27.0% residual [15%, 43%] |
| Correct joins destroyed by hygiene | **0 / 12** |

A 27% residual false-join rate is not shippable at any retrieval-facing setting.

---

## 6. The ordering invariant

> **Hygiene precedes reconstruction.**

Applying H1a's boilerplate metadata *before* joining preserved **12/12** adjudicated correct joins
while eliminating 38% of boilerplate-caused false joins. Joining first amplifies pollution.

This is a pipeline **ordering constraint**, measured — not a claim that joining is safe. It is not.

---

## 7. Prerequisites before any `assembled` unit may exist

1. A precision measurement for caption↔table association — the rate (41% associable, median gap
   6.9pt) is known; whether an associated caption is the **right** caption has never been
   adjudicated. This is H1c's cheapest and most natural first task.
2. A table-row reconstruction path limited to the population where PyMuPDF's `lines` strategy
   already fires with a detected header (100% header recall over 34 tables) — the one population
   where caption, row label, column header and cell all come from a single trustworthy source.
3. Per-component verification implemented and tested **before** the display layer can render a
   multi-region unit.
4. A display treatment that cannot be mistaken for a quotation, reviewed against invariant #2.

Until all four exist, `evidence_form` remains a documented distinction with exactly one inhabited
value: `verbatim`.
