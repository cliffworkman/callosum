# Local AI reliability audit — handoff to Codex for review (2026-09-01)

Written by Claude at the end of increment 557, **updated after increment 558** closed out several of this
document's own "still open" items before Codex ever picked it up — see the update note right before "Smaller
items" below. Cliff's framing for this handoff, verbatim: **"I figure we will ping-pong like that until
everything is resolved"** — this is a review-and-continue-fixing request, not a "here's what's left, go build
it" handoff. Your job is to look for anything this pass got wrong, missed, or introduced, fix what's cheap,
and report back the same way (a findings list + what you fixed) so the cycle can continue.

## READ FIRST — do not re-derive this

1. **`.claude/CLAUDE.md` in full**, if you haven't already this session — the design invariants (esp. #3
   local-first/egress-off-by-default, #5 Status findability), rule #9 (Principles gate), and the Verification
   protocol are binding.
2. **`.claude/docs/research/2026-09-01_llm-provider-integration-audit.md`** — the combined audit (my own
   6-fork pass + your independent pass, already merged) that this whole fix arc is answering. Read this in
   full before reading the increment notes below; it has the original findings, measured character envelopes,
   and the combined remediation plan (Wave 1/2/3) this handoff refers to by name.
3. **`.claude/docs/increment-notes/INCREMENT-557-NOTES.md`** — what actually got fixed this pass, file by
   file. This handoff summarizes it; the increment notes have the real detail.
4. **`.claude/docs/increment-notes/INCREMENT-558-NOTES.md`** — the same-day follow-up that closed 4 of this
   document's originally-listed open items before you ever picked it up. See the UPDATE note below.
5. **The three commits that preceded the audit** (`35fe406`, `555627b`, `479fa85`) — the two live bugs found
   pre-audit (Synthesize/Ask, single-paper Critical Review) that established the fix template every other site
   in this pass follows. `git show` them if you want the exact diff shape.
6. **Commits `2ba735a` and `dbb3562`** — the two CI-only fixes needed to get 557 fully green (demo-experience
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
reorder — this pass didn't attempt it, or the other three Wave 3 items:

1. **DB-transaction findings** — primary synthesis, both Critical Review paths, Workbench, and analytic
   flexibility all still hold a DB connection/transaction across the LLM call. Needs its own design pass; the
   project's own `.claude/LATENCY.md` already treats the synthesis case as known technical debt.
2. **Local AI cache-identity redesign** — the cache still keys on the per-launch credential/port, so a
   semantically-identical Local AI request never hits cache across a restart. Not touched.
3. **Auxiliary embedding/NLI/SPECTER model layer** — hidden first-use download, unpinned revisions, no
   progress/ETA. This was your finding alone (outside Claude's original 6-wave scope); still fully open.
4. **Cross-provider output-cap/sampling-parameter standardization** — Gemini/OpenAI still have no explicit
   cap; Anthropic is still hardcoded to 2048; only managed Local AI has task-aware caps. Not touched.

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
