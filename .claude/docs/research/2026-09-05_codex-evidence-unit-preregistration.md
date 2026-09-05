# Evidence-unit reconstruction replication: preregistration

Status: **FROZEN BEFORE SAMPLE TEXT OR RECONSTRUCTION OUTCOMES WERE INSPECTED**

## Identity and independence

- H1a / increment 577 commit: `614338b25739afe6a92f4fa0a5faea93aea090e0`
- H1a tree: `4bbd758c7ac6e4aa1816d7fe9820f5b25541004e`
- Branch: `codex/evidence-unit-replication-20260905`
- Worktree class: dedicated, outside the Dropbox checkout
- Task: deterministic reconstruction of proposition-preserving evidence units from PDF extraction
- Random seed: `20260905`
- No model/provider calls are permitted.
- Claude Code's new proposition-preserving evidence-unit report and scratch outputs are prohibited until the
  independent findings and recommendation are committed.

The source library was opened read-only and copied with SQLite's online backup API. The pristine copy is ignored at
`.local/evidence-unit-replication/source-pristine.sqlite`.

| Artifact | SHA-256 |
|---|---|
| source database as observed before backup | `16633e3b4e1acaed0aa7217c1fe8fed2e8f6e169fd2cd02d3d32b67d21bc4543` |
| pristine online-backup snapshot | `fc402464bfb9eb26b02f4b7bd12a844bbdc828413dcfc751b3cbf8252da93f70` |
| H1a increment notes | `8ecc473ab043a3cccfa8a617476cf76a01523965e7d20aca91b1e7d267276ef2` |
| H1a evidence-hygiene report | `9ff684ac78e04af5bbfb1e914959ac59e51806bd39940643940aef8c97e0e809` |
| H1a classifier | `0a7180466679c75589c5b455cbaa297109ce9c67f099073b03fe451c208b5951` |
| H1a schema | `88bf28877d7efdb99ee6311dc1341bd4be1058636acff95f1d031aa4e803e98b` |
| H1a backfill | `a8069c1229f4fe444a56073c672260d199584e0e547ba732b8d4e37fc5dc1ee0` |
| H1a ignored hygiene sidecar | `1a4eef57cf093df993ef3851caa4519eb2ea8e76d5088dab05f014840806361f` |
| H1a frozen fixtures | `d436a929cb21c90cdd953c5ab2e557f9e8133d864b7eae7a5fda25abe9d69713` |
| H1a normalization/anchor safety receipt | `14aa581e0e6210687a879bded7099d533d8b131c6cb6a780420ca3ca35af29c5` |
| H1a retrieval receipt | `72d31a4133e9972e01c753e84ebd707a8ceba2f32f91c7491bb8332c70078577` |
| H1a reference-region receipt | `a2a96884c72f2744de231f08d45db92cb3716cd4d89d41cee1ab9589de963834` |

The source and snapshot each contained 229 paper rows, 115 attachments, 23,875 chunks, and 24,134 embeddings, and
both returned `PRAGMA integrity_check = ok`. Counts are identity facts, not study outcomes.

## Hypotheses

- **H1:** A nontrivial proportion of scientifically meaningful current chunks are not proposition-bearing alone.
- **H2:** Stored geometry faithfully recovers a meaningful subset of prose fragmentation.
- **H3:** Chunk ID / emitted order is insufficient for safe general neighbor merging.
- **H4:** Table-cell meaning generally requires context beyond the cell.
- **H5:** Current geometry recovers some caption/table relationships, while richer reread structure is required for a
  substantial remainder.
- **H6:** Additional deterministic ingestion structure can recover evidence without an LLM inferring context.
- **H7:** Faithful semantic-referent recovery, not fewer chunks or higher cosine similarity, is the primary outcome.

## Study universe and sampling

The population universe is current chunks belonging to live papers and available scholarly-PDF attachments in the
canonical article roles, with source attachment checksum agreement and a current H1a `chunk_structure` row. The
currently retrievable subset additionally requires a current embedding and survival of the production repeated-
boilerplate filter. Population counts will be recorded before selection.

Sampling is deterministic without replacement:

1. **Probability arm (target 120).** Stratify by H1a's 13 `chunk_type` values. Allocate four cases to every nonempty
   stratum (or census a smaller stratum), then distribute remaining slots proportionally by largest remainder.
2. **Stress arm (target 60).** Select five non-duplicate anchors, when available, for each: short/truncated prose;
   heading/body; body/NULL/unknown scientific content; Results prose; Methods/statistics; captions/panels; simple
   tables; complex tables; isolated rows/cells; significance footnotes; multi-column pages; multi-page tables.
3. Stress anchors already selected by the probability arm are skipped. An undersized stratum stays undersized rather
   than being silently replaced by an unrelated case. Cases may receive multiple secondary tags.

The sample manifest records opaque case ID, sampling arm and primary stratum, inclusion probability for the
probability arm, paper/attachment/chunk IDs, source checksums and text hashes, page, nesting keys, and secondary
layout tags. Raw text and private paths remain ignored. Random overlap with old H1a fixtures is reported, not used to
choose or reject a case; no new Claude fixture is consulted.

## Proposition-bearing rubric and blind order

Adjudication has two separately hashed passes.

**Pass A: text only.** Cases are shuffled and expose only opaque ID and current chunk text. H1a type, section, paper,
neighbors, geometry, and PDF are hidden. Code:

- `scientifically_meaningful_as_shown`: yes / no / ambiguous;
- `standalone_proposition_bearing`: yes / no / ambiguous;
- `missing_context`: any of antecedent, population/group, comparison, outcome/construct, measure, value unit,
  direction, row header, column header, caption/title, table footnote, panel label, section/heading, or other;
- rationale.

A unit is proposition-bearing only when enough source-supported context remains to identify what the finding,
method, or value refers to. Grammar is not required. A bare statistic, orphan value, label-only heading, or table
cell without structural referents is not proposition-bearing. Ambiguity is preserved.

**Pass B: source revealed.** Only after Pass A is hashed, reveal stored neighborhood and the checksum-matching PDF.
Code whether meaningful content exists in the source; the minimum required neighborhood; DB-only, PDF-reread, and
unresolved recoverability; expected evidence-unit form; and false-join hazards. Source truth may correct the
`scientifically_meaningful_as_shown` interpretation but never rewrites the frozen Pass-A standalone rating.

## Fixed reconstruction strategies

- `S0_CURRENT`: the current chunk unchanged.
- `S1_ID_NEIGHBOR`: concatenate immediately adjacent same-attachment chunk IDs. This is an intentionally unsafe
  negative control for H3.
- `S2_STORED_PROSE_STRICT`: same attachment/page, different blocks, same inferred column, vertical gap from 0 to 1.5
  paper-median span heights, and lexical continuation (left lacks terminal punctuation or ends in a line-break
  hyphen; right begins lowercase, digit, or continuation punctuation). Caption, table, heading, running furniture,
  publication metadata, and reference boundaries veto the join. Maximum three source chunks.
- `S3_STORED_HEADING_CONTEXT`: attach an explicit same-column stored heading to the nearest following compatible
  body unit within three median span heights. Missing pure headings are not guessed.
- `S4_STORED_TABLE_GEOMETRY`: cluster page-local grid candidates; row peers must overlap in y or have midpoint
  separation no greater than 0.6 median span height; column alignment must be geometrically unique. A caption may
  attach only on the same page, within three median span heights, with at least 0.5 horizontal overlap and no
  competing candidate. Footnotes require an exact marker, table-width overlap, and no competing table. Any
  non-unique row, column, caption, or footnote mapping remains ambiguous.
- `S5_PDF_PROSE_REREAD`: reread page dimensions, original and sorted block order, block boxes, line order, span order,
  and span text; apply the strict prose rule using true page/column geometry.
- `S6_PDF_TABLE_REREAD`: compare PyMuPDF 1.27.2.3 `Page.find_tables()` output with independently reconstructed
  row/column/caption/footnote geometry. Simple, complex, and multi-page layouts are reported separately.
- `S7_FIGURE_STRUCTURE`: assess only preservation of figure bounds, caption, panel labels, extracted axis/legend text,
  adjacent explanatory prose, and provenance. No plot interpretation, OCR, or value estimation.

Every derived reconstruction retains ordered source components and their individual quote surfaces. A composite is
never called one contiguous verbatim quote unless it is actually contiguous.

## Outcomes and analysis

Primary outcomes are:

- standalone proposition-bearing share;
- scientifically meaningful but stranded share;
- reconstruction attempt, faithful recovery, partial recovery, unresolved, and false-association counts;
- harmful false joins by fragment, column, paragraph, caption/table, row/column, footnote, and reading order;
- current-storage versus PDF-reread recovery;
- table-specific useful-value, missing-referent, recovery, ambiguity, and false-association counts;
- exact source-component and quote-surface provenance retention.

Probability-arm estimates use design weights. Raw probability and stress counts remain separate. Any intervals use a
paper-clustered stratified bootstrap and are labeled sampling uncertainty only; cases nested in one paper are not
treated as independent scientific documents. Chunk-count reduction and embedding similarity are descriptive only.

The optional retrieval probe runs only if a strategy has zero confirmed harmful joins, at least 20 faithful
recoveries, at least five papers, at least two layout types, and complete component provenance. It reuses the two
exact frozen questions in H1a `tools/evidence_hygiene/experiment.py`, the same embedding model, and scratch-only
derived embeddings. Retrieval is reported separately from correctness.

## Interpretation and readiness rules

- `READY TO IMPLEMENT`: deterministic; complete provenance; ambiguity preserved; zero harmful joins in evaluated
  cases; at least 20 faithful recoveries across five papers and two layouts.
- `LIMITED PROTOTYPE ONLY`: useful for a bounded layout but insufficiently general or with unresolved precision risk.
- `RESEARCH FURTHER`: too few cases, missing required metadata, or unresolved ambiguity.
- `REJECT`: systematic false associations or misleading provenance.

The smallest recommended increment may contain only additive ingestion/evidence-substrate elements rated
`READY TO IMPLEMENT`. No result authorizes retrieval, prompt, verifier, provider, routing, model, planner, or
qualification changes.

## Stop and amendment rules

Stop before primary measurement if the H1a tree is incomplete; the snapshot fails integrity; migration/backfill
changes raw text or embeddings; runtime `bbox_json` representation disagrees with the harness; sample selection is
nondeterministic; a provider/model call occurs; or Claude's prohibited report/output is accessed. If a method defect
is found later, preserve existing artifacts, write and commit an explicit amendment, and restart only the affected
condition. Do not tune rules against primary outcomes.

If exact source PDFs are unavailable or checksum-mismatched, DB-only analysis may continue, but those cases are
`PDF_UNAVAILABLE` rather than inferred. If more than 20% of sampled cases lack a matching PDF, stop the reread arm
and report the coverage defect. Do not substitute a different file.
