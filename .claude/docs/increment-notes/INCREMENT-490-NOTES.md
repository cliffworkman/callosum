# Increment 490 — batch Critical Read local inference

## Implemented

- `app/backend/methods/critical_review.py` now encodes every bounded claim scope in one ordered call, performs the
  unchanged per-claim/top-k retrieval, records explicit scope/claim/hit positions for every usable passage, and
  classifies the complete ordered claim/passage collection through one batch stance call. Single-paper and WIP use
  this shared path; honest WIP progress now advances once the batch completes instead of replaying item progress.
- `app/backend/methods/critical_review_set.py` constructs all paper scopes first, so an entire selected set uses one
  claim-embedding call and one NLI call rather than one batch per paper. The hard bounds remain 12 papers, 12 claims
  per paper, and top-k 5 (at most 144 embeddings and 720 pairs); the underlying model APIs internally minibatch.
- `app/backend/summarization/verification.py` extends the stance scorer with `classify_stances`, while the shared
  dispatcher falls back to the existing single-item interface for injected/custom scorers. `NLIStanceScorer` keeps
  its previous fail-closed `None` behavior for the full failed batch and `classify_stance` remains compatible.
- Grounded single-paper and set Tier-2 candidate verification collects accepted unique/verbatim candidates first,
  batches only those NLI pairs, and reconstructs the unchanged output order.

## Key technical detail

Batching changes inference shape only. Ordered lists—not dictionaries, sets, completion order, or concurrency—carry
each vector back to its claim and each NLI row back through `(scope_index, claim_index, hit_index)`. Retrieval still
runs separately for each corresponding vector with the same candidate embedding ids and top-k. Candidate selection
still replaces a claim's best contrast only on strictly greater confidence, so equal-confidence tie behavior remains
first-hit-wins. Thresholds, labels, probabilities, evidence text and locators, scopes, ordering, persistence, and
public response models are unchanged.

Principles 1, 2, 4, and 8 and the THEORY disagreement contract remain controlling: every signal retains the same
verbatim paired evidence and visible local stance. The declined shortcut was deduplicating, reordering, or dropping
pairs for speed; repeated claim and passage text therefore remains repeated at its original positions.

## Manual verification script

1. Run a single-paper Critical Read against a paper with 12 extracted claims and at least five eligible retrieved
   passages. Instrument injected models and confirm one 12-item embedding call, 12 retrieval calls, and one 60-pair
   NLI call; compare the returned evidence order and confidences to the pre-change receipt.
2. Run WIP Critical Read on an exact manuscript snapshot. Confirm the job reports preparation, then completed local
   comparison, and persists the same snapshot/provenance/evidence receipt without draft embeddings.
3. Run set Critical Read for 2, 4, 8, and 12 papers. Confirm each run makes one embedding-model call and one NLI-model
   call while retaining per-paper contested-claim ordering.
4. Generate two grounded Tier-2 critique candidates plus one ungrounded candidate. Confirm one two-pair NLI batch,
   unchanged candidate order, and continued rejection of the ungrounded item.

## Verification

- Focused Critical Read/WIP/candidate/stance suite → **65 passed**.
- Broader summarization/NLI/citation compatibility suite → **38 passed**.
- Final-tree full suite: `pytest -n auto -q` → **2349 passed, 3 skipped in 1261.98s (0:21:01)**.
- Warm real-CPU benchmark (cached `all-MiniLM-L6-v2` + `cross-encoder/nli-MiniLM2-L6-H768`, three isolated
  counterfactual trials): 12 one-item embeddings median **0.2363 s** vs one batch **0.0566 s** (4.18×); 60 one-pair
  NLI calls median **3.3223 s** vs one batch **1.6041 s** (2.07×). Maximum vector difference was `9.01e-8`, maximum
  stance-probability difference `9.54e-7`, with zero label changes.
- Five warm current-flow 12-claim/60-pair trials: median **1.7005 s** total local search, **0.0716 s** embedding,
  **1.6250 s** NLI, exactly one embedding call and one NLI call.
- Set benchmark medians (one embedding + one NLI call each): 2 papers/24 pairs **0.909 s**; 4/144 **4.444 s**;
  8/480 **14.543 s**; 12/720 **21.681 s**.

## Boundaries

No model registry/lifetime reuse, provider HTTP/Gemini client reuse, synthesis overview change, output-token cap,
model routing, new cache, local concurrency, model/threshold/top-k change, API/frontend contract, schema, or migration
is included. The benchmark harness was temporary under `.claude/` and removed after use; it made no provider call.
