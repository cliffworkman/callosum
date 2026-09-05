# Proposition-preserving evidence units — architectural research

**Status:** research and scratch prototyping only. No production code, schema, migration, retrieval
path, prompt, provider, threshold, or embedding was changed. No model was called for any
reconstruction decision. The model/representation experiment has **not** been started.

**Date:** 2026-09-05
**Predecessor:** `.claude/docs/research/2026-09-04_evidence-hygiene-architecture.md` → increment 577 (H1a)
**Scratch:** `tools/evidence_units_geom/`, artifacts in `.local/evidence-units-geom/`

---

## 0. Frozen baseline

H1a was committed before any measurement, so every number below traces to one identity.

| Item | Value |
|---|---|
| H1a commit | `614338b25739afe6a92f4fa0a5faea93aea090e0` |
| Migration head | `0079_chunk_structure` |
| Study DB | `.local/evidence-units-geom/h1a.sqlite` |
| Study DB sha256 | `5877ad466ada1ad10505aff9184c4598549059b9b10dc343a1b839df8015cdff` |
| Corpus | 23,875 chunks across 108 papers; 115 attachment PDFs readable on disk |
| Sanity failures | 0 (corpus-level, not only fixture-level) |
| Geometry parseable | 4,000 / 4,000 sampled |
| `chunk_structure` coverage | 23,782 / 23,875 chunks — **93 unclassified (0.4%)** |

**Diagnosed: correct behaviour, not a defect.** All 93 unclassified chunks belong to one paper —
id 2, *"Association between serotonin denervation and resting-state functional connectivity in mild
cognitive impairment"* (Barrett et al., 2017, Hum Brain Mapp, `10.1002/hbm.23595`) — which was
**moved to the trash on 2026-08-28** (`papers.deleted_at`). Trash is a soft delete, so its chunk
rows remain in `chunks`, while `tools/backfill_chunk_structure.py:251` enumerates only
`papers.deleted_at IS NULL`. The backfill was right to skip it; the raw `COUNT(*)` was simply
counting rows the application itself treats as deleted.

Two earlier diagnoses were wrong and are recorded so the reasoning is auditable: the legacy
`primary` attachment role is **not** the cause (`document_roles.py:46` explicitly maps `primary` →
`article-fulltext`), and a follow-up attempt to reproduce the role filter directly was malformed
(it cross-joined) and proved nothing.

**Contamination check.** Ten papers in the study DB are trashed, but only paper 2 still has chunks.
Those 93 chunks (0.39%) *are* included in the §5 proposition-bearing baseline, which is therefore
very slightly inflated by a deleted paper. Four of the 179 sampled fixture cases come from it — all
in the `(unclassified)` stratum — and **none of them appear among the 44 adjudicated cases**, so
every §6A / §10 headline figure is unaffected. A future run should scope the baseline to
`deleted_at IS NULL` for exact agreement with the backfill.

The corpus-level sanity gate exists because of an inc-577 defect that fixtures alone could not
catch: `chunks.bbox_json` is a SQLAlchemy `JSON` column, so a DB read returns a decoded list while
a fixture returns a string; `json.loads()` on the list raised `TypeError`, a broad `except`
swallowed it, and **every geometry rule was silently disabled** while the fixture suite stayed
green. The freeze therefore asserts distributional bounds — a corpus with zero `running_head` and
zero `table_cell_debris` is the signature of that bug and now fails loudly.

### Preflight disposition of pre-existing test failures

A fresh worktree at the H1a commit reports 41 failures. These were investigated rather than
assumed, and they are **not** related to this work:

- 11 are in `test_citations.py` / `test_frontend_assembly.py` / `test_website_how_it_works.py`;
  the worktree has **no `node_modules`** (citeproc sidecar, esbuild) and **no built
  `callosum-app.html`**. They are environment failures of an unbuilt checkout.
- The **qualification-freeze tests pass 15/15** in that worktree, and `providers.py` hashes to
  `67065f72…`, exactly matching `freeze.json`.

That last point corrects a claim I made in planning and then checked: committing does **not** clear
the 6 freeze failures seen in the main working tree. `freeze.json` records the **LF-normalized**
digest while the working-tree file is **CRLF**, and git normalizes on the way *into* the index, not
on disk. The real cause is that **186 of 850 tracked `.py` files still carry CRLF** — `.gitattributes`
gained `eol=lf` in inc 575 and git never applies that retroactively. `providers.py` is one of them
and was last touched in inc 575, not by this work. The repair (`git add --renormalize`) is a
repo-wide action touching ~186 files that would collide with a parallel agent's working tree, so
per §0 of the brief it is **left unrepaired and reported**, not fixed here.

---

## 1. What this study had to decide

H1a shipped hygiene metadata that reads nowhere, because no exclusion reason code cleared the ≥95%
held-out precision gate. Its findings then reframed the problem. Under the maintainer's governing
principle —

> a quantitative value is usable scientific evidence only when the extracted or reconstructed unit
> retains enough trustworthy context to identify what the value is evidence about

— a large class of units **cannot be repaired by any eligibility setting whatsoever**. `p = .146` is
a real reported statistic that has lost its referent. Excluding it discards real evidence; keeping
it yields a unit that can never verify. Only reconstruction resolves that, which is why the question
"what should an evidence unit *be*" had to be answered before the substrate is frozen for the
model/representation experiment.

---

## 2. Information discarded at ingest

Verified directly against production code rather than inferred. The headline is better than
expected: **the two most valuable fields are already computed and then thrown away.**

| Field | Where | Status |
|---|---|---|
| Block bbox | `extraction.py:180` | computed, discarded |
| Page width / height | `extraction.py:188-189` | computed, discarded, and **zero readers anywhere in the repo** |
| Span font **size** | `extraction.py:558-559` | **is read** (inter-span spacing) |
| Span font **name**, bold/italic flags | — | never read |
| Line bbox, line `dir` / `wmode` | — | never read (rotated text silently flattened) |
| Span `origin` | — | never read |
| All 13 image-block fields | `extraction.py:145-146` | dropped wholesale |

**One correction to the brief's own list:** span font *size* **is** consulted. Font *name* and the
bold/italic *flags* are the ones never read. Preserving block bbox and page dimensions is additive
and cheap — not a re-architecture.

---

## 3. The narrow-and-tiny population, and a number that must not be carried forward

No arbitrary character or token minimum is used anywhere in this study. An earlier draft of the
predecessor work used `len(text) >= 200`, which silently did most of the filtering (the median chunk
is 88 characters) and was removed.

| Population | Count | Share |
|---|---|---|
| All chunks | 23,875 | 100% |
| Sub-40-character | 8,584 | 36.0% |
| **Narrow-and-tiny** (short *and* geometrically narrow) | 6,349 | 26.6% |
| Bare-statistic fragments (≤8 words carrying a statistic) | 228 | 1.0% |
| H1a `table_cell_debris` (grid-supported) | 2,674 | 11.2% |

**The ~23% figure quoted in earlier work is the 26.6% narrow-tiny population, not a table-debris
measurement.** H1a's stricter grid-based classifier types only 11.2% as `table_cell_debris`. The
~3,700-chunk gap between them is the genuinely ambiguous middle — narrow fragments with no grid
siblings — and it is exactly where recovery is hardest. The older number is not carried forward.

---

## 4. Frozen adjudicated case corpus

Deterministic sampling by stable hash of `(chunk_id, seed)`, **seed 20260905** — not RNG state, so
the corpus is reproducible regardless of iteration order. 179 cases across 18 strata, proportional
allocation with a floor of 3 so small-but-important classes survive sampling.

Artifacts: `fixtures.json`, `fixtures_adjudicated.json`.

| Stratum | Population | Sampled |
|---|---|---|
| `unresolved::truncated_prose` | 4,782 | 32 |
| `not_bearing::bare value or symbols` | 4,692 | 31 |
| `unresolved::other_unresolved` | 4,278 | 29 |
| `bearing::unknown` | 3,074 | 21 |
| `unresolved::structural_label` | 2,655 | 18 |
| `bearing::body_prose` | 1,462 | 10 |
| `unresolved::labelled_row` | 1,035 | 7 |
| `unresolved::name_only` | 651 | 4 |
| 10 further strata (reference entries, captions, abstract prose, metadata, …) | ≤367 each | 3 each |

---

## 5. Operationalizing "proposition-bearing"

Defined as a **conjunction**, which is what makes it falsifiable:

> proposition-bearing ⟺ carries a **referent** ∧ makes an **assertion** about it

- **Referent** — a named entity, variable or group the information is about. A number is not a
  referent; neither is a bare label with nothing predicated of it.
- **Assertion** — a finite reporting verb, an explicit relation, or a value bound to several named
  quantities.

Anything the rules cannot decide returns **UNRESOLVED** — never a forced binary. That is a design
commitment, not an accuracy excuse: forcing a verdict would manufacture the exact false confidence
this whole programme exists to prevent.

Baseline over the frozen corpus (`proposition_baseline.json`):

| Verdict | Count | Share |
|---|---|---|
| proposition-bearing | 5,321 | **22.3%** |
| not proposition-bearing | 5,153 | 21.6% |
| unresolved | 13,401 | **56.1%** |

The 56% unresolved share is the finding, not a defect in the proxy — and it decomposes into classes
that imply *different* repairs:

| Reason | Share of corpus | Implied repair |
|---|---|---|
| `truncated_prose` | 20.0% | reunification |
| `other_unresolved` | 17.9% | mixed |
| `structural_label` | 11.1% | none — not evidence |
| `labelled_row` | 4.3% | table reconstruction |
| `name_only` | 2.7% | none — not evidence |

---

## 6A. Prose reunification — the central negative result

This is the study's most important measurement, and it is a **stop signal**.

A deliberately bounded reconstruction (absorb at most one reading-order neighbour on each side) was
applied to all 179 cases. **44 were "recovered"** — the proposition verdict flipped to bearing. All
44 were then read individually against their own page context (`adjudicate.py`, one line per case,
contestable by chunk id).

| Outcome | n | Share | 95% CI (Wilson) |
|---|---|---|---|
| **correct** — genuine scientific unit reunified | 12 | 27.3% | [16%, 42%] |
| **not_evidence** — right join, but the result is acknowledgements / CRediT / licence text | 5 | 11.4% | [5%, 24%] |
| **false** — asserted a continuity that does not exist | **26** | **59.1%** | **[44%, 72%]** |
| unresolved | 1 | 2.3% | [0%, 12%] |

**A bounded, conservative joiner is wrong more often than it is right.** Reported before any recall
figure, per §11.

The `not_evidence` class deserves separate emphasis because it is the *dangerous* success: the
proposition test genuinely passes, so a naive recovery metric counts these as wins while they add
non-evidence to the retrievable pool.

### Why the false joins happen

| Mechanism | n | Share of false joins |
|---|---|---|
| **boilerplate contamination** | **16** | **62%** |
| section boundary crossed | 6 | 23% |
| empty self / caption→wrong body / stimulus boundary / topic boundary | 4 | 15% |

Representative failures, quoted from the frozen corpus:

- `F14958` — the heading **"Methods"** joined to **DISCUSSION** prose.
- `F31280` — the genuine *Table 1* caption ("Sex, age, baseline and one-year cognitive scores…")
  joined to unrelated Methods prose about MRI timing. Its real referent is the **table**, and the
  naive join confidently attaches the wrong body.
- `F25702` — two separately numbered vignettes merged into one unit.
- `F35987` — the heading "2.2. Stimuli" joined to the **Participants** body.

---

## 6B. Reading order

Two facts had to be established before any of the above could be interpreted.

**The stored block index is not MuPDF's block number.** `extraction.py:144` enumerates blocks
*after* `get_text("dict", sort=True)`, so `bbox_json["block"]` is an ordinal position in the
geometrically sorted list, **including image blocks that are then dropped**. `quote_matching.py:102`
stores MuPDF's *native* `word[5]`. The two integers are different numbering schemes and are not
comparable. Nothing joins them today, so this is latent — but any reconstruction that assumes
"block index == reading order" inherits it silently.

**`sort=True` sorts blocks only**, by `(y1, x0)` across the whole page; intra-block line and span
order is unchanged. On a two-column page that interleaves the columns.

Measured (`reading_order.json`, `reread.json`; the native-order arm covers **30 PDFs / 450 pages,
330 pages comparable**):

| Comparison | Median pair disagreement |
|---|---|
| Stored block order vs geometry-derived order, one-column | 0.032 |
| Stored block order vs geometry-derived order, two-column | 0.088 |
| **Stored order vs MuPDF native reading order** | **0.380** |

**The optimistic figure is an artifact and must not be believed.** My geometry-derived order and the
stored order share the same sorting principle, so they agree with each other while *both* differ
from true reading order. Against MuPDF's native `(block, line, word)` order — the closest available
ground truth, and the ordering that took exact-highlight hit-rate from ~53% to ~96% per
`quote_matching.py:81-86` — **70% of pages disagree by more than 25%, and only 12% are perfectly
ordered.**

An earlier 8-PDF smoke run of this same measurement gave 0.267 / 51% / 29%. The 30-PDF figures
above supersede it; the smaller sample was optimistic, and the direction of the correction is
*against* the stored order.

**"Next by chunk id" is also "next in reading order" only 65.6% of the time.** One chunk in three
has a different true successor than its id implies.

---

## 6C. Headings

Headings are the specific structure whose loss causes the `section_boundary` false joins (23% of
the total). H1a types 11.1% of the corpus as `structural_label`, but nothing associates a heading
with the body it governs — so a heading is equally likely to be joined to the *preceding* section's
tail as to its own body (`F14958`, `F35987`, `F31125`, `F32067`, `F15756`, `F22907`).

Font size is already read at `extraction.py:558-559` but only for spacing; heading detection by
relative font size is available and unused. GROBID, where configured, already produces a real
section tree (`paper_sections`, inc 479) — that is the trustworthy source, and it covers only papers
that have been parsed.

---

## 6D. Tables — the extractor already exists, and its default configuration barely fires

`app/backend/document_tables.py:104` already calls PyMuPDF `find_tables()` and returns
`TableRowEvidence(headers, cells, table_index, row_index, page, bbox_json, caption, section, …)`
with **per-row bboxes already in callosum's `pdf-points-top-left` idiom** (`:128-139`). It is pure,
cached, capped, and inc 387 already consumes it for statcheck — but it is **ephemeral per request
and never persisted**.

Measured over **30 PDFs / 450 pages** with the production default, plus a strategy comparison:

| Strategy | Tables | Rows | Assessment |
|---|---|---|---|
| `lines` (**production default**) | 34 | 256 | **sparse but clean** — fires on 11 / 30 papers (37%) |
| `text` | ~1 per page | — | **catastrophic precision** — see below |

Where `lines` fires, the structure it returns is good: **100% of the 34 detected tables have a
detected header row.** The recall limitation is that it finds only *ruled* tables, and the
per-paper distribution is skewed — `[1,1,1,1,1,1,2,3,5,7,11]` across the 11 papers with any table,
so most papers contribute a single table and 19 of 30 contribute none.

The `text` strategy returns roughly one "table" per page. Direct inspection shows why it must not
be used: on a page with no table at all it produced a *69 × 5* grid built from a running head and a
figure caption, **splitting words mid-token** —

```
['Figure 3. Participa', 'nts’ average targ', 'et ratings on the', 'three trustworthines']
```

**Correction to an earlier draft of this section.** An 8-PDF smoke sample returned 2 tables in 105
pages, and I wrote that `lines` had "near-zero recall." The 30-PDF measurement refutes that: the
smoke sample happened to contain almost no ruled tables. The accurate statement is that `lines` is
**precise but sparse**, covering roughly a third of papers. `text` remains unusable at any sample
size — that judgment rests on direct inspection of its output, not on counts.

---

## 6E. Captions

Two independent caption sources exist, and **both are currently disconnected from tables**:

1. **The PDF path never populates `caption`.** `document_tables.py` sets it for JATS and HTML; the
   PDF, DOCX and ODT paths do not.
2. **GROBID's TEI already contains `<figure><head>…<figDesc>` and `<figure type="table">` with
   `<row>/<cell>`** — visible in the committed fixture — but `tei_parse.py:113` walks only
   `.//tei:text/tei:body/tei:div`, so **every figure and table is silently discarded**, and
   `client.py:60` requests `teiCoordinates=div,head,p` only. Both are small additive changes.

Geometric caption↔table association — nearest caption-shaped block within 90pt above or below a
table bbox, same page — **is measurable, and this corrects an earlier draft that called it blocked**:

| Measure | Value |
|---|---|
| Tables with an associable caption | **14 / 34 = 41%** |
| Median caption gap | **6.9 pt** |
| Maximum caption gap | 32.8 pt |

The gap distribution is the informative part. The search window was 90pt, and **every match landed
within 33pt, with a median under 7pt** — so when a caption is found it is immediately adjacent, and
the rule is discriminating rather than opportunistically grabbing whatever is nearest. That is a
much better starting position than the association *rate* alone suggests.

The 59% with no associable caption are not evidence of a missing caption; the caption may sit on the
facing page, be typeset above a page break, or not match the caption-shape pattern. **Absence of an
association is not evidence of absence** and must never be reported as "this table has no caption."

The grey-zone case from H1a nonetheless remains open, and case `F31280` shows its teeth: a real
Table 1 caption exists, its values live in separate cell chunks, and the *adjacency* mechanism
tested in §6A attached it to the **wrong body**. Note the contrast — caption→**table** association
by geometry is tight and plausible; caption→**prose** association by reading-order adjacency is
wrong. These are different problems and the second one is the failure.

---

## 6F. Figures

Out of reach on the PDF path, structurally: **all 13 image-block fields are dropped at
`extraction.py:145-146`** (241 image blocks across the 450-page sample). No plotted value was
interpreted, no visual inference performed, no chart digitizer built or proposed.

The only viable figure path is GROBID's `<figure><figDesc>` caption text — caption *text*, never
plotted values.

---

## 7. What a PDF reread would buy

| Recoverable by reread | Value | Cost |
|---|---|---|
| Native `(block, line, word)` reading order | **High** — 0.380 median disagreement; only 12% of pages correct | one pass |
| Block bbox, page dimensions | Moderate; already computed and discarded | free at ingest |
| `find_tables()` structure | **Moderate** — precise where it fires (100% headers) but covers 37% of papers | one pass |
| Font name / flags for heading detection | Moderate | free at ingest |
| Image blocks | Low — caption text is the useful part, and GROBID has it | — |

MuPDF's unused `TEXT_DEHYPHENATE`, `TEXT_SEGMENT` and `TEXT_ACCURATE_BBOXES` flags remain
unevaluated here and are flagged for H1b, since callosum hand-implements de-hyphenation MuPDF can
do natively.

**The minimum justified addition is native reading order plus the two already-computed geometry
fields** — not a maximal PDF DOM.

---

## 8. Proposed evidence-unit model (design only, not implemented)

An evidence unit is a **span set over one attachment** plus the metadata needed to decide whether it
can be quoted:

```
EvidenceUnit
  attachment_id
  components : [ (chunk_id, page, bbox, char_range) ]   # 1 = verbatim, >1 = assembled
  evidence_form : verbatim | assembled
  reading_order_key : (page, native_block, native_line, native_word)
  proposition_state : bearing | not_bearing | unresolved
  assembly_basis : null | adjacency | caption_table | table_row
  confidence_in_assembly : measured, never assumed
```

This deliberately does **not** add a `scientific_claim_eligible` flag: eligibility is task-relative,
and H1a already declined that column for the same reason.

---

## 9. Provenance — the honesty-critical piece

A reconstructed table fact assembled from caption + row label + cell **never existed contiguously in
the document**. Presenting it as a quote would violate invariant #2 directly.

The proposal is a distinct `evidence_form`:

- **`verbatim`** — contiguous text; quotable; existing `exact` / `region` / `null` coordinate
  semantics unchanged.
- **`assembled`** — N components, **each with its own coordinates**, displayed as multiple
  highlights and never as a single quotation.

This **extends** invariant #2 rather than bending it. The verifier implication is documented, not
changed: `canonical_text_contains` would correctly **fail** an assembled string, because that string
appears nowhere in the source. Assembled units therefore require **per-component** verification.
That is a design note for H1b, not a change made here.

---

## 10. Recoverability, quantified

| Question | Answer |
|---|---|
| Units not proposition-bearing as they stand | **77.7%** (21.6% not bearing + 56.1% unresolved) |
| Mechanically "recovered" by a bounded one-neighbour join | 44 / 179 = **24.6%** |
| Of those, genuinely correct **and** scientific | **27.3%** [16%, 42%] |
| Of those, **false joins** | **59.1%** [44%, 72%] |
| Net genuine recovery over the sampled corpus | ≈ **6.7%** of units (24.6% × 27.3%) |
| Narrow-and-tiny population (6,349 units) | recoverable **only** via table reconstruction, which is blocked on detection (§6D) |

**The bounded joiner buys roughly 6.7% genuine recovery at a 59% false-join rate.** That trade is
not acceptable at any retrieval-facing setting.

### The counterfactual that matters

If H1a's existing boilerplate metadata is applied **before** joining:

| Measure | Result |
|---|---|
| Previously-correct joins that survive hygiene | **12 / 12 (100%)** — hygiene breaks nothing |
| Boilerplate-caused false joins eliminated | 6 / 16 (38%) |
| **Residual false-join rate** | **10 / 37 = 27.0%** [15%, 43%] |
| Residual mechanisms | section boundary, caption→wrong body, stimulus boundary, topic boundary |

Hygiene-before-reconstruction is **safe and helpful but not sufficient**: 27% residual is still far
too high to ship.

### Why hygiene only fixes 38%: H1a's boilerplate recall is 38%

| H1a verdict on adjudicated boilerplate contaminants | n |
|---|---|
| Detected (`running_head` / `running_footer` / `publication_metadata`) | 6 |
| **Missed** (typed `unknown` or `math_or_symbol`) | **10** |

The misses share one signature — **an embedded page number makes every occurrence textually
unique**, so an exact-text repeat key never sees a repeat:

```
'Frontiers in Neurology | www.frontiersin.org 8 January 2021 | Volume 11 | Article 580182'
'1512 THE AMERICAN ECONOMIC REVIEW June 2011'
'737 Policy Sciences (2020) 53:735–758'
'2 H. HAN ET AL.'
'Journal Pre-proof'
```

The obvious repair — mask digits in the repeat key — was tested and **must not ship in that form**:

| Repeat key | Chunks flagged | Recall on contaminants | Numeric-unit casualties |
|---|---|---|---|
| exact (H1a today) | 2,763 (11.6%) | 5/16 = 31% | 1,011 |
| digits masked (naive) | 5,261 (22.0%) | higher | **destroys real table values** |
| **digits masked, guarded by ≥3 real words** | 3,464 (14.5%) | **9/16 = 56%** | **1,011 — no increase** |

The naive version collapses `R2 = 0.021`, `0.040 0.159` and
`9.937e-01 6.620e-01 1.501 (3.113e + 02)` — **real reported values** — into shared keys and flags
them as boilerplate. The guarded variant masks digits only when the unit still carries real words
(a running head has prose; a table cell does not), lifting recall 31% → 56% **with zero additional
numeric casualties**.

---

## 11. How this was evaluated

Not by retrieval rank, per the brief. The primary criterion is **false-reconstruction rate, reported
before any recall figure**. A harmful false join outranks a recall gain, because a false join
manufactures a proposition the document does not contain — the precise failure mode this programme
exists to prevent.

---

## 12. Determinism

No model was used to decide reading order, fragment joins, table structure, caption/table linkage,
missing referents, or referent identity. Every classifier is a stated, inspectable rule. Where
geometry or text shape could not decide, the result is **UNRESOLVED** and remains so — 56.1% of the
corpus, and one adjudicated case (`F26243`) left explicitly undecided rather than forced.

---

## 13. Antecedent for the model/representation study

**77.7% of currently retrievable units are not proposition-bearing as they stand.** Under the
cheapest safe reconstruction that number improves by roughly 6.7 percentage points, at a false-join
rate that makes it unshippable. This is measured without running any model, and it is the baseline
the later study should be interpreted against: **a model asked to answer from this substrate is
selecting from a pool in which fewer than a quarter of units can support a proposition.**

---

## 14. Implementation-readiness matrix

| Candidate | Measured basis | Ready? |
|---|---|---|
| Preserve block bbox + page dims at ingest | computed and discarded today; zero readers | **Yes** — additive, no behaviour change |
| Store **native** `(block, line, word)` reading order | stored order disagrees with truth on 51% of pages | **Yes** — additive; fixes a latent numbering trap |
| Guarded digit-masked repeat key | recall 31% → 56%, zero added numeric casualties | **Yes, behind measurement** — needs a held-out precision gate |
| Hygiene **before** any reconstruction | 12/12 correct joins survive; fixes 38% of false joins | **Yes** — ordering constraint, not a feature |
| GROBID `<figure>` / `<figDesc>` parsing | captions currently discarded at `tei_parse.py:113` | **Yes** — small, additive, opt-in |
| Adjacency-based prose reunification | **59% false-join rate**; 27% after hygiene | **No** |
| Table reconstruction | `lines` covers 37% of papers, 100% header recall; `text` fabricates tables from prose | **Not yet** — precise but partial |
| Caption↔table association | 41% associable, median gap 6.9pt, max 32.8pt | **Promising** — measure precision before use |
| Figure/plot understanding | image blocks dropped at ingest | **No** — and out of scope |
| `evidence_form: verbatim \| assembled` | design complete, §9 | **Design only** — needed *before* any assembled unit exists |

---

## 15. Minimum recommended H1b

**H1b should be a substrate increment, not a reconstruction increment.** The measurements do not
support shipping any reconstruction that reaches retrieval.

Recommended:

1. **Preserve what is already computed** — block bbox and page dimensions. Free, additive.
2. **Record native MuPDF reading order** alongside the existing index, and document that
   `bbox_json["block"]` is a post-sort ordinal, not a block number. This closes a latent trap that
   would otherwise be inherited silently by every future reconstruction.
3. **Improve boilerplate recall with the guarded digit-masked key**, gated behind the same ≥95%
   held-out precision bar H1a used — and **not** wired to retrieval until it clears.
4. **Parse GROBID `<figure>` / `<figDesc>`**, giving captions a trustworthy source where GROBID has
   run.
5. **Fix the ordering constraint**: hygiene is applied *before* any future reconstruction, never
   after. Joining before hygiene amplifies pollution — measured, not assumed.

6. **Design `evidence_form` (§9) without building it.** The `verbatim` / `assembled` distinction
   must exist *before* the first assembled unit does, or an assembled string will reach a verifier
   that correctly cannot verify it.

**H1b should NOT include:** prose reunification, fragment merging, re-chunking, re-embedding,
figure understanding, any change to retrieval / thresholds / prompts / providers, or any actual
`assembled` evidence unit.

**Two candidates sit deliberately just outside H1b**, because they are promising rather than
disqualified — and the distinction matters for what H1c should attempt:

- **Caption↔table association** (41% associable, median gap 6.9pt). The *rate* is unproven but the
  *geometry* is tight. What is missing is a precision measurement: no adjudication has yet asked
  whether an associated caption is the **right** caption. That measurement is cheap and is the
  natural first task of H1c.
- **Table-row reconstruction** where `lines` already fires with a detected header (100% of 34
  tables). This is the one population where header + row label + cell are all available from a
  single trustworthy source, which is exactly the structure §9's `assembled` form was designed for.

---

## 16. Open questions for the maintainer

1. **Table detection coverage.** Production's `document_tables.py` (`lines` strategy) detects tables
   in **11 of 30 papers**, missing unruled tables entirely. Is widening that a *statcheck* concern
   worth its own increment, independent of evidence units? It would change what statcheck can
   recompute, not just what Ask can retrieve — and `text` is demonstrably not the way to do it.
2. **The 3,700-chunk ambiguous middle** (narrow-tiny without grid siblings) has no demonstrated
   recovery path. Is retaining it unchanged-but-labelled acceptable indefinitely?
3. **CRLF renormalization** is a repo-wide hygiene action (~186 files) currently blocked by parallel
   work. When should it be scheduled?
4. **Trashed-paper chunks linger in `chunks`** (§0). A soft-deleted paper keeps its chunk rows, so
   any analysis reading `chunks` directly silently includes deleted papers unless it joins `papers`
   and filters `deleted_at`. That bit this study (0.39%, harmless here) and would bite a
   re-embedding or re-chunking pass harder. Worth deciding whether purge-on-trash or a documented
   read convention is the right answer before H1b.

---

## Verification

- Every quantitative claim traces to an artifact under `.local/evidence-units-geom/`:
  `freeze.json`, `proposition_baseline.json`, `reading_order.json`, `reread.json`, `fixtures.json`,
  `fixtures_adjudicated.json`, `counterfactual.json`.
- Both fixture-level and **corpus-level** distribution checks were run for every detector.
- The study DB is a snapshot copy; H1a was read-only throughout.
- No model was called for any reconstruction decision (§12).
- False-reconstruction rate is reported **before** recovery rate throughout (§11).
- No file under `.local/evidence-units/`, `tools/evidence_units/`, or any other agent's 2026-09-05
  artifacts was read.

---

## Appendix A — H1b implementation (increment 578)

Added 2026-09-05, after this report was frozen. The report's findings are **not** revised here; this
records what §15's "minimum recommended H1b" became in production, including where implementation
contradicted or sharpened the research.

### What shipped

| §15 recommendation | Shipped as |
|---|---|
| 1. Preserve block bbox + page dimensions | `source_pages` (w/h/**rotation**) + `source_components` bbox at every level |
| 2. Record native MuPDF order alongside the existing index | separate `native_order` / `sorted_order` columns, pinned by a migration test |
| 3. Guarded digit-masked key, gated | `tools/evidence_hygiene/structure.py::guarded_digit_masked_key` — offline, unreferenced by production |
| 4. Parse GROBID `<figure>`/`<figDesc>` | `tei_parse.parse_figures` + `paper_figures`, plus `figure` added to `teiCoordinates` |
| 5. Hygiene precedes reconstruction | recorded as an invariant in the increment notes and the EvidenceUnit spec; no reconstruction exists to order |
| 6. Design `evidence_form` without building it | `.claude/docs/specs/2026-09-05-evidence-unit-contract.md` |

Deliberately beyond §15, on the maintainer's explicit decision: source components are written
**during normal ingest** as well as by the backfill, so newly imported papers are not structurally
incomplete until someone runs a research tool. The write is SAVEPOINT-isolated so it can never roll
back a chunk write.

### Three things implementation established that the study could not

**1. Native order needs no PDF re-read.** The study measured native-vs-sorted disagreement through a
separate re-extraction arm (`reread.json`). In fact `block["number"]` is present in the *same*
`get_text("dict", sort=True)` mapping the pipeline already builds — PyMuPDF's `extractDICT` sorts
the list in place and never renumbers. Confirmed in PyMuPDF's own source and measured across the
whole 114-PDF / 1,628-page validation library: **1,356 of 1,628 pages (83.3%) have the two orders
out of sequence** — higher than this study's own 70% estimate. H1c does not need a re-read arm for
reading order.

**2. `sorted_order` reproduces `bbox_json["block"]` exactly, gaps included.** The report noted the
stored ordinal counts image blocks that are then dropped. That is now pinned by a regression test:
for a page whose middle block is an image, text blocks carry `sorted_order` `[0, 2]` while
`native_order` is `[0, 1]`. The two numbering spaces are structurally separated, so no future
reconstruction can silently inherit the wrong one.

**3. The guarded digit-masked key needed a stricter guard than "≥3 real words".** Implemented
literally — any digit-free token counts — the rule *fails on the exact case it exists to protect*:
`M = 3.41, SD = 1.02` yields four digit-free tokens (`M`, `=`, `SD`, `=`), passes the guard, and
collapses a genuine reported result into a key shared with every other numeric result. A real word
must carry **at least two alphabetic characters**; that case then retains one (`SD`) and correctly
declines. This does not change the report's recall finding, but any future qualification run must
use the corrected guard — the naive reading is unsafe in a way the sample-level numbers did not
surface.

### Correction carried forward

The 93 unclassified chunks are confirmed **correct behaviour, not a backfill defect**: they belong
to paper 2, soft-deleted on 2026-08-28, and the backfill enumerates only `deleted_at IS NULL`. The
H1b tooling reports live coverage and trashed attachments as **separate lines** rather than folding
the latter into a gap, and reproduces the same split on the real library: **114 live PDF
attachments + 1 soft-deleted = 115**. `--include-trashed` exists solely for debugging.

### Measured cost

Writing at ingest costs **≈2.57 s/paper (+12.5%)** on a 20.50 s/paper baseline (0.15 s structural
walk, 2.42 s persistence) and **≈2.1 MB/paper**. Spans are 89.7% of components, consistent with the
measured 655.7 spans/page.

### Still open, unchanged by H1b

Caption↔table association precision is still unmeasured — the rate (41% associable, median gap
6.9pt) is known; whether an associated caption is the **right** caption has never been adjudicated.
That remains H1c's cheapest first task. One new constraint for it: GROBID's `type="table"` figures
arrive with a caption and grid but frequently **no coordinates at all**, so a geometry study must
take regions from PyMuPDF or re-parse with the new `teiCoordinates` request first.


---

## Appendix B — H1b.1 (inc 579): what an independent audit changed

An independent Codex audit of H1b (`2026-09-05_codex-h1b-source-component-audit.md`, preregistered
`955c606`, findings frozen `7f9e4fc` before reading any of H1b's own notes) reproduced the fidelity
results above from a separately-coded raw-PyMuPDF walker and found **one blocker plus two provenance
gaps**. All three are closed by increment 579; none of H1b's fidelity findings are revised.

### The blocker: identity is not completeness

With the component cap lowered inside the harness, H1b persisted one page and zero components and
still classified that graph as **current** — its `source_checksum` and `derivation_version` matched,
which was everything H1b checked. An ordinary backfill would then have skipped the partial
representation forever.

The conflation is the interesting part. Checksum and derivation version answer *"is this derived from
the current file by the current code?"* — a question about **identity**. Nothing answered *"is this
derived graph whole?"* — a question about **completeness**. In the happy path the two coincide, which
is why neither the corpus nor ordinary idempotence testing exposed it. Only adversarial state testing
did, and that is the transferable lesson: perfect corpus coverage says nothing about the bounded
paths the corpus never exercises.

H1b.1 adds a `source_representations` record whose sole job is the completeness answer, written last
so it cannot lie, and cross-checked against the rows actually present — pages **and** components —
so it cannot go stale in place. `current` now requires `complete`.

### Gap 1: surrogate ids are not provenance — and are worse than unstable

The audit showed every sampled `source_pages.id` / `source_components.id` changes on a forced
rebuild while the logical tree stays exact. Writing H1b.1's regression tests surfaced a sharper
finding the audit did not report: ids are allocated from `max(id) + 1`, so an attachment holding the
top of the id space is handed **its own old ids back**, now naming different content. A stale
reference does not fail — it resolves successfully to the wrong component.

Durable provenance therefore uses `SourceLocator` (source checksum + extraction tool + **extraction
version** + derivation version + page + `component_path`), materialized as
`b{sorted}[/l{child}[/s{child}]]` and unique within a page by construction. Measured **zero
collisions** across the corpus on the durable identity fields — a `GROUP BY source_page_id` is only a
local sanity check, since that id is itself replaceable.

### Gap 2: fidelity is not validity

The audit found 363 inverted raster bboxes and one out-of-page bbox **faithfully preserved**. That is
extraction fidelity working correctly, and precisely why a separate signal was needed: a future
association study must fail closed on a region it cannot intersect, without anyone normalizing,
clamping or swapping the coordinates the extractor actually reported. `geometry_state` records the
judgment beside the untouched observation, at a tolerance **frozen at 2.0pt before measurement**.

### What this changes for H1c

The sequencing disagreement in the audit's §19 is resolved in the audit's favour: caption↔table
precision remains the cheapest and most natural first task, but it could not begin until a truncated
graph was provably unable to masquerade as current. It now is. Two constraints carry forward into any
association work:

1. only components from a representation that is `complete` **and** current may be used — a unit
   assembled from a partial graph is missing pieces silently, and looks no different from a correct
   one;
2. only components whose `geometry_state` is `valid` may enter a spatial association.

### Still deferred, deliberately

Character offsets (they require settling a canonical page-text serialization first), and every GROBID
gap the audit found — table `<note>` preservation, cell roles and attributes, multi-page regions
currently unioned onto the first page, persisted grid-truncation markers, and richer TEI provenance
on `paper_figures`. Real findings, but none caused the gate failure.
