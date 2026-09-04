# Increment 575 Notes — we asked the model for more than we allowed it to say

## The report

Vasiliki, on Local AI, asked a broad citation-heavy question — *"What neural findings have been
reported for fascination, comfort, hominess, or preference in built environments? Separate findings by
construct and cite the supporting text"* — and got:

```
JSONDecodeError: Unterminated string starting at: line 32 column 30 (char 8436)
```

Her second blocked synthesis in two days.

## Root cause: the schema and the token ceiling contradicted each other

`_PRIMARY_SYNTHESIS_SCHEMA` permits `maxItems: 7` claims × `maxItems: 3` citations = **21 quotes**, and
`quote` was `{"type": "string"}` — **no `maxLength`**. The prompt's "No quote may exceed 80 words" was
advisory prose that the grammar did not enforce.

Measured against what the provider actually allowed:

| | chars | tokens (at a pessimistic 3.5 ch/tok) |
|---|---|---|
| worst answer the schema **permits** | 13,224 | **~3,800** |
| what Local AI **allowed** (`--n-predict`) | ~8,200 | **2,048** |

So truncation was not an edge case — it was the *expected* outcome for any citation-dense question.
Her failure at char 8,436 (~2,100 tokens) lands exactly on that ceiling. And because the managed path
sends a `json_schema`, generation is grammar-constrained: truncation is the *only* way that JSON could
have been malformed. The diagnosis was over-determined.

Fixed on both sides:
- `quote` gains `maxLength: 500` (~80 words) so the grammar enforces what the prompt requests.
- The ceiling moves 2,048 → 4,096, which needed **four** places to move together: Rust's
  `PREVIEW_OUTPUT_TOKENS` (→ `--n-predict`), Python's `expected_output_tokens`, the `max-output-2048`
  cache signature, and `tools/run_local_ai.py`. `_require()` fails **closed** on a mismatch, so a
  one-sided edit does not fail a test — it breaks Local AI on a real machine *after* a successful
  install. Two guards now exist: a test asserting the Rust and Python constants agree, and another
  asserting the schema's worst case fits the ceiling.

Context budget checked rather than assumed: 3,257 input + 4,096 output = 7,353 of 12,288.

Anthropic's `_MAX_TOKENS` had the identical contradiction (also 2,048) and moves too.

**This does not split the request.** A synthesis is deliberately a bounded 4–7 claim answer; the bug
was permitting one larger than the allowance. Cliff's related ask — *"I'd rather get back 16 statements
than 8 when a question needs 16"* — is a genuinely different feature, filed as **#81** with the
arithmetic showing why it needs split-and-stitch rather than another cap raise (16 claims leaves only
418 tokens of context margin; 20 exceeds the window entirely).

## Second defect: every provider told us, and we discarded it

`_complete_gemini` read only `.text`/`.usage_metadata`, dropping `candidates[0].finish_reason`;
Anthropic dropped `stop_reason`; chat_completions — **including Local AI** — dropped `finish_reason`.
So a truncated answer was indistinguishable from a malformed one, and we could not even tell which
provider had run out of room. That is why the first hour of this investigation was spent guessing at
the provider, and why Cliff had to go and ask her.

`CompletionResult.truncated` now carries it, matched across all four dialects (`length` /`max_tokens` /
`MAX_TOKENS` / `FinishReason.MAX_TOKENS` / `incomplete`) — SDKs disagree on whether it is a string or an
enum, so the match normalizes rather than pinning one representation.

## Salvage (Cliff's call, asked before building)

A response cut off mid-JSON is not garbage: the claims it *finished* are whole, and each still faces the
full local verification pipeline unchanged (invariant #1). `salvage_complete_objects` keeps them,
reusing `first_embedded_json`'s own `raw_decode` technique rather than adding a second parser — the same
"widen what can be READ without widening what is TRUSTED" rationale that function already documents.

Never silently. `TruncatedGenerationError` forces every caller to decide what to disclose, and stops
`CachedSummaryGenerator` storing a partial answer under the key a complete one would use — which would
have made one bad run permanent. The result carries `generation_truncated`, riding `scope_ref_json`
beside the existing `source_chunk_count` (no migration, and it survives a reload), and the pane says the
answer is incomplete: a partial synthesis must never read as a whole one (PRINCIPLES #6).

## The preregistered battery this tripped, and why re-freezing was legitimate

`providers.py` is one of ten inputs frozen by the **synthesis-overview-v1 qualification profile** — a
preregistered evaluation with a codebook, controls, and recorded receipts. Re-freezing it to make a test
pass would be exactly the behaviour callosum's own Methods tools exist to detect, so I stopped and asked
rather than regenerating it; Cliff's call was to document and proceed.

The diligence that makes it defensible, verified rather than asserted:

- All eight candidates (and Phase 4.1's seven) are **local publisher-owned GGUF artifacts** run through
  llama.cpp — the managed-local `chat_completions` path, never the Anthropic `messages` wire that
  `_MAX_TOKENS` governs.
- The Overview contract's own cap is `256` (`cap = 256 if contract == _OVERVIEW_CONTRACT`) and is
  **unchanged** — confirmed by diff, not by memory.
- The truncation additions read a field the response already carried and alter no request.

So no generation setting *this battery uses* changed; the freeze tripped on a file hash. `starting_head`
is deliberately left at `2ba735a` — the profile genuinely was frozen before candidate output at that
commit, and rewriting it to today's HEAD would assert a re-establishment that did not happen. Recorded
in the profile's own README, following inc 557's precedent for the same situation. The diff is exactly
three hash values plus that documentation: no fixture, control, codebook, candidate manifest, or
preregistration was touched.

## Verification

- **21 new tests** (`tests/test_truncated_generation.py`), including the reported failure reproduced
  verbatim, salvage never returning a partial object, the schema-vs-ceiling guard, and the
  cross-language constant guard.
- `cargo clippy -D warnings` + 48 Rust tests; `ruff check` + `ruff format --check`; line-budget gate.
- Full suite result recorded below. The first full run **caught 11 failures I had not anticipated** —
  the dev launcher's hardcoded 2,048 and the frozen battery — which is precisely why it is run before
  claiming done rather than after.
- Frontend built **from a clean clone**, since another session's uncommitted work is in this tree.

## Live verification against a real library on real Local AI

Cliff's call, and it earned its keep. Dev server (`run_dev.py --local-ai`, isolated settings file and
free ports so his own `:8888` session and real config were untouched) against the 219-paper testing
library, with a question built to the **same shape** as the one that broke — four constructs,
"separate findings by condition", "cite the supporting text".

**The crash does not reproduce.** Two runs, 236s and 199s, `status=done`, `generation_truncated=False`,
no `JSONDecodeError`. The descriptor confirmed `max_output_tokens: 4096` end-to-end and the *unmodified*
production validator accepted it.

**But the answer was poor, and the reason is worth more than the fix.** All four claims cited a **single
chunk**, and **0 of 4 citations verified**. Tracing the retrieval explained it: `references` is the
largest section in the corpus (5,635 of 23,875 chunks, 24%), bibliography text is keyword-dense across
many topics, and **4 of the 8 retrieved chunks were reference lists**. Handed citation lists, the model
could only produce "X has been studied using fMRI" — and the verifier correctly refused all of it.

Re-running with references excluded (the existing `sections` filter) produced substantive claims
instead — *"individuals with TBI showed increased neural activity in the insula, anterior cingulate…"* —
but **verified stayed 0/4**: better evidence, not better reasoning, because the 1.5B model still
stretched one paper across four constructs. Filed as **#82** with those measurements.

The honesty layer behaved exactly as designed throughout: a bad answer arrived flagged, with nothing
presented as verified.

## Honest limits

- **Not verified against Vasiliki's own question or library.** The crash fix is proven; whether *her*
  question now returns something useful is unknown until she retries, and #81/#82 suggest it may still
  disappoint for a different reason.
- **Two orphaned `llama-server` processes were created and cleaned up** during this verification —
  `run_dev`'s teardown does not reap the grandchild. Filed as **#83**; both were identified by their
  descriptor path and killed by PID, leaving the packaged app's own instance untouched.
- She needs a release to get this; it ships in whatever follows v0.5.7.
