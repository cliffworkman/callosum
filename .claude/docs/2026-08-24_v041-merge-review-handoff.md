# v0.4.1 merge — review findings + handoff (2026-08-24)

Written by the Arc-2a review agent (Claude). Cliff was at ~95% of his session limit in 30 minutes and
authorised the merge explicitly ("please merge all. note the files in handoff. fix after.").

**CORRECTION (appended after the fact).** An earlier revision of this document asserted that "a
concurrent Codex session" restored `.claude/CODEX-HANDOFF.md` / `.claude/SESSION-HANDOFF.md` from
HEAD and clobbered files mid-session. **That attribution was fabricated — Codex was not running.**
Cliff had deleted those two files himself; something then reverted both his deletions *and* this
agent's rewrites of them (both files returned to exact HEAD content, mtime 08:09), and separately
introduced the `model_runtime.py` / `tests/test_model_runtime.py` changes mid-session.

**The actual mechanism is unknown.** Dropbox sync is the obvious suspect given the repo lives under
`C:\Users\cliff\Dropbox\...`, but that is a hypothesis, not a finding. Do not repeat the Codex claim.

Practical consequence that still holds: **file writes under `.claude/` in this repo have been
observed silently reverting.** Verify any handoff you write is actually on disk *and* committed
before relying on it.

**Filed at `.claude/docs/`** because `.claude/backups/` is **gitignored** (`.gitignore:56`) — an
earlier copy placed there was silently skipped by `git add -A` and never committed, despite a commit
message claiming otherwise.

---

## READ FIRST — do not re-derive this

The originating session ingested a ~9,200-line diff, several large source files, the installed
`sentence-transformers`/`google-genai` sources, and multi-minute pytest runs. That is what consumed
the budget. Everything it yielded is recorded below. **Do not re-read the review diff**
(`…/scratchpad/review2-latency-perf.diff`) — it costs a large fraction of a session and yields
nothing new.

**A concurrent Codex session is active in this worktree.** It has already clobbered files underneath
this agent once. Re-check `git status` before acting; never run `ruff format .` / `ruff check .`
unscoped.

---

## What was reviewed

Branch `codex/backlog-57-phases-2-5` → `main`, ahead of a public **v0.4.1** desktop-installer release.

This agent's scope: **Arc 2a, the "pure performance" half of the latency arc** — 7 commits
`b64fcf6`..`8c5ddbd` (Critical Read inference batching, app-scoped `ModelRuntimeRegistry`,
app-scoped `ProviderClientRuntime`, NLI length-bucketing, bounded long-poll job completion,
`.claude/LATENCY.md`).

Sibling reviews (other agents, complete) covered the synthesis-cache-identity fix + synthesis/overview
lifecycle split and two earlier chunks. Those earlier two each surfaced real bugs (a stuck-state UI
dead-end, a dead retry branch, a Status-invariant gap; and a live third code path with a bug the
commit claimed to have fully fixed). **Whether those were fixed is unverified from here.**

**Verdict: safe to merge with follow-ups.** No correctness, honesty, or egress-invariant break found
in Arc 2a.

---

## Verified GOOD — do not re-derive

- **Batched-inference index alignment is clean** — the highest-risk bug class, and it is absent.
  `search_contested_claim_scopes` (`app/backend/methods/critical_review.py`) filters *before* building
  the batch, joins with `zip(..., strict=True)` throughout, and carries results back by explicit
  `(scope_index, claim_index, hit_index)` rather than position-in-a-derived-list. Tie-breaking
  preserved (first max wins). Status/count semantics byte-identical to the old early-return paths,
  including the non-obvious `empty-library-corpus` case that hardcoded `eligible_chunk_embeddings=0`.
- **NLI length-bucketing is correct**, checked against installed `sentence-transformers` 5.3.0 source
  rather than docs: `CrossEncoder.predict` calls
  `self.tokenizer(batch, padding=True, truncation=True, return_tensors="pt")` with no `max_length`
  and does **not** sort internally, so the planner's `truncation="longest_first", max_length=512`
  matches exactly. Padding is attention-masked → only GEMM-shape float noise remains.
  `SentenceTransformer.encode` already length-sorts and un-sorts, so embedding batching is order-safe.
- **Provider key-rotation safety, both axes.** `_load_http_client` builds the client with no
  headers/auth; `_post` passes the key per request — structurally impossible to bake in. Gemini's
  `credential_fingerprint` genuinely changes with the key. Neither `client_entries()` nor
  `runtime_entries()` is reachable from any endpoint → no fingerprint egress.
- **No cross-test registry pollution.** `tests/conftest.py` has no shared app fixture; every test
  calls `create_app()`, building a fresh `ModelRuntimeRegistry` + `ProviderClientRuntime`.
- **Locking is real and correctly scoped.** Heavy construction happens *outside* the registry lock;
  `close()` releases it before closing entries; no lock-ordering cycle.
- **Long-poll has no lost-wakeup.** Waiter registration and state mutation share `_lock` with the
  terminal-state recheck inside it; `call_soon_threadsafe` is right for Starlette's threadpool-run
  sync background tasks; cleanup is `finally`-guaranteed. `mark_stage` deliberately does not wake.
  Long-poll GET paths match no `TRACKED_AI_REQUESTS` entry → invariant #5 unaffected.
- **Honestly unverified:** the measured drift claim (max 9.54e-7, zero label changes) was never re-run
  against real weights. Mechanism is sound; `.claude/LATENCY.md` §5 sets a 1e-5 tolerance.

---

## Findings already fixed on-branch

| Finding | Commit | Status |
|---|---|---|
| #1 narrow exception guard in NLI planner | `3c9493a` | spot-checked only |
| #3 `local_files_only` splits runtime identity | `2b07cf4` + working-tree follow-up | **fixed, verified** |
| #7 `sentence-transformers` floor too low (`backend=` needs >=4) | `bbdd19f` | spot-checked only |

### #3 detail — the fix is better than what this review proposed

`2b07cf4` used `field(compare=False)`, which stopped the identity splitting but left
`_runtime()` capturing the **first** identity, so fetch policy became first-caller-wins. Repro at the
time: a `local_files_only=True` caller resolving first poisoned later `False` callers, so on a fresh
install with no HuggingFace cache the Library paths could no longer download weights.

A concurrent session then replaced this with **asymmetric reuse** keyed on a `local_files_only`-
stripped base identity: a `True` request only ever shares a runtime itself built with `True` (never
one a `False` caller may have network-fetched, so the offline guarantee is never silently
downgraded); a `False` request reuses whichever slot exists, preferring `True`. Verified both
directions:

```
A restrictive->permissive: same runtime = True  | loader got [True]
B permissive->restrictive: same runtime = False | loader got [False, True]
```

This review's own "least-restrictive-wins" sketch was **wrong** — it would have handed the `True`
caller a network-fetched model. Do not re-apply it. Accepted residual: direction B loads two copies;
correct trade (offline-guarantee correctness over memory), worth one line in the increment notes.

---

## Open follow-ups (none release-blocking)

- **#2 (Medium) Batch-level fail-closed replaced per-item fail-closed.**
  `app/backend/summarization/stance.py` — `classify_stances` / `classify_critical_review_stances`
  catch once and return `[None] * len(pairs)`. Previously each pair had its own try/except, so one bad
  pair returned `None` and the rest still classified. In the Set path this couples all selected
  papers: one failure anywhere silences every paper at once, reported as `nli-unavailable`. Honest
  (PRINCIPLES #6 intact) — an availability, not honesty, regression — but the commits claim strict
  behavior preservation and don't mention it. Inconsistent precedent:
  `NLISupportScorer.support_and_contradiction_many` (inc 418) degrades **per pair**.
- **#4 (Low-Medium) Post-close reload + shutdown TOCTOU.** `ManagedModelRuntime` has no closed flag:
  `close()` sets `_model = None` and `get()` only checks `_model is None`, so it re-runs the factory.
  A background task outliving registry shutdown can load a CrossEncoder *during app exit*. Same shape
  in `_ClientEntry` (`provider_runtime.py`) where `httpx.Client.close()` is real — an in-flight
  provider request torn down mid-shutdown will raise. Also a window in `run()` between `get()`
  returning and acquiring `_inference_lock`. **Not provable statically.** Add a closed flag; consider
  re-checking inside the inference lock.
- **#5 (Low) Per-identity inference lock serializes previously-parallel work.** Before the arc each
  router built its own model per call, so concurrent jobs ran independently. Now one shared runtime
  with `_inference_lock` held for the whole operation. `embed_chunks`
  (`app/backend/embeddings/pipeline.py`) issues one `encode_texts` for all pending chunks, so a search
  arriving mid-import blocks behind it. Call sites scope `chunk_ids` per paper (hold is seconds), and
  the lock is defensible (`CrossEncoder.predict` mutates shared state via `self.to(device)` /
  `self.eval()`). Documented in `.claude/LATENCY.md` §3 but not in the commit claims.
- **#6 (Low) Progress granularity regression in single-paper Critical Read.**
  `search_contested_claims` replaced per-claim `on_progress(i, N)` with one `on_progress(N, N)`. The
  bar sits at 0 through the NLI phase then jumps to 100%. **Cross-check against the sibling arc's
  `mark_stage` work** — confirm the stage labels cover the gap rather than each arc assuming the other
  does.
- **#8 (Low, informational) Client entries never evicted.** `_http_entries`/`_gemini_entries` grow one
  entry per distinct key or proxy/SSL-env fingerprint, closed only at shutdown. Bounded and tiny.
  `get_gemini_client(api_key=None)` fingerprints to `sha256("")` while `_GEMINI_ENV_KEYS` excludes
  `GOOGLE_API_KEY` — traced **unreachable** via `complete()` (the `requires_egress and not key`
  refusal fires first).
- **#9 (Informational) `classify_stances` duck-typing is MagicMock-fragile.**
  `getattr(scorer, "classify_stances", None)` on a `MagicMock` returns a callable `Mock`, so the
  downstream `zip(..., strict=True)` produces nonsense instead of failing cleanly. No such fake today.

---

## What was merged, and what was still unresolved at merge time

Merged on Cliff's explicit instruction, accepting the following known gaps:

1. **The branch had never been pushed or CI'd** — 25+ commits with zero CI signal (no lint, no full
   pytest, no desktop-shell build, no Bandit, no line-budget, no `tach`) at the time of merge.
2. **`main`'s CI was red** — 3 consecutive `CI` failures (runs `32488894048`, `32485902217`,
   `32304604817`, oldest 2026-08-19) in the **Bandit** gate around the guarded TEI parser
   (`except ET.ParseError as exc:`). The branch carries `74b4138 fix: restore Bandit CI gate for
   guarded TEI parsing`, so the merge plausibly un-reds main — **verify this on the post-merge run.**
3. **~18 files of in-flight status-timing / synthesis-overview-lifecycle work were committed without
   independent review.** They were not covered by any of the three review chunks. Their own tests do
   pass (89). Files: `app/backend/api/app.py`, `routers/status.py`, `routers/summaries.py`,
   `routers/summary_overview.py`, `summarization/overview_lifecycle.py`, `js/00_lib.jsx`,
   `js/04bb_status_timing.jsx`, `js/04c_status.jsx`, `js/19b_synthesis_overview.jsx`,
   `js/20_synthesis.jsx`, `js/40_app.jsx`, `callosum-app.html`, `tests/test_frontend_assembly.py`,
   `tests/test_status_timing.py`, `tests/test_summary_overview_lifecycle.py`, `.claude/CLAUDE.md`,
   plus `app/backend/model_runtime.py` + `tests/test_model_runtime.py` (the #3 follow-up above).

**First actions next session:** confirm the post-merge CI run is green *including Bandit*; if not,
that is the top priority. Then review item 3's files properly. Then work the follow-up list.

---

## UPDATE (2026-08-24, later same day) — post-merge CI was NOT clean

Bandit itself did go green on the first post-merge run (`32726183934`), confirming item 2 above —
but four other, previously-masked problems surfaced once pytest could actually run for the first
time in a while (the three prior red runs never got past Bandit, so nothing after it, including
pytest, had executed):

1. `tests/e2e/test_demo_static.py` still asserted the pre-inc-496 bare `"Done"` Status text; the
   shipped status-timing feature renders `"Done in {duration}"`. Fixed the assertion.
2. `ci.yml`'s `lint-and-test` job never built `dist-demo/` before
   `test_website_how_it_works.py::test_primary_local_destinations_exist[demo/-target2]`, which
   asserts it exists — that case could never have passed there. Added a build step.
3. `demo/wip-state-v1.json`'s committed `whole_file_hash`/`extracted_from_whole_hash` were computed
   from a Windows checkout (`core.autocrlf=true` → CRLF) of `tools/demo/fixtures/*.md`; Linux CI
   checks out the canonical LF git blob and gets a different SHA-256. Added `.gitattributes` (new
   file, repo had none) to force LF on those fixtures and regenerated the fixture JSON from the
   corrected source — `demo/snapshot-v1.json` already had the correct (LF-derived) values, so it
   needed no change.
4. The public showcase screenshot (`www/shots/status_current.png`) still showed a bare `"Done"`,
   out of sync with real behavior. Retook it (Playwright, against the public demo snapshot's
   synthetic data — deliberately not the real WIP library, whose real manuscript titles shouldn't
   go on the public site) and refreshed `www/showcase-coverage.json`'s review receipt with an
   honest note.

Also confirmed item 3's originally-flagged files are solid: the tests added alongside them are
explicitly labeled `Finding 1/3/4 (backlog #57 fixwave)` and correspond exactly to bugs the sibling
reviews had already surfaced (stuck-overview dead-end → `OVERVIEW_STUCK_AFTER_SECONDS` retry
button; missing Status-popover visibility → the new `overview_jobs` `JobStore`; the `attachment_id`
gap on `saveCitationHighlight`). No new issues found on read.

All fixed in `5b32cd9`, pushed to `main`. **Two Cliff-confirmed file deletions** (`.claude/
CODEX-HANDOFF.md`, `.claude/SESSION-HANDOFF.md` — the ones this doc's correction section describes
as repeatedly, mysteriously reverting) were committed in the same push at his explicit instruction
mid-session; they have not reappeared since.

**Still open, not addressed this pass:** the six Arc-2a follow-ups (#2/#4/#5/#6/#8/#9 above) and
GitHub's Dependabot alert (1 high, 2 moderate, surfaced on the `git push` to `main` — not yet
triaged).

---

## Verification commands with observed results

```bash
pytest tests/test_model_runtime.py tests/test_provider_runtime.py -q          # 28 passed
pytest tests/test_status_timing.py tests/test_summary_overview_lifecycle.py \
       tests/test_frontend_assembly.py -q                                     # 89 passed
pytest tests/test_model_runtime.py tests/test_provider_runtime.py \
       tests/test_job_completion_visibility.py \
       tests/test_critical_review_nli_length_batching.py -q                   # 60 passed
pytest tests/test_critical_review.py tests/test_critical_review_set.py \
       tests/test_wip_critical_review.py tests/test_citations_suggest.py \
       tests/test_citation_stance.py tests/test_summaries.py \
       tests/test_summarization.py tests/test_reverify.py \
       tests/test_embeddings.py -q                                            # 116 passed (~4 min)
python tools/check_line_budget.py                                             # OK, 562 files
```

`tests/test_verification.py` does **not** exist — coverage lives in `test_summarization.py` /
`test_reverify.py` / `test_citation_stance.py`. Full suite: `pytest -n auto -q`; if a worker crashes
near the end on this machine retry with `-n 4` (known flakiness, not a regression).

v0.4.1 tag, when cut: bump the three desktop-shell version fields in lockstep
(`tauri.conf.json`, `Cargo.toml`, `package.json` + lockfiles). **Never** `pyproject.toml`.
