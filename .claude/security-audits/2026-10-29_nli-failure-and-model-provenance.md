# Security audit — NLI failure fails closed; synthesis model provenance (inc 609)

**Date:** 2026-10-29 · **Branch:** `integrate/inc607-608-ask` (local, unpushed) · **Triggers:** response-schema change on
`/summarize/{job_id}`, `/summaries/{id}`, `/summaries/{id}/reverify` (new `model_provenance` field); changed error
contract of reverify (new 503). No new endpoint, external fetch, file path, dependency or auth logic.

## Threat review

- **Scientific-integrity failure mode (the point of the change).** Before: an app-resolved MiniLM2 support scorer that
  raised during inference silently substituted embedding cosine, which was read against the 0.55 NLI support threshold
  and persisted as an ordinary verification (invariants #1/#4). After: no app-resolved support scorer has an embedding
  fallback. `NLIInferenceError` fails the Ask job with nothing persisted (the verify+persist transaction rolls back),
  and makes reverify return 503 before any write. Tests replace `EmbeddingSupportScorer.score` with an assertion so
  any hidden substitution fails loudly.
- **Output encoding / information disclosure.** `model_provenance` exposes model ids, revisions and profile labels
  only, all public model identifiers already shown in Settings. It contains no path, secret, prompt or passage. The
  job error now includes the exception text from the NLI runtime (as the generic handler already did); it may name
  the model id or a cache-miss reason, never library content. The UI renders the values as React text, not HTML.
- **Provenance honesty.** Values are read only from the run's `scope_ref_json`. A missing record returns
  `recorded=false` with no names, rather than a default. Imported syntheses return `None`, since the import never
  carries the sender's provenance. Re-verification records the local models it actually used. Unknown profile keys
  in a stored record yield `label: null` and `experimental: false`, keeping the raw `model_name`. Non-string values
  are dropped rather than coerced.
- **Input validation / injection.** No new input. `scope_ref_json` is read through `isinstance` guards. No SQL or
  filesystem path is built from it.
- **Egress / resources.** Unchanged: all inference stays local, and no model is loaded by the response path.

## Negative-path checks (concrete results, all fake models)

| Check | Result |
|---|---|
| MiniLM2 load fails (`OSError` cache miss) during Ask | job `error`, detail starts "Citation verification failed, so no synthesis was saved."; 0 summary rows |
| MiniLM2 runtime raises mid-session (after a good run) | second job `error`; first synthesis still `verified`; 1 row total |
| Cosine scorer called on any failure path | never (assertion-trap scorer) |
| DeBERTa inference raises | job `error`, original message in `detail` (608 test, still passing) |
| Reverify while NLI raises | **503**, "was not changed"; summary still `imported` |
| Reverify after recovery | converted; `model_provenance` = MiniLM / MiniLM2 |
| Row with no provenance | `{"recorded": false, "retrieval": null, "verification": null}` |
| Imported synthesis | `model_provenance: null` |
| `default_support_scorer` (tools/tests only) | fallback retained; no app route reaches it (pinned) |

**Security Audit: PASS**
