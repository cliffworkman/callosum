# supervisor_eval — Ask 0.7 supervisor-model bakeoff (experimental)

Standalone, model-agnostic harness that qualifies a **supervisor** model for Ask 0.7 on JUNO. It is a lab
tool, not production code: nothing here is imported by Callosum, and it does not modify the Qwen worker
architecture. We are qualifying a supervisor, **not a topical classifier**: a claim must directly support the
user's actual obligation, and the nearest vaguely related bucket is a failure even when it looks plausible.

Semantic trust is the prerequisite; latency/resources only choose *among* models that clear it (smallest/fastest
qualifier wins). There is no weighted score and a single severe failure is never averaged away.

## What is frozen

Real artifacts only (`.local/ask-060-fix-run/run9-schema-obligations/`; no regeneration, no library query, no
cloud): the user's original request, its six obligations `s1-o1…s6-o1`, and the real verified ledger `p1…p6`.
`build_battery.py` verifies every constant in `cases.py` byte-for-byte against those files.

| Task | Calls | Asks the supervisor to |
|---|---|---|
| A — claim → obligation | 15 | select the obligations a **claim-only** proposition directly answers (empty list is legal). A1/A2/A3/A7 run in 3 presentation orderings (original / reversed / rotate-by-3); A4/A5/A6 once |
| B — coverage audit | 2 | per obligation: `responsive_support` (with proposition ids) or `unresolved`, from the real ledger (original + reversed proposition order) |
| C — bounded recovery | 2 | choose one legal next action per obligation under a **stated** recovery policy (original + reversed menu) |

Every prompt shows the user's original request verbatim. Task A never shows source provenance or quotes; Task B
shows the real quotes (private). Schemas use only the proven grammar vocabulary (no `uniqueItems`); IDs are
enum-constrained and re-validated after parsing, so an unenforced enum surfaces as an invented ID.

**Label authority.** Cliff's labels. Gates cover labeled pairs plus obligations clearly unrelated to the claim;
everything ambiguous is recorded as *diagnostic* and can neither rescue nor sink a model. Generic neuroscience
(A3 dmPFC, A4 mentalizing) and A5 (years of school) must map to **no** obligation; Task B's p5/p6 must support
none. A7 ("The EBQ measures explicit bias.") is byte-exact text of a stored *weak* candidate.
**Disclosed reconstruction:** Task C's s4 state marks NOMINATE as not-yet-performed to test "broaden before giving
up"; the real run had already nominated 5 papers there (0 new verified evidence). s3/s5/s6 use the real states.

## Hard gates (all must pass to qualify)

| Gate | Pass |
|---|---|
| G1 mechanical | every call parses, is schema-valid, not truncated (`done_reason=stop`), within the watchdog, internally consistent |
| G2 IDs | zero obligation/proposition/action IDs outside the supplied legal set |
| G3 positives | A1, A2, A7 select the required ID and nothing forbidden (all orderings) |
| G4 negatives | A3, A4, A5 select **nothing** (all orderings) |
| G5 order | A1/A2/A3/A7 pick the identical set in all three orderings |
| G6 coverage | p3 supports s1; p5/p6 support nothing; p1/p2 not s3–s6; s4/s6 stay unresolved |
| G7 recovery | s4 → NOMINATE; s5 → PRESERVE; no closure action on s3–s6; no repeat of a performed action on s3–s5 |
| G8 no corpus-absence claim | `rationale` text has no assertion that evidence *does not exist* in the library/corpus/literature |

**G8 is adjudicated, not auto-failed.** A frozen phrase list flags candidates (`scoring._ABSENCE`). A flagged sentence
FAILS if it asserts that evidence does not exist in the library/corpus/literature/field; it PASSES if it says only
that none was surfaced, supplied, or listed. `qualified` is `null` (pending) until every flag is adjudicated.

## Discipline

- The freeze (`FREEZE.txt`) hash-pins the scoring code, prompts, schemas, envelope, client request shape, the public
  manifest, and the private battery, and is verified before any call. Editing any of them after the first scored
  call invalidates the run.
- One observation per frozen case per model. A recorded case is never re-observed on resume. Only a
  pre-observation *technical* failure (`transport_error`/`http_error` with no output) may be retried, via
  `--retry-technical`, and the retry is written into the record. Semantic misses, timeouts and mid-generation
  crashes are never retried. No prompt tuning; no per-model accommodation.
- Uniform envelope for every model: `num_ctx 12288`, `num_predict 4096`, temperature 0, seed 42, native reasoning at
  the model's default level. Stage 0 uses ask_070's neutral-preflight fixtures.
- Blocked candidates (`BLOCKED_PENDING_RUNTIME_CHANGE`) are reported, never fixed by changing shared JUNO
  infrastructure. Pulled weights are left in place; pre-existing models are never touched.
- Public/private split: committed = harness, schemas, scorer, claims/obligations, expected judgments, `FREEZE.txt`,
  text-free `receipts/`. Private (`.local/ask-070-supervisor-bakeoff/`) = verbatim quotes, rendered prompts, raw
  output and reasoning, resource traces.

## Run order

```powershell
python -m experiments.ask_cli_revised.supervisor_eval.build_battery build    # from real run9 artifacts
python -m experiments.ask_cli_revised.supervisor_eval.build_battery freeze   # writes FREEZE.txt
python -m experiments.ask_cli_revised.supervisor_eval.build_battery verify   # must print "freeze intact"
python -m experiments.ask_cli_revised.supervisor_eval.run_eval preflight
python -m experiments.ask_cli_revised.supervisor_eval.run_eval stage0  qwen3.5-9b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval battery qwen3.5-9b
python -m experiments.ask_cli_revised.supervisor_eval.run_eval report
pytest experiments/ask_cli_revised/supervisor_eval -q
```

JUNO is reached through the standing SSH forward on `127.0.0.1:11434` (the client refuses any non-loopback host).
Host observation goes through `juno.ps1`, which owns the credential convention; nothing here handles a credential.
