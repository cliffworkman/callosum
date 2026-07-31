# Increment 425 — document-scoped chunk invariant

**Date:** 2026-07-31
**Status:** implemented; acceptance gate complete

## Outcome

The architectural prerequisite for registration acquisition is now enforced. A paper may carry and chunk an article,
supplement, preregistration, protocol, and other attachments without letting non-article documents silently enter
ordinary synthesis, search, critique, processing state, or article-facing APIs.

No registration discovery, network resolution, acquisition, commitment extraction, or comparison was implemented in
this increment. Those increments remain blocked on this invariant and can now build on exact paired-document reads.

## Architecture and decisions

- `app/backend/persistence/document_roles.py` owns the controlled vocabulary: `article-fulltext`, `supplement`,
  `preregistration`, `protocol`, `other`. It normalizes legacy metadata at read time, avoiding a destructive migration:
  `primary`/null → article, `supplementary-text` → supplement, and OCR `secondary` → other.
- `get_chunks_for_paper(..., document_roles=...)` has no default. `get_chunks_for_attachment` supports an exact
  comparison document; `get_all_chunks_for_paper` is the visibly named escape hatch for true management/export use.
- Ordinary synthesis, re-verification, citation suggestions, critical review, workbench drafting, full-text search,
  semantic retrieval, processing tier, text health, paper chunk counts/API, OCR eligibility, and the validation harness
  now state article scope explicitly.
- Statistical/Bayesian/LMM/meta-analysis and transparency tools explicitly retain article-plus-supplement coverage,
  preserving their established attachment-aware evidence behavior while excluding registrations and protocols.
- Statcheck table extraction and its cache fingerprint apply the same role boundary even though tables are read from
  attachments directly rather than from chunks.
- Exact chunk ids remain valid for attachment processing and future comparison embedding; ordinary similarity search
  independently filters by document role, so merely storing an embedding never makes it globally retrievable.
- The default PDF selector is article-scoped. A registration can still be opened through the existing ownership-safe
  `attachment_id` route, but cannot become the ordinary paper PDF/reprocessing target by fallback.

## Acceptance tests

`tests/test_document_scope.py` pins:

- simultaneous article/supplement/preregistration/protocol storage and separate retrieval;
- exact attachment and explicit all-document APIs;
- article-only ordinary synthesis and paper chunk responses;
- transparency's article-plus-supplement scope without registration contamination;
- lexical and semantic search isolation even when a preregistration embedding exists;
- registration-only chunks not promoting the paper's article processing tier;
- legacy null/primary compatibility and OCR-secondary exclusion;
- fail-closed missing scopes and an AST guard against new ambiguous app consumers.

Existing one-primary-PDF behavior and the deliberate Methods supplement evidence paths remain covered by their prior
test suites.

## Security, privacy, and epistemic boundary

- Audit: `.claude/security-audits/2026-07-31_document-scoped-chunks.md` — **PASS**.
- No network, egress, LLM, auth, secret, file-write, dependency, endpoint, or schema surface was added.
- The boundary prevents registration text from being mislabeled as article evidence locally or included in a
  consented-but-unintended external synthesis payload.
- The feature remains a substrate for evidence-bound comparison, never an overall compliance/integrity/risk score or
  an author-level judgment. Non-detection will remain non-adjudicative in later increments.

## Rollback

Revert Increment 425's code/tests/docs commit. No Alembic downgrade or data repair is required: the increment does not
rewrite attachment roles, chunks, embeddings, or other persisted records. Rolling back would restore ambiguous
paper-level reads and must therefore also keep registration acquisition disabled; attaching preregistration chunks on
the old code would reintroduce the contamination risk this gate closes.

## Verification

- New acceptance suite: **7 passed**.
- Persistence/embedding/full-text/transparency/synthesis/re-verification slice: **65 passed**.
- Methods/critical-review/citation/workbench/OCR/text-health/document/PDF/paper regression slice: **278 passed**
  after preserving transparency's established supplement scope.
- Focused transparency/evidence re-run: **31 passed**.
- Ruff and 419-file application line budget: pass.
- `ruff format --check .`: **560 files already formatted**.
- Full suite: **1720 passed, 1 skipped** in **825.63s** (`pytest -n auto -q`).
