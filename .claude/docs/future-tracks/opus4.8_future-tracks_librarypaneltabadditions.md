<!-- TAGS HOOK (added 2026-06-20, after tagging shipped in inc 71/72 — this doc predates tags).
     When a paper is SAVED from a Feed/Search source, attach the source's keywords as tags (PubMed MeSH,
     OpenAlex concepts, Crossref `subject`, a journal/feed name) with provenance `keyword:{source}` — so the
     authors'/indexers' own concept work becomes FIRST-ORDER tags (the inc-72 c-TF-IDF suggester is the
     second-order gap-filler). Reuse the inc-71 tag mechanism + `tags.import_source`; do not invent a parallel
     label store. See `.claude/docs/INCREMENT-BACKLOG.md` → "Tags & keywords". -->

Goal: Build a Literature Discovery feature — two center library-frame tabs, FEED and SEARCH, on a
shared, extensible source-query layer — bringing finding the literature into the same place you
read and understand it. Stay true to the Fraser method: fast comprehensive triage, AI augments but
NEVER filters the complete list, lightweight at intake.

PLACEMENT: center library-frame tabs (reuse the LibraryFrame tab system in 30_viewer.jsx /
40_app.jsx, the openPdf-style tab path), siblings to the PDF viewer. NOT THEORY/METHODS sections —
this is a discovery/intake workspace, a third functional category.

SOURCE LAYER (shared + extensible — the ethical core):
- A SourceProvider REGISTRY. Each source is a self-registering module conforming to a SourceProvider
  interface (query(params) -> normalized items; recent(since) -> normalized items; metadata).
  Ship providers: PubMed (via the connected PubMed MCP — keyword/author/journal), Crossref (by
  ISSN for journal recent-works; reuse the crossref adapter), bioRxiv (via the connected bioRxiv
  MCP — preprints), and a generic RSS provider (optional supplement). DESIGN for user-added
  providers later — internal registry now, user-facing source-plugin UI deferred. This registry is
  the architectural answer to not foisting one curator's source choices on everyone.
- Normalized item model: { source(s), external_id (DOI/PMID), title, abstract, authors, journal,
  date, url, dedup_key }. Dedup across sources by DOI/PMID/normalized-title (one paper arriving from
  a journal feed and a PubMed keyword feed is a single item tagged with both sources).

FEED TAB (the Fraser method):
- Subscriptions: the user curates sources to follow — journals (ISSN), PubMed keyword/author
  searches, bioRxiv categories, citation alerts. Suggestions seeded from the user's OWN library
  (most frequent journals/authors) — derived from their corpus, never auto-subscribed.
- Polling: per-subscription, poll the structured sources on a cadence; store new items with
  read/unread/starred state and a per-subscription last-checked timestamp; dedup across
  subscriptions.
- Triage UX (speed IS the product — replicate Fraser's workflow): a dense, keyboard-driven list —
  j/k to move, s to star/save, mark-read on scan; staged (titles -> abstract on expand -> open/save
  full). Persist read/unread/starred. No rich cards.
- AXIS-RELEVANCE HIGHLIGHT (augment, never filter): score each item's title+abstract against the
  user's axis embeddings (reuse axis_scoring + embeddings); HIGHLIGHT likely matches WITHIN the
  complete list, carrying the matched axis + similarity + the close-but-not-quite uncertainty tag.
  NEVER hide, filter, or reorder-away non-matches — the complete list is the anti-offloading
  safeguard. Relevance is a hint on the star step, not a gate.
- SAVE-TO-LIBRARY: one click flows the item into the library and the downstream pipeline (auto-axis
  suggest, METHODS checks). Acquiring the actual PDF is OUT OF SCOPE — save the record/metadata;
  PDF acquisition stays manual/external.
- NOTIFICATIONS: PULL-FIRST. Default is a feed you check during dead time. Any notification is
  OPT-IN, gentle, SOURCE-LEVEL ("new issues available to scan"), NEVER a per-paper AI-relevance
  push (which would break the scan rhythm and steer off the complete list).

SEARCH TAB (the lighter sibling on the same layer):
- Ad-hoc literature search over the same SourceProvider registry (PubMed/Crossref/bioRxiv from
  inside the app). Same item model, same axis-relevance highlight (hint, not filter), same
  one-click save, same keyboard triage components. On-demand query, not subscribed/polled. Reuse
  the Feed's list/triage components.

DESIGN.md PRINCIPLES TO RECORD:
- Lightweight at intake: the Feed/Search stage is triage only — fast scan, frictionless save, NO
  forced categorization. Organization happens automatically downstream (auto-axis on save). Do not
  import categorization overhead at intake.
- Discovery defaults are user-derived and user-overridable: suggestions come from the user's own
  library; subscriptions and prioritization are user-controlled; the source layer is extensible so
  one curator's mechanism isn't foisted on others.

DEPENDS ON / REUSE: the LibraryFrame tab system; the connected PubMed and bioRxiv MCPs; the crossref
adapter; embeddings + axis_scoring for relevance; the library save/import path + auto-axis. Build:
the SourceProvider registry + providers, a subscriptions/items store (alembic), and the Feed +
Search frontend tabs with shared triage components.

CONSTRAINTS:
- AI augments, never filters: the complete list is always shown; relevance is a highlight, never a
  gate or a reorder-away.
- Lightweight at intake; auto-organize downstream.
- Pull-first; notifications opt-in, gentle, source-level only.
- Structured sources primary (PubMed/Crossref/bioRxiv); raw RSS an optional supplement.
- Suggestions derive from the user's own library; never auto-subscribe.
- Source layer is a registry designed for user-added providers later (internal seam now).
- Reuse the tab system, MCPs, crossref adapter, embeddings/axis scoring, and the library save path;
  no parallel components.

TESTS:
- Subscribing to a journal (ISSN) and polling returns recent items with abstracts, deduped against a
  PubMed keyword feed for the same paper.
- The triage list is keyboard-navigable (j/k/s), persists read/unread/starred, and never hides
  non-matching items.
- Axis-relevance highlights matches within the complete list with the matched axis + uncertainty
  tag; turning relevance off changes only the highlight, not the item set.
- One-click save creates a library record and triggers auto-axis; the PDF is not fetched.
- The Search tab queries the same providers and reuses the triage/save components.
- A new SourceProvider registers without editing the Feed/Search components (registry proven).
- Any notification is source-level only; no per-paper relevance push exists.

OUTPUT: the SourceProvider registry + shipped providers, the subscriptions/items store, the Feed and
Search tabs with shared triage components, the axis-relevance highlight, the save-to-library wiring,
and confirmation the complete list is never filtered and a new provider needs no component edits.
