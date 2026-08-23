# Increment 493 — synthesis generation-cache identity hardening

## Implemented

- `GenerationCacheIdentity` gives synthesis generation one explicit, versioned semantic identity covering generator
  and prompt version, provider roster id, exact model, resolved wire/API mode, normalized endpoint, fixed wire-level
  request semantics, non-reversible credential identity, and Gemini SDK environment identity where applicable.
- Stored cache signatures contain only `summary-generation-v2` plus a SHA-256 digest. Raw API keys, bearer tokens,
  credentials embedded in endpoint URLs, and endpoint text are never persisted or logged by the cache.
- The outer summary input hash now includes every ordered source field emitted into the generation prompt
  (`chunk_id`, `paper_id`, page bounds, and text) plus `chunk_version` and scope. Source order remains significant.
- The versioned outer key makes every legacy under-specified row unreachable. Rows are left intact; a safe one-time
  miss is preferable to migrating an entry whose missing configuration cannot be reconstructed.
- Provider request identity is resolved from the same helper the live completion path uses. Trailing slashes and an
  explicitly specified builtin default endpoint normalize identically, while provider, endpoint, wire, model,
  prompt, source, fixed request-parameter, credential, or relevant Gemini environment changes miss.

## Key technical detail

Cache identity is intentionally stricter than provider-client runtime identity. Raw HTTP requests can share one
connection pool across API-key rotation because authorization is request-scoped. Cached generated output cannot make
that assumption: an arbitrary compatible endpoint may use the credential to select a different tenant or deployed
model behind the same endpoint/model alias. The cache therefore fingerprints credentials without storing them.

Principles 1, 8, and 10 and the synthesis worked example remain controlling. The declined shortcut was treating
fresh local verification as proof that cached wording came from an equivalent provider configuration. Verification
protects evidence support; it does not retroactively make provider provenance or wording configuration-identical.

## Verification

- Cache identity tests cover same-configuration hits; provider, endpoint, wire, model, prompt, source, fixed
  generation-parameter, credential, and Gemini-environment misses; endpoint equivalence; legacy-row isolation; and
  raw-secret non-disclosure: **16 passed**.
- Existing synthesis tests continue to prove generation-cache hits skip the provider while local citation
  verification reruns. The final cache/provider/runtime/synthesis focused set passed **64 tests**; an earlier
  expanded settings/verification/long-poll set passed **152 tests** before the final metadata-only hardening.
- Final-tree full parallel suite: **2415 passed, 3 skipped in 1454.99 s (0:24:14)**.
- Ruff format/check, Bandit, Tach module boundaries, the **557-file** line budget, and `git diff --check` passed.
- Final-tree local warm sanity benchmark: 5,000 identity builds had **0.0523 ms median / 0.1171 ms p90**; 1,000
  SQLite cache hits had **0.3372 ms median / 0.6087 ms p90**. The fake generator ran once and provider-client constructor
  counts remained HTTP **0**, Gemini **0**.

## Boundaries

No prompt, request payload/header/URL, provider routing, generation parameter, provider-client lifecycle,
verification, evidence mapping, overview, transaction, persistence schema, API, frontend, or user-visible behavior
changed. No migration, provider request, new dependency, or security-boundary expansion is included.
