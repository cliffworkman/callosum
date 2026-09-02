# Increment 565 Notes — OpenAlex downstream failure semantics and test DB reuse

## Implemented

- Followed-author Feed refreshes now require a complete OpenAlex author-work result. A partial page scan raises
  into the Feed refresh boundary, which preserves the prior items and last-successful-poll timestamp.
- Citation concentration for library papers, selected papers, and WIP manuscripts now uses strict OpenAlex work,
  reference, and field-sample reads. An unavailable or malformed provider response produces an explicit job error
  (or HTTP 503 for the synchronous selected-paper audit), never a completed empty audit.
- Overlooked-work, citation-neighborhood, and journal-discovery paths now use strict OpenAlex topic/work/source
  reads. Incomplete discovery is reported as an error or partial provider result rather than authoritative absence.
- OpenAlex funding lineage now reports `partial` when its related-work lookup is unavailable while the independent
  keyword search succeeds. Its keyword cache also follows the shared 24-hour OpenAlex freshness policy.
- Strict candidate-source parsing rejects malformed HTTP-success payloads instead of normalizing them to an empty
  journal pool.
- External OpenAlex reads in the selected-paper and WIP citation audits use read connections and self-committing
  cache clients rather than holding SQLite writer transactions for the duration of provider I/O.
- The test database fixture now migrates one template database per pytest worker and copies it for each test. This
  preserves per-test isolation and the real Alembic schema while avoiding more than a thousand repeated migration
  chains. Migration-specific tests continue to build and exercise their own databases.

## Scientific and product boundary

Provider unavailability is operational uncertainty, not evidence that no references, journals, related works,
funding lineage, or followed-author publications exist. Existing complete empty results remain valid.

## Concurrent-commit boundary

Increment 564 edited the same citation-neighborhood implementation and regression-test module for its NLI batching
work, so those two OpenAlex hunks landed in commit `770dfca` during the shared-worktree session. The remaining
OpenAlex changes and the explicitly authorized uncommitted CI fixture are recorded by this increment; Increment
564's note and history remain unchanged.

## Regression coverage

Focused tests cover:

- incomplete followed-author refresh rejection;
- citation-equity and WIP outage error states;
- selected-paper audit HTTP 503 behavior;
- publisher discovery outage and malformed-success rejection;
- funding-lineage partial status; and
- citation-neighborhood partial status.

## Validation

- Residual affected suites: **125 passed**.
- Malformed-source focused rerun: **2 passed**.
- Fresh parallel root suite, including the copied-template DB fixture: **2745 passed, 3 skipped** in 651.16 seconds.
- Ruff format/check, the ratcheted Bandit scan, Tach boundaries, 600-line budget, and `git diff --check`: passed.
- The optional pre-commit wrapper was unavailable in the active Anaconda environment; every configured local hook
  command was run directly instead.
