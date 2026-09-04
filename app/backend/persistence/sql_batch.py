"""Bounded batching for `IN (...)` id lists.

SQLite caps the number of host parameters in one statement (`SQLITE_MAX_VARIABLE_NUMBER`). That cap
is a **build-time property of the interpreter's SQLite**, not a fixed constant, which is what makes
it such a good trap:

- the development interpreter used on this project reports **250,000**;
- the CPython runtime shipped inside the packaged desktop app reports the upstream default **32,766**.

So an id list that is comfortably fine for the maintainer can fail for a user on the same code and
the same library size. That is exactly how ``Synthesize -> Ask`` failed for the first person with a
genuinely large library (716,670 chunks) in a path that had never once failed in development.

Batching removes the dependence on that limit entirely rather than trying to discover it at runtime:
a batch of 900 is below even the pre-3.32 SQLite default of 999, so it is safe on any build we could
plausibly run on, and the per-batch overhead is negligible against an indexed lookup.

Callers must treat results as **unordered across batches** and re-establish their own ordering, since
each batch is a separate statement.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence

# Below the pre-3.32 SQLite default of 999, so this holds on every build, not just modern ones.
SQL_VARIABLE_BATCH = 900


def in_batches(values: Sequence[int], size: int = SQL_VARIABLE_BATCH) -> Iterator[list[int]]:
    """Yield ``values`` in chunks small enough to bind as `IN (...)` parameters on any SQLite build.

    An empty input yields nothing, so a caller's ``for batch in in_batches(...)`` loop naturally
    produces an empty result rather than a statement with an empty `IN ()`.
    """
    if size < 1:
        raise ValueError("batch size must be at least 1")
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def batched_rows(execute, values: Iterable[int], size: int = SQL_VARIABLE_BATCH) -> list:
    """Run ``execute(batch)`` over each batch of ``values`` and concatenate the results.

    ``execute`` receives one list of ids and returns an iterable of rows. Ordering across batches is
    the caller's responsibility (see the module docstring).
    """
    ordered = list(values)
    collected: list = []
    for batch in in_batches(ordered, size):
        collected.extend(execute(batch))
    return collected
