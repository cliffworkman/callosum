# Increment 495 — exact pre-slice beyond-library stance inference

## Implemented

- Beyond-library suggestions now finish the existing complete-set provider merge, DOI/PMID/title deduplication,
  relationship resolution, library exclusion, and exact stable ranking before stance inference.
- Only abstract-bearing members of the exact returned slice receive NLI. They retain sequential one-pair inference
  and are scored in original construction order, then emitted in final ranked order.
- Ranking still uses relationship presence, descending stored/rounded `metadata_overlap`, lowercase title, and
  Python stable-sort order. Abstract-less returned candidates remain present without stance and are not backfilled.
- Discarded tail candidates no longer invoke the scorer. A failure that exists only in discarded work can no longer
  fail a valid response; scorer failures for selected candidates retain their existing behavior.

## Correctness coverage

- Focused tests compare the optimized response against an evaluate-all reference and protect candidate identity,
  order, metadata, provider/source aggregation, stance presence/value, scorer call order, and result limits.
- Boundary coverage includes DOI, PMID, and normalized-title deduplication; later-duplicate metadata filling;
  relationship precedence; complete stable ties; rounded-overlap ties; already-library exclusion; missing abstracts;
  disabled/missing/injected scorers; selected failures; discarded-tail failures; and provider request/status behavior.

## Performance receipt

- A three-trial, same-process warm benchmark used the production local CrossEncoder, four PyTorch threads, one
  shared model instance, sequential one-pair calls, and privacy-safe provider-shaped composite inputs. At limit 20,
  40 candidates fell from 29 calls / 3.9718 seconds to 20 calls / 2.7595 seconds (30.5%); 60 candidates fell from
  43 calls / 5.8434 seconds to 20 calls / 2.6683 seconds (54.3%). At the normal frontend limit of 5, 40 candidates
  fell from 29 calls / 3.9025 seconds to 5 calls / 0.6464 seconds (83.4%). Ten candidates with no avoidable calls
  were unchanged at 1.0819 versus 1.0820 seconds. Maximum probability delta was 0.0 with zero label differences.
- No provider traffic was made. Provider behavior, NLI model identity, tokenizer, thresholds, and batch granularity
  are unchanged; the optimization removes only discarded NLI pairs.

## Validation receipt

- The focused pre-slice and existing citation-suggestion suite passed 33 tests after final formatting. A 240-test
  parallel affected set covering citation APIs/saved state, providers, provider/model runtimes, PubMed, and frontend
  assembly passed. Ruff format/check, Bandit, Tach, the 560-file line budget, and `git diff --check` passed.
- The full parallel root-suite attempt reached its explicit 20-minute command bound without returning an aggregate;
  it is reported as incomplete, not passed. No individual failure output was emitted before the harness terminated.

## Principles and boundaries

LATENCY.md Principle 4 remains controlling: measured workload shape determines execution policy. Citation suggestion
retains sequential one-pair inference because it is faster than batching on measured workloads. This increment only
narrows the evaluated set after the complete candidate set has already determined exact response identity and order.
