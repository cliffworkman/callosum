# Registration workflow evaluation — separate dimensions

**Date:** 2026-07-31
**Fixture manifest:** `tests/fixtures/registration_evaluation_cases.json`

The workflow is evaluated as separable stages. There is intentionally no composite score: a high reference-extraction
precision cannot compensate for a wrong registration match, weak publication retrieval, or a bad evidence anchor.

| Dimension | Hermetic evidence | Failure interpretation |
|---|---|---|
| Reference extraction precision | OSF URL/DOI, hidden “here,” multiple-reference and false-positive tests | Wrong normalized provider/id or unrelated nearby URL surfaced |
| Candidate discovery recall | Direct printed links, OSF resource/DOI, DataCite typed relations, multiple candidates | Supported metadata route failed to surface candidate; never infer no registration |
| Candidate ranking precision | Explicit/contextual/similarity classes plus overlapping-title/author false candidate | Similarity candidate promoted or auto-attached |
| Commitment extraction accuracy | OSF schema labels/order, AsPredicted numbered questions, local PDF, amendment | Wrong canonical field/evidence/question/version or invented mapping |
| Publication evidence retrieval accuracy | Compatible section, expansion, supplement opt-in, multi-study tests | Wrong document/section/study or missed relevant bounded passage |
| Comparison classification accuracy | Numeric sample, either/both, outcome/model, disclosed deviation, underspecification, timing | Bounded deterministic rule assigned wrong status or semantic uncertainty forced into verdict |
| Evidence-anchor correctness | Attachment/chunk/page/bbox assertions on both sides | Evidence opens a different attachment/page or claims unavailable precision |
| False “not located” rate | Whole-article expansion, optional supplements, one-sided outcome, explicit scope note | Not-located status emitted despite evidence in searched scope, or rendered as absence |
| Optional LLM-triage utility | Bounded-payload, label-validation, fail-open, persistence/staleness, and All-rows restoration tests | Important/uncertain row hidden, malformed or missing label hidden, underlying crosswalk mutated, or stale label shown as current |

Every manifest row names its executable pytest function through `exercised_by`, and
`test_registration_evaluation_manifest.py` validates that trace. The tests remain a curated regression set, not a
claim of field-wide validation. Live registry health checks remain optional and are not CI dependencies. Add
discipline/domain-specific cases to the manifest and a corresponding stage test without combining the dimensions.
Treat triage noise reduction and false-hidden-important-row rate as separate measures. A smaller focused list is not
an improvement if it suppresses an uncertain or inspection-worthy row, and it does not alter any upstream accuracy
dimension.
