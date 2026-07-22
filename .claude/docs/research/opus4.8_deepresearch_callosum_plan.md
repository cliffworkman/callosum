# Building a Local-First, AI-Assisted Reference Manager: A Build Plan and Technical Survey

## TL;DR
- **Build it as a local FastAPI/Python backend + browser frontend (pdf.js for rendering), with SQLite for metadata and a local vector store; this is the lowest-friction "local-first" path for your skill set and keeps virtually everything free.** Use PyMuPDF + GROBID for PDF text/structure with page + bounding-box coordinates, local sentence-transformers/BGE embeddings for all semantic work, and reserve the Gemini free tier strictly for the one task that genuinely needs an LLM: citation-grounded summarization.
- **The hard, novel part — hover-to-source attribution — is solved by a post-generation verify-and-match pipeline, not by trusting the LLM.** Have the LLM summarize with sentence-level citations, then independently re-match each summary sentence to a source chunk via embedding similarity + verbatim quote extraction, and store the chunk's PDF page and bounding box so the hover modal can highlight the exact span via pdf.js.
- **Your stretch features are feasible and mostly free via OpenAlex (citation graph, open-access flags) and Semantic Scholar (citation intents, recommendations), but note two recent constraints: OpenAlex now requires a free API key (since Feb 13, 2026, and added usage-based pricing Feb 24, 2026) and Gemini free-tier daily quotas were cut 50–80% on Dec 7, 2025.** True "smart citation" support/contrast classification (Scite-grade) is not freely available at scale; approximate it locally with stance detection over citation contexts.

## Key Findings

1. **Architecture.** Existing managers cluster around two models: Zotero runs on a rebranded Mozilla/Firefox (Gecko) runtime with JavaScript app logic and a forked pdf.js reader; JabRef is Java/JavaFX. For a solo PhD-developer who knows Python/FastAPI and PHP/JS, the cleanest local-first stack is **FastAPI serving a browser SPA on localhost**, SQLite for the library DB, the filesystem for PDFs, and pdf.js in the browser. Tauri is a strong optional desktop-shell upgrade later; Electron is heavier and less necessary.
2. **Import.** Zotero is trivially importable (open `zotero.sqlite` read-only, join `items`/`itemData`/`itemAttachments`, resolve PDFs in the `storage/` folder). Mendeley is hostile: Mendeley Reference Manager has no real local DB, and Mendeley Desktop encrypts its SQLite with the proprietary SEE extension. The reliable path is interchange formats (BibTeX/RIS/CSL-JSON) plus Zotero's own "Mendeley online import" as a bridge.
3. **Citation-grounded summarization.** This is the heart of the tool and the research literature is mature: fine-grained, sentence-level attribution (ReClaim, SAFE) and **post-generation citation matching** (TrustRAG) are the key patterns. Combine with PyMuPDF/pdfplumber coordinate extraction and pdf.js text-layer highlighting for the hover modal.
4. **Guided clustering.** Your "user specifies the axes" requirement maps cleanly onto **zero-shot classification / embedding-similarity-to-axis-descriptions** (free, local) and **Guided/seeded BERTopic** for the cheap abstract-based first pass. No LLM required for the core; Gemini only for optional label cleanup.
5. **Stretch features.** OpenAlex (`referenced_works`, `related_works`, `cites:` filter) gives you co-citation/bibliographic-coupling discovery for free. Open-science scoring is partially achievable via OpenAlex/Unpaywall OA fields; preregistration/open-data/open-code detection requires heuristic PDF text mining. Claim-checking against consensus can mimic Consensus's "extract verbatim quotes + classify yes/no/possibly" pipeline locally.

## Details

### Thread 1 — Architecture for a local-first reference manager

**What existing tools actually use.**
- **Zotero (current, v7):** Built on the **Mozilla/Gecko platform**, not Electron. Official docs: *"Zotero 7 includes a major internal upgrade of the Mozilla platform on which Zotero is based, incorporating changes from Firefox 60 through Firefox 115."* Zotero 6 was based on Firefox 60.9 ESR; Zotero 7 on Firefox 115 ESR. The build process literally downloads Firefox ESR and rebrands it (the build script is still named `fetch_xulrunner`). App logic is **JavaScript** with XPCOM bindings; localization moved to Mozilla Fluent (`.ftl`) in v7. The built-in PDF reader is a **fork of Mozilla's pdf.js** (`github.com/zotero/pdf.js` and `zotero/reader`). This is significant: even the gold-standard reference manager renders PDFs with pdf.js — the same library you can use directly in a browser frontend for free.
- **JabRef:** Java/JavaFX desktop app, BibTeX-native.
- **Zettlr / Obsidian / Logseq:** Markdown-note apps; Obsidian/Logseq are Electron; academic PDF workflows are bolted on via community plugins (e.g., Zotero integration plugins) rather than native.
- **Paperpile / Papers:** commercial/cloud; not relevant to a free local build but confirm the market gap for a local-first AI tool.

**Recommended stack (lowest friction for you).** A **Python FastAPI backend on localhost + a browser SPA frontend** is the best fit:
- You already know FastAPI/Python, and *every* heavy library you need (PyMuPDF, GROBID client, sentence-transformers, BERTopic, pybtex) is Python-native. This avoids cross-language bridges.
- SQLite as the library database — zero-config, single-file, the same choice Zotero and Mendeley made. Use it for metadata; add a vector index (FAISS, sqlite-vec, or Chroma) for embeddings.
- PDFs live on the filesystem (mirror Zotero's `storage/`-style layout); store relative paths in SQLite.
- The browser frontend uses **pdf.js** (or the React wrapper `react-pdf` by wojtekmaj) for rendering, text-layer selection, and overlay highlighting.
- **PHP+SQLite/MySQL on localhost** is viable for the CRUD/UI layer if you strongly prefer PHP, but you would still need a Python sidecar for ML/PDF work, creating a two-runtime system. Recommendation: standardize on Python to avoid this split. Use PHP only if you want to reuse existing PHP UI components, and even then call the Python service over HTTP.

**Tradeoffs.**
- *FastAPI + browser (recommended):* single language for all the hard parts; runs identically on Windows-native Python or under WSL2 Ubuntu; browser gives you pdf.js for free. Downside: it's a localhost web app, not a packaged desktop binary.
- *Tauri shell (optional later):* Tauri uses the OS-native WebView (WebView2 on Windows) with a Rust core; installers are typically <10 MB and idle RAM ~30–50 MB vs Electron's ~150–300 MB. It can spawn and manage your Python backend as a subprocess and gives you a real desktop app with a tighter "deny-by-default" security model. Cost: a Rust learning curve. Good as a v2 packaging step, not a v1 requirement.
- *Electron:* most familiar to JS devs and consistent rendering (bundles Chromium), but large binaries and heavy memory; unnecessary given pdf.js works in any browser/WebView.

**WSL2 note.** Either approach runs fine. GROBID is distributed as a Docker image and runs most smoothly under WSL2/Linux. If you run GPU-accelerated embeddings, native Windows Python with CUDA is simplest; WSL2 GPU passthrough also works but adds setup.

### Thread 2 — Importing from Zotero and Mendeley

**Zotero (easy, fully local).** All data is in `zotero.sqlite` in the data directory (default `C:\Users\<you>\Zotero` on Windows), with attachments under `storage/` in 8-character subfolders. The schema (`resource/schema/userdata.sql`) uses:
- `items` (one row per item, `itemID`),
- `itemData` — an entity-attribute-value table `(itemID, fieldID, valueID)` joined to `itemDataValues` for actual values (title, abstract, etc.),
- `itemAttachments` (`itemID, parentItemID, linkMode, contentType, path, …`) linking PDFs to their parent item,
- plus `itemCreators`/`creators`, `collections`/`collectionItems`, `itemTags`/`tags`, `itemNotes`, `itemAnnotations`, and full-text tables.

**Critical caveat (from Zotero's own docs):** access the DB **read-only** — *"Modifying the database while Zotero is running can easily result in a corrupted database"* — and the schema *"can change between Zotero releases."* Best practice: copy `zotero.sqlite` to a temp file and read the copy. Better BibTeX is the dominant third-party plugin for stable citation keys (note: Zotero 8 adds a native citation-key field that supersedes BBT's).

**Mendeley (hard — deliberately locked down).** Two products exist:
- *Mendeley Desktop* (legacy): local SQLite at `…/Mendeley Ltd./Mendeley Desktop/<email>@www.mendeley.com.sqlite`, with a `Files` table holding `localUrl` paths to PDFs. **But since Mendeley Desktop 1.19, the DB is encrypted** with the proprietary, closed-source SQLite Encryption Extension (SEE) — `sqlite3` reports *"file is not a database."* Zotero's docs confirm: *"Mendeley 1.19 and later have begun encrypting the local database, making it unreadable by Zotero and other standard database tools."* Decryption requires a gdb-based `sqlite3_rekey_v2` hack on an old Mendeley binary (fragile, Linux-oriented).
- *Mendeley Reference Manager* (current): *"essentially a wrapper around the website and doesn't contain a real local database at all."*

**Reliable Mendeley import path:** Use **Zotero's "Mendeley Reference Manager (online import)"** as a bridge (it logs into Mendeley and pulls everything including PDFs into a clean Zotero library), then import from Zotero's SQLite. This is more robust than wrestling with SEE decryption. The Mendeley Web API exists but only exposes data already uploaded to Elsevier's servers and is under Elsevier's control.

**Interchange formats & parsers (the universal fallback).**
- **BibTeX:** Python — `bibtexparser` or `pybtex`; JS — Better BibTeX's `bibtex-parser`, `@orcid/bibtex-parse-js`, or Citation.js.
- **RIS / CSL-JSON / DOI / Wikidata:** **Citation.js** is the standout — it converts BibTeX/RIS/DOI/Wikidata → CSL-JSON and back, runs in browser and Node, MIT-licensed. CSL-JSON is the best internal canonical format (it's what citeproc-js and Zotero use under the hood).
- **Pitfall:** BibTeX↔CSL field/type name mismatches (e.g., `inproceedings`→`paper-conference`, `booktitle`→`container-title`) require mapping; Citation.js handles this, whereas raw `bibtexparser`/`pybtex` only parse (one developer documented "turning BibTeX into bibliographies with Python is a nightmare" precisely because of this gap).
- **PDFs with metadata intact:** RIS/BibTeX carry metadata but **not** attachments. To preserve PDFs + metadata together, the only fully reliable routes are (a) reading Zotero's SQLite + `storage/` directly, or (b) the Zotero online-import bridge. Plan your importer around CSL-JSON as the canonical record, with a separate attachment-linking step.

### Thread 3 — Citation-grounded / attributed summarization (the heart of the tool)

**The core principle: don't trust the LLM's own citations — verify them.** The research literature distinguishes two strategies (Survey on Knowledge-Oriented RAG, arXiv:2503.10677): *simultaneous* citation generation (model emits citations as it writes, e.g., WebGPT, GopherCite) vs *post-generation* citation retrieval (match claims to sources after writing). For a verifiable hover-modal feature, the **post-generation approach is the right architecture**, exemplified by **TrustRAG**, which *"matches the generated answers with retrieved reference materials afterward… ensures higher citation accuracy"* (see its `match_citation.py`).

**Recommended pipeline:**
1. **Chunk** each PDF into passages (paragraph- or sentence-window level). Keep, for every chunk, its source paper ID, page number, and bounding box (see below).
2. **Embed** chunks locally (sentence-transformers/BGE) into your vector store.
3. **Retrieve** the top-k chunks for the selected paper subset and feed them to Gemini with a prompt instructing sentence-level citations (the ReClaim "interleave reference then claim" pattern, arXiv:2407.01796, reports ~90% citation accuracy; SAFE, arXiv:2505.12621, does in-generation sentence attribution at ~95% first-step accuracy).
4. **Verify & re-map (the crucial step):** for each generated summary sentence, independently compute embedding similarity against candidate chunks and extract the **verbatim supporting quote** (longest-common-span / fuzzy string match). Flag any sentence whose best support falls below a similarity threshold as "unverified" — this is your hallucination guardrail. The "Correctness is not Faithfulness in RAG Attributions" work (arXiv:2412.18004) underscores that a cited document must actually *support* the statement, not merely be topically related.
5. **Store** the mapping {summary sentence → source paper, page, bbox, verbatim quote}. The hover modal reads this to display the excerpt and deep-link into the PDF.

**PDF extraction with page + bounding-box coordinates.**
- **PyMuPDF (fitz):** fastest; `page.get_text("dict"/"words"/"blocks")` returns text with bbox coordinates in points (1/72"), origin top-left. `page.search_for(text)` returns bounding boxes for a string (handles multi-line by returning multiple rects) — ideal for locating a verbatim quote to highlight. **License caveat: PyMuPDF is AGPL v3**, which has implications if you ever distribute a closed-source product; for personal/open-source use it's fine.
- **pdfplumber** (MIT, built on pdfminer.six): `.chars`/`.words`/`.search()` with bbox coords; slower than PyMuPDF but permissively licensed and great for precise char-level work.
- **GROBID:** ML tool that converts scholarly PDFs to structured TEI-XML — header metadata, sections, paragraphs, and **parsed references** (~0.87 F1 on a PubMed Central set, ~0.90 on bioRxiv using the deep-learning citation model). It exposes coordinates so you can map structures back to PDF regions (the GeoGalactica pipeline, arXiv:2401.00434, pairs GROBID bounding boxes with PyMuPDF). Use GROBID for *structure/section/reference parsing* and PyMuPDF for *fast text + quote-locating*. GROBID processes a page in ~2–5 seconds.
- **In-browser rendering/highlighting:** **pdf.js** renders the page to canvas plus a selectable text layer; convert stored PDF-space bboxes to viewport coordinates with `viewport.convertToViewportRectangle()` and draw absolutely-positioned overlay `<div>`s for highlights. Known gotcha: pdf.js text-layer fonts can be slightly misaligned vs the canvas, so anchor highlight overlays to the canvas and expect minor tuning; some projects draw highlights on an SVG/overlay layer to avoid text-layer drift.

**Real systems to learn from (directly relevant):**
- **NotebookLM** is the closest analog to your goal: a closed RAG system over user-uploaded sources, Gemini-backed, with **inline numbered citations that jump to the exact source passage on click**. Independent academic testing — Hagar et al., *"Not Wrong, But Untrue: LLM Overconfidence in Document-Based Queries"* (arXiv:2509.25498, Sep 2025), on a 300-document corpus — found *"the rate of hallucinations from Gemini and ChatGPT are approximately three times that of NotebookLM—40%… versus 13%."* This is essentially the UX (and the reliability advantage of source-grounding) you're rebuilding locally.
- **Elicit, SciSpace, Consensus, Semantic Scholar TLDR, Perplexity** all do retrieve-then-cite with verbatim quote extraction. Consensus explicitly powers its output with *"extracted word-for-word quotes from papers"* and applies relevance/confidence thresholding — a pattern worth copying for your "unverified" flag.
- **Open-source RAG-with-citations:** the ReClaim repo (`github.com/pdxthree/ReClaim`), TrustRAG's `match_citation.py`, and LlamaIndex/LangChain citation modules are concrete starting points.

### Thread 4 — Semantic hierarchical clustering along user-specified axes

**Local, free embedding models (no API cost).** Run any of these via `sentence-transformers` on your machine:
- `all-MiniLM-L6-v2` (384-dim, very fast, good default for a first pass),
- `all-mpnet-base-v2` (768-dim, higher quality),
- `BAAI/bge-m3` or `bge-base-en-v1.5` (state-of-the-art open quality, multilingual),
- `nomic-embed-text` (8,192-token context, good for long abstracts; runnable via Ollama offline).

For most RAG/clustering on English abstracts, open models now match OpenAI's `text-embedding-3-small` at zero cost. Gemini also offers a free embeddings tier (100 RPM / 1,000 RPD) if you want a hosted option, but local is unlimited and private.

**The two clustering modes you want:**
1. **Cheap automatic first pass on import (abstracts):** **BERTopic** is purpose-built — sentence-transformers → UMAP dimensionality reduction → HDBSCAN density clustering → c-TF-IDF topic labels. HDBSCAN is hierarchical and handles noise; BERTopic also supports **hierarchical topic modeling** to produce the nested tree you want. This runs fully locally on abstracts.
2. **User-specified axes (the distinctive requirement):** This is *guided/supervised* organization, and there are three free, local techniques, best combined:
   - **Embedding similarity to axis descriptions:** Embed each user axis as a short text description (e.g., "facial anomalies"; "signal detection theory"), embed each document, and score by cosine similarity. Sort/threshold documents under each axis. This is the simplest, fully-local approach and directly supports *user-definable text axes* — the CLIP-style "treat the label embeddings as the classifier" trick applied to text.
   - **Zero-shot classification (NLI-based):** Models like `facebook/bart-large-mnli` classify a document against arbitrary user-provided candidate labels with no training, by framing it as natural-language inference (does the text entail "this is about <axis>"?). Free, local, and exactly matches "user provides the categories." Research notes that large LLMs in zero-shot mode are competitive with fine-tuned BERT here, so quality is good even without API calls.
   - **Guided/seeded BERTopic:** pass `seed_topic_list=[["facial","anomaly",…],["signal","detection","theory",…]]` to bias topic creation toward the user's axes while still discovering others.
   - **For the nested hierarchy:** apply the technique recursively — first-order axis assignment, then within each first-order cluster run the second-order axis scoring/zero-shot pass. Store the tree in SQLite (adjacency list: `node_id, parent_id, axis_label, doc_id`).
   - **Where Gemini helps (optional):** label disambiguation, generating a crisp axis description from a few example papers, or resolving borderline documents — bounded calls, not per-document, to respect free-tier quotas.

### Thread 5 — Stretch features

**(a) Missing-literature suggestion (citation graph).**
- **OpenAlex is the free workhorse.** Each work object exposes `referenced_works` (outgoing citations) and `related_works` (*"computed algorithmically… recent papers with the most concepts in common"*); the `cites:W…` filter returns incoming citations. CC0 data, full REST API. **Important recency note:** per the OpenAlex changelog, *"February 13, 2026 — API keys required. All API requests now require an API key. You can get your free key at openalex.org/settings/api."* Without a key you get 100 credits/day (testing only); the free key gives 100,000 credits/day. OpenAlex also introduced usage-based pricing on Feb 24, 2026, reframing the free key as roughly "$1 of free usage per day." Use the `pyalex` Python client; the bulk data dump remains free for high-volume work.
- **Algorithms to implement (these are exactly what Connected Papers / ResearchRabbit use):**
  - **Bibliographic coupling:** two papers are similar if they *share references* (compute overlap of `referenced_works` sets). Works for brand-new papers with few citations.
  - **Co-citation:** two papers are similar if they're *cited together* by later papers.
  - Connected Papers combines both into a similarity metric and lays out a force-directed graph (its data comes from Semantic Scholar); ResearchRabbit adds co-authorship and embedding similarity, recommending starting from 5–20 seed papers. **Inciteful** is notable for transparency (you can edit its SQL ranking rules) — a good model for an auditable local implementation.
- **Semantic Scholar** complements OpenAlex: free API, **most endpoints need no key** (per official docs, *"rate-limited to 1000 requests per second shared among all unauthenticated users"*), and a free API key gives ~1 req/sec dedicated (per the allenai/s2-folks release notes, 1/sec for `/paper/batch`, `/paper/search`, `/recommendations` and 10/sec for other calls). It exposes `citations`/`references` with `contexts`, `intents` (classified as **Background / Method / Result** via the SciCite model), and `isInfluential` flags, a `tldr` field (BART/CATTS-generated summaries for ~60M papers), and a dedicated **Recommendations API** (`/recommendations/v1/papers/forpaper/{id}` plus a positive/negative-seed POST endpoint). Rate-limit figures conflict across sources ("1,000/sec shared," "100 per 5 min," "5,000 per 5 min") — verify the live number at build time.

**(b) Open-science scoring.**
- **Open access (free, reliable):** OpenAlex/Unpaywall `is_oa`, `oa_status` (closed/green/gold/hybrid/bronze/diamond), and `best_oa_location`. Note OpenAlex has documented quirks (4M+ `is_oa:true` works marked `oa_status:closed`); use `any_repository_has_fulltext` for "shadowed green." Diamond/gold = strongest OA signal. Unpaywall's open methodology is the industry standard for OA classification.
- **Preregistration / open data / open code (no clean free API):** There is no single authoritative API exposing these badges across the literature. Practical heuristics:
  - **PDF/text mining:** regex/NLP for DOI/URL patterns to OSF (`osf.io`), AsPredicted, ClinicalTrials.gov, GitHub/GitLab/Zenodo links, and phrases like "pre-registered," "data available at," "code available at," "supplementary data." GROBID's `datastet` and `software-mention` modules specifically detect dataset and software mentions in scholarly PDFs — directly reusable.
  - **OSF API** (free) can confirm a linked registration/dataset exists.
  - Assign weighted scores (e.g., +preregistered, +open data, +open code, +OA) and store per-paper. Treat detection as best-effort/probabilistic and surface the evidence snippet so the user can verify.

**(c) Assertion/claim checking against the literature.**
- **Scite** is the reference implementation: a deep-learning "smart citation" classifier labels each citation statement **supporting / contrasting / mentioning** with the surrounding context and section. Per the original paper (Nicholson et al., *Quantitative Science Studies* 2(3):882, MIT Press, 2021), it was built from *"over 25 million full-text scientific articles and… more than 880 million classified citation statements"* with *"the average distribution of citation statements [is] 92.6% mentioning, 6.5% supporting, and 0.8% contrasting"* (Scite's own materials now cite 1.4B+ classified statements from 38M+ papers). It has an API but is **paid/institutional** — not free at scale.
- **Consensus** aggregates an answer to a yes/no question over the top ~20 retrieved papers, using an LLM to classify each as yes/no/possibly from *verbatim extracted quotes*, with relevance/confidence thresholds and a self-reported ~10% misclassification rate. It deliberately doesn't weight by study quality (a documented limitation) and draws its corpus partly from OpenAlex.
- **Free/local approximation you can build:** (1) retrieve papers/citation contexts relevant to the selected assertion (via your embeddings + OpenAlex/Semantic Scholar); (2) run **stance detection** — either zero-shot NLI (entailment = support, contradiction = contrast, neutral = mention) locally, or a bounded Gemini call — over each citation context or abstract; (3) aggregate into a Consensus-style meter, always showing the verbatim supporting/contrasting quotes so the user verifies. Semantic Scholar's free `intents` (background/method/result) is a useful but coarse signal and is *not* the same as support/contrast — don't conflate them.

### Cross-cutting: where the Gemini free tier fits, and its limits
Use Gemini **only** for (i) the summarization generation step, (ii) optional axis-label cleanup, and (iii) optional borderline stance/claim classification. Everything else (embeddings, clustering, PDF extraction, citation-graph queries, verbatim quote matching) is free and local/unlimited.
- **Free-tier limits (volatile — re-verify at build time):** roughly Gemini 2.5 Flash ~10 RPM / 250 RPD; Flash-Lite ~15 RPM / 1,000 RPD; 2.5 Pro ~5 RPM / 100 RPD; all share 250,000 TPM and a 1M-token context window. **Google cut free-tier daily quotas 50–80% on Dec 7, 2025** — reporting at the time noted Gemini 2.5 Flash dropping from ~250 to as few as 20–50 requests/day — and Pro models moved behind billing in 2026. Design around Flash/Flash-Lite, batch your summarization jobs, cache results, and add exponential backoff for 429s. The 1M-token context window is a major asset: you can feed many full chunks at once. Free-tier inputs may be used to improve Google's models and the free tier is unavailable for EU/UK production — relevant if data sensitivity matters.

## Recommendations

**Stage 1 — Skeleton (first sprint).** FastAPI + SQLite + a browser frontend with pdf.js. Implement the Zotero importer first (read-only copy of `zotero.sqlite`; join `items`/`itemData`/`itemAttachments`; link PDFs from `storage/`). Add a CSL-JSON canonical schema and a BibTeX/RIS importer via Citation.js or `bibtexparser` for everything else. **Benchmark to proceed:** can round-trip a real Zotero library (metadata + PDFs) into your app.

**Stage 2 — PDF pipeline + embeddings.** Extract text with PyMuPDF (store page + bbox per chunk), optionally run GROBID (Docker, under WSL2) for section/reference structure. Embed chunks and abstracts locally with `bge-base-en-v1.5` (or MiniLM for speed). Stand up a vector store (sqlite-vec or Chroma). **Benchmark:** given a verbatim string, you can return its PDF page + bbox and highlight it in pdf.js.

**Stage 3 — Guided clustering.** Implement axis-as-text-description scoring (cosine similarity) + zero-shot NLI classification for user-defined axes; add Guided BERTopic for the automatic abstract first pass; store the nested tree in SQLite. **Benchmark:** user types two axes and gets a sensible two-level tree without any API call.

**Stage 4 — Citation-grounded summarization (the centerpiece).** Wire Gemini Flash for summary generation with sentence-level citation prompts; then build the **independent post-generation verifier** (embedding match + verbatim quote extraction + similarity threshold + "unverified" flag). Connect the hover modal to the stored {sentence→paper,page,bbox,quote} map. **Benchmark:** every summary sentence either shows a verifiable source excerpt on hover or is visibly flagged unverified.

**Stage 5 — Stretch features.** Add OpenAlex discovery (get the free API key now; implement bibliographic coupling + co-citation), OA/open-science scoring (OpenAlex OA fields + GROBID datastet/software-mention + regex heuristics), and the local stance-detection consensus meter. **Benchmark:** seeded with your library, the tool suggests missing papers and flags an assertion's support/contrast balance with verbatim quotes.

**Thresholds that change the plan.**
- If summarization volume exceeds the free daily cap (~250 papers/day on Flash, fewer after the Dec 2025 cuts) or you need EU-compliant/private inference, move to Gemini Tier 1 (pay-per-use, instant, removes data-sharing) or run a **local LLM via Ollama** (e.g., a 7–8B model) for fully-free, unlimited, private generation — at some quality cost.
- If you ever want to *distribute* the app, replace AGPL PyMuPDF with pdfplumber/pdfminer.six (MIT/BSD) to avoid copyleft obligations.
- If OpenAlex's free daily allowance becomes limiting, switch to the free fortnightly data dump.

## Caveats
- **Volatile external limits.** Gemini free-tier quotas were cut 50–80% on Dec 7, 2025 and Pro moved behind billing in 2026; OpenAlex began requiring a (free) API key on Feb 13, 2026 and added usage-based pricing Feb 24, 2026; Semantic Scholar rate-limit figures conflict across sources. Re-verify all three at build time. Do not build a production dependency on free-tier stability.
- **Mendeley import is genuinely hard.** The SEE-encrypted DB hack is fragile and Linux-oriented; prefer the Zotero online-import bridge. Some metadata (folders, annotations, date-added) may not survive any export-format route.
- **Attribution is probabilistic, not proof.** Even with post-generation verification, "supported" means "high semantic + lexical overlap with a source span," not logical entailment. Always show the verbatim quote and let the user be the final judge; flag low-confidence matches.
- **Zotero schema can change between releases** and must be read-only; pin to a schema version and copy the DB before reading.
- **Open-science signal detection is best-effort.** Preregistration/open-data/open-code have no authoritative free API; heuristic PDF mining will have false positives/negatives — surface evidence, don't assert.
- **"Smart citation" support/contrast at Scite's quality is not free.** Your local stance-detection approximation will be noisier; Semantic Scholar's free `intents` are background/method/result, not support/contrast.
- **PyMuPDF AGPL licensing** affects redistribution only; fine for personal/local use.
