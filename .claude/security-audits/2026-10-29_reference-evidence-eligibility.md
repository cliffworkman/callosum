# Reference evidence eligibility (narrow-path demotion + duplicate-DOI ownership)

**Date:** 2026-10-29. **Trigger:** audit gate item 5 (a net-new feature spanning 3+ files and more than 300 added
lines).

**No other gate trigger applies:**
- no new API endpoint or request schema;
- no new external fetch;
- no new file-ingestion or file-write path;
- no auth logic;
- no new dependency.

## Scope

| File | Change |
|---|---|
| `app/backend/summarization/evidence_eligibility.py` (new) | Pure policy. No connection, file, network or subprocess |
| `app/backend/summarization/evidence_selection.py` (new) | Narrow-path seam. Reads `chunk_structure`, orders eligible chunks before disputed ones |
| `app/backend/summarization/pipeline.py` | Calls the seam before slicing the reading budget; fetches 3× top_k for query scope |
| `app/backend/persistence/chunk_structure_repo.py` | `structure_role_states`: a batched read with a stale reason |
| `tools/backfill_chunk_structure.py` | `doi_owners`: maps a DOI to live canonical paper(s); reports ambiguous DOI groups on stdout |

The commit also adds a research-route adapter, CLI and tests under `experiments/ask_cli_revised/focused_discovery/`
(`reference_eligibility*.py`).
- **Containment:** no application module imports them, and the CLI opens the frozen databases only with
  `mode=ro&immutable=1`.
- **Writes:** only JSON outputs, to an `--out` directory the developer supplies.
- **Network:** none.

## Threat review

- **Injection / SQL.**
  - `structure_role_states` coerces every id with `int()` before SQL and binds them through `sql_batch.in_batches`
    (SQLAlchemy `in_`, bound parameters).
  - `doi_owners` uses SQLAlchemy Core `select` only.
  - No table or column name comes from data.
- **Input validation / untrusted content.** Chunk text is extracted PDF text, so it is untrusted. It is only hashed
  (`raw_sha`) on the application path. Since the H1 fix it is no longer canonicalized there. `None` text is treated
  as empty.
- **Output encoding / logging.**
  - The two new log lines are `%d` integer counts only: no chunk text, ids, titles or paths.
  - The backfill CLI prints DOIs and paper ids of ambiguous live duplicates to local stdout. That is bibliographic
    metadata, consistent with the tool's existing output.
- **Data egress.** None. There is no network import in any changed module. The backfill stays cache-only, reading
  `external_api_cache` and `reference_instances`. OpenAlex/Crossref are not contacted. The Gemini/provider path is
  untouched.
- **SSRF / external calls.** None added.
- **Secrets.** None read or written.
- **Resource caps.**
  - Query scope searches top_k × `ELIGIBILITY_OVERFETCH` (3), which is bounded.
  - The selected-papers scope already ranks every chunk of the selected papers. The seam now adds one batched
    metadata read plus a sha256 per candidate: 0.51 s median for 18,970 candidates after the H1 fix, against 25 s
    before it.
  - The pure matcher (`map_region`) is used only by the research route. An adversarial repetitive input
    (4,000 × "a" vs 3,000 × "a" + "b") completed in 0.02 s.
- **File-path safety.** No path construction added.
- **Integrity / fail-closed behaviour.**
  - A stale label (derivation version, text hash or chunk version changed) is ignored and logged, never reused.
  - A label never withholds or deletes a chunk; it only reorders.
  - A library without `chunk_structure` rows is an exact no-op (tested).
  - DOI ownership never assigns a live paper's references to a soft-deleted or merged row. An unresolvable merge
    chain yields no owner.
- **Supply chain.** No new or changed dependency.

## Negative-path checks (run 2026-10-29, read-only against the frozen MiniLM library)

1. **20,000 ids with the connection's `SQLITE_LIMIT_VARIABLE_NUMBER` lowered to 999:** returned 19,677 rows with no
   error, so batching holds below even the pre-3.32 default.
2. **A non-integer id (`"1; DROP TABLE chunks"`):** rejected with `ValueError` before any SQL is issued.
3. **Unknown and negative ids:** return `{}`; absence means "no label", never "eligible because verified".
4. **Log content:** one demotion line, counts only. The only chunk texts that occur in it are bare page numbers
   ("9", "30", "39") coinciding with the digits; no chunk text of 10 or more characters appears.
5. **An empty-text candidate:** handled, and returned unchanged.
6. **Static scan of the changed modules** for `httpx`/`requests`/`socket`/`urllib`/`subprocess`/`pickle`/`eval`/
   `exec`: none.
7. **Adversarial repetitive text through the matcher:** 0.02 s.
8. **Egress while disabled:** no egress code path was added, so there is nothing to gate. The provider consent gate
   is unchanged.

Unit tests also cover the DOI cases: merged duplicate, merge chain, live duplicate group, and a deleted paper
without a survivor (`tests/test_backfill_doi_owners.py`).

## Residual risks (documented, accepted as product limitations rather than security risks)

- Anchored labels have about 77% precision. A genuine Results passage can be demoted behind other evidence, but
  it is never removed.
- A disputed fallback is visible only in the backend log, not in the UI or the persisted synthesis.
- A live backfill applying the DOI fix needs a separate authorization and a backup first.

**Security Audit: PASS**
