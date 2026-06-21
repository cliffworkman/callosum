# Competitive Analysis: Zotero's AI Plugin Ecosystem vs. Callosum — Feature-Gap Report

## TL;DR
- Zotero's third-party plugins now cover the full AI surface — single/multi-PDF chat, library RAG with page-level citations, agentic search, MCP bridges, translation, AI reference extraction — but ONLY through ~15 fragmented, separately-installed, sometimes-paid, security-unreviewed add-ons; Callosum already matches the privacy-first RAG core and beats the ecosystem on curation, provenance, and trust.
- Callosum's most surprising **table-stakes gaps** are not AI features at all but assumed basics: a **built-in PDF reader/annotation layer**, **Word/Google Docs/LibreOffice citation integration** (planned, not shipped), **browser web-capture/connector**, **duplicate detection**, **BibTeX/LaTeX export**, **citation counts**, and **single-PDF chat + summarization** — all present in 5–7 of the seven surveyed managers.
- Callosum should expose its own **MCP server** (read-first, write-gated) — this is the single highest-leverage architectural move, turning the agent-bridge layer from a threat into a moat while keeping bibliographic state, provenance, and write-safety under Callosum's control.

## Key Findings
1. **Zotero ships zero native AI** (confirmed June 2026 on zotero.org); every AI capability is a plugin. The plugin master list was removed from zotero.org; the support page now reads verbatim: "We don't currently provide a list of available plugins, but most plugins are announced and discussed in the Zotero Forums. An official plugin directory is planned." It also warns: "Be aware that plugins have full access to your Zotero and your computer. You should only install plugins from developers you trust."
2. **AI capabilities that are well-covered** across the Zotero plugin ecosystem: single-PDF chat, paper summarization, multi-provider model support (incl. local Ollama/LM Studio), translation, and MCP bridging. **Partially covered:** library-wide RAG with grounding, figure/table understanding, agentic search, AI metadata/reference extraction. **Rarely covered:** citation-context analysis (only Scite, non-LLM), provenance-anchored systematic-review extraction, methods/reporting auditing — i.e., exactly Callosum's differentiation zone.
3. **Provenance/grounding is strong in only a few tools** — Beaver (sentence/page-level citations), llm-for-zotero (click-to-source), the open-source "Semantic Search Tool for Zotero" (Evidence/Sources panels). Most chat plugins (zotero-gpt, AIdea, kazgu) show no grounding.
4. **The cross-manager commonality test** (Zotero, Mendeley, Paperpile, ReadCube/Papers, EndNote, RefWorks, Citavi) shows that Callosum's true risk is users assuming **basic reference-manager infrastructure** is present. Native AI PDF chat is now in 3 of 6 commercial managers — Mendeley's **Reading Assistant** ("helps quickly and efficiently find important information by querying individual documents… responses include one or more in-text citations to support the claims made"), ReadCube's **AI Assistant**, and EndNote's **Research Assistant** ("no extra downloads or third-party plugins are required… engage in natural language conversations with the full text of a document"). So even "AI chat" is becoming table-stakes, not a differentiator.

## Details

### Part 1 — Zotero AI plugin capability map

**(A) In-Zotero AI assistants**

| Plugin | What it does | AI capabilities | Models / keys | Library access | Grounding | Privacy | Maturity (mid-2026) | Cost |
|---|---|---|---|---|---|---|---|---|
| **Beaver** (jlegewie/beaver-zotero) | Agentic research assistant + reading assistant in side panel | Agentic library search, cross-doc synthesis, single-PDF Q&A, reading-assistant explanations, figure/table/equation understanding (v0.18 visual PDF), OCR-less text extraction (Pro), note read/write & review (v0.17), metadata fill, web search over 240M+ works | OpenAI, Claude, Gemini, DeepSeek + custom endpoints (OpenRouter); tool-vendor backend (Supabase) required; custom local models "untested" | Reads metadata, PDFs, notes; writes notes/tags/items **with explicit confirmation**; annotations (Pro) | **Strong** — page/sentence-level citations linking to source PDFs | Cloud backend required (file processing not local); plugin AGPL-3.0 but backend closed; local-only is an open issue (#35) | Latest v0.19.0 (May 4 2026); ~150 stars; Zotero 7; active; beta | Free tier (25 credits); Plus from $10/mo (100 credits) |
| **PapersGPT** (papersgpt.com) | PDF chat + AutoPilot batch + integrated MCP server | Single & multi-PDF chat, collection chat ("Chat Multiple PDFs"), summaries, AutoPilot (batch-read 100+ papers → notes), MCP server (BM25 + full-text) | Huge list: GPT-5.x, Gemini 3.x, Claude 4.x, DeepSeek V4, Grok, Qwen, Kimi, GLM, Mistral, Llama, gpt-oss via OpenRouter/SiliconFlow; **one-click local LLMs**; BYOK or tool licence | Reads PDFs/metadata; writes notes (AutoPilot) | Multi-PDF chat over selected collection; weaker explicit citation display than Beaver | Local LLM option (was Mac-only; now Win/Mac/Linux); freemium | Zotero 8/9 since v0.3.7; C++ MCP server; very active | Freemium: 20 free chats; Basic $29 lifetime, Premium $59 |
| **llm-for-zotero** (yilewang) | Research-agent system, deeply Zotero-rooted | Single-paper chat with focused retrieval, summaries (full/methods/results), paragraph explain, agent mode (read+write+undo), note generation to Obsidian/Logseq/Zotero, figure handling via MinerU, cross-model checking | Presets: OpenAI, Gemini, Anthropic, MiniMax, GLM, DeepSeek, Grok, Qwen, Kimi, Copilot; any OpenAI-compatible (Ollama, LM Studio, vLLM); BYOK | Read tools direct; write tools via **confirmation cards + session undo**; tags, metadata, move, merge, attachments | **Strong** — click any generated citation to jump to source passage; cache-aware evidence tracking | MinerU local mode option; local models supported | Zotero 7/8/9; very active; agent mode beta/off-by-default | Free (BYOK) |
| **ARIA / ai-research-assistant** (lifan0127) | Early conversational assistant | Library Q&A by metadata/tags, drag-drop referencing, GPT-4 Vision visual analysis, save chats as notes/annotations | **OpenAI GPT-4 family only**; BYOK (paid OpenAI account) | Reads metadata; weak content access (notes/PDF search limited) | Weak | Cloud (OpenAI) only | **Broken/stale** — not Zotero-8 compatible; broke when OpenAI retired `gpt-4` (issue #184, Oct 2025); last v0.7.4 | Free (BYOK) |
| **AIdea** (Visterainer) | Free side-panel chat, no API key | Chat (library + PDF reader), summaries, selection-context Q&A, translation, multimodal (image), AI memory, note export, custom buttons | **OAuth login** (OpenAI/ChatGPT 5.x, Gemini, Qwen, GitHub Copilot) — no key needed; OpenAI-compatible + Ollama/LM Studio/vLLM | Reads selected items/PDF text; note export | Weak (no source citations) | OAuth token local-only; local models supported; AGPL-3.0; "no data collected" | Zotero 7/8; new (launched ~early 2026); active | Free |
| **Zotero AI Bar** (zotero.fukeke.com) | Sidebar AI tasks | Summaries, translation, PDF Q&A | Claude, DeepSeek, Doubao, Gemini, GLM, Grok, Kimi, Qwen, Wenxin, Yi; BYOK | Reads PDF content | Weak | Cloud (provider) | Zotero 7+; China-oriented | Free (BYOK) |
| **AskYourPDF** | Targeted PDF Q&A with passage display | Single-PDF chat, relevant-passage display | ChatGPT, Claude; needs ChatGPT Plus for full | Reads PDFs | Shows relevant passages | Cloud required (also mobile/Chrome) | Zotero 6+; commercial product | Free tier; paid for full |
| **zotero-gpt** (MuiseDestiny) | Classic scriptable GPT plugin | Single-PDF Q&A (full/selected), abstract Q&A, summarize, library search by selected text, AI annotation (v3.1.4), command tags (scriptable), AI writing into Better Notes | gpt-3.5/gpt-4 + custom endpoints/local; BYOK | Reads PDFs/library; scriptable Zotero API access | Weak | Cloud or local endpoint; AGPL-3.0 (but see security note) | **7.2k stars** (most popular); v3.1.4 (May 1 2026); Zotero 6/7; flagged for shipping obfuscated XPI not matching repo | Free (BYOK) |
| **kazgu/zotero-chatgpt** | Early ChatGPT plugin | Basic chat | OpenAI; BYOK | Limited | None | Cloud | Largely stale; reported broken on Mac V6 | Free |
| **SeerAI** (dralkh/seerai) | Full research framework in Zotero | Chat, RAG (per-context embeddings, chunking, vector store), web search (Firecrawl/Tavily/You.com), Semantic Scholar agent (filters by year/venue/citations), table extraction, OCR, PDF discovery, workspaces w/ Git, cloud (GDrive/Dropbox/etc.), MCP server + local API | Sophisticated tool-calling models needed; BYOK; configurable | Reads library; autocomplete tags/creators/collections; workspace file read/write | Inline citations in tables/chat; RAG retrieval | Local workspace + cloud options; MCP server | Active; feature-rich but heavy; newer/smaller | Free (BYOK) |
| **BibGenie / Zotero Copilot** (BaiRuic) | AI assistant for Zotero | Chat/assistant features | BYOK | Reads library | Weak | Cloud | Rebranded (Copilot→BibGenie); smaller | Free/freemium |
| **Zotero-ChatPDF** (ljeagle) | Predecessor to PapersGPT lineage | PDF chat | OpenAI | Reads PDFs | Weak | Cloud | Largely superseded by PapersGPT | Free |

**(B) AI-enabled utility plugins**

| Plugin | Function | AI details | Models | Maturity | Cost |
|---|---|---|---|---|---|
| **Scite Zotero Plugin** | Citation-context tallies in library | Smart Citations: supporting/contrasting/mentioning counts as sortable columns; right-click → Scite report with classified citation statements (filter by section/type) | Scite's own NLP/deep-learning (no external LLM) | Zotero 7; maintained; "Now part of Research Solutions, Scite has indexed 1.6B+ citations, partners with 30+ publishers, and serves 2M users worldwide"; a Scite MCP launched Feb 2026 (Claude/ChatGPT/Copilot/Cursor) | Free tallies; Scite subscription ($7.99–$20/mo) for reports |
| **Zotero Add Items from Text** (jmiba) | Extract references from pasted unstructured text | AI parses references → JSON; optional AI validation; index validation against Crossref/OpenAlex/lobid/LoC/GBV/Wikidata; field enrichment | **Gemini, OpenAI-compatible, Ollama** | Zotero 7/8; v1.0.10; Zenodo DOI; actively iterated; users report Gemini rate-limit issues | Free (BYOK) |
| **Zotero PDF Translate** (windingwind) | Translate PDF/EPub/web/metadata/annotations/notes | 20+ services incl. LLM-based (OpenAI, Claude, Gemini, custom GPT); in-reader popup + annotation translation | Free (Google/Bing/CNKI), API (DeepL/MS), LLM (BYOK) | **11k stars**; v2.4.4 (May 2026); Zotero 7, supports Z10; very active | Free (services may need keys) |
| **Better Notes** (windingwind) | Note management / knowledge base | AI writing assistant *via* zotero-gpt integration (chat pane in editor); templates aggregate annotations across papers; bidirectional Obsidian/Markdown sync; export Markdown/Docx/PDF/mindmap; backlinks | Relies on zotero-gpt for LLM | **7.8k stars**; v3.0.6 (May 2026); Zotero 7/8; AGPL-3.0; very active | Free |
| **AI Summary for Zotero** (forum) | Auto-summarize items | Summaries to notes | BYOK | Forum-distributed; smaller | Free |
| **AI Chat Referencing Plugin** (forum) | Chat with citation referencing | Chat with source references | BYOK | Forum-distributed; smaller | Free |

**(C) MCP / agent bridges**

| Project | Type | Access | Semantic search | Notes | Stars |
|---|---|---|---|---|---|
| **54yyyu/zotero-mcp** | External Python server (pip/uv) | Read (local + Web API); write via separate tools | Yes (local model, OpenAI, or Gemini embeddings) | Oldest/most popular; PDF annotation extraction, summaries, citation analysis; CLI companion; v0.5.0 (Jun 8 2026); heavy ML stack (Torch/CUDA) caveat | ~1,600 |
| **cookjohn/zotero-mcp** | Zotero plugin (.xpi) w/ integrated MCP server (Streamable HTTP) | **Read + write** (internal JS API) | Optional (OpenAI/Ollama → sqlite-vec) | 20 MCP tools; no Python/Node needed; full write access (notes/tags/metadata/new items); writes can be disabled | ~490 |
| **Xevos117/mcp-zotero** | Node server (npm) | Read + write (Web API) | No | **Citation injection into Word .docx** with native Zotero field codes; add-by-DOI; Unpaywall OA PDF attach | — |
| **MCP for Zotero** (alejandroarnaud) | Hosted cloud service | Read + write (Web API proxy) | No | Zero-install; enter API key, get endpoint; BibTeX/RIS/APA export; encrypted credentials | proprietary |
| **PapersFlow MCP** (papersflow-ai) | Hosted MCP (doxa.papersflow.ai/mcp) | Read (external corpus, not your library) | N/A | 14 tools (8 free public): search 474M+ (OpenAlex + Semantic Scholar), citation verification, citation-graph traversal, deep research; OAuth for premium; works w/ Claude/Codex/Gemini/Cursor | MIT |
| **ChiKen** (yuanjua) | Desktop app (RAG + MCP) | Read (local) | Yes (local) | Privacy-first; all parsing/indexing/inference local; keys in OS keychain; planned PyTauri shift | MIT |
| **kujenga/zotero-mcp** | Python/Docker server | Read | No | Minimal/stable; Docker support | ~138 |
| **ZotPilot** (xunhe730) | Python agent skill + MCP | Read (SQLite), write (Web API) | Yes (Gemini/DashScope/local MiniLM) | Most feature-rich: **chapter-based search** (Methods/Results/Abstract weighting), table/figure search, OpenAlex citation graph, SCImago journal-quality ranking; 32 tools | MIT |

**(D) External Zotero-integrated platforms**
- **ResearchRabbit** — free citation-network discovery (280M+ articles, OpenAlex + Semantic Scholar); seed-paper → similar/earlier/later works, visual maps/timelines, author networks, recommendations, alerts, collaboration. One-way Zotero import (OAuth); two-way sync "coming." No PDF chat. Free.
- **PapersFlow** — bidirectional Zotero sync (8 metadata fields, PDFs, annotations); hybrid BM25 + vector + RRF + Jina Reranker v3 search; multi-agent AI (Research/Analysis/Synthesis/Writing/Critique); summaries; counter-evidence; hosted MCP. From $20/mo (free tier exists).

**(E) DIY / local RAG patterns** — pyzotero + Chroma/FAISS + OpenAI/local (the Emmett McFarlane Medium recipe); Ollama + Open WebUI knowledge base over exported library/collection; RAGflow integration (deulofeu1); Zotero-RAG (windfollowingheart); the open-source desktop "Semantic Search Tool for Zotero" (vector embeddings of PDFs + Zotero metadata, with Evidence/Sources panels and local-model option, explicitly "find where to look, not what to think"). These confirm Callosum's exact architecture (local embeddings + sqlite-vec + grounded sources) is a recognized, demanded pattern but normally requires DIY assembly.

### Part 1 synthesis — what's covered

- **Well-covered (mature, many tools):** single-PDF chat; paper summarization; multi-provider model support including local Ollama/LM Studio; translation; MCP bridging to external chatbots; note generation.
- **Partially covered (few good tools):** library-wide RAG with grounded page/sentence citations (Beaver, llm-for-zotero, ZotPilot, Semantic Search Tool); cross-document synthesis; figure/table/equation understanding (Beaver visual, MinerU, SeerAI, ZotPilot); agentic library search; AI metadata/reference extraction (jmiba); section-specific retrieval (only ZotPilot chapter-aware).
- **Rarely / barely covered:** citation-context classification (Scite only, and non-LLM); provenance-anchored, human-verified systematic-review extraction; statistical/methods reporting audits; deterministic effect-size pipelines; citation-equity / attribution-lineage tooling. **These are Callosum's whitespace.**
- **Cloud/paid vs local:** Grounding and agentic features skew cloud/paid (Beaver backend, PapersGPT licence, PapersFlow). Genuinely local options exist but require setup (cookjohn MCP + Ollama, ChiKen, ZotPilot local model, 54yyyu local embeddings, DIY).

### Part 2 — Deprecated master list: functional coverage (the "expected surface")

The ~90-plugin list shows what a mature reference-manager ecosystem is expected to cover (mostly non-AI):
- **Item metadata:** citation counts (Crossref/Inspire-HEP/NASA-ADS/Semantic Scholar), DOI/shortDOI management, PMCID/PMID fetch, PubPeer comments, Scite, ORCID/Memento archiving, TL;DR (Semantic Scholar).
- **Attachment/file management:** ZotFile/ZotMoov/Attanger (rename/move/attach), storage scanner, OCR (Tesseract), OPDS e-reader export, open-in-external-reader, zotero://select deep links.
- **Reports:** report customization/cleaning.
- **Interface:** Better Notes, PDF Translate, PDF Preview, citation preview, QuickLook, Zutilo (shortcuts/batch editing), Actions & Tags (rule automation), system tray, Ethereal Style.
- **Library analysis/visualization:** Cita (citation metadata + WikiData + local citation network), Voyant text-analysis export, ZotNet/ZoteroKeywordsGraph network maps, Inciteful.
- **Website integration:** WordPress/SPIP/Drupal/Omeka/BibBase/Kerko/Zotsite bibliography exposure.
- **Word processor & writing:** Word/LibreOffice/Google Docs (bundled), Reference Extractor (.docx embedded refs), Better BibTeX, LyX, BibDesk, zotxt, VS Code, Emacs, Pandoc, RStudio/rbbt/citr, Jupyter/cite2c, Logseq, Obsidian, ONLYOFFICE, RTF/ODF-Scan, Zettlr, InDesign.
- **Developer tools:** plugin scaffolds, CSL style editor/validator, citeproc test runner.
- **Desktop/program integration:** Alfred, Calibre, Todoist/Zotodo, TheBrain.
- **Duplicate management:** Zoplicate / Duplicate detection.

### Part 3 — Prioritized gap analysis against Callosum

**Cross-manager commonality baseline** (the seven: Zotero, Mendeley, Paperpile, ReadCube/Papers, EndNote, RefWorks, Citavi). Highest-priority gaps = capabilities present in MANY managers that users will assume Callosum has.

#### TABLE-STAKES GAPS (common, expected, surprising if absent) — ranked by cross-manager commonality

| Rank | Gap | In how many of 7 managers | AI-dependent? | Which Zotero tools have it | Difficulty for Callosum stack |
|---|---|---|---|---|---|
| 1 | **Built-in PDF reader + annotation/highlight layer** | 6–7 (all but text-only setups) | No | Native Zotero reader | High (UI-heavy; but core expectation) |
| 2 | **Word + Google Docs + LibreOffice citation integration** (CWYW / live fields) | 7 (all) | No | Bundled in Zotero | High — **planned** (LibreOffice→Word→Docs); gap is "not yet shipped" |
| 3 | **Browser web-capture / connector** (one-click save w/ metadata + PDF) | 6 (all but pure-LaTeX) | No | Zotero Connector | Medium-High (browser extension + translators) |
| 4 | **Duplicate detection / merge** | 7 (all) | No | Zoplicate, native | Low-Medium (deterministic on metadata) |
| 5 | **BibTeX/RIS/CSL-JSON export + LaTeX/BibTeX workflow** | 7 (all) | No | Better BibTeX | Low (CSL engine planned anyway) |
| 6 | **Citation counts + metadata auto-completion (DOI/ISBN/PMID lookup)** | 7 (all) | No | citationcounts, DOI Manager | Low-Medium (API calls to Crossref/OpenAlex — Callosum already uses these) |
| 7 | **Single-PDF AI chat + summarization** | 3 native (Mendeley, ReadCube, EndNote) + all Zotero AI plugins | Yes | nearly all (A) plugins | Low — Callosum's consent-gated LLM + RAG covers this; mostly UI |
| 8 | **PDF translation / multilingual reading** | partial (varies) | Mixed | PDF Translate (11k★) | Medium (LLM or service integration) |
| 9 | **OCR fallback for scanned PDFs** | several (EndNote, etc.; Zotero via plugin) | No | Zotero OCR (Tesseract) | Medium (Tesseract bundling) |
| 10 | **Cross-paper / library-wide AI Q&A with grounding** | 2 native (Mendeley Ask My Library, ReadCube) + Beaver/llm-for-zotero | Yes | Beaver, ZotPilot, SeerAI | Low-Medium — Callosum's sqlite-vec RAG is the right substrate; needs grounded-citation UI |
| 11 | **Note-taking / knowledge-management layer** (templates, backlinks) | most | No | Better Notes (7.8k★) | Medium |
| 12 | **Cross-paper annotation/notebook view** | 2 (Mendeley Notebook, ReadCube) | No | Better Notes templates | Medium |
| 13 | **Literature discovery / related-paper recommendations** | 3–4 (ReadCube, Mendeley Suggest, EndNote/WoS) | Mixed | ResearchRabbit, Beaver, PapersFlow | Medium — overlaps Callosum's planned OA-first acquisition cascade |

**Interpretation:** Items 1–6 are the dangerous ones — pure infrastructure that every manager has and that no amount of AI sophistication substitutes for. A user evaluating Callosum will try to read a PDF, cite in Word, and save from a browser within the first ten minutes; if those are missing or rough, the AI story never gets heard. Items 2 and 13 are already on Callosum's roadmap (citation engine; acquisition cascade), so the gap is sequencing/shipping, not vision. Item 7 (single-PDF chat) is now becoming table-stakes because three commercial managers ship it natively — Callosum's consent-gated LLM already covers the capability; it needs the in-context UX. Note that even where commercial managers ship AI, it is gated behind paywalls (Mendeley's free tier allows only "5 Reading Assistant questions"), which is an opening for Callosum's local/BYOK model.

#### DIFFERENTIATION OPPORTUNITIES (rare, but on-brand for local-first / verify-everything)

| Opportunity | Who (barely) has it | Why on-brand for Callosum |
|---|---|---|
| **Grounded, provenance-anchored RAG where every claim resolves to a quoted source passage + page** | Beaver, llm-for-zotero, Semantic Search Tool, Atlas | Core of "verify-everything" ethos; Callosum's local embeddings + sqlite-vec is the ideal substrate |
| **Provenance-anchored, human-verified systematic-review extraction → metafor/JASP/RevMan** | none in Zotero ecosystem; partial in dedicated SR tools | Callosum's planned EXTRACTION workbench is genuinely unique among reference managers |
| **Methods/reporting audits (statcheck-style, Bayesian, LMM completeness, citation-equity)** | none | No competitor offers integrated reporting auditing — strong wedge for methods-conscious researchers |
| **Curated, security-reviewed, principles-enforced in-app plugin store** | none (Zotero explicitly has NO directory + "full access to your computer" warning; zotero-gpt shipped obfuscated code) | Direct answer to Zotero's biggest weakness; Callosum's served-from-own-webserver store is a trust differentiator |
| **Citation-context classification done locally/openly** | Scite only (paid, proprietary, non-LLM) | On-brand if Callosum can ground it in retrieved passages |
| **Section/chapter-aware retrieval** | only ZotPilot | Fits provenance focus (cite the Methods vs Results) |
| **CRediT contribution builder + credit-the-lineage attribution** | none | Unique; aligns with research-integrity positioning |
| **First-class local MCP server with write-safety** | cookjohn (write), 54yyyu (read) — but none with provenance guarantees | See MCP assessment below |

#### CONSCIOUSLY-DECLINE CANDIDATES (out of scope or against principles)
- **Cloud-required multi-agent synthesis / "write my literature review"** (PapersFlow-style) — against verify-everything; risks fabricated synthesis. Decline; offer grounded retrieval instead.
- **Social/collaboration networks & cloud group libraries** (Mendeley-style) — large scope, off-mission for local-first v1.
- **Website-bibliography publishing** (WordPress/Drupal/Kerko/Zotsite) — niche; decline or leave to export.
- **Mind-mapping / TheBrain / Alfred / Todoist integrations** — exotic; decline.
- **Selling/embedding a proprietary closed model** — against AGPL/open ethos.
- **Figure/table "data extraction from charts" as a headline AI feature** — high hallucination risk; if built, must be provenance-gated and human-verified (fits EXTRACTION workbench, not casual chat).

### MCP / agent-bridge assessment
The MCP layer is **both** the biggest architectural threat and the biggest opportunity. **Threat:** hosted bridges (PapersFlow, alejandroarnaud) and plugin bridges (cookjohn, 54yyyu, PapersGPT's built-in server) let any external chatbot use a Zotero library directly — meaning a competitor's AI client can treat the reference manager as a dumb data store while capturing all the user-facing value and provenance decisions. If Callosum has no MCP surface, it gets bypassed; if it exposes an unsafe one, it inherits Zotero's "full access to your computer" problem.

**Recommendation: Callosum should ship its own MCP server, designed read-first with gated writes.** This keeps Callosum as the authority over bibliographic state, provenance metadata, and write-safety while letting users bring Claude/ChatGPT/Cursor/Gemini. Concretely: (1) expose read tools (search, metadata, full-text, **grounded passage retrieval with page anchors**) freely; (2) route ALL writes (add/move/delete/tag/note) through explicit confirmation + session undo, mirroring the best patterns already proven by llm-for-zotero (confirmation cards + undo) and cookjohn (toggleable write tools); (3) stamp every AI-originated write with provenance/lineage metadata so "what did the agent change and on what evidence" is always auditable. This converts the bridge layer into a moat: external agents become more useful *because* Callosum guarantees verifiability that raw Zotero MCP servers do not.

### UX / trust lessons from the ecosystem
1. **Write-permission gating is the proven safe pattern.** Beaver applies changes "only with your approval"; llm-for-zotero uses confirmation cards + session undo + off-by-default agent mode; cookjohn lets users disable write tools. Callosum should make confirmation + undo + default-read-only the standard, and surface a clear "the AI wants to change X" diff (Beaver's inline note diff is a good model).
2. **Provenance display is a differentiator users notice.** Beaver's page/sentence citations and llm-for-zotero's click-to-source are repeatedly cited as what makes a tool trustworthy; the Semantic Search Tool author explicitly frames Evidence/Sources panels as the antidote to hallucination. Commercial managers are converging here too — Mendeley's Reading Assistant explicitly "include[s] one or more in-text citations to support the claims made." Callosum's verify-everything ethos should make grounded, clickable citations the default, never optional.
3. **Local-vs-cloud model selection must be explicit and honest.** The ecosystem conflates "supports local models" with "private/offline" (PapersFlow's own guide warns these differ). Callosum's privacy gate should clearly distinguish (a) local inference, (b) what leaves the machine (metadata vs full text vs PDF), and (c) which provider sees prompts — and default to the most private path.
4. **Security/trust is Zotero's open wound.** Zotero ships no plugin directory, warns plugins have "full access to your computer," and a documented 2026 forum thread showed popular plugins (zotero-gpt, zotero-reference, zotero-style) shipping obfuscated XPIs not matching their AGPL repos. Callosum's curated, security-reviewed, principles-enforced store served from its own webserver is a direct, marketable answer — but only if Callosum holds itself to publishing corresponding source and reproducible builds.
5. **Avoid plugin sprawl / startup cost.** The recurring complaint is that getting AI into Zotero means hunting forums, installing several add-ons, juggling API keys, and hitting breakage (ARIA's GPT-4 death). Callosum's in-app, curated, BYOK-with-sane-defaults approach is the antidote — provided onboarding is one path, not ten.

## Recommendations
**Stage 0 — Close the infrastructure table-stakes before marketing AI (highest priority).** Ship, in rough order: a usable built-in PDF reader + annotation layer; the citation engine on its planned LibreOffice→Word→Google Docs path; a browser web-capture/connector; duplicate detection; BibTeX/RIS/CSL-JSON export; and metadata auto-completion + citation counts via the Crossref/OpenAlex APIs Callosum already calls. *Benchmark to advance:* a new user can read a PDF, save a paper from the browser, and insert a live citation in Word/LibreOffice without leaving Callosum. Until that is true, AI features are premature.

**Stage 1 — Make the grounded AI core a headline, in-context experience.** Wire the consent-gated LLM + sqlite-vec RAG into (a) single-PDF chat + summarization in the reader and (b) library-wide Q&A — both with mandatory clickable page/passage citations (match Beaver/llm-for-zotero). *Benchmark:* every AI answer resolves to a quoted source with a page anchor; no ungrounded output ships.

**Stage 2 — Ship the MCP server (read-first, gated writes, provenance-stamped).** This is the key defensive+offensive move. *Benchmark:* external Claude/ChatGPT can search and retrieve grounded passages immediately; every write is confirmed, undoable, and lineage-stamped.

**Stage 3 — Press the differentiation wedge.** Deliver the EXTRACTION workbench, methods/reporting audits, citation-equity, CRediT/lineage, and the curated security-reviewed plugin store — the capabilities no competitor has. *Benchmark to reprioritize:* if a major manager (e.g., Mendeley/Elsevier or ReadCube) ships provenance-anchored SR extraction or reporting audits natively, accelerate; otherwise this is durable whitespace.

**Triggers that would change the plan:** (a) if Zotero ships native AI or an official curated directory, Callosum's trust/curation advantage shrinks — lean harder on local-first + methods auditing; (b) if a competitor ships a safe, provenance-aware MCP server first, accelerate Stage 2; (c) if single-PDF AI chat becomes universally expected (already 3/6 commercial managers and adopted under demand — Clarivate's EndNote 2025 launch cited a survey finding "72% are interested in using AI tools to assist with manuscript preparation"), treat it as table-stakes (Stage 1), not a differentiator.

## Caveats
- **This ecosystem shifts monthly.** Star counts, versions, and model lists are mid-2026 snapshots; Beaver star figures even vary across GitHub pages (57–184 depending on cache) — treat as order-of-magnitude. PapersGPT's model list (GPT-5.5, Gemini 3.x, Claude 4.6) reflects rapidly-changing vendor naming.
- **Mendeley's native AI is genuinely new** — launched December 8, 2025 per the Mendeley Blog ("The Future in Mendeley: AI features are here!" — "Today, we're excited to unveil a new suite of AI features designed to transform the way you read, compare, and explore scientific literature"). Several 2026 comparison articles understate it; this analysis prioritizes official Mendeley/Elsevier sources. Similarly, EndNote 2025's AI launched in stages — Clarivate's April 23 2025 press release announced "Key Takeaway" AI, with the full natural-language Research Assistant chat shipping later in 2025 on the Clarivate Academic AI Platform. The pace means "3 of 6 commercial managers have native AI chat" is rising, not stable.
- **Vendor blogs (PapersFlow, PapersGPT, citationstyler) are interested parties.** Their feature claims are corroborated against GitHub repos and official docs where possible, but some superlatives ("best," "most powerful") are marketing.
- **Beaver's backend and PapersGPT's licensing are closed**, so some grounding/processing claims cannot be independently audited from source.
- **Callosum's own roadmap items (citation engine, acquisition cascade, EXTRACTION workbench, plugin store) are planned, not shipped** per the brief; gap rankings assume current-state absence and should be revisited as features land.
- **OCR availability** across commercial managers could not be fully confirmed and is flagged as uncertain.