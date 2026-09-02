# Local AI reliability audit — handoff to Codex for review (2026-09-01)

Written by Claude at the end of increment 557. Cliff's framing for this handoff, verbatim: **"I figure we
will ping-pong like that until everything is resolved"** — this is a review-and-continue-fixing request, not
a "here's what's left, go build it" handoff. Your job is to look for anything this pass got wrong, missed, or
introduced, fix what's cheap, and report back the same way (a findings list + what you fixed) so the cycle
can continue.

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
4. **The three commits that preceded the audit** (`35fe406`, `555627b`, `479fa85`) — the two live bugs found
   pre-audit (Synthesize/Ask, single-paper Critical Review) that established the fix template every other site
   in this pass follows. `git show` them if you want the exact diff shape.

## Non-negotiable verification requirements

Same standing rule as every other handoff on this project: **never claim a test passed without having
actually run it this turn and reporting the real output.** This pass ran 400+ targeted tests across every
touched area with zero failures (exact command list is in `INCREMENT-557-NOTES.md`'s Verification section),
but **the full `pytest -n auto -q` run was never completed locally** — it hit this session's background-task
time ceiling at ~29% (zero failures observed up to that point). **Confirm CI is actually green on the current
`main` HEAD before you start** (`gh run list --branch main --limit 5` / `gh run view --log-failed` if it
isn't) — don't assume it passed just because this document says the targeted tests did. If CI is red, that is
your first job, before reviewing anything else.

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

## Smaller items from your report that this pass also did NOT address — genuinely still open, not forgotten

These were in your report's "Codex-exclusive findings" list but weren't part of the Wave 1/2 items this pass
scoped to. Worth a look, or worth explicitly deciding to leave open with a reason:

- **Help's independent enable-switch gap is only half-fixed.** The misleading env-var message is gone
  (`help.py` now says "Enable it in Settings → AI features"), but selecting Local AI as the active provider
  still does **not** auto-enable the separate `help_assistant_enabled` toggle — a user has to flip two
  separate switches. Not touched this pass; worth deciding whether Local AI selection should auto-enable it,
  or whether the two-toggle design is intentional (Help sends the question text even with a local model, so a
  separate consent gate may be deliberate — check the original design reasoning in `help.py`'s module
  docstring before assuming this is a bug to fix).
- **Critical Review triage's candidate-ID list is still unbounded at the API layer** before the DB query runs
  (the evaluator itself caps processed items downstream). A resource-amplification concern, not a live bug —
  your own report flagged it as low-priority.
- **Windows credential-fallback hardening is still weaker than the POSIX path.** Dev/fallback-only caveat per
  your own report (packaged builds use the OS keychain, unaffected).

## A small, unrelated pre-existing bug found while testing this pass — flagging, not fixed

`app/backend/workbench_assist.py::page_tagged_text` **drops a chunk entirely rather than truncating it** when
that single chunk's page-tagged text alone exceeds `cap` (`if total + len(seg) > cap: break` fires on the
very first chunk if it alone is too big, before anything is appended — so `parts` stays empty and the
function returns `""`). This predates this session's changes and isn't part of either audit pass's findings —
it surfaced only because a first draft of `tests/test_workbench.py::test_propose_bounds_paper_text_tighter_
for_managed_local` used one giant synthetic chunk and got an unexpected 422 (fixed by using multiple
realistic-sized chunks in the test instead — see the final version in `tests/test_workbench.py`). In practice
this needs a single real PDF chunk to individually exceed the (now much smaller) `MAX_TEXT_CHARS_MANAGED_LOCAL
= 8_000`, which the project's normal chunking strategy makes unlikely but not impossible for an unusually
dense paragraph. Worth a one-line fix (truncate the oversized chunk instead of breaking before appending it)
if you're already in that file — not urgent enough to justify its own pass.

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
3. **New-issue check**: did any of these fixes introduce a regression? Full suite hasn't completed locally
   (see above) — CI is the first real signal.
4. **The `critical_review_triage.py` broad-except design choice** (see Wave 1 above) — confirm you agree
   "match the sibling architecture" was the right call, or propose the alternative if not.

## Reporting back

Same shape as this document worked for me: a findings list (what you checked, what you found, CONFIRMED vs.
PLAUSIBLE where you didn't fully verify), what you fixed inline if it was cheap, and what's still open for the
next round. No pressure to close everything in one pass — this is explicitly the ping-pong Cliff asked for.
