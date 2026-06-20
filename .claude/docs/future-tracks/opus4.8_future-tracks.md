# Future Tracks Scope

Capture document for post-core functionality. These are not part of the increment-by-increment core build; they are tracks to design *toward* so the core's data contracts don't foreclose them. Each entry records what comparable tools actually do, where the difficulty lives, the dependencies inside Callosum, and the honest caveats. Nothing here should be built until the persistence core, import, PDF-to-coordinate pipeline, embeddings, and verified summarization are working.

The connective principle across these tracks: they are **signals, suggestions, and retrievals that must remain inspectable and non-authoritative**, the same spine the core already commits to for citation grounding. None of them may auto-apply a judgment, silently fold a weak signal into a score, or fabricate a link or source. Each must show its evidence and leave the decision to the user.

---

## Track A: statcheck integration for the open-science layer

### What it is
statcheck is an established method (originating as an R package, with a maintained Python port) that acts as a "spellchecker for statistics." It uses regular expressions to find null-hypothesis significance test (NHST) results reported in APA style — `t(df)`, `F(df1,df2)`, `r(df)`, `χ²(df, N)`, `Z`, and `Q` (meta-analytic) — then recomputes the p-value from the reported test statistic and degrees of freedom and compares it to the reported p-value. It flags two tiers: an **inconsistency** (reported and recomputed p disagree) and a **gross inconsistency / decision error** (significance flips — reported significant, recomputed not, or vice versa). It accounts for correct rounding of the test statistic and has a one-tailed-test option, so it does not naively flag rounding artifacts as errors. (see: https://statcheck.io/#tab-4936-5)

### How comparable tools use it
statcheck's documented use cases are self-check before submission, peer-review screening, and research on p-value distributions. There is no major reference manager that surfaces statcheck as a per-paper signal in a library view — this would be a genuinely novel placement for Callosum, not a copy of an existing feature. The closest existing surfaces are the standalone statcheck web interface and journal-side screening (some publishers screen submissions with it).

### Where it slots into Callosum
It is another **open-science signal** in the discovery layer, alongside preregistration, open-data, and open-code detection. It runs on extracted text, which the PDF pipeline already produces, so it adds no new extraction dependency. The Python port means it lives natively in the backend with no R bridge.

### Dependencies
- The PDF-to-text pipeline (already core). statcheck operates on the same extracted text used for chunking.
- The open-science signal model in `data-contracts.md` (the "Open-science signals and evidence snippets" table). statcheck results attach as one more signal type with evidence snippets (the matched statistic string, the reported vs recomputed p, the flag tier).

### Honest caveats (must be recorded in the feature design)
- **APA-format-only.** statcheck recognizes only completely-reported NHST results in APA style. It misses results in tables, structural-equation output, Bayesian reporting, confidence-interval-only reporting, and any field that does not report inline in that exact format. For a neuroscience / neuroimaging-adjacent corpus this is a real coverage gap — a paper with zero detected statistics is not necessarily a paper without statistics.
- **Inconsistency ≠ error ≠ misconduct.** A flag means "the reported p does not match the recomputed p," which can arise from typos, rounding the wrong way, reporting adjusted vs unadjusted values, or genuine error. It is not evidence of wrongdoing, and the literature on statcheck is explicit about this.
- **PDF conversion noise.** statcheck's own documentation recommends HTML over PDF input because PDF-to-text conversion introduces character errors (especially around comparison operators `<`/`>`/`=`) that can produce false flags. Callosum should treat PDF-derived statcheck results as lower-confidence than born-digital text, and ideally show the user the exact matched string so they can see a conversion artifact for what it is.

### Design rule
statcheck consistency is surfaced as an **inspectable, separately-displayed signal**, never silently weighted into a composite open-science score that ranks a paper down. Show the count of checked statistics, the count and tier of flags, and the matched evidence for each. If an open-science composite score exists, statcheck may contribute only as a transparent, user-visible, optionally-weighted component the user can inspect and disable — consistent with the core's "do not hide uncertainty" principle.

### First validation (when built)
Run the Python statcheck port over a born-digital PDF with known APA-style results and confirm the detected statistics, recomputed p-values, and flag tiers match a hand-checked expectation, with each result carrying its matched source string.

---

## Track B: word processor citation plugin (Word + LibreOffice)

### What it is
A "cite-while-you-write" integration that lets the user insert in-text citations and a managed bibliography into a manuscript from their Callosum library, with the bibliography updating dynamically as citations are added or edited.

### How comparable tools do it (and why this is a track, not a feature)
Zotero's integration is the reference design and it confirms the scope. Zotero implements each word processor through a **separate plugin exposing a common `Application` / `Document` / `Field` interface**, with a central coordinator handling session state and CSL-driven formatting. The two host environments share almost no code:

- **Microsoft Word.** The modern path is an **Office.js task-pane add-in**: an HTML/JS panel that runs in a WebView inside Word and talks to a local web server over HTTPS-on-localhost. Microsoft publishes a working citation-management sample that does exactly the relevant primitive — the user picks a `.bib` file, the add-in lists references (parsing with `@orcid/bibtexParseJs`), the user selects document text, and the add-in inserts a citation mark plus a managed reference entry. Citations live in the document as **content controls bound to custom XML parts**, which is how the add-in can find, refresh, and reformat its own citations later without clobbering the user's text. Office.js runs on Word for Windows, Mac, and the web from one codebase. (Zotero's older path used a Word startup template / field codes; the Office.js add-in model is the current, cross-platform, distributable approach and is the recommended target.)
- **LibreOffice Writer.** A completely separate **UNO extension** (`.oxt`), historically requiring a working Java runtime, installed through the Extension Manager and adding a Writer toolbar. None of the Word add-in code transfers.

Zotero, Mendeley, and others maintain these as parallel integrations precisely because the surfaces are this different. That is the scope signal: this is a **track with its own internal staging**, not a single deliverable.

### Where it slots into Callosum
It sits outside the local browser app as a distribution surface that calls the same local backend over localhost. The shared dependency both plugins lean on is a **CSL citation processor** — `citeproc-js` (JS, fits the Office.js add-in directly) or `citeproc-py` (in the backend) — driving formatted in-text citations and bibliographies from the canonical CSL-JSON the core already stores per paper.

### Dependencies
- The canonical CSL-JSON payload per paper (already core — `data-contracts.md` "Canonical Metadata Shape"). This is the input to CSL formatting; the plugin track is a direct consumer of the decision to store verbatim CSL-JSON.
- A local HTTP boundary on the backend the add-in can call (the FastAPI app, a later core increment). The add-in is a client of it.
- A CSL processor and a citation-style story (which CSL styles to ship; 10,000+ exist via the CSL repository).

### Honest caveats
- **Two near-independent builds.** Budget for Word and LibreOffice as separate efforts sharing only the CSL layer and the backend API. Do not plan as if one follows trivially from the other.
- **Document-portability of citation state.** Office.js content-control + custom-XML binding ties the citation state to the document; this is robust but Word-specific, and the LibreOffice equivalent is a different mechanism. A document cited in one will not carry its live citation fields into the other.
- **Office.js requires HTTPS-on-localhost and a Microsoft 365-connected Office**, plus a loopback exemption on first run — minor but real setup friction to document for users.
- **Distribution.** Office add-ins ship via manifest/sideload or the partner store; LibreOffice via `.oxt`. Neither is a one-click install in the way a single desktop app would be.

### Design rule
The plugin inserts and manages citations the user explicitly chooses. It must never auto-insert a citation the user did not select. (Reference *suggestion* — proposing candidates — is Track C; insertion is only ever user-confirmed.)

### Staging (when this track opens)
1. Backend CSL formatting endpoint: given a paper ID and a CSL style, return a formatted in-text citation and bibliography entry.
2. Word Office.js add-in: list library references, insert a user-selected citation as a bound content control, render/refresh the bibliography. (Word-first, given the user base.)
3. LibreOffice UNO extension reaching feature parity with the Word add-in.

### First validation (when built)
From the Word add-in, select text in a document, pick a paper from the Callosum library, insert a formatted citation bound to a content control, and confirm the bibliography updates and survives a refresh.

---

## Track C: highlight-to-suggest and highlight-to-evaluate

### What it is
Two related actions on a span of text (a sentence or paragraph, either in a draft inside the plugin or pasted into the app):
- **Suggest references**: find the papers most relevant to cite for this sentence — first from the user's own library, optionally extended to papers they do not yet have.
- **Evaluate the claim**: assess whether the sentence's claim is supported, contrasted, or merely mentioned by the most relevant literature, with the evidence shown.

This is the most novel and most "Callosum" of the three, and it is largely a **recombination of machinery the core already builds**, pointed in a new direction.

### How comparable tools do it
- **Scite Assistant** does exactly the suggest-references action: paste a claim, get citations that support it, retrieved from an indexed full-text + citation-context database (so it surfaces papers keyword search misses). Crucially, Scite frames it correctly — "AI can find the right paper; whether it's the right citation for your specific sentence is still your call" — and pairs suggestion with **Smart Citations** (supporting / contrasting / mentioning, with the citing sentence shown in context) for the evaluate action.
- **Consensus** does the evaluate action as claim aggregation: retrieve relevant papers, classify each as yes/no/possibly against the claim from extracted verbatim quotes, and aggregate into a meter — explicitly grounding the answer in extracted quotes rather than generated prose.
- **Academic systems map almost exactly onto this feature and are the best technical references.** *SciLit* (Gu, 2023) is a pipeline that recommends relevant papers, extracts highlights, and **suggests a citation sentence given user-provided context and keywords**, using a two-stage pre-fetch + re-rank search over hundreds of millions of papers. *LitLLM* (2024) does plan-based, citation-grounded related-work generation using the Semantic Scholar recommendation API, with explicit prompts that force every generated sentence to cite a provided reference. Both are retrieval-then-attribute architectures — the same shape as Callosum's verified summarization.
- A 2024 study (Algaba et al.) found LLM-suggested citations have "remarkable similarity" to human citation patterns but warned they "may amplify existing biases and introduce new ones." This is a caveat to record, not a blocker.

### Where it slots into Callosum
- **Suggest (in-library)**: embed the highlighted span and retrieve the most similar abstracts/chunks already in the library. This is the guided-clustering / retrieval machinery run in reverse (instead of sorting the library under an axis, score the library against the span). Fully local, no LLM.
- **Suggest (extend beyond library)**: use OpenAlex (`related_works`, co-citation, bibliographic coupling) and the Semantic Scholar recommendation API to surface relevant papers the user does not yet have — each suggestion carrying an explainable reason ("shares N references with papers you cite here," "co-cited frequently with X"). This reuses the discovery layer.
- **Evaluate**: this is the assertion-checking stretch feature applied to the *author's own draft sentence* rather than to a generated summary. Retrieve relevant chunks, run NLI/stance classification (support / contrast / mention), aggregate with visible confidence and verbatim quotes. Reuses the verification machinery from summarization wholesale.

The one genuinely new capability is **section-scoping** — "the literature most relevant for citing *in that section*" implies the tool can constrain the candidate set to a section's working bibliography. That is a real but bounded addition (it requires section awareness, which GROBID already provides for imported papers, and a notion of "the references already cited in this section" if operating inside the plugin).

### Dependencies
- Local embeddings + vector store and the retrieval layer (core).
- The NLI/stance classifier and the verified-vs-related confidence contract (core — `data-contracts.md` "Verification Confidence Contract"). The evaluate action is the same support/contrast/mention computation, and the same rule applies: stance comes from local NLI over retrieved spans, **never** from Semantic Scholar intents (which are Background/Method/Result, not stance).
- The discovery layer (OpenAlex + Semantic Scholar) for the extend-beyond-library suggestions.
- For maximum usefulness, Track B (the plugin), so the highlighted span and the section's existing citations come straight from the manuscript. A paste-a-paragraph version works standalone first, without the plugin.

### Honest caveats
- **This is where Callosum becomes a writing-assistance tool**, not just a reading/organizing tool. Suggesting a citation the author did not make, or judging their claim, is a strong action with the same trust hazard as summarization. It must show evidence and never auto-insert or auto-judge.
- **Citation suggestion can amplify bias** (over-suggesting already-highly-cited work, entrenching the user's existing library). Surfacing the *reason* for each suggestion is the mitigation; ranking purely by similarity or citation count is the failure mode.
- **"Relevant for citing here" is a ranking claim, not a correctness claim.** The tool proposes; the author decides whether a paper is the right citation for their specific sentence — exactly Scite's framing.

### Design rule
Suggestions are proposed with visible reasons and never auto-inserted. Claim evaluations show the supporting/contrasting verbatim quotes and confidence, and never render a verdict without that evidence. The author is always the final judge of fit.

### Staging (when this track opens)
1. In-library suggest: highlight/paste a span, return ranked library papers by embedding similarity, fully local.
2. Evaluate: add stance classification over retrieved spans, with the support/contrast/mention meter and verbatim quotes.
3. Extend-beyond-library suggest: add OpenAlex/Semantic Scholar candidates with explainable reasons.
4. Section-scoping: constrain candidates to a section's working bibliography (strongest inside the plugin).

### First validation (when built)
Given a pasted sentence and a small imported library, return the most relevant in-library papers ranked by local embedding similarity, then label each as support/contrast/mention with a verbatim supporting quote and a visible confidence — no external API call required for the in-library path.

---

## Track D: full-text acquisition (legal free-source resolver)

### What it is
Suggested and library papers should not be dead-ends. When the user wants the full text of a paper Callosum knows about (from a discovery suggestion, a citation, or a metadata-only library record), the tool runs an **ordered chain of free, legal sources** to locate and fetch the PDF, downloading it when a legitimate copy exists and reporting a clear "no free full text found" state with sensible next steps when one does not. The full text it retrieves then flows into the normal pipeline (attachment record, PDF processing, chunking), upgrading a metadata-only paper toward the fully-chunked tier.

### How comparable tools and workflows do it
The resolver-chain pattern is well established. The standard shape: try the most authoritative open source first, fall through to broader aggregators, and terminate in an honest not-found state. A representative chain seen in open-access fetching workflows is: check PubMed Central / Europe PMC for a free full text, try the DOI directly, then query Unpaywall, and if all fail, report no full text with options (institutional access, contact authors, abstract only). Discovery systems like Alma/Primo embed Unpaywall the same way — surface the OA PDF link when `best_oa_location.url_for_pdf` exists, otherwise show nothing rather than a broken promise.

### The legal free sources, as an ordered chain
Each step is free and (except where noted) keyless. The chain stops at the first success.

1. **OpenAlex `best_oa_location` / `oa_url`.** Already integrated for discovery and OA scoring. Often already holds a direct OA PDF link, so it is the cheapest first check.
2. **Unpaywall (by DOI).** The workhorse: it checks 50,000+ OA sources across 30M+ articles and returns `best_oa_location.url_for_pdf`, including author-deposited green-OA copies in repositories. Free, no key; requires an email parameter; ~100k calls/day suggested, with a data dump available for bulk. (OpenAlex's OA fields are Unpaywall-derived, so treat this as the authoritative resolution of step 1.)
3. **PubMed Central / Europe PMC.** For biomedical and neuro-adjacent work, a free full text or `pdf=render` link is frequently available here even when the publisher page is paywalled. Highly relevant to the user's field.
4. **Preprint servers (arXiv, bioRxiv, PsyArXiv, etc.).** For fields where preprints are common, the author manuscript is legally free. Match by DOI/title; arXiv has a free, keyless API.
5. **CORE.** Aggregates 200M+/300M+ open-access papers with direct PDF links; useful as a broad sweep for repository-hosted copies the narrower sources miss (free API; key for heavier use).
6. **Institutional access (Penn link resolver / EZproxy / OpenURL).** For content the user is legitimately entitled to through their institution. This is a per-user configuration: the user supplies their library's OpenURL/resolver base, and Callosum constructs an entitled-access link. It does not bypass anything — it uses access the user already has.
7. **Author-contact / request path.** For the genuinely closed remainder, surface a "request from author" affordance (corresponding-author email from metadata, or an ORCID/email lookup), and the option to continue with abstract-only.
8. **Terminal state: "no free full text found."** An explicit, honest end state — never a false or broken link. The paper remains a valid metadata-only or abstract-embedded record (per the processing-tier contract) and can still be clustered and cited as unverified-context, just not grounded to PDF coordinates.

### Where it slots into Callosum
It is a discovery-layer capability that consumes the OpenAlex/Unpaywall integration already planned and feeds the PDF-processing pipeline already planned. A resolved PDF becomes a managed attachment (content-addressed, per the library-store contract), then runs through extraction/chunking, which upgrades the paper's processing tier. So this feature is the bridge that turns a discovery suggestion into a fully-grounded, citable library item.

### Dependencies
- OpenAlex + Unpaywall integration (planned in `integrations/openalex/` and the discovery layer). Unpaywall is a small additional adapter sharing the same caching and email-identification pattern.
- The PDF-processing pipeline (the resolved PDF is just another input to it).
- The library store (resolved PDFs are copied into the managed, checksummed store).
- A user-supplied email (for Unpaywall) and, optionally, institutional resolver configuration (for step 6).

### Honest caveats (must be recorded in the feature design)
- **The chain will not find everything.** A meaningful fraction of recent paywalled literature has no legal free copy anywhere, and the design must say so plainly rather than imply completeness. The terminal "not found" state is a first-class outcome, not an error.
- **Resolved links can be stale or wrong.** Unpaywall is third-party data; OA links occasionally 404 or point to the wrong version. Validate that a fetched file is actually a PDF before storing it, and record the resolution source and version per the provenance philosophy used elsewhere.
- **Polite use.** Honor each source's rate-limit guidance and identification requirements (email/User-Agent), cache resolutions, and prefer the bulk Unpaywall snapshot for any large batch rather than hammering the API.
- **Institutional access is the user's own entitlement.** Step 6 uses access the user already holds through their institution; it is configured per-user and constructs entitled-access links, not circumvention.

### Scope boundary (explicitly out of scope)
This track covers **free, legal acquisition only.** Paywall-circumvention sources (e.g. Sci-Hub-style services that distribute articles by bypassing publisher access controls) are out of scope for Callosum's design and will not be built into the resolver chain, in any form — fetcher or link-builder. The chain ends at the honest "no free full text found" state. This boundary is recorded here so the decision is documented rather than relitigated; what a user does on their own machine beyond that terminal state is their own affair, but it is not part of this tool's design.

### Design rule
Acquisition only ever retrieves what a source legitimately offers for free or what the user is legitimately entitled to. Every resolved file records its source; the chain never fabricates a link; the not-found state is always honest.

### First validation (when built)
Given a DOI with a known green-OA copy, the resolver returns the correct free PDF URL via the OpenAlex→Unpaywall steps, validates and stores it as a managed attachment, and the paper advances to a chunkable tier. Given a DOI with no legal free copy, the resolver returns the explicit not-found state without a broken link.

---

## Cross-track placement relative to the roadmap

- **Track A (statcheck)** folds into **Stage 5 (Discovery and Scoring)** as an additional open-science signal. It is the lightest of the three and has no new core dependency beyond extracted text.
- **Track D (full-text acquisition)** also folds into **Stage 5**, extending the OpenAlex/Unpaywall integration into an ordered resolver chain. It is the natural partner to discovery — a suggestion the user cannot read is only half useful — and it feeds resolved PDFs straight into the existing PDF pipeline, upgrading metadata-only papers toward citable, fully-chunked status.
- **Track C (highlight-to-suggest/evaluate)** is mostly a recombination of Stage 3 (clustering/retrieval) and Stage 4–5 (verification, discovery) machinery; its standalone (paste-a-paragraph) form can begin once those exist. It is the highest-value novel capability.
- **Track B (plugin)** is a distinct **post-V1 authoring track** with its own internal staging (Word → LibreOffice), depending on the canonical CSL-JSON (already core) and a backend HTTP boundary. It is the largest commitment and makes Track C maximally useful by bringing the manuscript's text and section context into reach.

A reasonable sequence once the core is done: statcheck signal + full-text acquisition (both cheap, both slot into Stage 5 and reuse discovery infrastructure) → standalone highlight-to-suggest/evaluate (reuses existing machinery) → Word add-in (opens the authoring surface) → section-scoped suggestion inside the add-in → LibreOffice parity.

## Sources consulted
statcheck: CRAN package page and manual (MicheleNuijten/statcheck), the Python port (hplisiecki/statcheck_python). Word processor integration: Zotero word-processor integration architecture (Application/Document/Field pattern) and documentation; Microsoft Office.js Word add-in docs, the Word citation-management sample (content controls + custom XML + `@orcid/bibtexParseJs`), and content-control binding docs. Suggestion/evaluation: Scite Assistant and Smart Citations; Consensus claim aggregation; SciLit (arXiv:2306.03535) and LitLLM (arXiv:2402.01788) for retrieval-then-cite architectures; Algaba et al. on LLM citation-suggestion bias. Full-text acquisition: Unpaywall API (free, email-identified, ~100k/day, OA `best_oa_location`); OpenAlex OA fields (Unpaywall-derived); PubMed Central / Europe PMC; arXiv API; CORE; the OpenURL/institutional-resolver pattern; and the established OA resolver-chain workflow (PMC → DOI → Unpaywall → not-found). Dates on volatile external limits should be recorded in `research/` per its rules.
