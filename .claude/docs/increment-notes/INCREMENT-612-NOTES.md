# Increment 612 — Reference-rescue memo keyed by text, not row identity

Branch `integrate/inc607-608-ask`, on inc 611 `7af0b676`. Not pushed, not merged. Found by the cache preflight of the
held-out evaluation (`C:\Users\cliff\callosum-data\experiments\source-role-heldout-20261030\`), before any
evaluation document was used.

## Implemented
- `app/backend/summarization/reference_rescue.py`: the per-process rescue memo was keyed by `(chunk_id,
  chunk_version)`. Two independent libraries can share both while holding different text, so a decision made for one
  was inherited by the other in the same process (reproduced: a genuine reference entry in library B was admitted
  because library A's conclusion at the same id/version had been rescued). The memo is now keyed by a 16-byte
  BLAKE2b fingerprint of the text itself; the narrow query selects `(id, text)` for labelled rows.
- `tests/test_reference_exclusion.py::test_rescue_cache_never_crosses_databases` (fails on inc 611, passes now);
  `tests/test_source_role_repair.py` memo test updated to the new signature `rescue_decision(text)`.

## Key technical detail
The decision is a pure function of the text, so a text key is correct across database replacement, re-extraction and
version changes with no invalidation logic. Cost is unchanged: the (id, text) narrow query plus hashing is a median
0.213 s on the 13,404 labelled chunks of the 251-paper replay copy, equal to the old (id, version) query. The rescued
set on that copy is unchanged (236).

## Manual verification script
1. `pytest tests/test_reference_exclusion.py -k crosses -q` (on 7af0b676 it fails `[True, True] == [True, False]`).
2. Confirm 236 rescued chunks on the inc-611 replay copy (read-only).

## Pytest
90 passed (focused: reference exclusion, source-role repair/migration, Ask 607/608 integration, faceted, sql_batch).
