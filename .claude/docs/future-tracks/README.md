# Future tracks — index

The longer-horizon vision for Callosum: a complete, **inspectable** ecosystem for engaging the scientific
literature responsibly and efficiently. These are design-toward documents (mostly self-contained build
prompts), **not** the near-term increment queue — that lives in [`../INCREMENT-BACKLOG.md`](../INCREMENT-BACKLOG.md).
Nothing here is built until it passes the **Principles alignment gate** (`.claude/PRINCIPLES.md`): every track
below is a *signal / suggestion / retrieval that stays inspectable and non-authoritative* — none may auto-apply
a judgment, fold a weak signal into a hidden score, or fabricate a link or source.

These were moved here from the repo root (2026-06-21) so the root stays clean for GitHub; they are the
detailed source the backlog references rather than recapitulates.

| File | Track | One-line scope | Key dependencies |
|---|---|---|---|
| `opus4.8_future-tracks.md` | **Tracks A–D (master)** | A: **statcheck / open-science signals**; B: **Word + LibreOffice citation plugin** (cite-while-you-write); C: **highlight-to-suggest / highlight-to-evaluate** references; D: **free-legal full-text acquisition** resolver chain | PDF text (core), CSL-JSON (core), NLI/verification (core), OpenAlex/Unpaywall/Semantic-Scholar |
| `opus4.8_future-tracks_theorymethods.md` | **THEORY/METHODS panes + findings subsystem** | Reorganize side panels into a THEORY/METHODS accordion on a module registry; a **findings subsystem** that keeps deterministic **FACTs** (e.g. retraction via Crossref Retraction Watch, statcheck, open-science/transparency) visually + epistemically distinct from reviewable **candidates** | module registry; Crossref adapter; PDF text |
| `opus4.8_future-tracks_theorymethodsextension.md` | **THEORY/METHODS module pool** | A pool of additional "fits-the-principle" panel-module candidates (constructs, claim mapping, etc.), each a self-contained prompt | the findings subsystem + module registry above |
| `opus4.8_future-tracks_librarypaneltabadditions.md` | **Literature discovery (Feed/Search)** | Two center tabs — **FEED** + **SEARCH** — over a shared `SourceProvider` layer (PubMed/Crossref/bioRxiv); Fraser-method fast triage; axis-relevance **highlight (augment, never filter)** | SourceProviders; embeddings + axis_scoring; the save→auto-axis path |
| `opus4.8_future-tracks_gapfinder.md` | **Literature gap-finder** | Surface papers **relevant-but-absent** from the library via citation methods (backward/forward gap, followed authors), each candidate carrying transparent provenance, ranked by axis relevance, add-or-dismiss | OpenAlex adapter (referenced_works / cited_by / authors); research tab; My-Publications patterns |
| `opus4.8_future-tracks_mypublications.md` | **My Publications** | An automated, pinned axis of the researcher's **own** papers; **LLM-free** OpenAlex/ORCID author resolution with confirm-and-learn for low-confidence matches | OpenAlex adapter (ORCID/author); the axis machinery |
| `opus4.8_future-tracks_plugins.md` | **User-authored modules (deferred record)** | Record-and-mark only: the *idea* of user-authored THEORY/METHODS plugin modules + the extension point + open questions. **No plugin system is to be built** until a dedicated design pass | (none — a capture task) |
| `opus4.8_future-tracks_equityintegritysignals.md` | **Equity & integrity signals (HACKADEMIA-derived)** | The net-new residual from HACKADEMIA, **repointed** to private/inspectable/non-accusatory: overlooked-work lens (inverse Matthew effect), citation credit-concentration (self-cite / reciprocal clusters), self-correction (positive integrity); + 2 principle-fraught forensic candidates (analytic-flexibility — **decomposed, no index**; stylometric — **flagged, open question**) | OpenAlex adapter (citation graph / field-year percentile); GROBID (methods parsing); the findings subsystem; system-facts tags |
| `opus4.8_future-tracks_researchimpactanalytics.md` | **Research-impact analytics (opt-in, local-first, commons)** | Voluntarily + pseudonymously measure whether Callosum changes how people research. **A.** local usage analytics (zero-egress; near-term: instrumentation seam + personal dashboard) vs **B.** cross-user impact signal (far-future, gated). HSR-grade consent, **default-deny**, transmit-summaries-only, public field registry as a data-minimization gate, commons reciprocity | the egress-seam pattern; (later) accounts/hosting decision + N>1; the Principles gate + **A-A values layer** |

**Cross-cut already opened:** tagging (inc 71–73) connects to the findings subsystem — system FACTs like
`RETRACTED` should be filterable via the existing tag mechanism (see the "Tags hook" notes in the theorymethods
+ librarypaneltab docs and the "Tags & keywords" section of the backlog).

**Shared external dependencies across tracks** (currently README-only stubs under `integrations/`, kept on
purpose): **OpenAlex** (gapfinder, my-publications, discovery, acquisition), **Semantic Scholar** (discovery,
suggest), **GROBID** (section/reference structure for Track C section-scoping), **Unpaywall** (Track D),
**mendeley** (import-via-bridge).
