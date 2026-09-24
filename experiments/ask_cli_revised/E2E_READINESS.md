# Ask 0.7 E2E — readiness report (harness ready; scored Wave-1 runs NOT started)

Substrate: branch `experiment/ask-e2e`, tag **`e2e-substrate-v1`** (local only, never pushed). Package tests: **542 passed, 3 skipped**.
How to run and what it guarantees: `E2E_HARNESS.md`. Arms and waves: `E2E_TOPOLOGY_PLAN.md`.
The frozen bakeoff package (`supervisor_eval/`) is untouched by every E2E commit; `build_battery verify` reports "freeze intact".

## Built (Cliff's sequence 1-11)

1. Coherent base: category-1 substrate only (`167db328`); uncertain WIP left untouched in the old worktree.
2. Frame-carrying contract repair (`0e209a8d`): each list fragment keeps its literal unit/id and shows its exact containing sentence
   to model-facing stages; AIB's 6 units and hash unchanged; frozen common contract for aib/lld(`q_depr`)/builtenv, hash-checked before every run.
3. Context-gate repair (`dc111e05`): schema-constrained; any mechanical failure is NO ANSWER (packet not accepted, not grown, excluded).
   The recovery query got the same repair (run9: 3/6 truncated then silently replaced by the literal obligation text) — beyond the named gate.
4. Execution-policy seam wired into role binding (Qwen3.5 recovery planning 8,192; everything else 4,096; workers their own caps).
5. Role/backend bindings T0-T5, phase residency guard for one 8 GB GPU and two Ollamas (`252628d1`).
6. Two-round sequence `W -> verify -> R -> C -> P -> W -> verify -> R -> C -> render`, topology-absent stages omitted, no-op stages recorded as skipped;
   P NO ANSWER = no recovery and no legacy fallback; C NO ANSWER = not assessed, no plan (`bbc49461`, `3723ad99`, `066b841c`).
7. Responsiveness-aware deterministic renderer: "source-verified" vs "judged responsive", clean prose, roles only in the manifest.
8. Mechanical checks and telemetry (`e2e_checks.py`): contract, ledger, conformance, plan legality, authority, NO ANSWER by task/model
   (model-mechanical vs infrastructure vs timeout vs oversized-prompt; the gate rate is reported, not thresholded), absence scan, frozen AIB label reuse,
   blinded adjudication-sheet generator.
9. Library-copy fingerprint (counts, max ids, size, sha256, WAL) verified before and after every run; clean-tree gate; exact SHA in every manifest.
10. Qwen3.5 `think:false` worker preflight: **PASS** (8/8 usable, all `stop`, 0 reasoning chars).
11. Live plumbing smokes (unscored, tiny slivers; private run dirs): T0, T2, T3, T4, T3-on-built-env, plus seeded T0 and T5 (see below). T1 was not run separately
    (it is T0's worker + T2's R/P; no new binding type).

## What the live smokes verified

Every binding type ran through the full sequence with technical validity true and the library copy unchanged: managed-local Q2.5 (worker and R),
Ollama-native Qwen3.5 worker `think:false`, Qwen3.5 R `think:true` and P at 8K, gemma3:12b R/P, gpt-oss:20b `think:"medium"` R/P, phi4 model-C (authority recorded
in the manifest), live model swaps across both Ollamas, plan-driven recovery (NOMINATE, DEEPEN, LEGACY), fragment display frames on built-env, after-phase VRAM
observation and the optional JUNO sampler. Across all smokes: **0 NO ANSWER in 140 gate calls** (111 Qwen3.5, 29 Qwen2.5) and 100% usable worker calls (~190).
Seeded smokes (`--smoke-seed`) replay run9's source-verified claims through R/C/P because a Q2.5 worker yields almost none; they say nothing about arm quality.

## Findings that bear on Wave 1 (measured; smoke slivers, not scored)

1. **The repaired gate exposes Qwen2.5's real behavior: it discards ~95% of packets** (run9's valid gate decisions: 49 discard / 1 before / 1 accept; smoke: 27/29).
   Run9's yield was inflated by 99/152 truncated gates silently becoming "accept". Q2.5-worker arms (T0/T1/T5) will be evidence-starved; a Q2.5 sliver produced 0-2 source-verified claims.
   Qwen3.5 as worker (think off) is fast (~1 s/call) and yields evidence (gate: 58% discard / 27% accept / 15% before).
2. **Qwen3.5 R (`think:true`, 4,096 allowance) hit the cap on 9/9 real claims** (~120 s each; the bakeoff saw 3/9 NO ANSWER on positives at this allowance). T1/T2 therefore get no usable R
   mapping: det coverage leaves items unresolved and the renderer says so ("could not be assessed ... mechanical failure"; nothing is downgraded to "not responsive").
   In the T2 smoke R consumed 1,100 s of 1,405 s. gemma3:12b R (9/9 usable, ~17 s/claim) and gpt-oss R (8/8 usable, 20-125 s/claim) work.
3. P is usable everywhere it ran: Qwen3.5 at 8K (5,712 tokens, 176 s), gemma (26-86 s), gpt-oss (27 s). Qwen3.5 and gemma chose one uniform search action for every item (NOMINATE, or DEEPEN on the seeded ledger); gpt-oss mixed NOMINATE with
   `MARK_COVERED:pN` on already-resolved items (which, by design, writes no coverage).
4. On the seeded run9 ledger, phi4 as C attached only s1 (p3, p4) and s2 (p1, p2, p4) and left s3-s6 unresolved (consistent with the frozen expectations),
   while Q2.5 as R over-attached (11 attachments the frozen labels forbid).

## Decisions for Cliff before the first scored run

Recommendation (not applied; the approved plan is unchanged): given findings 1-2, start AIB with **T3 and T4** (functional R plus an evidence-yielding worker), add **T0**
(minutes; the honest repaired baseline, expected near-empty). Hold **T1/T2** (Qwen3.5 R cannot complete at 4K; a full run would spend ~2 min per claim re-confirming it) and **T5**
(a Q2.5 worker leaves phi4 almost nothing to audit) unless you want them altered (e.g. R at 8K, or T5 with the Qwen3.5 worker, which are plan changes).

Also flagged: the recovery-query repair (beyond the gate); the first planning call treats the initial pass as neither DEEPEN nor NOMINATE and P arms perform one bounded
action per item (T0's legacy recovery does deepen-then-nominate, so its search budget is not strictly equal); R is off in T5; LLD is `q_depr`; gate NO ANSWER is reported
per run with no threshold.
