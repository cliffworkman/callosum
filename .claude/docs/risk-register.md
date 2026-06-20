# Risk Register

This register reflects the current MVP, not the original planning skeleton.

## Active High Risks

- Citation verification is probabilistic. Mitigation: keep retrieval, quote, and support confidence separate; show the quote/page/status; flag anything not fully verified.
- PDF extraction varies by publisher, scans, rotated pages, tables, and figures. Mitigation: PyMuPDF extraction records page/bbox provenance; coordinate precision prevents approximate regions from appearing exact.
- Data egress can expose library text. Mitigation: Gemini summary generation is off by default and must pass `CALLOSUM_ALLOW_DATA_EGRESS`; egress gates wrap injected and default providers.
- External metadata APIs can drift or fail. Mitigation: Crossref responses are cached in `external_api_cache`, response shape is normalized, and DOI re-resolve fails gracefully.
- Zotero schema drift can break import. Mitigation: importer assumptions are isolated under `integrations/zotero/` and app import writes into canonical CSL-JSON plus projected columns.
- Duplicate detection is heuristic. Mitigation: it is local, flag-only, reviewable, dismissible, and resolves by Trash rather than destructive merge.
- Permanent delete is irreversible for app records/vectors. Mitigation: only reachable from Trash and intentionally does not delete user PDF files from disk.
- Version drift can stale summaries and mappings. Mitigation: chunks, embeddings, summaries, mappings, and verification rows carry extraction/chunking/embedding/verification versions.
- PyMuPDF licensing affects redistribution choices. Mitigation: extraction is kept behind `pdf_processing` boundaries so a fallback can be evaluated before packaged distribution.

## Security And Deployment Risks

- Callosum currently assumes localhost personal use. There is no auth, no account model, and no rate limiting.
- Pre-public or hosted deployment requires an explicit security pass for auth, rate limiting, CORS/origin posture, file ingestion limits, secret storage, logging, and abuse/resource-exhaustion controls.
- The source-exposure threat model for publishing the repository is covered by `.claude/security-audits/2026-06-20_pre-github-fullsweep.md`.
- Secrets must remain environment-provided today (`GOOGLE_API_KEY`, `CALLOSUM_DB_URL`). BYO-key UI/keychain storage is future work.

## Standing Mitigations

- Keep all SQL parameterized through SQLAlchemy Core.
- Validate PDFs and external responses at boundaries.
- Keep Gemini limited to summary generation unless a future feature passes the Principles and egress gates.
- Preserve provenance: imported/user/synthesis annotations, tag import sources, user-edited metadata, and system-fact vocabulary for future findings.
- Run `pytest` and relevant focused tests after code changes; current MVP baseline is Increment 73 with 279 passing tests per the session briefing.
