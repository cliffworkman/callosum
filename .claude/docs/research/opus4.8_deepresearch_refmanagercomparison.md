# Competitive Feature-Characterization for Callosum: Seven Reference Managers + Elicit Deep-Dive

## TL;DR
- **Part A:** Among the seven incumbents, **Zotero is the only fully open-source, local-first, inspectable, no-lock-in option** (and thus Callosum's true philosophical sibling), while EndNote, Citavi, RefWorks, Mendeley, Paperpile and ReadCube/Papers each lead on a specific axis (institutional Word workflows; knowledge-structuring; web-based institutional admin; free polish; Google-Docs writing; AI-assisted discovery, respectively). Every one of them now bolts on cloud-only "chat-with-PDF" AI with inconsistent provenance and meaningful lock-in or governance concerns.
- **Part B:** Elicit is genuinely strong at AI evidence-extraction — sentence-level grounded citations and vendor-validated **95% search recall / 97% abstract screening / 99% full-text screening / 96% extraction across 994 Cochrane reviews**, plus a PRISMA-2020 systematic-review workflow — but it is **cloud-only, closed-source, and has no citation-insertion / Word / LibreOffice / CSL / reference-library features at all**. It is a discovery-extraction-synthesis engine, not a reference manager.
- **The "Elicit is the closest thing to Callosum" framing is only half-right:** Elicit is the nearest neighbor on AI extraction/synthesis, but **Zotero (plus its AI plugins) is the nearest neighbor on architecture and citation management**. No single product fuses local-first + open-source + true citation manager + auditing METHODS suite the way Callosum plans to — but these tools expose real holes in the backlog (notably citation-context "smart citations," citation-graph discovery, and literature alerts).

---

## PART A — REFERENCE MANAGER FEATURE MAP

### Orientation: ownership & model (2026)
- **Zotero** — open-source nonprofit (Corporation for Digital Scholarship / Center for History and New Media). Client is AGPL-licensed. Free app; paid cloud storage only. Local SQLite DB, fully inspectable.
- **Mendeley** — Elsevier-owned, free, cloud-centric (Mendeley Reference Manager + Mendeley Cite). Legacy Mendeley Desktop kept alive after Elsevier reversed its planned shutdown in July 2025 "based on customer feedback."
- **Paperpile** — independent commercial, subscription, Google-Docs/Drive-centric. New pricing tiers introduced **March 2026** (Regular, Expert, Enterprise/Institutions); legacy "Academic/Business" plans discontinued, with "Paperpile Classic" retained for pre-March-2026 subscribers.
- **RefWorks** — Clarivate/ProQuest (Ex Libris); web-only; institution-licensed.
- **ReadCube Papers** — Digital Science; subscription; "Papers" consumer manager + "ReadCube" enterprise literature-management/SLR; AI powered by the Dimensions database (150M+ records).
- **Citavi** — Lumivero (ex-QSR International / Swiss Academic Software, backed by TA Associates); Windows-centric + Citavi Web; reference management + knowledge organization + task planning; 11,000+ styles.
- **EndNote** — Clarivate; one-time purchase (EndNote 2025); desktop + EndNote Web; AI "Research Assistant" on the Clarivate Academic AI Platform.

### 30-dimension highlights per tool

**ZOTERO**
- *Acquisition:* Best-in-class browser Connector (Chrome/Firefox/Safari/Edge) with hundreds of site translators; DOI/PMID/ISBN/arXiv lookup; drag-drop PDF with metadata retrieval; RIS/BibTeX/CSL-JSON/EndNote-XML/Zotero-RDF import; full web-page snapshots with access date. Most robust capture across messy sources.
- *Metadata cleanup:* PDF metadata retrieval, "rename from parent," duplicate detection/merge, and **Retraction Watch integration** (flags retracted items in the list and warns when citing via the word-processor plugin). No native journal-abbreviation engine (plugin territory).
- *Organization:* Hierarchical collections, tags, color tags, saved searches, related items, per-item notes; no native ratings/flags.
- *PDF/files:* Attach/store/link; "linked files" mode for user-controlled storage; ZotMoov/ZotFile-style plugins for auto-rename and watch folders.
- *Reading/annotation:* Native PDF reader (Zotero 7) with highlight, note, area/image annotation, ink; annotation extraction to a note; iOS app; no Android.
- *Citation:* Word, LibreOffice and Google Docs plugins; **10,000+ CSL styles** (community repo); Better BibTeX plugin gives stable citekeys + LaTeX/Markdown workflows (with Zotero 8 now storing a native citation-key field). Strongest open citation stack.
- *Collaboration:* Group libraries (public/private), shared annotations; storage tier governs file sync.
- *Sync/offline:* Local-first by design; optional Zotero cloud sync; WebDAV alternative; transparent, directly queryable SQLite DB; user-controlled storage location.
- *Portability:* Full BibTeX/RIS/CSL-JSON/RDF export; open DB; documented web API. **Best portability of the seven.**
- *AI:* **No native AI in 2026** — the Zotero team has publicly stated it focuses on citation management, not AI. AI is added via third-party plugins (PapersGPT, Aria, Beaver, ZotSeek) supporting local models (Ollama) and BYO-API keys; Beaver can also search 240M+ papers and fill missing metadata with confirm-before-apply.
- *Systematic review:* No native PRISMA workflow; used alongside external tools; SQLite directly queryable for bespoke analysis.
- *Privacy/trust:* Open source, local-only possible, nonprofit governance, inspectable formats. **Highest trust posture of the seven.**
- *Platforms:* Win/macOS/Linux desktop, iOS, web library; browser extensions.
- *Pricing (2026):* App free; storage 300 MB free, 2 GB ≈ $20/yr, 6 GB ≈ $60/yr, unlimited ≈ $120/yr (yearly billing only; a recurring user complaint).

**MENDELEY**
- *Acquisition:* Mendeley Web Importer (Chrome/Firefox/Edge) auto-detects identifiers and fetches available PDFs; drag-drop PDF; watched folders; Mendeley Web Catalog search. (Standalone literature search was removed in the desktop→web transition.)
- *Metadata:* Auto metadata extraction; duplicate detection. Adequate, not class-leading.
- *Organization:* Collections, smart collections, tags; "Notebook" aggregates highlights across multiple PDFs.
- *Reading:* PDF reader with highlights/notes; Notebook; reading-position sync across devices.
- *Citation:* Mendeley Cite (Word 2016+/365/Online/iPad, also usable standalone); legacy Cite-O-Matic plugin supports LibreOffice. Style set smaller than Zotero's CSL repo.
- *Collaboration:* Private groups (free tier limited to **5 groups / 25 members**).
- *Sync/offline:* Cloud-centric; PDFs stored in Elsevier cloud (new Reference Manager has **no local-folder library**). 2 GB free storage.
- *Portability:* **Major concern — the newer Mendeley encrypts citation data, which blocks export to other reference managers.** A 2018 update also caused some users to lose PDFs/annotations.
- *AI:* New 2026 "AI in Mendeley" features (library Q&A, "connect the dots" across references) being rolled out; cloud-based, still marketing-stage.
- *Trust:* Elsevier ownership widely distrusted in the open-science community (Mendeley was de-listed as a recommended green-OA repository after the acquisition); cloud-only storage; export lock-in. **Weak trust posture.**
- *Pricing:* Free (2 GB); institutional storage upgrades.

**PAPERPILE**
- *Acquisition:* Chrome-first extension (Firefox added; Safari requested), tight Google Scholar/PubMed/publisher capture; auto-downloads PDFs via institutional access; auto-fixes incomplete references; Open-Access links via Unpaywall.
- *Metadata:* Auto metadata repair and duplicate cleanup; reviewers want stronger dedup/version control.
- *Organization:* Folders, labels, stars; real-time search (full-text PDF search is an Expert-tier feature).
- *PDF/files:* PDFs stored in the user's own Google Drive (effectively unlimited); highlight/annotate; iOS/Android apps (mobile import weaker than web).
- *Citation:* Best-in-class **Google Docs** citation plugin; Word plugin; native BibTeX export with auto-sync to **Overleaf** and auto-updating citekeys; one-click style switching; thousands of styles.
- *Sync:* Cloud via Google Drive; good cross-device, occasional sync flakiness reported.
- *Portability:* BibTeX/RIS export available; data tied to a Google account; users can always export on cancellation.
- *AI:* AI-assisted related-paper suggestions (per third-party reviews); no deep synthesis/chat.
- *Trust:* Commercial, closed, Google-dependent; reasonable export story.
- *Pricing (2026):* **No free plan** (30-day trial). New March-2026 tiers — **Regular** (collect/organize/read/write/cite core), **Expert** (adds full-text PDF search, notes/annotations, shared folders/libraries, supplementary files, Drive PDF sync, up to ~20% group discount), **Enterprise/Institutions** (SAML SSO, advanced security, HIPAA, custom agreements). Public per-seat monthly prices for Regular/Expert were not posted on the captured pricing page; historical entry pricing was ~$2.99–$9.99/mo.

**REFWORKS (ProQuest/Clarivate)**
- *Acquisition:* "Save to RefWorks" web-page capture; direct database export (EBSCO, JSTOR, ProQuest, ScienceDirect, Wiley, Google Scholar); PDF import with metadata read; RIS/BibTeX import; import from Mendeley/legacy RefWorks.
- *Metadata:* "Find ref info" lightning-bolt lookup; "missing-data" alerts; expanded ref types (Computer Program/Software, Figure/Image, Government Document, Lecture, Film, Video).
- *Organization:* Folders/subfolders, Projects, full-text + advanced field search; Normal/Table/Full/Citation views.
- *Reading:* In-browser PDF viewer + annotation (screen-reader access to PDFs in the viewer is a documented accessibility gap).
- *Citation:* RefWorks Citation Manager (RCM) for Word + Google Docs add-on; thousands of styles; a citation-formatting on/off toggle for large documents. **RCM's Google Docs add-on draws frequent "doesn't work / works half the time" user reviews.**
- *Collaboration:* Project sharing (read/annotate/modify), public-URL bibliographies, institutional folder sharing; admin dashboards + usage analytics.
- *Sync/offline:* Web-only, cloud; **5 GB** attachment limit; the institution is the data controller.
- *Portability:* Export RIS/BibTeX; institution-gated; full data deletion on account removal.
- *AI:* No notable native generative AI in 2025–2026 release notes.
- *Trust:* Institution-licensed; Clarivate-owned; data governance handled at the institution level.
- *Pricing:* Institutional site license (no consumer price); unlimited references.

**READCUBE PAPERS (Digital Science)**
- *Acquisition:* Browser-extension import; "Get PDF" **document-delivery** (paid full-text ordering with cost/time shown); search over Dimensions (150M+ publications, plus grants/patents/clinical trials).
- *Metadata:* Auto metadata; personalized recommendation feeds.
- *Reading:* Enhanced PDF reader (highlight, strikethrough, underline, inline + sticky notes, tabs, supplemental files).
- *Citation:* **SmartCite** for Word + Google Docs; 9,000+ styles.
- *Collaboration:* Shared libraries (up to 5 on individual Pro; unlimited on enterprise), shared annotations, SmartLists; enterprise SSO/admin dashboard/cost-center controls.
- *AI:* AI Assistant — chat with one/multiple PDFs or the whole library; **every answer links back to where in each reference the information derives** (designed for validation); AI-curated literature monitoring with email summaries; enterprise **Systematic Literature Review** tool with AI-assisted data-extraction fields ("verify rather than start from scratch") and multi-stage screening. Framed as "private and secure."
- *Sync:* Cloud, unlimited storage; cross-device.
- *Portability:* Export supported; subscription-only since the discontinuation of the one-time Papers 3.
- *Pricing (2026):* Papers individual ≈ **$7/mo Essentials**, ≈ **$14/mo Pro** (academic discounts; unlimited cloud storage, SmartCite, 8,000+ styles, up to 5 shared collections); enterprise/SLR by custom quote.
- *Trust:* Commercial; Digital Science (Holtzbrinck-affiliated) ownership.

**CITAVI (Lumivero)**
- *Acquisition:* Citavi Picker (Firefox/Chrome/IE) recognizes ISBN/DOI/PMID/PMCID/arXiv; online search across thousands of catalogs/databases (PubMed, Web of Science); COinS; RSS feeds; capture web pages as PDF.
- *Metadata:* Auto metadata extraction on drag-drop; **35+ reference types**.
- *Organization:* **Strongest knowledge-organization model of the seven** — quotations, summaries, comments and images saved as discrete "knowledge items," each linked to its reference; flexible categories/outline for structuring a draft; built-in **task planner with deadlines**.
- *Reading:* PDF annotation in-app; full-text search of extractable text.
- *Citation:* Word add-in (insert citations + quotations, auto-bibliography); LaTeX support via several editors; **11,000+ styles**; custom-style editor; multilingual.
- *Collaboration:* Cloud projects with Reader/Author/Project-leader roles; **Citavi for DBServer** lets institutions host project data in an intranet MS-SQL Server with Active Directory access control and concurrent multi-user access.
- *AI:* "Citavi Assistant" — generate an overview of an article, or summarize a paragraph/section in one click.
- *Sync/offline:* Local projects on the hard drive OR Citavi Cloud; Windows license includes **5 GB** attachment storage; Citavi Web is OS-independent (usable on Mac via browser).
- *Platforms:* Windows desktop (primary) + Citavi Web; **no native mobile app**.
- *Pricing (2026):* From ≈ **$197**; after the Lumivero acquisition, users report prices roughly doubled, support slowed, and perpetual licensing largely disappeared.
- *Trust:* Commercial, private-equity-owned (TA Associates → Lumivero, which also owns NVivo/ATLAS.ti/XLSTAT); consolidation and price-hike concerns.

**ENDNOTE (Clarivate)**
- *Acquisition:* Online search connections to hundreds of databases; PDF import + auto-metadata; **Find Full-Text**; **EndNote Click** browser plugin; import filters.
- *Metadata:* **Find Reference Updates**; **retraction flags** in the library and during Cite While You Write; Web of Science citing-articles and related-records to grow a library.
- *Organization:* Groups, smart groups, combined groups, **Tags** (new in 2025), ratings; redesigned configurable summary panel.
- *Reading:* PDF viewer + annotation; **"Cite from PDF"** inserts a highlighted quote + its citation in one click.
- *Citation:* **Cite While You Write (CWYW)** for Word — the gold standard for institutional Word workflows; thousands of styles with continuously updated definitions; LibreOffice via older paths.
- *Collaboration:* Share library with collaborators; EndNote Web syncs across the desktop/cloud.
- *AI (EndNote 2025):* **Key Takeaway** (generative summary of a single paper, **explicitly extracted from the document only — not using other library documents or public LLMs**), **EndNote Research Assistant** (chat with a full-text PDF, answers "sourced directly from the paper," plus translation of full PDFs or selections), and **Find a Journal** (ML journal-matcher inside CWYW). Built on the **Clarivate Academic AI Platform**: uses commercially pre-trained LLMs through a private setup, **does not train public LLMs, and does not pass user data to LLMs**. A natural-language Research Assistant and proactive citation-update notifications were slated for later releases.
- *Sync/offline:* Desktop + EndNote Web (unlimited storage); data-restoration functions; local file format with a 30-year track record (local-first heritage).
- *Portability:* EndNote-XML, RIS, BibTeX export.
- *Pricing (2026):* One-time purchase ≈ **$274–$275** (full), ≈ **$175 student**; institutional site licenses; free iPad/iOS app; single license installs on up to 3 machines for one person.
- *Trust:* Clarivate-owned and closed, but strong longevity and reliable local file format.

### Minimal comparison matrix

| Dimension | Zotero | Mendeley | Paperpile | RefWorks | ReadCube Papers | Citavi | EndNote |
|---|---|---|---|---|---|---|---|
| Capture/import | ★★★★★ | ★★★★ | ★★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★ |
| Metadata cleanup | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ |
| PDF management | ★★★★ | ★★★ | ★★★★ | ★★ | ★★★★ | ★★★ | ★★★★ |
| Organization model | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★★★ | ★★★★ |
| Search/retrieval | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★ |
| Reading/annotation | ★★★★ | ★★★★ | ★★★ | ★★ | ★★★★ | ★★★ | ★★★ |
| Citation generation | ★★★★★ | ★★★ | ★★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★★ |
| Writing integrations | ★★★★ (Word/LO/GDocs/LaTeX) | ★★★ (Word) | ★★★★ (GDocs/Overleaf) | ★★★ (Word/GDocs) | ★★★ (Word/GDocs) | ★★★★ (Word/LaTeX) | ★★★★★ (Word) |
| Collaboration | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★ |
| Sync/offline | ★★★★★ (local-first) | ★★ (cloud-only) | ★★★ (Drive) | ★★ (web) | ★★★ | ★★★★ | ★★★★ |
| Export/portability | ★★★★★ | ★ (encrypted) | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ |
| Discovery/recommend | ★★ | ★★ | ★★ | ★★ | ★★★★ | ★★★ | ★★★ |
| AI features | ★ (plugins) | ★★ | ★★ | ★ | ★★★★ | ★★★ | ★★★ |
| Provenance/verifiability | ★★★★ | ★★ | ★★ | ★★ | ★★★ | ★★★ | ★★★ |
| Privacy/data ownership | ★★★★★ | ★ | ★★ | ★★ | ★★ | ★★ | ★★★ |
| Extensibility | ★★★★★ | ★ | ★ | ★ | ★ | ★★ | ★★ |
| Platform support | ★★★★ | ★★★ | ★★★★ | ★★★ | ★★★★ | ★★ | ★★★ |
| Pricing/licensing | ★★★★★ (free/OSS) | ★★★★ (free) | ★★ (sub) | ★★★ (inst) | ★★ (sub) | ★★ (paid) | ★★ (one-time) |
| Systematic-review | ★★ | ★ | ★ | ★★ | ★★★★ (SLR) | ★★ | ★★ |
| Performance at scale | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ |

*(Stars are this analyst's qualitative reading of 2026 documentation and credible reviews, not vendor metrics.)*

### Hidden-quality dimensions (what matters most for a local-first OSS entrant)
- **Metadata cleanup quality:** EndNote and Citavi lead on reference-update/repair; Zotero is strong on dedup + Retraction Watch flagging; all seven are weak on journal-abbreviation normalization and conference-vs-journal disambiguation — an opening for Callosum.
- **Provenance/verifiability:** ReadCube and EndNote explicitly tie AI answers to the source passage/document; Zotero has page-linked annotations. This is exactly Callosum's intended differentiator, and incumbents implement it inconsistently.
- **Export/portability (lock-in):** Zotero is best (open DB, full export). **Mendeley is worst — encrypted citation data blocks export.** Paperpile/ReadCube/RefWorks/Citavi/EndNote all export, but bind PDFs/notes to their cloud or proprietary format.
- **Privacy/data-ownership:** Only Zotero offers true local-only + open source. EndNote is notable for keeping AI document-local and avoiding public LLMs. Mendeley uploads everything to Elsevier cloud.
- **Trust posture (can users leave?):** Zotero (nonprofit, OSS, leaveable) > EndNote (longevity, local format) > Paperpile/ReadCube > Citavi (PE-owned, consolidating) > RefWorks (institution-gated) > Mendeley (Elsevier ownership + prior willingness to deprecate user data).

---

## PART B — ELICIT DEEP-DIVE

### What Elicit actually does
Elicit (elicit.com; formerly the nonprofit Ought) is an **AI research assistant**, not a reference manager. Core workflows:
1. **Find papers** — semantic search over **~138 million academic papers** (drawn from **Semantic Scholar, PubMed and OpenAlex**) plus **545,000+ trials from ClinicalTrials.gov**; natural-language queries return ranked papers with AI summaries.
2. **Extract data** — the signature feature: the user defines columns/concepts (sample size, methodology, population, outcomes, side effects, etc.) and Elicit populates a structured table across many papers, with each cell linked to a supporting quote; export to CSV/RIS/BIB/PDF/DOCX.
3. **Summarize / chat** — per-paper summaries; chat with full text; "list of concepts" across papers.
4. **Research Reports** — systematic-review-inspired structured briefs with citations; customizable papers/columns; up to 80 papers per report.
5. **Systematic Review workflow** — PRISMA-2020-compliant, "reproducible, traceable, auditable at every step," with exclusion reasons, per-criterion scores and supporting quotes; AI screening + AI-assisted extraction; **Pro screens up to 5,000 papers; Enterprise up to 40,000 in real time.**
6. **Library + Alerts + Research Agent** — store/organize found sources; topic alerts for new papers; a multi-step agentic "Research Agent."

### Corpus & coverage
- Searches its **own aggregated index** (~138M papers via Semantic Scholar + PubMed + OpenAlex; 545K clinical trials), with "more data sources coming soon."
- Reports can extract from **up to 135–200 data sources** (Pro/Scale tiers).
- Also works over **user-uploaded PDFs** (custom extraction from uploads is a Pro feature).
- Coverage is broad but skews STEM/biomedical given the Semantic Scholar base.

### Accuracy / grounding / provenance
- **Sentence-level citations** for all AI-generated claims; clicking a cell or claim shows the supporting quote.
- **Vendor validation** (elicit.com/blog/evaluating-elicit-slr): across 994 Cochrane reviews, **95.0% search recall, 96.9% abstract-screening sensitivity, 99.5% full-text paper-level recall (94.8% per-criterion accuracy), and 96% extraction**. Elicit's own data-extraction benchmark cites **94–99% accuracy**; a German VDI/VDE case reported **1,502/1,511 data points correct (99.4%)**, and an independent Cochrane study (Helms Andersen, 2025, *Cochrane Evidence Synthesis and Methods*, cesm.70036) found **precision, recall and F1 all 92%** for Elicit.
- **Anti-hallucination design:** compositional (not end-to-end black-box) pipeline, multiple-model ensembling/cross-checking, and confidence shown only when multiple models agree; all answers grounded in real papers.
- **Important caveat:** a peer-reviewed evaluation, **Lau et al. (2025), *Cochrane Evidence Synthesis and Methods*, doi:10.1002/cesm.70050**, found Elicit's relevance-ranking stage "neither as transparent or reproducible as using a traditional database search strategy," reporting **sensitivity of 35.6% (16/45) and precision of 35.6%** in their test and noting the underlying Semantic Scholar query/version history "remains opaque, which limits full reproducibility." Verification of every cell remains necessary.

### Privacy & data governance (from official Elicit sources)
- **Cloud-only** web SaaS, AWS-hosted (US servers); **no local/desktop/offline/self-hosted option.** Enterprise gets single-tenancy (logically isolated AWS clusters; data never co-mingled).
- **Uploaded PDFs:** per Elicit's help center, "PDFs you upload are encrypted and remain private to your account only, until you choose to delete them," and are **not added to the Elicit corpus** or shared with other users. Encrypted in transit (TLS 1.2+) and at rest (AES-256-GCM); AWS RDS multi-zone with daily backups.
- **Model providers:** model-agnostic across **OpenAI (GPT), Anthropic (Claude Opus/Sonnet), and Google (Gemini)**; per the elicit.com homepage, **"Claude Opus 4.5 is better than Sonnet 4.5, Google Gemini 3 Pro, and OpenAI GPT 5 at data extraction and writing reports with fewer hallucinations,"** and Opus 4.5 is the live high-quality model for Pro/Teams/Enterprise. This implies uploaded text **is** processed by third-party providers (under no-training agreements for Enterprise).
- **Training on user data — the key nuance:** Enterprise data is "fully redacted," explicitly not trained on, with provider zero-data-retention guarantees. **However, Elicit's API Terms of Service grant Elicit a license to use inputs "including… to train AI models."** So "no training" is an **Enterprise/contractual guarantee, not a universal default**; no documented consumer self-service training opt-out toggle was found.
- **Compliance:** **SOC 2 Type II achieved (October 2025, clean audit opinion)**; GDPR/CCPA addressed via a Data Processing Addendum + Standard Contractual Clauses + UK IDTA; SAML SSO + MFA for organizations. **No HIPAA/BAA found.**
- **Retention:** uploads retained until the user deletes them; otherwise a general "as long as necessary" policy (no published numeric window for consumer data); DSAR/deletion process available; daily backups can persist after deletion until cycled.

### Pricing & tiers (2026, from elicit.com/pricing — note volatility)
- **Basic (Free):** limited Research Agent; **2 automated reports/mo**; unlimited search over 138M papers; unlimited summaries; unlimited chat with full-text; **2 table columns** at a time; view sources; import from Zotero.
- **Plus (~$7/user/mo billed annually, ~$84/yr in one capture; widely tracked elsewhere at $12/mo):** export RIS/CSV/BIB/PDF/DOCX; 4 reports/mo; 5 columns; clinical-trials search.
- **Pro (captured at both $29 and $49/user/mo billed annually — in flux):** dedicated Systematic Review workflow (5,000-paper screening); 144 reports/SRs per year; **20 columns**; up to 135 data sources; 10 alerts; custom extraction from uploaded papers; explanations for answers; multiple output templates; API access.
- **Scale (captured at both $49 and $169/user/mo annually — in flux):** full Research Agent; **figure/table extraction**; real-time collaboration; 240 reports/yr; 200 data sources; 30 columns; admin panel with seat management.
- **Enterprise (custom):** **no training on data by default**; 40,000-paper screening; 40 columns; PRISMA-grade accuracy; SSO/SAML/2FA; single-tenancy; unlimited Search API.

### Elicit's limits as a reference manager
Elicit does **NOT**: insert citations into a manuscript; integrate with Word/LibreOffice/Google Docs as a citation plugin; format CSL styles or build a formatted bibliography; manage a PDF library with stable citekeys; offer a built-in annotation/highlighting reading workflow; run offline/local; or guarantee universal no-training. It is a discovery/extraction/synthesis engine — the opposite end of the stack from a citation manager.

### THREE-WAY ANALYSIS

**(i) What Elicit does that Callosum does NOT / will NOT (per its backlog):**
- Large-scale **semantic search over a hosted 138M-paper external corpus** with AI ranking (Callosum's acquisition is an OA-first cascade — OpenAlex/DOAJ/CORE + entitlement-based browser fetching — not a hosted index with in-app semantic ranking of all literature).
- **AI-generated research reports / synthesis narratives** (Callosum's meta-analysis workbench is explicitly NOT a synthesis/stats engine; it stops at provenance-anchored extraction + deterministic effect-size conversion + export to metafor/JASP/RevMan).
- **Automated AI screening at 5,000–40,000-paper scale** with vendor-validated recall (Callosum's screening is human-verified, protocol-driven, and smaller-scale by design).
- **AI figure/table interpretation**, an agentic multi-step "Research Agent," and **topic Alerts** on new literature.
- **Cloud collaboration with real-time co-editing** of extraction tables.

**(ii) What Callosum does (or plans) that Elicit CANNOT:**
- **Local-first, offline, open-source (AGPL-3.0), inspectable SQLite + local sentence-transformers/sqlite-vec semantic search**, with **consent-gated** (not default-on, not cloud-only) LLM calls behind a privacy gate. Elicit is cloud-only and closed.
- **A true reference manager + citation engine** (CSL + citeproc-js, with LibreOffice/Word/Google Docs live tracked fields and bibliography generation). Elicit has none of this.
- **The auditing METHODS suite** — statcheck-style reporting checks, a Bayesian-reporting auditor, an LMM-reporting-completeness auditor, a citation-equity audit, a where-to-submit PUBLISHERS tool, and a CRediT contribution-statement builder. No AI literature tool offers anything like this.
- **Credit-the-lineage attribution infrastructure** and a verify-everything provenance ethos with **no vendor PDF upload by default**.
- **Ownership / lock-in posture:** data in open formats, self-hostable, and leaveable. Elicit's value evaporates when the subscription lapses, and the data is cloud-bound.
- **Deterministic effect-size conversion → metafor/JASP/RevMan export** with human-verified extraction (Elicit's extraction is AI-first, cloud, and — per Lau et al. — less reproducible for formal SR).

**(iii) Is "Elicit is the closest thing to Callosum" correct?**
**Partly — and the framing should be revised.** Elicit is the closest on the **AI-extraction/evidence-synthesis** axis, but it is the *opposite* of Callosum on architecture (cloud vs local), licensing (closed vs AGPL), and core function (no citation management). The honest mapping:
- **On "local-first open-source reference manager" → the true nearest neighbor is Zotero** — specifically Zotero 7/8 + Better BibTeX + AI plugins (PapersGPT/Beaver/ZotSeek) that already add local-model semantic search and chat-with-library. Callosum is effectively *"Zotero's openness + Elicit's AI extraction + a novel auditing suite."*
- **On "AI evidence extraction" → Elicit** (with Consensus, SciSpace and Undermind as semantics-based peers, and scite for citation context).
- **On "meta-analysis extraction workbench" → the real competitors are Covidence, Rayyan, DistillerSR and Elicit's SR workflow**, not the general reference managers.
- **Conclusion:** No single product is Callosum's nearest neighbor; it sits in a genuinely unfilled niche at the intersection. The closest *combination* is "Zotero + Elicit + scite." Recommended framing: *"Elicit is the closest AI-extraction analog; Zotero is the closest architecture/citation analog; Callosum uniquely fuses both and adds an auditing METHODS suite no competitor offers."*

### The competitive AI-literature landscape (nearest-neighbor map)

| Tool | Core function | Corpus | Provenance | Citation mgmt? | Local/OSS? |
|---|---|---|---|---|---|
| **Elicit** | AI extraction tables, SR screening, reports | ~138M (Semantic Scholar + PubMed + OpenAlex) + 545K trials | Sentence-level quotes | No | No |
| **Consensus** | Yes/no evidence synthesis, "Consensus Meter" | ~200M via Semantic Scholar | Snapshot + sources | No | No |
| **scite** | Smart Citations (supporting/contrasting/mentioning) | **1.3B+ in-text citation statements from 34.3M full-text articles; 187M+ articles indexed** | Citation-sentence level | No (has a Zotero plugin) | No |
| **SciSpace** | Explain papers, "table mode," AI agent | 280M+ | Inline | Partial | No |
| **Undermind** | Agentic recursive deep search | Semantic Scholar | In-line citations | No | No |
| **Research Rabbit** | Citation-graph discovery, ongoing suggestions | Semantic Scholar + Crossref + OpenAlex + PubMed | Graph | No (Zotero sync) | No (free) |
| **Connected Papers** | Single-paper similarity graph | Semantic Scholar | Graph | No | No |
| **Semantic Scholar** | Free discovery, TLDRs, citation graph | 200M+ | TLDR + graph | No | No (free API) |
| **Zotero + AI plugins** | Reference mgmt + plugin AI (PapersGPT/Beaver/ZotSeek) | Local library (+240M via Beaver) | Page-linked | **Yes** | **Yes (OSS, local models)** |
| **ReadCube / Papers** | Reference mgmt + AI assistant + SLR | Dimensions 150M+ | Source-linked | Yes (SmartCite) | No |
| **Callosum (planned)** | Local-first ref mgr + consent-gated AI + auditing + MA extraction | OA cascade (OpenAlex/DOAJ/CORE) + entitlement fetch | Page/passage-anchored, verify-everything | **Yes (CSL/citeproc-js)** | **Yes (AGPL, local)** |

### HOLES that Elicit and peers reveal in Callosum's backlog
Capabilities that users of Elicit / scite / Research Rabbit / Consensus expect, and that Callosum's stated backlog does not yet clearly address — candidates to add or consciously decline:
1. **Citation-context / "smart citations" (scite-style):** does a citing paper *support, contrast, or merely mention* a claim? Extremely on-brand for a verify-everything tool, and buildable locally from OpenAlex/OpenCitations data. Currently absent.
2. **Citation-graph discovery (Research Rabbit / Connected Papers-style):** forward/backward citation exploration, co-citation, bibliographic coupling, related-papers visualization. Callosum's acquisition is OA-fetch-oriented, not graph-exploration-oriented — a discovery gap.
3. **Literature alerts / monitoring:** new-paper alerts on saved topics/authors (Elicit Alerts; ReadCube monitoring; Citavi RSS). Not in the backlog.
4. **Provenance-anchored cross-study contradiction/consensus surfacing:** Elicit/Consensus surface agreement/disagreement across studies. Callosum tracks contradictions at the note level but not automatically across studies; a *grounded* contradiction surfacer (with passage links) would fit its ethos without becoming a synthesis engine.
5. **General-purpose literature-matrix extraction (not just meta-analysis):** Elicit's column-extraction is a daily-driver feature. Callosum's extraction workbench is MA-scoped; a lighter "literature matrix" mode would broaden everyday appeal.
6. **Figure/table data extraction:** Elicit Scale extracts from figures — directly relevant to effect-size capture, since data often live in forest plots/tables/figures.
7. **Reading-progress / triage UX and study-comparison views** that screening tools provide.
8. **Journal TOC / RSS recommendation feeds** (ReadCube/Citavi have these).
9. **Mobile/tablet reading:** every cloud competitor offers it; a local-first desktop app risks under-serving on-the-go reading.
10. **Reproducible, exportable search-strategy logs** (PRISMA search documentation): Elicit's SR workflow and scite's reproducible boolean search set a bar the Callosum acquisition layer should meet to be SR-credible — and ironically a place where Callosum's local, inspectable design could *beat* Elicit (whose search reproducibility was criticized by Lau et al.).

---

## Recommendations (staged, with decision thresholds)

**Stage 1 — Lock in the differentiators incumbents do worst (now):**
- Make **local-first + open + full-export** the headline. It is the one thing *no* competitor except Zotero offers — and Zotero lacks AI + auditing. Treat export/portability and inspectable SQLite as first-class, documented features (directly counter Mendeley's encrypted lock-in).
- Ship the **CSL/citeproc-js citation engine** with LibreOffice/Word/Google Docs live tracked fields early. This is table-stakes that Elicit/Consensus/scite entirely lack and is the durable moat against "AI literature tools."
- Ship **provenance-anchored AI** (every answer → exact page/passage). Match the best incumbent behavior (ReadCube/EndNote) and *exceed* Elicit, whose citations don't always reach the exact sentence.

**Stage 2 — Close the highest-value holes (next 2–3 quarters):**
- Add **citation-graph discovery** (OpenAlex/OpenCitations-powered, local) and **scite-style citation-context** classification — the two most-expected discovery features Callosum lacks. *Threshold to reprioritize:* if user interviews show >50% rank discovery above writing-integration, move graph discovery ahead of Stage-1 polish.
- Add **literature alerts** on saved queries/authors via OpenAlex.
- Add a **general literature-matrix extraction mode** (lighter than the MA workbench) to capture Elicit's daily-driver use case while preserving human verification.

**Stage 3 — Reinforce the auditing moat (differentiate, don't chase):**
- Invest in the **METHODS suite** (statcheck/Bayesian/LMM auditors, citation-equity, PUBLISHERS, CRediT) rather than trying to out-scale Elicit's 40K-paper screening — this is genuinely unique. *Threshold:* if methods-audit features measurably drive adoption/retention, double down; if not, reallocate to discovery.
- Add **figure/table extraction** specifically to feed effect-size capture in the MA workbench.

**What would change these recommendations:**
- If a major incumbent (Zotero especially) ships native local-model AI + provenance, Callosum's AI differentiation shrinks → shift emphasis to the auditing suite and MA workbench.
- If users overwhelmingly want cloud collaboration, consider an *optional* end-to-end-encrypted sync tier without compromising the local-first default.
- If Elicit/Consensus add citation insertion + CSL, the writing-integration moat weakens → accelerate the Stage-1 citation engine.

## Caveats
- **Pricing is volatile and partly conflicting.** Elicit's own pricing page returned different numbers across captures (Plus ~$7 vs widely-reported $12; Pro $29 vs $49; Scale $49 vs $169) — treat all Elicit tier prices as approximate and re-verify at decision time. Paperpile restructured tiers in March 2026 and did not post per-seat monthly prices for Regular/Expert on the captured page (historical entry pricing ~$2.99–$9.99/mo). ReadCube (~$7/$14), Citavi (~$197), and EndNote (~$175/$275) prices are approximate.
- Many "best reference manager 2026" pages are SEO/affiliate content (Paperguide, PapersFlow, Atlas, etc.); their claims about *competitors* were cross-checked against official documentation where possible and should be read cautiously.
- Star ratings in the matrix are this analyst's qualitative synthesis, not vendor benchmarks.
- Vendor accuracy figures (Elicit's 95–99% Cochrane numbers; "up to 80% time saved") are self-reported; the peer-reviewed Lau et al. (2025) evaluation disputes search reproducibility (35.6% sensitivity/precision in their test), and independent results vary (Helms Andersen 2025: 92% precision/recall/F1).
- The AI-feature landscape changes monthly (scite's MCP launched Feb 2026; Elicit swapped to Claude Opus 4.5 within days of its release) — any AI-specific claim here may be stale within a quarter.
- Elicit's strongest privacy guarantees (no training, zero data retention, single-tenancy) are **Enterprise-tier**; its API Terms permit training on inputs, so do not overstate a blanket "Elicit never trains on your data."
- Zotero's client is AGPL-licensed; "open-source nonprofit governance" is accurate, but exact licensing can vary per component.