# Product Scope

Callosum is a local-first, AI-assisted reference manager for scholarly PDFs. The current product thesis is already implemented in MVP form: generated synthesis is only useful when every citation is independently checked against the source PDF and displayed with evidence.

The guiding product principle is **reference manager first**. Verified synthesis is the crown feature, but the app must also work as a credible day-one library manager.

## Current Users

- Researchers and students managing personal or lab-scale scholarly PDF libraries.
- Users who need inspectable evidence, local control, and low recurring cost.
- Users willing to bring their own API key for optional cloud generation while keeping local verification as the source of trust.

## Shipped

- Zotero import for records, PDFs/attachments, collections, tags, notes, and annotations.
- PDF ingest, PyMuPDF text extraction, page/bounding-box provenance, chunking, and PDF viewer overlays.
- Local sentence-transformers embeddings, `sqlite-vec` vector search, and local retrieval.
- User-defined semantic axes with scoring, manual assignment overrides, axis merge/delete/sort/filter, optimal-axis suggestions, and local/Gemini-assisted term/label suggestion where gated.
- Tags, tag filtering, manual tag editing, Zotero tag import, Crossref `subject` import as `keyword:crossref`, and local c-TF-IDF tag suggestion.
- Citation-grounded synthesis over queries, selected papers, or cluster scopes, with local post-generation verification and visible evidence.
- Citation export as BibTeX, RIS, and CSL-JSON.
- Duplicate detection with local layered scoring, review modal, soft-delete resolution, persistent dismiss/undismiss.
- Library sort/filter/select, multi-select summarization/export/delete, Trash/restore, and permanent delete for trashed papers.
- Editable Details pane, DOI correction, Crossref re-resolve, JATS abstract cleanup, and user-edit provenance.
- Help modal, optional AI help assistant, Settings modal, and dark mode.

## Out Of Scope Today

These are tracked in `.claude/docs/INCREMENT-BACKLOG.md` and `.claude/docs/future-tracks/`, not implemented MVP behavior:

- Cloud sync, collaboration, accounts/auth, or hosted multi-user deployment.
- Desktop packaging/Tauri shell and OS keychain storage.
- Mendeley direct encrypted-database import; planned import coverage is through bridge/export formats.
- BibTeX/RIS/CSL-JSON import.
- Folder watch/refresh, managed PDF file deletion, and full attachment merge semantics.
- Manual library merge of duplicate records.
- Word/LibreOffice citation plugin.
- Highlight-to-suggest or highlight-to-evaluate authoring tools.
- Free legal full-text acquisition resolver chain.
- OpenAlex/Semantic Scholar/GROBID/Unpaywall production integrations.
- THEORY/METHODS panes, findings subsystem, statcheck, retraction/transparency/system-facts modules.
- Literature discovery Feed/Search tabs, gap-finder, My Publications, and user-authored modules.

## Success State

For a real scholarly library, Callosum can import records, extract PDFs, embed and organize papers locally, manage tags/duplicates/trash/details, and generate synthesis where each sentence is either verified against visible source evidence or flagged for review.
