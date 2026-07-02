Review of beneficial repos to integrate into/adapt for Callosum: https://lakens.github.io/automated_review_daily_build/

Highest-value additions
1. ODDPub + rtransparent + output-it-forward	Build a local Transparency signals METHODS/findings module. Detect data availability, code availability, repository links, COI, funding, protocol registration, preregistration language, and "upon request" statements. Store as evidence-backed findings and optional read-only system tags, not as author accusations. ODDPub is especially useful because it returns detected categories and sentences, and reports validation on PubMed biomedical papers. rtransparent broadens this to COI, funding, and registration indicators. OIF contributes editable phrase and repository-domain lists.

2. RegCheck	Add a future Registration-to-paper comparison module. This is the biggest missing open-science capability: compare preregistrations, clinical trial registrations, or preclinical registrations against published papers. But it must sit behind your auditability gate because RegCheck is LLM-assisted and inherently interpretive. Best Callosum shape: import a registration as a companion document, align sections locally, surface claim-level deltas with quoted evidence, and label them "reported match / possible divergence / not located / ambiguous", never "QRPs."

3. JATSdecoder + docpluck	Add them as text-ingestion and normalization references, not necessarily hard dependencies. Callosum already has PyMuPDF/Tesseract, but JATS/PMC XML and DOCX/HTML extraction would strengthen every downstream checker: statcheck tables, transparency statements, section-scoped citation suggestions, meta-analysis extraction, and preregistration comparison. JATSdecoder is especially relevant because it extracts metadata, sectioned text, references, statistical results, methods, software, power, assumptions, and multiple-comparison language.

4. ContriBOT + tenzing	Use both for the CRediT track. Tenzing is the producer-side builder: authors x CRediT roles -> contribution statement, affiliations, JATS XML, YAML, funding, COI. ContriBOT is the consumer-side extractor: contribution statements, acknowledgements, ORCIDs, CRediT-like estimates, responsibility statements. Together they make Callosum's future CRediT builder much stronger.

5. scrutiny	Mine it for consistency-test expansion. Callosum already has GRIM/GRIMMER, so do not bolt on the whole R package. Instead, use scrutiny as lineage and validation material for DEBIT, duplication analysis, and a more general consistency-test registry. This fits your existing statcheck/GRIM pattern.

6. metacheck	Treat as an architectural reference for a modular research-output check registry. It is not one killer feature, but its premise maps well onto Callosum's METHODS module pool: checks should be modular, testable, and skip/mock web, LLM, or long tests.

7. auto-zcurve	Add only as a collection-level, opt-in, disclosure-table-first module. It uses Gemini to extract focal statistics and produce z-curve reports, so the Callosum version should require human verification of extracted focal results before any plot or ERR/EDR estimate is shown. Good fit beside p-curve, but more dangerous because "focal statistic" extraction is judgment-laden.

8. TOSTER, BF_TOST, JustifyAlpha, sample-size justification, ANOVApower	Build these as methods-literacy/reporting prompts, not automated verdicts. Most valuable first: a "null-effect inference" checker that detects "no effect/no difference" claims and asks whether equivalence bounds, SESOI, TOST, Bayes factors, precision, or sample-size rationale are reported. TOSTER's core value is correcting the common "non-significant = no effect" inference.

9. WORCS + reproducibleRchunks	Keep for a later producer-side reproducibility lane. WORCS is a workflow/template approach, while reproducibleRchunks fingerprints R Markdown outputs to test whether rebuilt chunks reproduce prior results. Useful when Callosum starts reasoning about code/data artifacts, not urgent for the reference-manager spine.

Tools I would not prioritize
> QuartoReview is mostly a local .qmd / .Rmd / .md editor. It is useful if Callosum becomes a manuscript editor, but it is not an automated research-checking module.
> coarse is methodologically useful but too specialized. It belongs in a future causal-inference METHODS module only if Callosum later audits causal designs.
> open_peer_review is more a study-specific text-mining repo than a reusable checker. It could inspire an "open peer review available" signal, but it is not a near-term integration.

Concrete integration order
1. First increment: build methods/transparency.py with ODDPub/rtransparent/OIF-derived detectors over existing chunks. Output evidence rows with kind, status, matched_sentence, source_page, confidence_basis, and detector_credit. Feed them into the existing findings/tag design, especially the open #19 tags-to-system-facts problem.

2. Second increment: add DocumentTextProvider adapters for JATS/XML, DOCX, and HTML. Keep PyMuPDF/Tesseract as primary PDF paths. This is infrastructure, but it unlocks better table/stat extraction, PMC transparency detection, and preregistration comparison.

3. Third increment: spec RegCheck the Callosum way. The failure mode is letting an LLM summarize "deviations" without inspectable evidence. The aligned version is a registration-paper delta table with source-paired quotes and statuses. This likely touches your unresolved "how auditable is auditable enough?" gate.

4. Fourth increment: CRediT builder/extractor. Use tenzing for the builder lineage and ContriBOT for extracting/reading contribution statements from already-published papers. This fits the existing future track directly.

5. Fifth increment: extend statistical consistency checks from "statcheck + GRIM/GRIMMER" toward a registry: DEBIT, table-aware stat extraction, more statcheck forms, and maybe z-curve later. The backlog already identifies more statcheck forms and table results as the remaining open follow-up.

Bottom line: the biggest missing category is not another inferential-statistics checker. It is transparency and registration alignment. Callosum already has a strong statistical-auditing spine. The most natural next expansion is: "Does this paper make the open-science and preregistration artifacts visible, and how do those artifacts line up with the published report?"