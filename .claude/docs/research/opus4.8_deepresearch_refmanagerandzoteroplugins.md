# Callosum vs. the Field — Integrated Competitive Comparison

*Seven reference managers (Zotero, Mendeley, Paperpile, RefWorks, ReadCube Papers, Citavi, EndNote) ·
Elicit · Zotero's AI-plugin ecosystem · benchmarked against **Callosum-now (inc 104)** and
**Callosum-future (post-backlog)**.*

This document **integrates** two prior research passes — `comparison-with-other-ref-managers.md` (the seven
incumbents + an Elicit deep-dive) and `comparison-with-zotero-ai-plugins.md` (the ~15-plugin AI surface + the
deprecated ~90-plugin master list) — into one map, then adds the two Callosum columns and a **gap ledger** that
sorts every shortfall into *already-closed / already-in-backlog / genuinely-absent*. The last of those is the
decision surface for what (if anything) to add to the backlog.

---

## Provenance & method note — three reconciliations the reader must hold

1. **The two source reports predate the inc-104 codebase.** They were written against an earlier Callosum and
   describe several capabilities as *missing* that are, in fact, **shipped today** (built-in PDF reader, duplicate
   detection, BibTeX/RIS/CSL export, single-paper and library-wide grounded synthesis, Crossref/OpenAlex metadata
   enrichment). Every such item is re-scored here against the actual code. **Where this document and the source
   reports disagree on Callosum's current state, this document is authoritative** because it was checked against
   the running code; where they disagree on the *incumbents*, the source reports are authoritative.
2. **The root README is stale** (it says "Increment 73"). The codebase is at **≈ inc 104, ~410 tests**; that is
   the "current" baseline used here.
3. **One self-characterization overstatement carried forward and corrected.** Callosum's own characterization docs
   describe verification as "verified / **contrasted** / flagged" (a stance classifier). The schema *defines* a
   `contradicted` status, but the verifier only ever emits `verified / weak / unverified` and the UI renders only
   `verified / flagged` — the NLI model's **contradiction** signal is scaffolded but **dormant**. So Callosum
   currently distinguishes *supported* from *not-sufficiently-supported*; it does **not** yet flag a source that
   actively *contradicts* a claim. This matters below (it is adjacent to the scite-style "smart citations" gap).

**Rating key (unified):** 🟢 strong / a differentiator · 🟡 partial / present-but-limited · 🔴 absent
(*non-goal* = deliberate, *deferred* = planned). The seven incumbents were originally star-rated (1–5★) by the
source analyst; those stars are preserved in the matrix and the Callosum columns are mapped onto the same scale
(🟢-differentiator → ★★★★★; 🟢-strong → ★★★★; 🟡 → ★★★; 🔴 → ★). Emoji↔star compression is approximate; the
seven-manager stars remain the source analyst's qualitative reading of 2026 docs, not vendor metrics.

---

## TL;DR — the net read

- **No incumbent is Callosum's nearest neighbor; Callosum sits in genuinely unfilled space.** The closest
  *combination* on the market is "Zotero + Elicit + scite." **Zotero** is the nearest neighbor on
  architecture/citation/trust (open, local-first, leaveable); **Elicit** is the nearest neighbor on AI
  evidence-extraction. **Neither does what the other does, and neither offers an auditing METHODS suite.** The
  honest one-liner: *Callosum ≈ Zotero's openness + Elicit's AI extraction + an auditing suite no one offers.*
- **The "Elicit is the closest thing to Callosum" framing is half-right and should be retired.** Elicit is the
  *opposite* of Callosum on architecture (cloud vs. local), licensing (closed vs. AGPL), and core function (Elicit
  has **no** citation insertion / Word / LibreOffice / CSL / reference library at all). It is a
  discovery-extraction-synthesis engine, not a reference manager.
- **The most dangerous gaps are boring, not AI.** A prospective user tries to read a PDF, save from a browser, and
  cite in Word within ten minutes. Two of the four classic "boring gaps" are **already closed** in inc-104 (PDF
  reader ✅, dedup-detection ✅). Two are **not**: Word/LibreOffice/Docs cite-while-you-write (in-backlog, the
  citation-engine spine) and browser capture (deliberately **parked** behind counsel). Closing the citation engine
  is the single highest-value move on the board.
- **The durable moat is the part that isn't "AI chat."** Provenance-anchored verify-everything RAG, the
  methods/reporting auditors, the human-verified meta-analysis extraction workbench, credit-the-lineage, and a
  curated principles-enforced plugin store are **whitespace** — no competitor offers them. "AI in your reference
  manager" *undersells* Callosum by entering it in a footrace with a dozen Zotero plugins; "the reference manager
  that makes its own outputs auditable" is a race nobody else is running.

---

## PART I — Callosum vs. the seven reference managers (+ Elicit)

### I.1 Unified matrix (7 incumbents + Callosum-now + Callosum-future)

| Dimension | Zotero | Mendeley | Paperpile | RefWorks | ReadCube | Citavi | EndNote | **Callosum now** | **Callosum future** |
|---|---|---|---|---|---|---|---|---|---|
| Capture / import | ★★★★★ | ★★★★ | ★★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★ | **★★★★** | **★★★★** |
| Metadata cleanup | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | **★★★** | **★★★★** |
| PDF management | ★★★★ | ★★★ | ★★★★ | ★★ | ★★★★ | ★★★ | ★★★★ | **★★★** | **★★★** |
| Organization model | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★★★ | ★★★★ | **★★★★** | **★★★★** |
| Search / retrieval | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★ | **★★★** | **★★★★** |
| Reading / annotation | ★★★★ | ★★★★ | ★★★ | ★★ | ★★★★ | ★★★ | ★★★ | **★★★★** | **★★★★** |
| Citation generation | ★★★★★ | ★★★ | ★★★★ | ★★★ | ★★★★ | ★★★★ | ★★★★★ | **★** | **★★★★★** |
| Writing integrations | ★★★★ | ★★★ | ★★★★ | ★★★ | ★★★ | ★★★★ | ★★★★★ | **★** | **★★★★** |
| Collaboration | ★★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | ★★★ | **★** | **★** |
| Sync / offline † | ★★★★★ | ★★ | ★★★ | ★★ | ★★★ | ★★★★ | ★★★★ | **★★★** | **★★★** |
| Export / portability | ★★★★★ | ★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | **★★★** | **★★★★** |
| Discovery / recommend | ★★ | ★★ | ★★ | ★★ | ★★★★ | ★★★ | ★★★ | **★★** | **★★★★** |
| AI features | ★ (plugins) | ★★ | ★★ | ★ | ★★★★ | ★★★ | ★★★ | **★★★★★** | **★★★★★** |
| Provenance / verifiability | ★★★★ | ★★ | ★★ | ★★ | ★★★ | ★★★ | ★★★ | **★★★★★** | **★★★★★** |
| Privacy / data ownership | ★★★★★ | ★ | ★★ | ★★ | ★★ | ★★ | ★★★ | **★★★★★** | **★★★★★** |
| Extensibility | ★★★★★ | ★ | ★ | ★ | ★ | ★★ | ★★ | **★★★** | **★★★** |
| Platform support | ★★★★ | ★★★ | ★★★★ | ★★★ | ★★★★ | ★★ | ★★★ | **★★** | **★★★** |
| Pricing / licensing | ★★★★★ | ★★★★ | ★★ | ★★★ | ★★ | ★★ | ★★ | **★★★★★** | **★★★★★** |
| Systematic-review | ★★ | ★ | ★ | ★★ | ★★★★ | ★★ | ★★ | **★** | **★★★★** |
| Performance at scale | ★★★ | ★★★ | ★★★ | ★★★ | ★★★ | ★★★★ | ★★★★ | **★★★** | **★★★** |

† *Sync/offline is a split axis for Callosum:* offline-first/local-only is **★★★★★**, sync is **✗** — netted to
★★★ here. *(Notes & knowledge-synthesis is not a row above because the source analyst did not star the seven on
it; it is handled in Part IV. Callosum scores 🟡-now → 🟢-future there.)*

**What the two Callosum columns show at a glance:** the future build closes its **two glaring 🔴→★★★★★/★★★★
jumps** (citation generation, writing integration) and lifts four 🟡→🟢 dimensions (metadata, search, discovery,
systematic-review), while its **already-leading ★★★★★ dimensions — AI, provenance, privacy, pricing — hold and
generalize**. Collaboration stays ★ by design. Platform and extensibility stay mid because packaged
desktop/mobile and a full plugin system are deferred.

### I.2 Where each incumbent actually leads (so we know what we're really up against)

- **Zotero** — the only **fully open-source, local-first, inspectable, no-lock-in** incumbent, and therefore
  Callosum's true *philosophical sibling*. Best capture (Connector + hundreds of translators), best portability,
  best CSL citation stack (Word/LO/GDocs + 10,000+ styles + Better BibTeX), **Retraction Watch** flagging,
  highest trust posture. **Ships zero native AI by stated policy** — AI is entirely plugin-territory.
- **EndNote** — the **gold standard for institutional Word workflows** (Cite While You Write); 30-year local file
  format; retraction flags; and notably **document-local AI** ("Key Takeaway"/Research Assistant explicitly *not*
  using other library docs or public LLMs, no user data passed to LLMs).
- **ReadCube Papers** — the **most mature commercial AI**: chat one/multi/whole-library with **answers linked back
  to the source passage**, AI literature monitoring, and an enterprise **Systematic Literature Review** tool with
  AI-assisted extraction ("verify rather than start from scratch"). Powered by Dimensions (150M+).
- **Citavi** — the **strongest knowledge-organization model**: quotations/summaries/comments saved as discrete
  linked "knowledge items," outline-for-drafting, a task planner; 11,000+ styles. (PE-owned, Windows-centric,
  price-hiked.)
- **Paperpile** — best-in-class **Google Docs** citation + **Overleaf** auto-sync; PDFs in the user's own Drive.
- **Mendeley** — free, polished, **native AI since Dec 2025** (Reading Assistant with in-text citations); but
  **Elsevier-owned, cloud-only, and the worst export story of the seven (encrypted citation data blocks export).**
- **RefWorks** — institutional/web admin, project sharing, dashboards; no notable native generative AI; the Google
  Docs add-on draws frequent reliability complaints.

### I.3 Elicit head-to-head (the "closest thing" claim, corrected)

**What Elicit does that Callosum will not (by design):** semantic search over a **hosted ~138M-paper index**
(Semantic Scholar + PubMed + OpenAlex) + 545K trials with AI ranking; **AI research reports / synthesis
narratives**; **automated AI screening at 5,000–40,000-paper scale** (vendor-validated 95% recall / 97% abstract /
99% full-text / 96% extraction across 994 Cochrane reviews); **figure/table interpretation**; an agentic
**Research Agent**; **topic alerts**; and **real-time cloud co-editing** of extraction tables.

**What Callosum does (or plans) that Elicit cannot:** local-first, offline, **AGPL** open-source, inspectable
SQLite + local embeddings with **consent-gated** (not cloud-only) LLM calls; a **true citation engine** (CSL +
citeproc-js → LibreOffice/Word/GDocs live fields) — Elicit has **none**; the **auditing METHODS suite**
(statcheck/Bayesian/LMM/citation-equity/PUBLISHERS/CRediT) — *no AI literature tool offers this*;
**credit-the-lineage** + verify-everything provenance with **no vendor PDF upload by default**; and **ownership /
leaveability** (Elicit's value evaporates when the subscription lapses).

**The honest verdict:** Elicit is the nearest neighbor on **AI extraction/synthesis only**, and it is the
*opposite* of Callosum on architecture, licensing, and core function. **Retire "Elicit is the closest thing to
Callosum."** Adopt: *"Elicit is the closest AI-extraction analog; Zotero is the closest architecture/citation
analog; Callosum uniquely fuses both and adds an auditing suite no competitor offers."* One important external
check cuts in Callosum's favor: a peer-reviewed evaluation (**Lau et al. 2025, *Cochrane ESM*, cesm.70050**) found
Elicit's relevance-ranking "neither as transparent nor reproducible as a traditional database search" (35.6%
sensitivity/precision in their test; opaque Semantic-Scholar query history) — i.e., **reproducible, inspectable
search is a place a local-first design can *beat* Elicit, not merely match it.**

### I.4 Nearest-neighbor AI-literature map (where Callosum sits)

The AI-literature field clusters into discovery/extraction engines (**Elicit, Consensus, SciSpace, Undermind**),
citation-graph/discovery (**Research Rabbit, Connected Papers, Semantic Scholar**), citation-context (**scite** —
1.3B+ classified citation statements, the lone "smart citations" player), and reference-managers-with-AI
(**ReadCube**, **Zotero+plugins**). **Only Zotero+plugins and Callosum are local/OSS *and* true citation
managers.** Of those two, only Callosum adds verify-everything provenance + an auditing suite. That intersection —
*local-first + open + true citation manager + grounded AI + methods auditing* — is occupied by **no shipping
product**.

---

## PART II — Callosum vs. Zotero's AI-plugin surface

### II.1 The plugin landscape, in five classes

The ~15 live AI plugins (and the deprecated ~90-plugin master list) sort into: **(A) in-Zotero assistants**
(Beaver, PapersGPT, llm-for-zotero, ARIA, AIdea, zotero-gpt, SeerAI, …), **(B) AI-enabled utilities** (Scite, PDF
Translate, Better Notes, jmiba reference-extraction), **(C) MCP/agent bridges** (54yyyu, cookjohn, ZotPilot,
PapersFlow, ChiKen), **(D) external platforms** (ResearchRabbit, PapersFlow), **(E) DIY local RAG** (pyzotero +
Chroma/FAISS + Ollama).

**Coverage verdict, mapped to Callosum:**

- **Well-covered by the ecosystem** (mature, many tools): single-PDF chat, summarization, multi-provider incl.
  local Ollama/LM Studio, translation, MCP bridging, note generation. → Callosum **matches the capability**
  (single-paper and library-wide *verified* synthesis is a superset of "chat with this PDF"); what it lacks is the
  *conversational affordance* and *translation*, not the substrate.
- **Partially covered** (a few good tools): grounded library RAG with page/sentence citations (Beaver,
  llm-for-zotero, ZotPilot, the OSS "Semantic Search Tool"); figure/table understanding; agentic search; AI
  reference-extraction; **section/chapter-aware retrieval (only ZotPilot)**. → Callosum's grounded RAG is
  **best-in-class on provenance** already; section-aware retrieval is a clean, on-brand gap.
- **Rarely/barely covered** — *Callosum's whitespace*: citation-context classification (Scite only, non-LLM,
  paid), provenance-anchored human-verified SR extraction, methods/reporting audits, deterministic effect-size
  pipelines, citation-equity / credit-lineage. **No competitor and no plugin offers these.**

The deprecated master list confirms the *expected* mature surface (citation counts, DOI/PMID management, OCR,
ZotFile-style file moving, Word/LO/GDocs/LaTeX/Pandoc/Obsidian writing bridges, duplicate management, CSL
tooling) — almost entirely **non-AI**, which is the point: the table-stakes that make a reference manager feel
complete are boring infrastructure, and they predate this AI wave.

### II.2 The assembly-cost & trust argument (corroborated, not punctured)

The research **confirmed** the startup-cost critique rather than puncturing it: Zotero ships zero native AI,
**removed its plugin master list (~May 2026)**, has **no AI category**, and warns outright that plugins have
**"full access to your … computer."** The genuinely damning corroboration: a 2026 forum thread documents popular
plugins (**zotero-gpt** among them, 7.2k★) shipping **obfuscated XPIs that don't match their AGPL repos**. So the
trust anxiety is not aesthetic fastidiousness — it's a correctly identified, real, exploitable hole. **But the
edge is narrower than "Zotero can't do AI":** every AI capacity a user could want already *exists* in the
ecosystem — it's just **unbearable to assemble** (hunt forums, install several add-ons, juggle keys, hit
breakage like ARIA's death when OpenAI retired `gpt-4`). That makes Callosum's edge an **integration / curation /
trust / "don't become a sysadmin to read a paper"** edge — real, but an *experience* edge that decays like a
footrace, not a *capability* moat. The capability moat is elsewhere (Part III).

### II.3 The MCP layer — threat, and the curated-store answer

**The MCP bridge layer is both the biggest architectural threat and the biggest opportunity.** Hosted/plugin
bridges (PapersFlow, cookjohn, 54yyyu, PapersGPT's built-in server) let any external chatbot treat a reference
manager as a **dumb data store** while capturing all the user-facing value and *making the provenance decisions
itself*. If Callosum has no MCP surface it gets **bypassed**; if it ships an unsafe one it inherits Zotero's
"full access to your computer" problem. The report's headline recommendation — **Callosum should ship its own
read-first, write-gated, provenance-stamped MCP server** — converts the bridge into a moat: external agents
become *more* useful precisely because Callosum guarantees verifiability raw Zotero MCP servers do not. *(This is
an architectural bet, not a cross-manager table-stake — flagged for your decision in Part IV.C.)*

The **curated, security-reviewed, principles-enforced plugin store served from your own webserver** is the direct,
marketable answer to Zotero's open wound — *provided* Callosum holds itself to publishing corresponding source +
reproducible builds (or the same critique boomerangs). The AI-assisted submission pipeline you sketched
(automated security audit + auto-categorization + defer-risky-to-manual-review + principles/A-A conformance
gating, submitter-identity capture) is well-aligned; it is **already a backlog track** ("plugins," currently
record-only) that this research **upgrades from "nice-to-have" to "trust differentiator."**

---

## PART III — Synthesis: the moat vs. the footrace

Two different races are running, and the framing determines which one Callosum is in.

**The footrace (experience edge, decays fast):** "AI in your reference manager." Here Callosum competes with
Beaver, llm-for-zotero, PapersGPT, ReadCube, Mendeley, EndNote, Elicit — all of whom already ship grounded chat,
local models, or SR extraction in some form. Callosum **wins on integration + trust + no-assembly + verify-by-
default**, and that is genuinely valuable, but it is a footrace: the moment Zotero ships native AI or an official
curated directory, the curation advantage shrinks.

**The moat (capability edge, structurally empty):** "the reference manager that makes its own outputs auditable."
Here Callosum competes with **no one**:

- **Provenance-anchored, verify-everything RAG** — every claim resolves to a quoted passage + page, independently
  re-checked by local machinery. ReadCube/EndNote *link* to a source; Elicit's citations don't always reach the
  sentence; **none independently verify the model's own claim against the source.** *(Caveat: the contradiction
  half of this — flagging a source that *disagrees* — is the dormant `contradicted` stance; closing it would
  deepen the moat, not just polish it.)*
- **Human-verified, provenance-anchored systematic-review extraction → metafor/JASP/RevMan**, with a hard line
  (extract/screen/convert, **never pool/model/adjudicate**). No reference manager offers this; dedicated SR tools
  (Covidence/Rayyan/DistillerSR) are the real comparison and are cloud/closed.
- **Methods/reporting auditors** (statcheck live; Bayesian/LMM/GRIM/p-curve planned), **citation-equity audit**,
  **PUBLISHERS where-to-submit**, **CRediT builder** — *integrated reporting auditing exists in no competitor.*
- **Credit-the-lineage** attribution woven through every tool, and a **curated principles-enforced store**.

**Recommendation on positioning:** lead with the moat, not the footrace. The "AI reference manager" pitch
*undersells* Callosum by entering a crowded race; "makes its own outputs auditable" is the claim no competitor can
match — and the boring table-stakes (Part IV) exist to *earn the hearing* for that claim, not to win on their own.

---

## PART IV — The gap ledger (bridge to the backlog decision)

Every shortfall surfaced by either report, re-scored against inc-104 and sorted into three buckets. **Bucket C is
the decision surface** for what to add to the backlog. Prevalence = how many of the seven incumbents have it
(your stated prioritization signal: high cross-manager prevalence ⇒ users assume it's present).

### IV.A — Already closed in inc-104 (the source reports are stale here; do **not** re-add)

| Capability | Report's claim | Actual inc-104 state |
|---|---|---|
| Built-in PDF reader + annotation | "gap (high difficulty)" | **Shipped** — pdf.js, colored highlights + notes, management panel, reading mode (inc 30/31/35/101) |
| Duplicate **detection** | "gap" | **Shipped** — union-find over identifier→title/author/year→embedding (inc 56/64/67) |
| BibTeX/RIS/CSL-JSON export + stable keys | "gap (low)" | **Shipped** — inc 70; per-card copy inc 103 |
| Single-PDF chat/summarization | "gap (mostly UI)" | **Capability shipped** as single-paper *verified* synthesis (superset; lacks only the conversational affordance) |
| Library-wide AI Q&A with grounding | "gap (low-med)" | **Shipped** — query/cluster-scoped verified synthesis with page-anchored citations (Callosum's core) |
| Metadata auto-completion (DOI/PMID, Crossref/OpenAlex enrich) | ranked #6 table-stake | **Shipped** — enrichment + DOI re-resolve (inc 49); acquisition does DOI/PMID/title lookup |
| Provenance-anchored grounded RAG | "differentiation opportunity" | **Shipped and best-in-class** — the verify-everything spine |

### IV.B — Already in the backlog / future-tracks (vision exists; the question is *sequencing*, not *whether*)

These need **no new decision** — they are specified. Listed so they aren't mistaken for Bucket-C candidates.

- **Word/LibreOffice/Google Docs cite-while-you-write + CSL formatted styles** — the citation-engine spine
  (citeproc-js, backend-side, LibreOffice→Word→GDocs). *Table-stakes rank #2; the single highest-value item.*
- **Library merge** (preprint+published), **retraction/transparency facts** (Crossref Retraction Watch via
  findings) — deferred-deliberately-last / findings track.
- **Citation-graph discovery** (gap-finder: backward/forward/co-citation/followed-authors) — addresses holes #1's
  graph cousin + #2; *discovery track.*
- **Literature alerts / TOC / RSS feeds** (subscribe to journals/keywords/authors) — *FEED track* (holes #3, #8;
  table-stakes #13).
- **Meta-analysis extraction + PRISMA search-strategy logs** — *MA workbench* (holes #5-partial, #6, #10).
- **Methods auditor suite beyond statcheck** (Bayesian/LMM/GRIM/SPRITE/p-curve), **citation-equity**,
  **PUBLISHERS**, **CRediT builder** — *methods/writing tracks* (the moat).
- **BYOK multi-provider + local models** — *byokproviderkeys track* (directly attacks Zotero's key-juggling
  startup cost).
- **Curated principles-enforced plugin store** — *plugins track*, upgraded by this research to a trust
  differentiator.
- **THEORY modules / quote banks / cross-paper notes / disagreement maps** — *theorymethods track* (table-stakes
  #11/#12; hole #4's cross-study contradiction surfacing).
- **Highlight-to-suggest / highlight-to-evaluate** (support/contrast/mention for *your draft sentence*) — *Track
  C* (a partial, draft-side cousin of scite's library-level classifier).

### IV.C — Genuinely absent, **not** in backlog, **not** a clearly-stated non-goal → the decision surface

> **Dispositions now resolved** — this subsection is the analysis-of-record (what was surfaced + my leans); the
> outcomes-of-record are in **"Phase 2 — Settled decisions"** below. (Folders/collections was resolved out as
> superseded by axes; see the note at the end of this subsection.)


Sorted into what I judge **clearly warranted (no confirmation needed)** vs. **needs your input**. The warranted
set is dominated by *high prevalence × low cost × no identity conflict*; the input set is *high prevalence but
identity-tensioned, expensive, or strategically off-axis*.

#### Clearly warranted — I'll commit these to the proposed-additions list without asking

| Addition | Prevalence (of 7) | Why warranted | Cost / scope note |
|---|---|---|---|
| **Saved searches (persisted boolean/metadata filters)** | ~6/7 | Distinct from axes: this persists *metadata/boolean filter state* ("author = Krendl AND year > 2018 AND tag = X"), which semantic axes don't reproduce. Filters already exist; just *persist* them. | Low — persistence + a saved-filter UI |
| **Library-wide per-paper citation counts** | ~6–7/7 | Metadata staple (table-stake #6); Callosum already calls OpenAlex/Crossref. | Low — one API field surfaced on cards |
| **Basic full-text PDF search box** | ~7/7 | Users will *expect a search box*; the extracted chunks already exist. Distinct from internal semantic retrieval (keep both). | Medium — FTS index over existing text + UI |
| **Plain-Markdown annotation export** | ~3–4/7 (huge in OSS) | Directly on-brand for the "you can leave" / open ethos; complements the existing annotation layer. | Low — serialize annotations to .md |
| **Color tags / ratings / flags** | ~4–5/7 | Cheap organizational polish complementing tags + stars; no model conflict. | Low — schema + UI |

*(Rationale for "no confirmation": each is cheap, broadly expected across the incumbents, and creates no tension
with local-first / verify-everything / the axes-and-tags organizing model. The full-text **search box** is the
only medium-cost item here, but a missing search box is the kind of first-ten-minutes surprise the whole
table-stakes argument is about — so I'm treating it as warranted while flagging the FTS-index scope.)*

#### Needs your input — surfaced, not committed

| Candidate | Prevalence (of 7) | The tension / the question for you |
|---|---|---|
| **Cloud sync / multi-device** | **7/7 (some form)** | Directly tensions the local-first identity. Both reports suggest an *optional, end-to-end-encrypted* tier that preserves the local-first default. **Q:** entertain an opt-in E2E sync seam, or hold the line and let Dropbox/Git be the backup story? |
| **Mobile / tablet reading** | ~5/7 | Large scope; currently a non-goal. **Q:** accept as a permanent non-goal, or reserve a "read-only mobile companion" as a far-future seam? |
| **Collaboration / shared libraries** | **7/7** | Declared non-goal; reports say decline-for-v1. **My lean: decline** (clearest off-mission item) — but flagging because it's the single most universal incumbent feature. |
| **OCR for scanned PDFs** | ~4–5/7 | Table-stake #9; real packaging cost (Tesseract bundling → implies desktop-distribution work). **Q:** worth the dependency now, or defer until the desktop shell lands? |
| **First-class read-first/write-gated MCP server** | n/a (off-axis) | **Not** cross-manager-prevalent (the seven don't have MCP) — so it scores low on your stated rule — but the Zotero report's #1 *architectural* recommendation and a genuine bypass-moat. **Q:** does this clear the bar *despite* not being a table-stake, on strategic grounds? |
| **scite-style citation-context classifier (library/graph-level)** | 1/7 (Scite) | A differentiation opportunity that *also* interacts with the dormant `contradicted` stance. Track C does support/contrast/mention for *your draft sentence*, not for *citing papers across the graph*. **Q:** build the library-level classifier, or rule that Track C's draft-side evaluation + activating the dormant contradiction stance is sufficient? |
| **PDF translation / multilingual reading** | low (partial/varies) | Big in the Zotero ecosystem (PDF Translate, 11k★), thin across the seven incumbents → low on your prevalence rule. **My lean: low priority / decline** unless you want the i18n reach. |

**Note on what's *correctly absent* and should stay so** (consciously-decline, per the Zotero report and
Callosum's principles):
- **Folders / collections hierarchy (7/7 — superseded by axes, *not* a gap).** Resolved out of the input list: a
  collection answers "which papers belong under this label," and an **axis** answers it automatically — define the
  concept once (curated terms or an accepted discovered theme) and the library self-populates, scored, ranked, and
  overridable, preserving many-to-many + non-destructive membership. Folder use-cases decompose cleanly onto
  existing primitives: *semantically coherent set* → axis; *arbitrary flat set* ("papers Jeff sent") → tag;
  *"read this week"* → the needs-review/status filter. The only residual axes+tags don't cover is **nested,
  arbitrary, non-semantic hierarchy** ("Grant X › Aim 2 › to-cite") — which is precisely the hierarchy-creep
  Callosum deliberately refuses, so its absence is a design stance, not a shortfall. (This is arguably a
  *differentiator* the matrix's ★★★★ under-credits: no incumbent turns collection-definition into an automated,
  overridable, semantic operation.)
- cloud multi-agent "write my literature review" (against verify-everything); website-bibliography publishing
  (WordPress/Drupal/Kerko); mind-mapping/Alfred/Todoist exotica; any embedded proprietary closed model;
  figure/table "data-from-charts" as a *casual* feature (only inside the human-verified MA workbench,
  provenance-gated).

---

## Caveats

- **Both source reports predate inc-104**; Bucket-A items were re-scored against the running code. Gap rankings
  elsewhere assume the reports' current-state snapshot and should be re-checked as features land.
- **The AI-feature landscape shifts monthly.** scite's MCP launched Feb 2026; Elicit swapped to Claude Opus 4.5
  within days of release; Mendeley's native AI launched Dec 8 2025; EndNote 2025's Research Assistant shipped in
  stages. "3 of 6 commercial managers ship native AI chat" is *rising, not stable* — treat single-PDF chat as
  table-stakes (Stage 1), not a differentiator.
- **Star ratings for the seven are the source analyst's qualitative synthesis**, not vendor benchmarks; the
  Callosum columns are an emoji→star mapping of Callosum's own characterization docs (approximate).
- **Vendor accuracy figures are self-reported.** Elicit's 95–99% Cochrane numbers are vendor validation; the
  peer-reviewed Lau et al. (2025) disputes search reproducibility (35.6% sensitivity/precision in their test);
  independent results vary (Helms Andersen 2025: 92% precision/recall/F1). Verification of every cell remains
  necessary — which is, itself, the Callosum thesis.
- **Pricing is volatile and partly conflicting** (Elicit Plus ~$7 vs. widely-reported $12; Pro $29 vs. $49; Scale
  $49 vs. $169; Paperpile restructured March 2026 without posting per-seat prices). Re-verify at decision time.
- **The `contradicted` stance is dormant in code** but described as live in Callosum's own characterization;
  closing that gap is tracked here as adjacent to the scite-style opportunity, not as a marketing claim to make
  before it ships.

---

## Phase 2 — Settled decisions & backlog additions

*The analysis that produced these is Part IV.C; this is the resolved outcome. **Each item below becomes its own
`future-tracks` prompt** (one per feature) so Claude Code can sequence and security-gate them independently.
Sequencing is by dependency, not bundled stages: the **museum-before-crown-jewel** rule — table-stakes + the
already-specced citation-engine spine first, the deferred moat items after — because a user who can't read a PDF
and cite in Word never reaches the auditing suite.*

**Build now — table-stakes polish + agreed axis refinements** *(alongside the citation-engine spine, which
remains the single highest-priority track):*

- **Saved searches** — persisted boolean/metadata filters ("author = X AND year > Y AND tag = Z"); distinct from
  semantic axes, which don't reproduce metadata predicates.
- **Library-wide per-paper citation counts** — surfaced on cards via the OpenAlex/Crossref calls already in use.
- **Basic full-text PDF search box** — FTS over already-extracted chunk text; complementary to (not a replacement
  for) internal semantic retrieval.
- **Plain-Markdown annotation export** — on-brand for the leaveable/open ethos.
- **Color tags / ratings / flags** — cheap organizational polish over the existing tag + star primitives.
- **Drag-and-drop deposit into axes** — for a Keyword Axis it is a manual override (pin regardless of score); for
  a Curated Axis it is add-and-position.
- **Curated Axis mode** — the umbrella term stays **"Axis"** (never "folder," which would undersell it); a curated
  axis disables/hides keyword scoring and is distinguished by a **subtle aesthetic cue**, not a loud label.
  **Switching is bidirectional**, protected by the existing *manual-assignments-survive-re-scoring* guarantee, so a
  flip never ejects hand-picked members: a Keyword Axis can **freeze** to curated (snapshot members, hide scoring,
  unlock manual drag-ordering), and a curated axis can return to keyword — with a one-line warning that the latter
  requires search terms and replaces manual ordering with fit ordering (members preserved). **Nesting is deferred,
  not forbidden:** when it lands it should be **recursive *semantic* sub-axes** (the auto-axis method applied within
  a parent card — the planned *My Publications* subheading grouping is the prototype, and the right answer to "900
  papers, hard to navigate"), **not** arbitrary manual folder-trees (those stay declined); the infrastructure rides
  in free on the My Pubs sub-grouping work, and flat ships first. **Tags demote to pure
  labels** (filter + provenance) so axes own working-set grouping and there is no tag/folder overlap.
- **Synthesis scope label** — at summarize time, show "summarizing N papers; uncertain excluded," riding with —
- **[Fix, own record]** the **hide-uncertain display-logic bug**: the count badge already switches to
  certain-only when "hide uncertain" is toggled, but the **library-pane axis-contents display does not carry that
  logic through** — fix so what is shown equals what is summarized.

**Backlog — deferred behind critical functionality** *(sequenced after the table-stakes + word-processor
integration):*

- **Read-first / write-gated, provenance-stamped MCP server** — off the cross-manager-prevalence axis, but the
  real defensive moat (keeps Callosum the authority over bibliographic state + provenance while letting users
  bring Claude/ChatGPT/Cursor). Queued.
- **Collaboration / shared libraries** — *deferred, not declined.* Rides the account + web surface already planned
  (auth + plugin store), built later as an opt-in layer under the same E2E/consent discipline as sync.
- **OCR for scanned PDFs** — Tesseract bundling (implies desktop-distribution work); after the word-processor
  track.
- **Library-level scite-style citation-context classifier** — after Track C (draft-side support/contrast/mention)
  and after **activating the dormant `contradicted` stance**, which captures much of the value first.
- **Mobile / tablet reading** — directional via the new **read mode** (the foundation is in); a read-only
  companion is the plausible later step.

**Reserved / declined:**

- **Optional E2E-encrypted sync** — reserved as a far-future *seam only*; not actively planned (no clear sync
  target yet).
- **PDF translation** — declined, out of scope (thin across the seven incumbents; a Zotero-ecosystem pattern).

Next: on request, draft the per-feature prompts (one each, dependency-ordered) for the `future-tracks` inbox.
