# LLM provider-integration reliability audit — combined (Claude + Codex, read-only)

**Date:** 2026-09-01
**Scope:** every place callosum's backend (and, as Codex's pass extended it, frontend) contacts a
local or cloud LLM provider — the ~14 call sites in the inc-547 provider-gated feature inventory,
the shared provider plumbing, and the Local-AI-readiness gating in the UI.

**Method:** two fully independent read-only passes were run in parallel and are merged here.
Claude's pass split the backend inventory into 6 waves (shared plumbing + 5 feature-area groups),
each applying the same 7-point checklist, and produced qualitative/plausibility findings without
running the suites or measuring real character counts. **Codex's pass additionally ran the actual
test suites (304 Python + 29 Rust, all passing), executed the real production prompt-builders
against bounded worst-case inputs to measure actual character envelopes, ran a live HTTPX
proxy-selection probe, and checked release-tag ancestry against `main`** — materially more
empirical than Claude's pass in several places, and caught two categories of bug (frontend gating,
release/deployment lag) that Claude's backend-only wave split never looked at. Every Codex-only
finding below that Claude could quickly fact-check independently has been verified; those are
marked accordingly. Nothing on this page should be treated as fixed — **this is still a
read-only document**, combining findings, not a fix log.

**Two bugs were found and fixed earlier in this same session**, before either audit pass: Synthesize
primary generation (`summaries.py`, `generator.py`) and Critical Review's single-paper candidate
generation (`critical_review.py`, `integrations/gemini/critical_review.py`) — both had an unhandled
`ManagedLocalTargetError` crash and a cloud-sized (not Local-AI-aware) prompt cap. These are what
motivated auditing everywhere else, and are the reference fix shape cited throughout.

---

## P0 — the published installer doesn't have today's fixes (Codex; verified by Claude)

`main` (HEAD `3806e7c`) is **4 commits ahead of the published `v0.5.2` tag** (`f103b8d`), including
all three fixes from this session (`35fe406`, `555627b`, `479fa85`) plus a docs commit. Verified
directly: `git rev-parse v0.5.2` → `f103b8d...`; `git rev-list v0.5.2..main --count` → `4`.
**Anyone running the current public installer still has the crashes/overflow bugs those three
commits fixed.** This should be resolved with a new patch release before treating today's `main`
as what end users are actually experiencing — the exact gap that made "is Local AI deployed and
working" hard to answer honestly earlier in this session.

---

## P1 — three frontend panels gate Local AI off entirely, checking the wrong field (Codex; verified by Claude)

Confirmed by direct read, byte-for-byte matching Codex's citations:

```
app/frontend/js/08n_methods_analytic_flexibility.jsx:29
app/frontend/js/08x_methods_critical.jsx:188
app/frontend/js/08y_critical_set.jsx:168
```

All three do `setAiReady(Boolean(r.data.data_egress_enabled))` from `GET /settings`. But
`data_egress_enabled` is **false by design** for `managed_local` (Local AI has no egress — that's
the whole point). The correct field, `generation_provider_available` (confirmed present in
`app/backend/api/routers/settings.py:50`, and already used correctly at
`app/frontend/js/45_workbench.jsx:114`), reflects whether the *active* provider can actually
generate right now, regardless of egress posture.

**Concrete effect: with Local AI selected, ready, and working end-to-end on the backend (as
verified live earlier this session), the paper analytic-flexibility check, single-paper Critical
Review, and set Critical Review UI all still present as unavailable.** This is arguably the single
highest-impact finding in the combined report for "does the demo actually work" purposes — the
backend fixes from earlier today don't fully manifest for the user without this frontend fix too.
`20_synthesis.jsx:54` has the same field confusion but only affects messaging, not blocking —
lower priority, same root cause.

---

## P1 — Local-AI-unaware prompt-size overflow (both passes; Codex measured real envelopes)

Both passes independently found the same feature set overflowing; Codex additionally *measured*
actual character output from the real prompt-builders against bounded worst-case inputs (not
estimated), which sharpens several of Claude's qualitative findings considerably — most
importantly, **funding triage is far worse than "no cap" suggested: measured at 641,896 characters**,
not a two-to-three-x overflow but nearly two orders of magnitude past the ~10,240-token
(~30-40k-character) input budget.

| Feature | Claude (estimated) | Codex (measured) | File |
|---|---|---|---|
| Funding triage | "no total cap at all" | **641,896 chars** — by far the worst finding in either pass | `app/backend/funding/llm_triage.py:18` |
| Help | "up to 80,000 chars (history only)" | **98,783 chars** (history + corpus + question together) | `integrations/gemini/help_assistant.py:23` |
| Registration triage | "~40-45k typical against a 60k cap" | **58,209 chars** | `app/backend/registration_comparison/llm_triage.py:17` |
| Research summary | "~10-13k tokens at the 60-doc/600-char max" | **56,397 chars** | `integrations/gemini/research_summary.py:18` |
| Workbench extraction | "50,000-char cap, plausibly hit" | **50,546 chars** | `app/backend/workbench_assist.py:27` |
| Critical Review triage | "40,000-char cap, near-certain overflow" | **39,879 chars** | `app/backend/methods/critical_review_triage.py:21` |
| Critical Review set | "~20,000 chars constant regardless of set size" | **20,565 chars** — usually feasible, limited headroom | `integrations/gemini/critical_review_set.py` |
| Analytic flexibility | "20,000-char cap, both Library and WIP sides" | **20,703 chars** — usually feasible, limited headroom | `app/backend/citations/section_scope.py:70`, `app/backend/wip/analytic_flexibility_text.py:26` |

All eight need the same fix shape already applied to Synthesize and Critical Review's single-paper
path: a provider-aware character/token budget, `managed_local`-branch reduced. Codex's recommended
direction — **one shared provider-aware input-budget utility applied before every `complete()`
call, with feature-specific prioritization/truncation, rather than N independent character
constants** — is a stronger fix than patching each constant individually, given how many
independent copies of "pick a cloud-sized number" this pattern has already produced.

`integrations/gemini/extraction_assistant.py:54` has no cap at all *at its own layer* (Claude) —
relies entirely on `workbench_assist.py` having pre-bounded input; a defense-in-depth gap, not a
live bug given the upstream cap exists.

---

## P1 — managed-target resolution failures escape as unhandled crashes (both passes)

Both passes independently found the same call sites; line numbers differ only in *which point in
the call chain* was cited, not in substance — reconciled below.

| Call site | Claude's citation | Codex's citation | Notes |
|---|---|---|---|
| Paper analytic flexibility | `analytic_flexibility.py:33` | `analytic_flexibility.py:33` | Exact match |
| WIP analytic flexibility | `wip_checks.py:260` | `wip_checks.py:260` | Exact match |
| Workbench extraction | `workbench.py:356` (the endpoint's unguarded call site) | `workbench.py:135` (inside the `_extraction_assistant()` helper it calls) | **Same bug, two depths of the same call chain** — verified directly: `resolve_llm_config()` at helper line 135 is unguarded, and the endpoint invoking that helper at line 356 has no surrounding try either. Fix either layer, but the helper (135) is the single point that fixes every caller at once. |
| Critical Review triage | standalone `POST /critical-read/candidates/triage` (fully sync, zero handling) | `critical_review_triage.py:30` | Same endpoint |
| Overview retry | `summary_overview.py:40` | `summary_overview.py:40` | Exact match |
| Axis cluster-label | flagged as a *design-inconsistency* (job's documented "never raises, falls back to local label" doesn't cover config-resolution failure, but the outer job wrapper still catches it — not a raw crash) | `axes.py:489`, listed among the "escape as raw 500s" group | **Worth resolving before fixing**: Claude's read was that this fails the whole axis-suggest *job* (caught by its outer `except Exception`, landing as a job error, not a bare 500) rather than surfacing as an unhandled request-level crash. Recommend confirming which is accurate with a quick live/traced test before writing the fix, since the correct patch differs slightly (restore the per-cluster fallback promise vs. add a request-level catch). |
| Critical Review's optional triage sub-step | `critical_review.py:302`, inside `generate_candidates`'s `{"triage": true}` path, outside the function's own already-fixed try block | Same, described as "escapes the main generator's recovery boundary" | Exact match |

All resolve to the same fix template already shipped twice today.

---

## P1 — malformed Critical Review triage output can crash (both passes, exact match)

`app/backend/methods/critical_review_triage.py:135` — bare `json.loads()`, no try/except, no
fallback (unlike `critical_review.py`'s own `_loads_lenient()` used elsewhere in the same feature
family). Codex additionally checked the sibling triage evaluators (funding, registration) and
confirmed **their routes already convert a parser failure into a safe degraded result** —
Critical Review is the one place this doesn't happen consistently.

---

## P1 privacy — manual "local"/custom providers can leak through an HTTP proxy (Codex only; structurally verified by Claude)

Codex ran a live in-process HTTPX probe: with `HTTP_PROXY`/`HTTPS_PROXY` set and no `NO_PROXY`,
httpx mounts a proxy for `http://` requests. Claude verified the structural root cause directly:
`LLMConfig.http_trust_env` (`integrations/gemini/generator.py:46`) defaults to `True`, while the
managed Local AI target explicitly forces `http_trust_env=False`
(`app/backend/llm/managed_local.py:215`) — the managed preview is unaffected, but a manually
configured "local" (e.g. Ollama) or custom loopback-declared provider inherits the `True` default
and will honor an ambient proxy environment variable if one happens to be set, meaning traffic
declared "local, no egress" can be silently routed through a proxy. **Does not affect the managed
Qwen preview.** Fix: every no-egress loopback target (not just managed_local) should force
`trust_env=False`, not just the one that happens to construct it that way today.

---

## Codex-exclusive findings not cross-checked by Claude's original waves (new scope)

Claude's pass scoped to the ~14 generative LLM call sites and their immediate router/plumbing;
Codex's pass additionally covered frontend gating (see P1 above), release/deployment state (P0),
and the separate local-model layer (embeddings/NLI/SPECTER) that Claude explicitly scoped out.
None of these were independently re-verified by Claude beyond the spot-checks noted; treat with
the same evidentiary weight as the rest of Codex's report (real code citations, not speculation,
per its own methodology write-up):

- **Auxiliary local models (embedding/NLI/stance/SPECTER) have a hidden first-use download
  dependency, unpinned revisions, and no progress/ETA.** A fresh install can silently trigger an
  unannounced download the first time a feature needing them runs, or fail outright on paths using
  `local_files_only=True` (`registration_retrieval.py:93`, `registration_comparisons.py:313`,
  `wip_critical_review.py:51`) if nothing earlier happened to warm the cache. Different from the
  managed-Qwen model (which has full digest verification/pinning) — this layer has none of that
  rigor. Genuinely adjacent to, not part of, the generative-provider audit, but real user-facing risk.
- **Help has an independent enable-switch gap**: selecting Local AI doesn't auto-enable the
  separate `help_assistant_enabled` toggle, and — **verified independently by Claude** — the
  disabled-state error message is hardcoded to say "Set CALLOSUM_HELP_ASSISTANT_ENABLED=1 and
  GOOGLE_API_KEY" (`app/backend/api/routers/help.py:80`) regardless of which provider is actually
  selected. **This same stale, provider-specific messaging pattern also exists in two more places
  Codex's report didn't name**: `app/backend/api/routers/axes.py:157` ("set
  CALLOSUM_ALLOW_DATA_EGRESS=1 and GOOGLE_API_KEY") and `app/backend/api/routers/my_publications.py:381`
  (identical wording) — both hardcode Gemini's env var name even when OpenAI/Anthropic/a custom
  provider/Local AI is what's actually configured. Worth fixing all three together.
- **Status coverage gap**: standalone `POST /critical-read/candidates/triage` isn't tracked in the
  Status registry at all; tracked rows are held in an in-memory JS map that a page/modal reload
  can silently lose even while the backend request continues (unlike backend-job-store-backed
  operations, which survive a reload).
- **Custom provider base URLs accept embedded userinfo credentials** (`https://user:pass@host`) —
  not rejected at input validation, risking secrets landing in stored config/error text.
- **Cross-provider generation-parameter inconsistency**: Gemini/OpenAI have no explicit output-token
  limit or sampling params set; Anthropic is hardcoded to `max_tokens=2048`; only managed Local AI
  has task-aware output caps. Affects reproducibility/cost/truncation consistency across providers,
  not a crash risk.
- **Critical Review triage's candidate-ID list is unbounded at the API layer** before the DB query
  even runs (the evaluator itself caps processed items) — a resource-amplification concern, not a
  normal-use bug.
- **Windows credential-fallback hardening is weaker than the POSIX path** (chmod-based permission
  hardening doesn't map to Windows ACLs) — dev/fallback-only caveat; packaged builds use the OS
  keychain, which is unaffected.
- **`0.0.0.0` is classified as loopback** in `providers.py:34`'s `_LOOPBACK_HOSTS` — both passes
  found this independently (Claude flagged it as suspected/low-priority; Codex confirms it as a
  real classification error, though — same as Claude noted — it only affects manual/custom
  provider egress classification, never the managed Qwen target, which is hard-pinned to a literal
  `127.0.0.1` separately).

---

## Latency / DB-transaction findings — Codex extends Claude's flag to a confirmed broader pattern

Claude's pass flagged Critical Review's multi-paper path (`_run_set_tier2`) as holding a SQLite
write transaction open across the entire LLM call, contradicting a comment in the code itself, and
explicitly did **not** verify whether this also applied to primary synthesis or caused real
contention — flagged as "needs live testing," not asserted as fact. **Codex's pass confirms the
same shape additionally applies to primary synthesis** (`engine.begin()` held through generation
*and* verification), single-paper Critical Review, Workbench, and analytic flexibility (via
`Depends`-provided connections held across the model call), and notes some triage flows too.
Codex frames the correct fix explicitly: **the project's own latency documentation already treats
the synthesis case as known technical debt, and any fix needs snapshot/version/CAS semantics — a
naive "just move the call outside the transaction" risks introducing stale-write correctness bugs**,
not just a mechanical move. This reframes Claude's "needs live testing to confirm impact" into "the
pattern itself is confirmed across more call sites than originally scoped; the *performance impact
under real contention* is what still needs live verification," which is a meaningfully different
and more actionable state than either pass had alone.

---

## Local AI cache never surviving a restart — both passes, exact same mechanism

Both independently traced this to the same root cause: `cache.py`'s cache-identity hashing
includes the resolved credential (`app/backend/llm/cache.py:82`), and Tauri regenerates Local AI's
bearer token + picks a fresh ephemeral port on every launch (security-motivated, not a bug).
Consequence: a semantically identical Local AI request can never hit cache across a restart, while
cloud-provider entries persist normally. Codex's suggested fix: key the managed target's cache
identity off stable scientific/runtime/model identity instead of the transport credential and
ephemeral endpoint, rather than leaving this as a permanent gap.

---

## Confirmed safe / working well — both passes agree

- `app/backend/api/routers/settings.py`'s connection-test endpoint is correct — the one call site
  everyone else should already look like (both passes independently reached this conclusion).
- No silent managed-local-to-cloud fallback exists anywhere (Codex explicitly checked for this
  across the whole provider-gated inventory — a structural confirmation Claude's pass didn't
  separately attempt at this scope, but is consistent with everything Claude found).
- The managed Local AI security/lifecycle design itself is sound: pinned runtime + digest
  verification, download-host allowlisting, no proxy use for managed downloads, literal
  `127.0.0.1`, random bearer token outside argv, no web UI, prompt/output logging suppressed,
  requested/observed backend+layer matching, crash-invalidated descriptor, proper process-tree
  cleanup, `trust_env=False`. Codex's pass explicitly credits this as the strongest part of the
  system; nothing in either pass contradicts it.
- No prompt/response content logging was found in normal usage-instrumentation paths (Codex
  explicitly checked this; consistent with Claude's earlier read of `app/backend/usage.py`'s
  structurally payload-free design from prior session work).
- Response parsing in `help_assistant.py`, `axis_terms.py`, `axis_cluster_labeler.py`,
  `extraction_assistant.py`'s `parse_proposals`, and both non-Critical-Review triage evaluators is
  genuinely defensive — degrades to empty/partial results, never crashes, on a small local model's
  messier output (Claude's finding, not contradicted by Codex).
- No `isinstance(config, LLMConfig)`-style type assumption that would break the separate
  `ManagedProviderConfig` dataclass was found anywhere by either pass.

---

## Combined remediation plan

**Wave 1 — end-user-visible blockers (fix first):**
1. The three frontend `data_egress_enabled` → `generation_provider_available` swaps
   (`08n_methods_analytic_flexibility.jsx`, `08x_methods_critical.jsx`, `08y_critical_set.jsx`) —
   cheap, surgical, and the single highest-leverage fix for "does Local AI actually work end to
   end" of anything in this report.
2. Cut a new patch release once the fix set lands, so the public installer isn't several fixes
   behind `main`.
3. The ~9 unhandled-crash call sites (both passes converge on the same list) — same mechanical
   fix shape already shipped twice.
4. Defensive parse for `methods/critical_review_triage.py:135`.
5. Provider-aware prompt budgeting for the 8 measured-overflow features — ideally via one shared
   utility per Codex's recommendation, not 8 more independent constants.

**Wave 2 — privacy/consistency:**
1. Force `trust_env=False` for every no-egress loopback provider, not just managed_local.
2. Drop `0.0.0.0` from the loopback allowlist.
3. Reject userinfo in custom provider URLs.
4. Fix the 3 hardcoded `GOOGLE_API_KEY`-specific error messages (`help.py:80`, `axes.py:157`,
   `my_publications.py:381`) to name whichever provider is actually active.
5. Standardize the "Local AI is not ready" messaging across every remaining cryptic-message call
   site (cosmetic, low-risk, can ride along).
6. Add Status tracking for the standalone Critical Review triage endpoint.

**Wave 3 — performance/reproducibility (needs design, not just a mechanical patch):**
1. Move provider calls outside DB transactions using snapshot/version/CAS semantics — per Codex's
   explicit warning, not a naive reorder — starting with primary synthesis and Critical Review's
   two paths, which both passes now confirm hold connections across the LLM call.
2. Give managed Local AI a stable, restart-persistent cache identity independent of its per-launch
   credential/port.
3. Preflight or explicitly manage the auxiliary embedding/NLI model layer's first-use download and
   revision pinning — separate from, but as real a user-facing risk as, the generative-provider work.
4. Standardize cross-provider output caps/sampling parameters.

Confirm the axis-cluster-label discrepancy (job-error vs. raw-500) with a quick live test before
writing that specific fix, since Wave 1 item #3's correct patch shape depends on which is true.
