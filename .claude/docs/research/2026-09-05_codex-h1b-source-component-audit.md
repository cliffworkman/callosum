# Independent H1b Source-Component Audit

## 1. Provenance / independence boundary

This audit was performed on the dedicated branch
`codex/h1b-source-component-audit-20260905` in an isolated worktree. The semantic target was fixed
before measurement at H1b commit `a41266ba4850a17ce04af3480b7237197416574f`, tree
`1fa67760adce3476aaf2ec99ae5b075171d82752`. H1a is commit
`614338b25739afe6a92f4fa0a5faea93aea090e0` (increment 577).

The copied pre-H1b database snapshot has SHA-256
`fc402464bfb9eb26b02f4f7bd12a844bbdc828413dcfc751b3cbf8252da93f70`. Detailed paths, article
text, database copies, and private measurements remain ignored under
`.local/h1b-source-component-audit/`. The deterministic seed was `20260905`.

Before freezing sections 1-18, I did **not** read Claude's H1b increment notes, implementation
appendix, final summary, or H1b scratch output. I used production code at the target, the committed
design-only `evidence_form` contract, pre-H1b research, my own earlier independent evidence-unit
replication, tracked fixtures, local PDFs, and my own measurements. No model or provider was called.

Two protocol amendments are committed separately. Amendment 01 excludes a copied database against
which two backfill processes accidentally overlapped before any outcome was recorded. Amendment 02
excludes two pre-measurement harness failures and a full-corpus comparison interrupted by a host
crash; none wrote an accepted receipt. After restart, the unchanged study copy passed
`PRAGMA integrity_check`, and the full measurement restarted from page 1. Neither amendment changed
the target, sample, hypotheses, metrics, tolerances, or interpretation rules.

Field semantics were preregistered. Text, hierarchy, kinds, identities, and orders had to match
exactly. Coordinates, dimensions, and font sizes used both exact comparison and the fixed absolute
tolerance `0.0001` PDF points; direction cosines used exact comparison and tolerance `0.000001`.
Surrogate primary keys were not required to survive destructive replacement; a stable logical
source locator was required.

## 2. Exact H1b commit audited

| Item | Identity |
|---|---|
| H1b commit | `a41266ba4850a17ce04af3480b7237197416574f` |
| H1b tree | `1fa67760adce3476aaf2ec99ae5b075171d82752` |
| H1b parent | `e64f5f7f4a07064850b55cffa3621ec674f6177d` |
| H1a commit | `614338b25739afe6a92f4fa0a5faea93aea090e0` |
| Database before migration | `0078_imported_collection_axes` |
| Audited migration head | `0080_source_components` |
| H1a migration | `0079_chunk_structure.py`: `8f717a208091d4ef3ea0ace374a3169578d942a279ddddc3943544710793b3ec` |
| H1b migration | `0080_source_components.py`: `39d8205c20a6ef2fb1eefbda51f2303daf95076adfa91c74ad8211258a4a0800` |
| H1a schema | `schema_chunk_structure.py`: `88bf28877d7efdb99ee6311dc1341bd4be1058636acff95f1d031aa4e803e98b` |
| H1b schema | `schema_source_components.py`: `e2d820e3cd002a0955773692dc4e520dbb5bb8ef45172b29be7f2d9ad3a37aa3` |
| Extraction module | `extraction.py`: `f7fc735d988d9acdcaa10c71e5e8a41bf2c9049c0ab58317dd9524fa6f82de5c` |
| Component builder | `source_components.py`: `f1a7686b66b702fee8c13b1dde3c138b9db2257f91bff786224b3ca7c0ce99d7` |
| H1a backfill | `backfill_chunk_structure.py`: `a8069c1229f4fe444a56073c672260d199584e0e547ba732b8d4e37fc5dc1ee0` |
| H1b backfill | `backfill_source_components.py`: `0818c4cf6e7ce1a40ca66acde59ff60d37bd7f1bcc55f850ee6ead36addc6602` |

The final research harness hash is
`c20c600cbe6279f0bf03abed9ac2b361cb161bc664d31e4f53c69c01431d3847`. Primary ignored receipt
hashes are: coverage `72962d482d1efce81a326843d8836a5191744dcf3023cf612e10c34915b6b1c0`,
Callosum round trip `f14810353d936b33d82904d02409fe5a2f7f2f01d86df2c519dd8c710892bc2d`,
independent raw reread `7e260feed017e7c8959bf0d65b8b89e44cfcaba89bbc4bf3ff2676489ce2fbb5`,
retrieval identity `8b8ac6b474cc40865935be99f7939e938421290fd16a2d032ee4539341926e07`,
structural audit `91771aed8be8bc2f0a85dab4a9159ed1231ea4faa06148b13a20e6e8c3068464`,
backfill edge cases `498905c485571655940ae4e7e8beb39077b80501327e9797ab938788ead8b49b`,
heading audit `825d09355ca25cabd9266742b97996951d34d233cfae32baf0877dec1e70c36c`,
and GROBID fixture audit `f03d006ec2d2b787b5d128c87985e5edaa898c86d26df04c4767411a0066c685`.

H1b adds `source_pages`, `source_components`, and `paper_figures`. It also captures source pages on
the extraction result, writes source rows under an ingest savepoint, adds figure coordinates to the
optional GROBID request, and records parsed GROBID figure/table structures. It does not add an
`EvidenceUnit`, reconstructed text, assembled-verification path, retrieval surface, or prompt path.

## 3. Live/current coverage

The live universe was the production backfill's actual predicate:

```sql
attachments
JOIN papers ON papers.id = attachments.paper_id
WHERE attachments.content_type = 'application/pdf'
  AND papers.deleted_at IS NULL
```

Current source state additionally required at least one `source_pages` row whose
`source_checksum` equals the live attachment checksum and whose `derivation_version` is
`source-components-v1`.

| Measure | Result |
|---|---:|
| PDF attachments total | 115 |
| Live/current PDF attachments | 114 |
| Trashed PDF attachments | 1 |
| Source pages | 1,628 |
| Source components | 1,089,546 |
| Text blocks | 24,192 |
| Headings | 598 |
| Lines | 146,579 |
| Spans | 910,764 |
| Raster-image blocks | 7,413 |
| GROBID figure rows in this snapshot | 0 |

All 114 live PDFs existed locally, matched their attachment checksum, and had current H1b rows.
The largest live attachment had 37,045 components, well below the 250,000-row cap. No page in the
accepted study snapshot had zero components.

## 4. Soft-delete accounting

The database retains 23,875 chunks: 23,782 live and 93 attached to trashed papers. There are ten
trashed papers. Direct joins established that all 93 chunks lacking H1a `chunk_structure` belong to
paper 2, that paper 2 is soft-deleted, and paper 2 contributes exactly those 93 rows. No live chunk
lacks H1a structure.

The one trashed PDF attachment is excluded by the production H1b backfill predicate. Its retained
chunks are therefore not a live/current coverage defect. This independently explains the earlier
93-row observation rather than accepting that explanation from the maintainer.

## 5. Raw-text / embedding invariants

Canonical order-stable hashes were taken before migration, after migration, after H1a backfill,
after the first H1b backfill, and after two normal H1b reruns. Every pre-H1b retrieval-bearing row
set remained exactly identical:

| Data | Rows | SHA-256 | Result across all snapshots |
|---|---:|---|---|
| `chunks` (complete rows, including text) | 23,875 | `c0b4d848a5b0178ad868a6d8d96ca8002a61c3d23bc9d31a30157f41d0fa6e97` | Exact |
| `embeddings` metadata | 24,134 | `f91de983ec3dc4afa11231be4ae18f79b986265a128af367471d46bd552e7d01` | Exact |
| `attachments` | 115 | `6ee7c19275e3007989493682dfa672b954d58b5049bb835e842c564acbedef84` | Exact |
| sqlite-vec row-ID map | 24,032 | `d9ef326667658fc474b388a5a02de054ea96f49700ef8363ba89fe1f3955c3b9` | Exact |
| sqlite-vec vector blobs | 24,032 | `ab474f0468b434dc518fd77ad1648ea05f33c369fd560fcf590878b1fcdd35db` | Exact |

The first H1b backfill wrote 1,628 pages and 1,089,546 components. Two subsequent ordinary reruns
wrote zero rows and classified all 114 attachments as already current. The second and third source
table snapshots were exactly equal: pages hash
`3724eaf614cd19699a123e2914e498424f843f1cc365af6db89a60d32c62c9a2`, components hash
`d5a614b3204610207c49f3a1aa995c3de7c2165dd72483d886f03008c1910853`.

Conclusion: H1b did not rewrite raw chunk text, attachments, embedding metadata, vector identities,
or vector content on the isolated database.

## 6. Retrieval non-coupling

Static inspection found H1b table names only in schema/repository, PDF extraction/ingest, the
optional GROBID parse pipeline, and the backfill. No Ask, summarization, provider, prompt, embedding,
vector-search, verifier, or API retrieval module reads `source_pages`, `source_components`, or
`paper_figures`. `ExtractionResult.source_pages` is ignored by `make_chunk_drafts`; persistence is
isolated in a nested transaction whose failure leaves authoritative chunks intact.

Ten preexisting sqlite-vec rows (IDs 14353-14362) were used as fixed query vectors. Their ordered
top-20 row IDs and exact hexadecimal floating-point distances matched before and after H1b. Both
result payloads hashed to `884470634b09f8bbb8938a08788107c7a064e920290f9e8667e05ab4eb426025`.

H1b therefore remained non-load-bearing for current retrieval, prompts, providers, verifier
behavior, and thresholds. The optional GROBID request now asks the external service for `figure`
coordinates and saves figures, but current retrieval does not read the new rows. This audit made no
network call, so exact behavior of an external GROBID build under the added request field was not
measured.

## 7. Native-vs-sorted-order validation

H1b's `sorted_order` is the enumerate position in `page.get_text("dict", sort=True)["blocks"]`,
including raster blocks that current chunking drops. It is the same numbering basis as
`chunks.bbox_json["block"]`. `native_order` is the unchanged MuPDF `block["number"]` carried by that
sorted dict. It is not a separately persisted `sort=False` list, but its unique numbers allow the
native block sequence to be reconstructed. No page had duplicate top-level native numbers.

All 1,089,546 stored values matched fresh Callosum extraction and the independent raw-PyMuPDF
sample. The fields are distinct in schema and behavior:

| Deterministic layout proxy | Pages | Pages whose orders differ | Mean pair disagreement |
|---|---:|---:|---:|
| One-column | 794 | 599 | 0.212 |
| Two-column | 476 | 475 | 0.356 |
| Uncertain | 358 | 282 | 0.372 |

In preregistered 40-page samples, 28 one-column and 40 two-column pages disagreed. These results
strongly reject treating either field as semantic reading order. They also confirm that H1b does
not silently reuse `bbox_json["block"]` as native identity.

## 8. Page/component geometry fidelity

The full Callosum round trip re-opened all 114 live PDFs and compared all 1,628 pages and 1,089,546
components against fresh `extract_pdf()` output. Page number, width, height, rotation, coordinate
system, extraction identity, derivation identity, checksum, component count, component path, kind,
all three order fields, bbox coordinates, text, font, font size, flags, line direction, and writing
mode had **zero exact mismatches**. Exact and tolerance-qualified rates were both 100% for every
field.

To prevent shared production code from masking a defect, a separately coded raw-PyMuPDF walker
then reread 31 deterministic adversarial pages. The sample covered one-/two-column layouts, order
disagreement, headings, images, captions, dense/table-like spans, and orphan values. All 29,405
component records again matched exactly; exact and tolerance-qualified geometry rates were 100%.

The graph had zero missing parents, cross-page parents, invalid top-level kinds, invalid line/span
parents, partial bboxes, empty span texts, or logical-path collisions. Ten pages retained nonzero
rotation.

There were 363 inverted bboxes, all raster-image blocks, concentrated in four attachments; 318
were in one attachment. One image bbox exceeded page bounds. Independent reread reproduced these
values exactly, so H1b faithfully preserved malformed/unusual extractor observations rather than
inventing them. They must be treated as unusable/uncertain geometry by a future association study,
not silently normalized into valid regions.

## 9. Per-span text/style fidelity

Every one of the 910,764 spans retained exact per-span text and a one-to-one mapping to its own
span bbox. All spans carried at least one observational style field; all 146,579 lines retained
direction fields. The full and independent comparisons found zero text, hierarchy, font, font-size,
flags, direction, or writing-mode mismatches, including sampled ordinary prose, multi-span blocks,
headings, dense table-like blocks, and multi-column text.

Style remains observational. No retrieval, eligibility, evidence, or heading gate reads font,
size, or flags. Superscript/subscript information is limited to PyMuPDF's span flags and geometry;
H1b does not assert semantics from it.

## 10. Heading preservation

H1b preserved 598 pure heading blocks with exact text, page, bbox, native/sorted order, and line/span
hierarchy. A deterministic 20-heading sample was passed back through current production extraction
and `make_chunk_drafts()`: **0/20** heading `(page, sorted block)` pairs appeared in fresh chunk
drafts.

Twenty-eight preserved heading coordinates do intersect heading-only chunks already stored in the
frozen database. Those chunks were created between 2026-06-21 and 2026-07-09, before the July
heading-skipping behavior and before H1b. H1b did not create or newly expose them; its exact
chunk-row invariant confirms they were unchanged. Thus preserving headings did not make headings
ordinary retrieval evidence, while the database usefully records a legacy-corpus caveat.

H1b does not bind a heading to body text. That is appropriately deferred.

## 11. Image/figure structural preservation

H1b stores 7,413 PyMuPDF raster-image blocks with page and bbox provenance and no pixels,
scientific interpretation, chart values, or retrieval text. Zero image blocks appeared in current
chunk provenance. Four independently reread image/figure pages matched exactly.

H1b does not call `page.get_drawings()` and does not promote vector drawing groups to figures. This
avoids the pre-H1b study's false-figure trap, but it means vector-only figure/rule bounds are absent.
The 363 inverted raster bboxes noted above are faithfully raw but unsafe for association until
validated. Figure-aware quantitative interpretation remains out of scope.

## 12. GROBID figure/figDesc review

The tracked TEI fixture has SHA-256
`4caa1b5746a20f78c7ef4cbdad8b70cbd696e036095a37cd1003eb7b7e8ad238`. An independent ElementTree
walk found three figures (one ordinary figure, two tables); production `parse_figures()` returned
three with the exact XML IDs. Both table grid shapes matched the TEI exactly: 3 rows x 4 cells and
11 rows x 7 cells. The ordinary figure's nested graphic supplied geometry; both tables honestly
retained null geometry because this fixture predates the added figure-coordinate request.

The preservation is useful but incomplete:

- the fixture's one table `<note>` has no destination field and is discarded;
- cell attributes and structural roles are not retained;
- multiple coordinate regions are unioned only on the first page, so a multi-page figure cannot be
  represented faithfully;
- grid row/cell/text bounds can truncate, but no persisted truncation marker records that fact;
- `paper_figures` lacks attachment checksum, derivation/parser version, and TEI-response hash, so
  staleness/provenance is weaker than `source_pages`;
- this database snapshot has no actual `paper_figures` rows, so corpus-level GROBID coverage could
  not be measured.

These rows add inspectable structure without changing current retrieval, but they are not yet an
adequate provenance substrate for load-bearing table reconstruction.

## 13. `evidence_form` contract review

The design-only `verbatim | assembled` distinction preserves the central invariant: a derived
multi-region string must never masquerade as a contiguous quotation. It correctly requires
per-component verification, separate verification of the assembly assertion, multiple highlights,
explicit roles, and an assembly basis. It explicitly forbids weakening `canonical_text_contains`
to accept text that never occurs contiguously.

The sketch is not yet sufficient as a storage contract. It permits `source_component_id` even
though forced replacement changed every sampled page/component surrogate ID. It mentions
`attachment_id` and `derivation_version`, but does not require attachment checksum, extraction
identity, a stable logical component path, or assembly-strategy version. H1b components also have no
character offsets, despite the sketch's `char_range`. A safe future reference should minimally use:

```text
attachment checksum
+ extraction / derivation identity
+ page number
+ stable component path (top sorted/native identity + child-order hierarchy)
+ exact component bbox/text hash
+ ordered role in the assembly
+ assembly strategy and version
```

The measured path basis had zero collisions across all 1,089,546 components and survived forced
replacement exactly for three attachments (five pages, 890 components). Surrogate page and
component IDs changed in every case. The logical locator is therefore derivable and stable, but it
is not materialized or enforced by schema. Future provenance must not expose the surrogate IDs as
durable source identity.

## 14. Backfill/idempotence

Normal backfill was idempotent: the first run covered 114 live attachments; two reruns wrote no
rows, skipped all 114 as current, and produced identical source-table hashes. Deleting one
attachment's rows on a disposable clone and rerunning restored two pages / 395 components; the next
run skipped it with stable counts. Altering the live attachment checksum excluded its old rows from
the current set. Trashed papers remained outside default processing.

Forced rebuilds of three attachments reproduced every logical page tree exactly while changing
surrogate IDs. Per-attachment transactions make a missing-row interruption recoverable.

However, the component-cap path has a confirmed completeness defect. With the cap lowered to ten
only inside the research harness, replacing a two-page attachment returned
`{pages: 1, components: 0, truncated: 1}` and logged the truncation. Because the persisted page's
checksum and derivation matched, `attachments_with_current_source()` classified this partial graph
as current. A subsequent ordinary backfill would therefore skip it forever. The production corpus
did not hit the cap, but H1b lacks a page-count/completeness/truncation invariant that prevents a
partial structure from masquerading as current.

This is a substrate defect, not a current retrieval regression: no current retrieval reads these
rows and all 114 accepted corpus rows were complete under fresh full extraction.

## 15. Adversarial fixture results

The safety set combines the newly selected raw-PyMuPDF pages with opaque cases from my own frozen
pre-H1b evidence-unit replication. All named PDF pages had one current H1b page row and component
coverage; no private path or article text is tracked here.

| Required hazard | Opaque fixture(s) | H1b observation |
|---|---|---|
| One-column prose | `H1B-37367932F1A8`, `H1B-2A9FCDDA9BFB` | Exact raw-source hierarchy/geometry |
| Two-column prose | `H1B-2AA5AE6FB640`, `H1B-FD864659D6B4` | Exact; native/sorted disagreement preserved |
| Stored/native disagreement | `H1B-D61A1ED10582`, `H1B-DA22AED0B48F` | Both fields exact and distinct |
| Cross-column false adjacency | `EU-05BF1228`, `EU-D9A733BB` | Components preserved; no continuity asserted |
| Cross-page continuation | `EU-05BF1228`, `EU-A02BD5D8` | Page boundary preserved; no continuation asserted |
| Pure heading | `H1B-5F01FC77D122`, 20-case heading sample | Exact; 0/20 in fresh chunk drafts |
| Caption near unrelated prose | `EU-5EF3E86E` | Text/geometry preserved; no association asserted |
| Caption near its table / competing caption | `EU-93B26BA6` | Components preserved; relation not represented |
| Simple ruled table | `EU-93B26BA6` | Span geometry retained; rules/grid not retained |
| Malformed/false table detection | `EU-5EF3E86E` | Raster/text retained; no table promoted |
| Complex side-by-side tables | `EU-CDACC579` | Structure retained; column/table identity unresolved |
| Multi-page table | `EU-D24CC1FD`, `EU-280A5F02` | Page components retained; continuation identity absent |
| Orphan table value | `H1B-AE864BDB5653`, `H1B-C089E374FFC6` | Value span retained; referent not reconstructed |
| Raster image/figure | `H1B-CFED436B973D`, `H1B-45014E71F62C` | Raster bbox exact; no scientific claim |
| GROBID figure/table | tracked TEI hash above | IDs/grid exact; notes/staleness/multi-page gaps |
| Soft-deleted retained chunks | paper 2 aggregate | 93 retained chunks correctly outside live coverage |

No H1b row falsely asserts paragraph continuation, caption ownership, table membership, row/column
meaning, footnote scope, or scientific interpretation. That is the key adversarial safety success.
The completeness bug is instead a false assertion about whether the stored graph is current.

The optional H1c association/reconstruction probe was **not run**. Its preregistered gate required
that truncated structures could not masquerade as current; the experiment in section 14 falsified
that condition. No false-association or recovery rate is therefore reported for H1c.

## 16. H1c readiness matrix

| Substrate / question | Classification | Independent basis |
|---|---|---|
| Non-load-bearing isolation | READY | Exact chunk/vector invariants; static and behavioral retrieval identity |
| Page dimensions/rotation | READY | 1,628/1,628 exact; 31-page raw sample exact |
| Block bbox + component hierarchy | READY WITH BOUNDED FIX | Exact fidelity; reject malformed raster rectangles explicitly |
| Per-span text/bbox/style | READY | 910,764 spans exact; observational only |
| Native and sorted order | READY | Distinct, exact, unique native numbers; neither semantic |
| Pure-heading preservation | READY | 598 retained; 0/20 fresh draft leakage |
| Raster-image bounds | READY WITH BOUNDED FIX | Exact preservation; 363 inverted bboxes require invalid-geometry state |
| Stable logical component locator | READY WITH BOUNDED FIX | Zero path collisions and force-stable; must be formalized, not surrogate PK |
| Backfill restart/idempotence | READY WITH BOUNDED FIX | Missing rows recover; truncated rows falsely look current |
| Same-column prose study | READY WITH BOUNDED FIX | Required fields present; begin only after completeness fix |
| Heading/body association study | LIMITED | Geometry/style available; scope remains unrepresented |
| Caption-to-table association study | LIMITED | Geometry available; table regions/rules and competing-object identity incomplete |
| Ruled-table detection | LIMITED | Span/raster structure present; vector drawing/rule geometry absent |
| Row/column/value reconstruction | INSUFFICIENT | No stable table grid for PyMuPDF corpus; GROBID subset incomplete |
| Table footnotes | INSUFFICIENT | GROBID notes discarded; PyMuPDF footnote roles absent |
| Multi-page tables | INSUFFICIENT | No continuation identity; GROBID region collapses to first page |
| Figure structural study | LIMITED | Raster bbox/captions possible; vector figures and malformed bboxes remain |
| Derived-unit provenance | INSUFFICIENT | Design invariant sound; stable locator/char ranges/strategy version not formalized |
| Persistent/retrievable assembled units | NOT IMPLEMENTED | Correctly outside H1b |

Answer to the primary readiness question: H1b preserves enough deterministic structure to justify a
bounded H1c design **after one narrow completeness/current-state repair**, but it does not pass the
preregistered gate to start that study today. Table reconstruction, table footnotes, multi-page
tables, and assembled-unit persistence remain materially under-specified.

## 17. Unresolved risks

1. **Partial-current state:** truncation can be permanently skipped as current. Similar partial-page
   loss from a future bounded extractor needs an explicit completeness contract.
2. **Invalid raster geometry:** raw extractor bboxes can be inverted or out of page bounds. Fidelity
   is not validity; consumers must fail closed on invalid geometry.
3. **Logical locator is implicit:** component paths are deterministic but not materialized or named
   in the design contract. Surrogate IDs are unstable under replacement.
4. **No character offsets:** exact sub-span provenance or text evolution cannot be expressed without
   additional deterministic offsets/hashes.
5. **GROBID provenance/staleness:** no source checksum, TEI hash, parser version, or truncation marker
   accompanies `paper_figures`.
6. **GROBID information loss:** table notes, cell attributes, multiple page regions, and role-bearing
   hierarchy are not preserved.
7. **Vector structure absent:** line art/table rules are deliberately omitted, limiting ruled-table
   work. Adding raw drawings without a strict candidate/safety design would recreate false figures.
8. **Legacy chunks:** 28 old heading-only chunks remain in the frozen corpus. H1b did not create
   them, but future comparative corpus analyses should distinguish legacy chunk versions.
9. **External GROBID variance:** the new request field was tested at the HTTP contract level, not
   against a live matrix of GROBID versions.
10. **Research-tool CI baseline:** Ruff reports 22 preexisting findings at `1abc203` and H1b's parent,
    and 20 at H1b. H1b removed two findings in `structure.py` and introduced none; the remaining 20
    are preexisting and unrelated to the source substrate. They were not repaired.

The guarded digit-masked boilerplate function at H1b requires at least two alphabetic characters
per real word. Direct checks returned `None` for both `M = 3.41, SD = 1.02` and `p = .761`, while an
ordinary journal header was masked. The function is research-only and unreferenced by production
retrieval. The alleged earlier faulty version is not in H1b's parent history, so that historical
claim cannot be independently verified from committed code; no prior result should be promoted to
production qualification on this audit's authority.

## 18. Smallest justified next step

The smallest justified production increment is **not reconstruction**. It is a bounded H1b
completeness/provenance hardening change:

1. persist and validate an attachment-level source-representation status containing expected page
   count, written page/component count, `complete | truncated | failed`, source checksum, and
   derivation identity;
2. make `attachments_with_current_source()` require `complete`, so an interrupted/truncated graph is
   always reprocessed or explicitly reported rather than skipped;
3. formalize the stable logical locator as checksum + extraction/derivation + page + component path,
   and forbid durable provenance references to surrogate IDs alone;
4. mark invalid/inverted/out-of-page geometry unusable for association without rewriting the raw
   observation; and
5. add the truncation, forced-ID replacement, stale-checksum, invalid-raster, and interrupted-resume
   cases as regression tests.

After that bounded change is independently verified, the next research increment may study
same-column prose reunion and caption/table association with harmful false-association rate as the
primary safety outcome. It should still not persist evidence units, alter retrieval, or infer table
semantics. Row/column reconstruction, footnotes, multi-page tables, and assembled verification need
separate methods work.

Validation actually run: full corpus migration/backfill on an isolated copy; two idempotence
reruns; three-attachment forced replacement; stale/truncation/resume experiments; canonical chunk,
embedding, vector, and attachment hashes; ten-query retrieval identity; 1,628-page Callosum round
trip; 31-page independent raw-PyMuPDF comparison; heading and GROBID fixture audits; 110 focused
source/GROBID/migration/PDF tests; eight GROBID-client tests; audit-harness Ruff and bytecode checks;
and `git diff --check`. No full product suite was run because no application code changed and the
known unrelated research-tool Ruff baseline remains red.

**Independent conclusion frozen before cross-agent comparison:** H1b is genuinely additive and
non-load-bearing for current retrieval, and its core page/block/line/span/heading/raster substrate
has excellent deterministic source fidelity. It is not yet safe to begin H1c under the approved
gate because a truncated graph can masquerade as current. A narrow completeness and stable-locator
hardening increment should precede any reconstruction study.

## 19. Post-hoc Claude comparison

This section was appended only after sections 1-18 were frozen in commit
`7f9e4fcb1194752b7d95e158839f57712d47077d` (pre-comparison report SHA-256
`08dd7a2dafeb232c0004a5af5dba78f1e73a3c2b6c6755331596d7a4f551376f`). I then read
`INCREMENT-578-NOTES.md`, the H1b appendix appended to Claude's proposition-preserving report, and
the H1b entries in the project/change documentation. I did not alter the frozen findings.

| Major conclusion | Classification | Comparison |
|---|---|---|
| H1b is additive/non-load-bearing for retrieval | **AGREEMENT** | Both audits found no new-table reader in retrieval/generation and exact preservation of chunks/embeddings/vectors. Codex additionally ran ten exact before/after vector queries. |
| Live coverage is 114 PDFs; one trashed attachment is outside scope | **AGREEMENT** | Both independently resolve the 93 H1a rows to soft-deleted paper 2. |
| Native and sorted order are distinct | **AGREEMENT** | Both obtain exactly 1,356/1,628 disagreement pages. Codex additionally stratifies one-/two-column disagreement and independently raw-rereads 31 pages. |
| “Native” is semantic reading order | **AGREEMENT (rejected)** | Both source code and notes say neither order proves continuity. Claude's phrase that H1c needs no reread “for reading order” should be read as native-number recovery, not semantic order validation. |
| Page/block/line/span/style structure is faithfully persisted | **AGREEMENT** | Claude's implementation tests and counts align with Codex's zero-mismatch 1,628-page full round trip and separate zero-mismatch raw-PyMuPDF sample. |
| Pure headings are preserved without becoming new chunks | **AGREEMENT** | Both report 598 headings. Codex separately finds 0/20 in fresh drafts and explains 28 legacy heading chunks. |
| Raster blocks remain structural and uninterpreted | **AGREEMENT** | Both report 7,413 bounds and no figure interpretation. Codex-only inspection identifies 363 faithfully preserved inverted image bboxes and one out-of-page bbox. |
| GROBID figures/descriptions/grids are additive | **AGREEMENT** | Both get three tracked-fixture figures, one located raster figure, and two unlocated tables. |
| GROBID substrate is sufficient for future table provenance | **CODEX-ONLY qualification** | Claude notes missing table coordinates; Codex additionally finds discarded table notes, first-page-only multi-region union, unmarked grid truncation, and missing checksum/parser/TEI provenance. |
| Backfill is idempotent and resumable | **PARTIAL AGREEMENT** | Normal and missing-row paths behave as Claude reports. Codex's unanticipated cap experiment shows a truncated partial graph is nevertheless marked current and then skipped, so the general claim requires a completeness qualifier. |
| Stable component provenance exists | **CODEX-ONLY** | Claude's docs do not audit surrogate replacement. Codex shows every sampled surrogate changes on force rebuild while logical trees remain exact, and requires the derivable stable path to be formalized. |
| H1c can proceed directly to caption/table precision | **DISAGREEMENT on sequencing** | Claude identifies caption/table precision as the cheapest H1c task. Under the maintainer-approved Codex gate, the confirmed partial-current defect blocks that probe until a narrow completeness repair is independently verified. This is a sequencing disagreement, not disagreement that caption/table precision matters. |
| Guarded digit-masked key uses a corrected word definition | **AGREEMENT on committed target** | Both observe the two-alphabetic-character guard and research-only status. Codex directly verifies the statistical examples decline, but cannot verify the alleged earlier implementation because it is absent from committed parent history. |
| H1b performance/storage overhead | **NOT COMPARABLE** | Claude reports +2.57 seconds/paper and about 2.1 MB/paper. Codex did not preregister or repeat this benchmark and therefore does not adopt it as an independent finding. |
| Repository-wide validation baseline | **NOT COMPARABLE / compatible** | Claude ran a full suite and reports six preexisting frozen-battery failures caused by CRLF/LF drift. Codex did not rerun the full suite, but independently confirms a separate Ruff baseline of 22 pre-H1b versus 20 at H1b, with no new H1b Ruff failure. These are different checks and do not conflict. |

The strongest combined conclusion is that H1b's central representation is unusually well supported:
implementation tests, Claude's corpus audit, Codex's full production-extractor round trip, and
Codex's independent raw-PyMuPDF sample all converge. The cross-agent comparison also demonstrates
why adversarial state testing matters even when corpus coverage is perfect: neither ordinary
idempotence nor the real library exercised the bounded truncation path.

The discriminating next check is small and deterministic: add an explicit completeness record,
force a capped/truncated write and an interrupted write, and prove neither enters the current set;
then rerun the same H1b invariant/fidelity checks. Only after that should H1c measure caption/table
or same-column associations, with harmful false association reported before recovery.
