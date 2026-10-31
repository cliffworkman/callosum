# Source-role repair contract (inc 611)

## One shared, pure judgement of text form

`app/backend/pdf_processing/source_role.py`:
- has no connection, file, model or network access;
- never reads a section label, because the label is the signal under suspicion.

`assess_prose(text)` returns one of four outcomes, each with a reason code.

| Outcome | Condition (all must hold) | Reason |
|---|---|---|
| `substantive_prose` | With citation apparatus stripped, the residual: has ≥20 words; ends in terminal punctuation; has stopword ratio ≥0.22 and capitals ratio <0.30; contains a finite-clause marker from a closed list (auxiliaries, copulas, modals, first person); shows no entry structure. The raw text also shows no entry start | `prose.citations_stripped` |
| `mixed_prose_and_entries` | ≥2 leading sentences, each ≥6 words and free of entry marks, together reading as ≥20 words of prose; followed by entry structure or an entry start | `prose.leading_prose_then_entries` |
| `prose_fragment` | 8–19 words; terminal punctuation; no citation apparatus at all (raw text equals residual); no bare year, no colon, no entry structure; stopword ratio ≥0.25; capitals <0.20; a finite marker | `prose.short_finite_clause` |
| `not_prose` | Anything else | `prose.criteria_not_met` |

**What citation stripping removes:**
- parenthetical author-year groups (looped);
- a leading orphaned citation tail ("al., 2004; Tucker et al., 2006).");
- numeric brackets;
- superscript numerals flattened after punctuation.

**What counts as entry structure:**
- ≥2 `Surname, I.` matches, or ≥2 Vancouver initials;
- `volume(issue)` (including issue ranges such as `1(3/4)`) or `volume:pages`;
- a DOI, or a numbered entry.

**What counts as an entry start** (detected on the raw text, because stripping destroys it):
- `Surname, I. (Year)`, `Surname AC (Year)` or `C. A. (Year)`.

Running prose cites `Surname (Year)` or `Surname et al. (Year)`, never initials before the year.

## Consumer 1: classification (`chunk_structure.classify_paper`)

| Context | Old (v1) | New (v2) |
|---|---|---|
| In region, `_is_clear_prose` | `body_prose` `ref_region.prose_veto` | unchanged |
| In region, substantive, not a caption | `reference_entry` `ref_region.member` | `body_prose` / scientific, `ref_region.prose_veto.citations_stripped` |
| In region, fragment or mixed | `reference_entry` `ref_region.member` | `unknown` / unknown, `ref_region.ambiguous.<outcome>` |
| In region, otherwise | `ref_region.member` | unchanged |
| Shape rule (`biblio_score ≥ 3`), substantive | `reference_entry` | skips the shape rule; falls through to the prose rule |
| Shape rule, mixed | `reference_entry` | `unknown`, `shape.ambiguous.mixed_prose_and_entries` |
| Final, substantive | `unknown` `fallthrough` | `body_prose`, `shape.clear_prose.citations_stripped` |

**Provenance is preserved:**
- `reference_region` and `reference_region_source` are still recorded on every overridden row;
- the old reason codes are untouched;
- every changed outcome carries a new, specific reason code.

**Ambiguity stays explicit.** A fragment or a prose-then-entries chunk becomes `unknown`, never a confident
label. The 607 policy never demotes `unknown`.

**Captions are never promoted** by the new veto.

## Consumer 2: the heading filter (`summarization/reference_rescue.py`)

`reference_filtered_rows(conn, stmt)` works in two phases.

1. **Main fetch.** This is the unchanged SQL exclusion of references-family chunks: GROBID preferred, NULL kept.
2. **Rescue.** A narrow `(id, chunk_version)` query lists the labelled chunks in the same scope.
   - A chunk is rescued when `rescued_from_reference_label(text)` holds: `contains_prose(text)`, and the text is
     not a publisher, licence or access notice.
   - Text is read only for chunks not yet decided in this process.
   - Full rows are fetched only for rescued chunks, in batches of 900 (`sql_batch`).
   - Rescued rows are merged into chunk-id order, so the result equals what one ordered query would return.

**Ordering and scope:**
- This runs before boilerplate detection and vector retrieval.
- It applies in whole-library (query) scope and in the faceted pool. These are the same callers as before, so the
  backlog #82 parity holds.
- Selected-papers and cluster scopes never applied the filter, and still do not.

## Not changed (verified)

**Retrieval models:**
- MiniLM default; Arctic S opt-in;
- identity-scoped vector search;
- the complete-index fail-closed check.

**Budget and policy:**
- the 8-slot budget and the 3× overfetch;
- deterministic ranking;
- the 607 policy (`evidence_eligibility`, unchanged), which demotes current `bibliographic` labels only.

**Not touched:**
- inc 609 NLI fail-closed and model provenance;
- inc 610 index supervision;
- DeBERTa.

**607 is not extended to the faceted or broad path.** The faceted pool gains only the heading-filter rescue it
already shared.

## Known limitations (not repaired here)

- **Declarations inside reference regions.** Competing-interest, data-availability and funding statements are
  neither science nor bibliography. v2 marks them `unknown` instead of `bibliographic`. A dedicated structural
  type would be more precise, but that is a taxonomy change outside this task.
- **Non-scientific prose rescued from a `references` label.** Some rescued chunks are prose but not science:
  author biographies, a book preface, questionnaire items. Each is a recognised non-reference, kept on purpose:
  silence is not a certificate, and they compete on retrieval rank like any other non-reference prose.
- **Rule calibration.** The rules use fixed linguistic floors carried over from the existing prose veto (20 words,
  0.22 stopwords). They were not tuned to the adjudicated pilot. Three shape bugs found while reading population
  samples were fixed as rule errors: initials before a year; issue ranges; a single title-like "sentence" before a
  source. Their precision has been inspected, not estimated. A held-out evaluation is still required before
  anyone claims the rules are scientifically superior.
