# Security audit — local WIP critical read

**Increment:** 445
**Date:** 2026-08-03
**Status:** COMPLETE — PASS

## Scope and trust boundary

This increment adds an explicit local-only WIP job at
`POST /wip/manuscripts/{manuscript_id}/critical-read`, polling at `GET /wip/critical-read/{job_id}`, and a
Synthesize → Critique manuscript surface. The write route inherits `require_local_wip`, read-only write blocking,
the registered-primary resolver, trusted-child path handling, and existing primary-file extraction ceilings.

The unpublished manuscript is never converted into a Library paper. One exact-snapshot receipt uses the existing
generic `tool_runs` / `wip_tool_runs` tables. No migration, provider client, public endpoint, remote destination,
secret, device identifier, automatic run, or automatic retry is added.

## Data and model boundary

- Claim extraction retains at most 12 unique verbatim sentences, each 20–1000 characters. Non-PDF synthetic pages
  are cleared. The exact claims remain local and are visible in the local receipt.
- Draft query embeddings are transient: the path calls `encode_texts` and vector `search` only. It has no vector-add
  call, paper-row shim, or embedding-table write. Tests pin the embedding-row count.
- The server selects eligible embeddings by exact model name/version/normalization, live paper, chunk target, and
  canonical `article-fulltext` document role. Supplement, preregistration, other-role, deleted-paper, mismatched-
  model, and even out-of-allowlist vector-backend hits are rejected.
- At most five Library passages per claim are retrieved. Only a local NLI `contrast` at confidence ≥0.55 is shown.
  `None`, support, mention, below-threshold, unavailable-model, and unresolved-passage states do not become a claim.
- Paired evidence is verbatim draft claim + verbatim Library chunk with paper, attachment, page, stance, confidence,
  and model/vector provenance. React renders it as text; no raw HTML, URL, Markdown, or executable formatting enters.

## Persistence, status, and errors

- The receipt composes a fixed allowlist of WIP method tools. A method receipt is available only when its relevant
  content hash equals the prepared snapshot hash; old receipts are described as unavailable, never silently reused.
- Contrasting evidence creates no `wip_findings` row, severity, score, rank, grade, correctness result, or author
  accusation. No silence is described as a clean bill of health.
- Status receives only `{manuscript_id}` through `Job.nav`, merges a server-owned Synthesize/Critique destination,
  and labels compute as Local AI. The Status response model never reads or serializes `job.result`; tests reject
  manuscript claims, Library passages, and local paths in that response.
- Expected primary-file failures expose only bounded allowlisted local validation text. Model/retrieval
  unavailability becomes an inspectable partial receipt. Unexpected errors use one fixed generic message and fixed
  activity copy; raw exceptions, model paths, manuscript text, and job results are not logged or returned.
- Duplicate active jobs for the same manuscript are reused. The UI disables a running start, retains the previous
  receipt on failure, and performs no silent or unbounded retry.
- Immediately before persistence, the job re-resolves the registered primary file and rechecks its file id,
  whole-file hash, and extracted-text hash against the prepared basis. A primary-selection or content change stops
  the job with fixed retry copy and writes no receipt, so an old async basis cannot masquerade as current.

## Egress and deferred provider critique

There is no provider import or remote HTTP call. The only comparison inputs are local manuscript extraction, local
Library embeddings/chunks, and local models. The WIP UI deliberately omits the paper Tier-2 generation control and
states that any future provider critique needs a separate exact transmission preview and explicit consent. The
paper critical-read and provider-candidate routes remain unchanged.

## Verification

Hermetic backend tests cover grounded paired evidence, snapshot staleness, current-vs-old method receipts, transient
embeddings, model/document-role/live-paper scope, out-of-scope vector hits, no claims, empty corpus, NLI unavailable,
embedding failure, generic persistence failure, primary/missing ids, bounded extraction, source locators, and Status
privacy. A mid-job real-file mutation test pins the pre-write identity revalidation and absence of a receipt.
Frontend wiring tests pin the WIP/provider split and exact attachment target. The Chromium path uses the real
local job, renders it in WIP Critique at desktop/mobile width, and records no outbound request or page error.

Final full-suite, QA-map, dependency, Bandit, secret-pattern, and diff results are recorded exactly in
`INCREMENT-445-NOTES.md`.

## Result

**Security Audit: PASS.** Residual risks are local model false positives/negatives and bounded compute cost over a
user-selected maximum-size draft plus an existing local Library corpus. Neither risk adds egress, a persistent draft
fingerprint, remote abuse surface, secret, correctness verdict, or automatic action.
