# Local AI reliability audit — handoff to Codex for review (2026-09-01)

Written by Claude at the end of increment 557, **updated after increments 558, 559, 560, and 561** — four
same-day/next-day follow-ups that closed several of this document's own "still open" items, plus all four
Wave 3 items (three fully, one partially), before Codex ever picked it up. See the UPDATE notes below (search
this document for "UPDATE" — there are three: after 558, after 560, and after 561). Cliff's framing for this
handoff, verbatim: **"I figure we will ping-pong like that until everything is resolved"** — this is a
review-and-continue-fixing request, not a "here's what's left, go build it" handoff. Your job is to look for
anything this pass got wrong, missed, or introduced, fix what's cheap, and report back the same way (a
findings list + what you fixed) so the cycle can continue.

## READ FIRST — do not re-derive this

1. **`.claude/CLAUDE.md` in full**, if you haven't already this session — the design invariants (esp. #3
   local-first/egress-off-by-default, #5 Status findability), rule #9 (Principles gate), and the Verification
   protocol are binding.
2. **`.claude/docs/research/2026-09-01_llm-provider-integration-audit.md`** — the combined audit (my own
   6-fork pass + your independent pass, already merged) that this whole fix arc is answering. Read this in
   full before reading the increment notes below; it has the original findings, measured character envelopes,
   and the combined remediation plan (Wave 1/2/3) this handoff refers to by name.
3. **`.claude/docs/increment-notes/INCREMENT-{557,558,559,560}-NOTES.md`**, in order — what actually got fixed
   each pass, file by file. This handoff summarizes them; the increment notes have the real detail. 559 and
   560 are the two Wave 3 items already closed (cache-identity restart-persistence; auxiliary-model revision
   pinning) — don't re-attempt either.
4. **The three commits that preceded the audit** (`35fe406`, `555627b`, `479fa85`) — the two live bugs found
   pre-audit (Synthesize/Ask, single-paper Critical Review) that established the fix template every other site
   in this pass follows. `git show` them if you want the exact diff shape.
5. **Commits `2ba735a` and `dbb3562`** — the two CI-only fixes needed to get 557 fully green (demo-experience
   drift-gate refresh; the three-layer qualification-battery re-freeze). Read `dbb3562` in particular before
   touching `app/backend/llm/providers.py` again — see the UPDATE note below for why.

## Non-negotiable verification requirements

Same standing rule as every other handoff on this project: **never claim a test passed without having
actually run it this turn and reporting the real output.** This pass ran 400+ targeted tests across every
touched area with zero failures (exact command list is in `INCREMENT-557-NOTES.md`'s Verification section).
**CI was pushed through to fully green** on `main` (run `33581825060`: e2e-smoke + lint-and-test, Pytest 2703
passed/4 skipped) — two real CI-only failures were found and fixed along the way (a demo-experience drift
gate; the qualification-battery freeze cascade described above), both documented in their own commits.
**Still confirm CI is green on the current `main` HEAD before you start** (`gh run list --branch main --limit
5` / `gh run view --log-failed` if it isn't) — increment 558 landed after 557 and may have moved HEAD further
by the time you read this; don't assume it's still exactly where this document describes. If CI is red, that
is your first job, before reviewing anything else.

## What this pass fixed (Wave 1 + Wave 2, in full)

**Wave 1 — end-user-visible blockers:**
- Frontend Local-AI gating (`data_egress_enabled` → `generation_provider_available`) across 4 panels.
- Every `resolve_llm_config()` call site in the codebase (16 files, confirmed by direct grep, not sampling)
  now either catches `ManagedLocalTargetError` and surfaces "Local AI is not ready (`<code>`). Check Settings
  → AI features." or was already safely wrapped by an existing broad catch. Two gaps beyond your original
  report's explicit list were found and fixed live during this pass:
  - Set Critical Review's Tier-2 path (`critical_review.py::_run_set_tier2`) — same unguarded
    `resolve_llm_config()` shape as the already-fixed single-paper path, just not named in either audit pass's
    crash-site table.
  - The axis-suggestion job's cluster-labeler polish step (`axes.py::_run_axis_suggest_job`) — confirmed by
    direct read that the whole job was wrapped in one `except Exception`, so a labeler-construction failure
    failed the *entire* suggestion job (losing every cluster) instead of degrading to local labels the way
    `apply_labels(labeler=None)` already promises. **This resolves the one open reconciliation question the
    combined audit flagged** (job-error vs. raw-500) — it was neither; it was a design inconsistency, and
    Claude's original framing (not yours) was the accurate one for this specific site.
- `critical_review_triage.py`'s three orchestration paths (`triage_contested`/`triage_contested_dicts`/
  `triage_and_persist_candidates`) had **zero** exception handling before this pass — unlike the sibling
  funding/registration triage routers, both of which already wrap their evaluate call in a broad
  `except Exception` returning a safe degraded status. Brought Critical Review triage to the same shape. This
  transitively closes the bare-`json.loads()` defensive-parse gap your report flagged
  (`methods/critical_review_triage.py:135`) — it's still unguarded at that layer, matching its siblings
  exactly (neither funding's nor registration's own parse function defends itself either; the safety net is
  one layer up, at the router). **Worth double-checking this design choice** — I judged "match the sibling
  architecture" as more correct than "add a third, inconsistent local try/except," but you may disagree.
- New shared `app/backend/llm/prompt_budget.py` (`is_managed_local`, `per_item_char_budget`, `truncate_items`,
  `truncate_text`, `select_total_chars`) applied at all 8 measured-overflow sites from your report. Funding
  triage got the most invasive change — it had **no** total-character cap at all before this pass (only an
  80-item count cap), so a `_bounded_items` cumulative-size-and-drop mechanism was added from scratch,
  mirroring the registration/critical-review triage evaluators' pre-existing shape.

**Wave 2 — privacy/consistency:**
- `complete()`'s HTTP dispatch (`providers.py`) now forces `trust_env=False` for any loopback destination
  regardless of the config's own `http_trust_env` value — this is the structural fix for your live-probe
  finding, at the one shared seam every wire format routes through.
- `0.0.0.0` removed from `_LOOPBACK_HOSTS`.
- Custom/local provider base URLs now reject embedded userinfo (`providers_store.py::_norm_base` and
  `settings.py`'s `local_base_url` path both).
- The 3 hardcoded `GOOGLE_API_KEY` messages (`help.py`, `axes.py`, `my_publications.py`) now name Settings
  generically.
- `POST /critical-read/candidates/triage` added to `TRACKED_AI_REQUESTS` (`04c_status.jsx`).

## What's deliberately NOT touched — Wave 3, deferred on purpose

Your own report explicitly warned the DB-transaction fix needs snapshot/version/CAS semantics, not a naive
reorder. Status as of increment 560 (two of the four items have since been closed — see the UPDATE note below
for the full detail; this list is kept as the original framing for context):

1. **DB-transaction findings** — ~~all sites still hold a DB connection/transaction across the LLM call~~ —
   **primary synthesis CLOSED, increment 561** (the riskiest sub-case, done properly in Plan Mode per Cliff's
   explicit choice, not a mechanical patch — see the UPDATE note below). **Critical Review (both paths),
   Workbench, and analytic flexibility remain deliberately deferred** — surveyed this session and confirmed
   lower risk (see the UPDATE note for the ranking); the WIP analytic-flexibility site already shows the right
   shape in-repo as a reference for whoever picks this up next.
2. ~~**Local AI cache-identity redesign**~~ — **CLOSED, increment 559.** `ManagedLocalTarget.
   stable_identity_fingerprint()` + `GenerationCacheIdentity.from_config()` now key managed_local's cache
   identity off model/runtime/param digests instead of the per-launch endpoint/credential.
3. **Auxiliary embedding/NLI/SPECTER model layer** — **partially closed, increment 560**: revision pinning is
   done (`PINNED_MODEL_REVISIONS` in `model_runtime.py`). **Still open**: first-use download progress/ETA (no
   Status-popover entry today) and a friendlier failure when a `local_files_only=True` call site hits a cold
   cache — both explicitly UI-touching, larger pieces of work, documented as deferred in
   `INCREMENT-560-NOTES.md`.
4. **Cross-provider output-cap/sampling-parameter standardization** — **still open, deliberately not
   attempted.** Gemini/OpenAI still have no explicit cap; Anthropic is still hardcoded to 2048; only managed
   Local AI has task-aware caps. The reason this one was skipped rather than just being smaller-scoped like
   item 3: fixing it means editing `app/backend/llm/providers.py` (the request-building code for every wire
   format), which is one of the 10 files frozen by the `synthesis-overview-v1` qualification study — see the
   UPDATE note above about the three-layer re-freeze cost. Given the audit's own framing of this item as "not
   a crash risk," the re-freeze overhead didn't seem worth it for a consistency nicety in this pass — but it's
   a legitimate item if you want to pick it up; just budget for the re-freeze cycle (commits `2ba735a`/
   `dbb3562` show exactly how).

## UPDATE (increment 558) — several items below are now CLOSED, before you ever picked this up

Right after 557 landed and CI went green, a same-day follow-up (`.claude/docs/increment-notes/
INCREMENT-558-NOTES.md`) closed 4 of the items originally listed in this section. **Read that increment's
notes, not just this summary, before re-investigating any of the four:**

1. **`page_tagged_text` FIXED** (was "flagging, not fixed" below) — it now truncates an oversized single
   chunk instead of dropping it entirely. Regression test added.
2. **Critical Review triage's candidate-ID list is now bounded** — `MAX_TRIAGE_CANDIDATE_IDS = 500` via
   `Field(min_length=1, max_length=...)` on the request model.
3. **Help's enable-switch "gap" investigated and confirmed intentional, not a bug** — the two-toggle
   separation is deliberate per `help_assistant.py`'s own docstring (sending the question anywhere, even to a
   no-egress local provider, gets its own explicit consent). No code change; don't "fix" this.
4. **Windows credential-fallback hardening confirmed low-priority and already honestly documented** — the
   packaged build installs `keyring` as a hard dependency (`build_python_windows.ps1`), so real end users are
   unaffected. Only a source checkout without the optional extra is exposed. No code change made.

**One more thing surfaced only by pushing 557 and watching real CI, worth knowing before you touch
`app/backend/llm/providers.py` again**: it's one of several files whose exact byte-content is frozen inside a
preregistered local-model qualification study (`.claude/qualification/synthesis-overview-v1/`, already
concluded with a negative/no-qualification result, plus two downstream dependents —
`benchmark-calibration-v1/` and the Phase 4.1 cohort — that each carry their own witness of the base
battery's identity). **Any edit to `providers.py` will break three independent frozen-manifest checks** (two
`freeze.json`-style files re-frozen via each module's own `freeze --starting-head <commit>` CLI command, plus
a third, `phase4-1-freeze.json`, which has no CLI and needs its `base_battery_aggregate_sha256` field
hand-edited) **and two hardcoded test witnesses** (`tests/test_overview_cloud_calibration.py::
test_historical_battery_remains_frozen`, `tests/test_overview_phase41.py::
test_phase41_cohort_keeps_the_base_battery_frozen`). This is by design, not a bug to route around — before
re-freezing, confirm (and document in your commit) that your specific change doesn't alter any behavior the
managed_local qualification path actually exercises, the same way 557's own commits did. If you can't confirm
that, stop and ask rather than re-freezing anyway. See commits `2ba735a`/`dbb3562` for exactly how this was
done last time, including the confirmation reasoning.

## UPDATE (increment 561) — the DB-transaction/CAS item is CLOSED for primary synthesis

Read `.claude/docs/increment-notes/INCREMENT-561-NOTES.md` in full before touching this area again — this
summary is compressed. Cliff was explicitly asked (via AskUserQuestion, after all 6 prior increments were
CI-green) whether to design this properly or attempt a fast patch; he chose "design it properly now." The
approach: 3 parallel Explore-agent research passes (the Overview lifecycle's own reference pattern; primary
synthesis's exact current transaction shape; a breadth survey of the other 4 sites), then a dedicated Plan
agent to validate/detail the design, then direct reading of every critical file (`overview_lifecycle.py`,
`summary_overview.py`, `pipeline.py`, `cache.py`, `egress.py`, `verification.py`,
`schema_summaries.py`) before writing the final plan and getting explicit approval via `ExitPlanMode`.

**What shipped**: `summarize_scope` (`pipeline.py`) now takes a bare `Engine` and runs 3 phases, each its own
short transaction — prepare (retrieval) → generate (zero DB connection held during the provider call; the
connection-vs-engine split lives *inside* `CachedSummaryGenerator.generate`, `cache.py`, not in `pipeline.py`
— this matters, see below) → verify+persist (a new `_refresh_source_chunks` re-reads every chunk fresh right
before verification). Fixes two concrete bugs, not just a tidiness concern:
1. **Reliability**: two concurrent synthesis jobs could lock each other out via SQLite's 5s `busy_timeout`,
   since the old single-transaction shape often already held the writer lock (via retrieval's opportunistic
   embedding writes for a query-scoped request) for the entire slow provider call.
2. **Correctness/staleness**: a chunk mutated between retrieval and verification (e.g. a concurrent
   re-extraction) could leave the persisted `chunk_version_verified_against` provenance disagreeing with what
   verification actually checked — the exact "stale-write correctness bug" your own report and mine both
   flagged as the reason this needed a real design, not a naive reorder.

**A design subtlety worth your independent check**: my first-draft idea was to hoist the generation-cache
check up into `pipeline.py`'s own Phase 1/Phase 2 split (check cache in Phase 1, only call the provider in
Phase 2 on a miss). Reading `egress.py` directly caught that this would have **silently inverted a deliberate
existing security order**: the real call chain is `EgressGatedSummaryGenerator.generate` (checks egress
**first**) → `CachedSummaryGenerator.generate` (checks cache **second**) → the real provider (network call,
**third**) — the egress wrapper's own comment says "a cache hit can never bypass the gate." Hoisting the
cache-check above the egress gate would have let a cache hit skip the egress check entirely. Fixed by pushing
the connection-vs-engine split *inside* `CachedSummaryGenerator.generate` itself instead (it now opens its own
short `engine.connect()`/`engine.begin()` around the cache read/write, holding neither open during the
provider call) — zero change to call order. **Worth an independent read of `egress.py` + `cache.py` to confirm
this reasoning holds** — it's the single most consequential design decision in this increment.

**No schema migration** — unlike Overview's CAS (which defends against two callers racing to fill the *same*
pre-existing row), primary synthesis has no such race (each job creates a brand-new row), so the fix is
simpler: don't create the `summaries` row until generation+verification both succeed, exactly preserving
today's "no row = clean failure" behavior.

**A real bug found and fixed along the way, not by inspection**: `tools/validation_harness.py` wrapped PDF
ingestion and the summarization probe in one still-open transaction; the new Phase 1 (a fresh connection that
can't see uncommitted work on a different one) exposed it immediately as a live test failure (`StopIteration`
in the fake generator — zero chunks retrieved). Fixed by committing ingestion before the probe starts.

**Two new regression tests** (`tests/test_summary_overview_lifecycle.py`) prove both fixes directly — the
staleness one was verified to actually discriminate: reverting `_refresh_source_chunks`'s call site locally
and re-running it fails (`quote_confidence` 1.0 → 0.0, status `verified` → `weak`), confirmed live before
restoring the fix. Don't just trust the green run; that discrimination check is the real proof.

**Explicit scope boundary, mirrored from the survey done this session** (breadth-only, not deep-traced —
worth your own closer look if you pick any of these up): Critical Review single-paper Tier-2 with
`triage=true` is the single highest-risk remaining site (a real write executes on the held connection before
a *second* provider round-trip runs on the same connection — `critical_review.py:299` then
`critical_review_triage.py:135`). Everything else surveyed (Critical Review's default/Set paths, Workbench,
Library-side analytic-flexibility) holds an open connection/snapshot during the provider call but no actual
writer-lock exposure under WAL semantics (the DB write happens only after the call returns). WIP-side
analytic-flexibility (`wip_checks.py::analytic_flexibility_run`) already has zero connection open during its
provider call — the one site that's already correctly shaped, useful as an in-repo reference.

**Verification status when this was written**: targeted tests (203, every touched-file test) green; a live
end-to-end synthesis run against the real ~200-paper testing DB (Gemini-backed, since the DB's default
`managed_local` provider has no runtime outside the packaged app) confirmed byte-for-byte the same response
shape as before — verified/weak/flagged sentences, exact bbox coordinates, an Overview. `ruff format`/`check`,
line-budget, and `tach check` all clean. The demo-experience drift gate fired on `summaries.py` (in its
watched glob) and was refreshed with a note — no demo-relevant behavior changed, purely transaction plumbing.
`app/backend/llm/providers.py` was **not** touched, so the qualification-battery freeze did **not** need
re-freezing this time (confirmed by checking `freeze.json`'s file list directly, not assumed). Full local
suite: **2713 passed, 3 skipped, 0 failures** (`pytest -n 4 -q`, 35m10s — `-n auto` and an earlier `-n 4`
attempt both hit this machine's known xdist worker-crash flakiness before a clean run; unrelated to this
change, see the memory note on it). Confirm CI is green on the current `main` HEAD before you start, same as
every prior UPDATE note in this document says.

## Specific things to review

1. **Completeness**: did the crash-site sweep actually catch everything? I grepped every `resolve_llm_config`
   call site directly (16 files) rather than trusting either audit pass's list — worth an independent
   spot-check, especially of the 2 gaps I found that neither original pass named (see above; if I found two,
   there may be a third).
2. **Budget tuning**: are the new `_MANAGED_LOCAL` character-budget constants (mostly `8_000`, a few smaller)
   well-chosen? They're deliberately conservative (well under the ~10,240-token/~30-40k-character ceiling,
   leaving headroom for prompt scaffolding), but if you have a way to measure real token counts against
   Qwen's actual tokenizer the way your original audit measured character envelopes, that would sharpen these
   from "conservative guess" to "measured."
3. **New-issue check**: did any of these fixes introduce a regression? **CI is now fully green** (confirmed via
   `gh run watch`, run `33581825060`: e2e-smoke + lint-and-test both passing, Pytest 2703 passed/4 skipped) —
   the local 10-minute background-task ceiling that blocked a full local run in 557 wasn't a real problem, CI
   completed it. Still worth your own independent read, not just trusting the count.
4. **The `critical_review_triage.py` broad-except design choice** (see Wave 1 above) — confirm you agree
   "match the sibling architecture" was the right call, or propose the alternative if not.

## Reporting back

Same shape as this document worked for me: a findings list (what you checked, what you found, CONFIRMED vs.
PLAUSIBLE where you didn't fully verify), what you fixed inline if it was cheap, and what's still open for the
next round. No pressure to close everything in one pass — this is explicitly the ping-pong Cliff asked for.
