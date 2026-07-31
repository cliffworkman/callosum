# Security and privacy audit — document-scoped chunks

**Date:** 2026-07-31
**Increment:** 425
**Status:** PASS

## Surface

Increment 425 makes attachment/document scope explicit before registration documents can enter the chunk table.
It adds no endpoint, schema migration, parser, downloader, provider, subprocess, dependency, credential access, or
network destination. Existing paper readers now select canonical attachment roles; exact attachment and explicitly
named all-document retrieval remain available for comparison and management paths.

The audit gate fires because this is a cross-cutting architectural and privacy boundary: a failure could disclose
registration text to an external summary provider through an otherwise consented article-synthesis request, or could
misattribute registration text to the published article in local audits and search.

## Threat review

- **Cross-document disclosure / egress:** ordinary synthesis selects `article-fulltext` before any generator or
  egress-gate wrapper receives source chunks. A future preregistration attachment therefore cannot enter an external
  model call merely because general AI egress is enabled. Registration comparison may use exact attachment ids later,
  but that path does not exist in this increment.
- **Local semantic and lexical leakage:** chunk embedding can still be generated for an exact attachment, which is
  required for future bounded comparison. Ordinary vector retrieval filters candidate chunk embeddings by role, and
  the FTS5 query joins the owning attachment and applies the same article-role interpretation before ranking/limit.
- **Legacy metadata confusion:** roles are normalized at read time without destructive mutation. `primary` and null
  legacy attachments remain article full text; `supplementary-text` maps to supplement; OCR-preserved `secondary`
  maps to `other` so the scanned original cannot duplicate its searchable replacement; unknown non-null roles fail
  closed into `other`.
- **Role validation / SQL injection:** requested roles are checked against a fixed five-value allowlist. SQLAlchemy
  paths use bound expressions. The one raw FTS CASE contains only module constants; the selected canonical role is a
  bound parameter and no client string is interpolated into SQL.
- **Escape-hatch misuse:** `get_chunks_for_paper` has no default scope. Unrestricted access is deliberately named
  `get_all_chunks_for_paper`; exact comparison access is named `get_chunks_for_attachment`. An AST regression test
  rejects new ambiguous app call sites for paper chunk reads, bulk embedding, and chunk similarity retrieval.
- **Attachment selection / path safety:** the ordinary PDF selector now accepts only normalized article-fulltext PDFs.
  Explicit `attachment_id` serving remains ownership-checked by the existing audited route, so preregistration PDFs
  can later be inspected without becoming the paper's default viewer/reprocessing target.
- **Persistence and availability:** no stored roles or chunks are rewritten. Existing exports/purge and exact
  attachment reprocessing retain their explicit all-document or attachment-specific behavior. Provider failure and
  network availability are not applicable.
- **Secrets / supply chain:** no secrets are read or transmitted; no dependency is added.

## Negative-path evidence

- A single paper stores article, supplement, preregistration, and protocol chunks, while each scoped repository read
  returns only the intended rows.
- Ordinary synthesis, the paper chunks endpoint, transparency detection, article processing tier, lexical search,
  and semantic search do not consume preregistration chunks.
- Transparency deliberately retains its established article-plus-supplement evidence coverage while excluding
  preregistration/protocol documents.
- A preregistration embedding can exist locally and still cannot enter ordinary semantic retrieval.
- Legacy null/primary roles remain readable; OCR `secondary` does not enter article scope.
- Missing role arguments fail closed, and structural tests reject ambiguous new app consumers.

## Result

**Security and privacy audit: PASS.** The change reduces an existing cross-document data-flow risk and introduces no
new egress or acquisition surface. Registration discovery/acquisition remains blocked until this invariant is green;
those later increments require their own provider/SSRF/privacy audits.
