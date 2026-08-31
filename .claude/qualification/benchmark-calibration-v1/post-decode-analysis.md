# Phase 5A post-decode analysis

## 1. Executive Summary

The blinded workbook was frozen at SHA-256
`1490784fd34ac8eee0324e3c85fccb06e5cfbd7636b833dcd870913d3be8212e` before the original decode key was opened.
Commit `2192642c34f098c3d455074c22f8b25b773ef08a` is the hard pre-decode boundary. The authoritative key then mapped:

- `K-aa465905` to the time-bound Gemini `gemini-2.5-flash-lite` calibration condition;
- `K-9384d6c5` to Phase 4 C03, exact artifact Qwen2.5-1.5B-Instruct Q4_K_M.

Under the frozen human semantic protocol, C03 had 61/72 response-slot PASS verdicts and at least one failure in
4/24 fixtures; Gemini had 51/72 PASS verdicts and at least one failure in 7/24 fixtures. These are descriptive
nested counts, not 72 independent scholarly cases per candidate. Under the separate downstream Callosum policy,
C03 had 56/72 PASS verdicts and failed 6/24 fixtures, while Gemini remained 51/72 and 7/24. C03 therefore performed
better under both recorded verdicts, although its advantage narrowed under the product policy.

Neither configuration is qualified. Both failed the frozen maximal-context fixture 0/3, C03 was already
mechanically disqualified in Phase 4, Gemini has not passed a challenge holdout, and this calibration does not
transfer to another Callosum task. The local 1.5B artifact was approximately comparable on many fixtures and better
on these frozen semantic counts, but it retained concentrated omission/reference failures and product-policy
violations.

## 2. Pre-Decode Freeze Identity

| Item | Frozen value |
|---|---|
| Study | `benchmark-calibration-v1` over `synthesis-overview-v1` |
| Task | Synthesis Overview |
| Starting HEAD | `efb0e485c06821cba412495c4630bbf2b4481ee3` |
| Workbook | `.local/automatic-ai-phase5a-clean/callosum_blinded_local_model_review_final.xlsx` |
| Workbook SHA-256 | `1490784fd34ac8eee0324e3c85fccb06e5cfbd7636b833dcd870913d3be8212e` |
| Candidate state at freeze | Still blinded: `K-9384d6c5`, `K-aa465905` |
| Freeze commit | `2192642c34f098c3d455074c22f8b25b773ef08a` |
| Freeze commit time | 2026-08-31 01:21:34 UTC |

The workbook contained no provider/model label in cells, comments, hidden sheets, hyperlinks, external links, or
workbook identity metadata. Its only author metadata was ordinary reviewer metadata, not a candidate decode.

## 3. Human Review Completion

The workbook contains 9 controls and 144 candidate response slots: 72 for each of two opaque candidates, nested as
3 repetitions in each of 48 candidate-by-fixture cells over 24 fixtures. All intended core adjudication columns are
populated. Claim-grounded notes are present for every candidate slot. No candidate identity was decoded when the
workbook and pre-decode receipt were frozen.

Response-level counts below describe the realized fixed-condition repetitions. The scientific design has 24
fixture opportunities per candidate; repetitions characterize conditional stability within each opportunity.

## 4. Intentionally Uncollected Fields

The following are **INTENTIONALLY NOT COLLECTED IN THIS CALIBRATION**:

- severity;
- detectability;
- verification burden;
- practical utility.

Every candidate and control row records these as `Not scored — scale definition not supplied`. This was a deliberate
pre-decode burden decision. The fields are not imputed, reconstructed from notes, treated as accidental missingness,
or used to invalidate the completed core adjudication.

## 5. Semantic Control Validation

The reviewer classified the one known-good control PASS and all eight known-bad controls FAIL. The failures covered
malformed output, out-of-range/semantically wrong references, invented numbers, causation, generalization,
significance/certainty, and misleading omission. This is sufficient for the frozen trained-reviewer procedure.

The controls were completed after explicit training examples. They therefore test whether this reviewer could apply
the codebook after training, not whether the written codebook alone is self-explanatory. The small purposive set was
not designed to estimate formal sensitivity, specificity, or a strong false-positive profile across judgment-heavy
omission/framing categories.

## 6. Decode Provenance

| Artifact | SHA-256 | Result |
|---|---|---|
| Mixed blinded packet | `be16f671b3a3e326344002be82c3f9246fd522c3d4175daa53a776936afdfdbc` | Matches tracked Phase 5A receipt |
| Original separate decode key | `dbb032707b91c348d92062fde69a9bb7fe2cb76283aef6720a5402cfd23d3fb4` | Matches tracked Phase 5A receipt |

The schema-1 key contained two candidate mappings, nine control mappings, and 144 response mappings. Every workbook
response ID joined to the original packet/key. The key was not regenerated or inferred from output style. Decode was
performed only after Commit A; the mapping is recorded in `decode-receipt.json`.

## 7. Decoded Candidate Identities

| Opaque code | Exact study identity | Evidence class |
|---|---|---|
| `K-aa465905` | Gemini `gemini-2.5-flash-lite`; time-bound hosted alias; Google GenAI `models.generate_content`; 256-token cap, temperature 0, seed 42, thinking budget 0 | Phase 5A calibration only |
| `K-9384d6c5` | Phase 4 C03; Qwen2.5-1.5B-Instruct Q4_K_M; artifact SHA `6a1a2e…407e`; llama.cpp b10516/b95502ba9; CPU 0 requested and observed | Historically not qualified; descriptive comparator |

Hosted identity is time-bound and not equivalent to an immutable artifact digest. The full privacy-safe execution
identities are in `decode-receipt.json` and prior receipts.

## 8. Frozen Protocol Results

| Candidate | Slots | Mechanically complete / incomplete | Protocol PASS / FAIL | Fixtures with >=1 FAIL | Fixture topology (passes of 3) |
|---|---:|---:|---:|---:|---|
| Gemini 2.5 Flash-Lite | 72 | 69 / 3 | 51 / 21 | 7/24 | 17 at 3/3; 7 at 0/3 |
| C03 Qwen2.5-1.5B Q4_K_M | 72 | 69 / 3 | 61 / 11 | 4/24 | 20 at 3/3; 1 at 1/3; 3 at 0/3 |

C03 had 10 more protocol-PASS response slots and three fewer failed fixtures. The repetitions are nested and often
identical, so no naive response-level significance test is appropriate.

## 9. Callosum Policy Results

| Candidate | Policy PASS / FAIL | Fixtures with >=1 policy FAIL | Fixture topology (passes of 3) | Difference from protocol |
|---|---:|---:|---|---|
| Gemini 2.5 Flash-Lite | 51 / 21 | 7/24 | 17 at 3/3; 7 at 0/3 | None |
| C03 Qwen2.5-1.5B Q4_K_M | 56 / 16 | 6/24 | 18 at 3/3; 2 at 1/3; 4 at 0/3 | 5 additional failures in 2 fixtures |

C03's five policy-only failures comprise three provenance/reference-mapping violations in Q23 and two manufactured
connective/evidential-link violations in Q06. The original protocol verdicts remain PASS. The policy layer is not
retroactively merged into the frozen semantic codebook.

## 10. Fixture-Level Topology

`P` is frozen protocol passes/3; `C` is Callosum-policy passes/3; `U` is the number of unique raw Overview texts/3.
Abbreviations: `ref` semantic-reference inadequacy; `uf` unsupported fact; `up` inferential upgrade; `om` critical
omission; `frame` framing distortion; `prov` policy-only provenance/connective failure; `cap` truncation/output cap.

| Fixture | Gemini P/C/U | Gemini recorded issue | C03 P/C/U | C03 recorded issue |
|---|---|---|---|---|
| Q01 | 0/0/1 | ref + causal up + uf + frame | 3/3/2 | — |
| Q02 | 0/0/1 | ref + causal/significance up + uf + frame | 3/3/1 | — |
| Q03 | 3/3/1 | — | 3/3/1 | — |
| Q04 | 3/3/1 | — | 3/3/1 | orphan omission flag; frozen verdict PASS |
| Q05 | 0/0/1 | om + frame | 3/3/1 | — |
| Q06 | 3/3/1 | — | 3/1/2 | 2/3 policy-only connective failures |
| Q07 | 3/3/1 | — | 3/3/1 | — |
| Q08 | 3/3/1 | — | 3/3/1 | — |
| Q09 | 0/0/1 | ref + efficacy/temporal up + uf + frame; om 1/3 | 3/3/1 | — |
| Q10 | 3/3/1 | — | 3/3/1 | — |
| Q11 | 3/3/1 | — | 3/3/1 | — |
| Q12 | 3/3/1 | — | 3/3/1 | — |
| Q13 | 3/3/1 | orphan omission flag; frozen verdict PASS | 0/0/2 | ref 2/3 + om/frame 3/3 |
| Q14 | 0/0/1 | ref + evidence-strength/generalization up + uf + frame | 3/3/1 | — |
| Q15 | 3/3/1 | — | 1/1/2 | ref + om + frame 2/3 |
| Q16 | 0/0/1 | ref + significance up + uf + frame | 3/3/2 | — |
| Q17 | 3/3/1 | — | 3/3/1 | — |
| Q18 | 3/3/1 | — | 3/3/1 | — |
| Q19 | 3/3/1 | — | 3/3/1 | — |
| Q20 | 3/3/1 | — | 3/3/1 | — |
| Q21 | 3/3/1 | — | 0/0/1 | ref + om + frame 3/3 |
| Q22 | 3/3/1 | — | 3/3/1 | — |
| Q23 | 3/3/1 | — | 3/0/2 | provenance policy failure 3/3 |
| Q24 | 0/0/1 | cap/truncation 3/3 | 0/0/2 | cap/truncation 3/3 |

Under the protocol, only Q24 failed for both. Gemini alone failed Q01, Q02, Q05, Q09, Q14, and Q16; C03 alone
failed Q13, Q15, and Q21. Fourteen fixtures were 3/3 protocol PASS for both. Under product policy, Q06 and Q23 join
C03's failure set, leaving twelve fixtures at 3/3 for both.

The two `orphan omission flag` entries are immutable workbook inconsistencies. In each case the row has
`critical_omission=yes` and copied notes about a different scenario while both stored overall verdicts remain PASS.
They are counted in component-field totals, but the PASS verdict is not changed and the unrelated notes are not used
to reinterpret the actual response.

## 11. Error Category Profiles

Counts are recorded response flags and fixture opportunities, not normal-use prevalence estimates.

| Candidate | Recorded component/category | Responses | Fixtures with >=1 |
|---|---|---:|---:|
| Gemini | Unsupported factual content / unsupported fact | 15 | 5 |
| Gemini | Semantic-reference inadequacy | 15 | 5 |
| Gemini | Any inferential upgrade | 15 | 5 |
| Gemini | Causal upgrade | 6 | 2 |
| Gemini | Statistical-significance invention | 6 | 2 |
| Gemini | Safety/efficacy upgrade | 3 | 1 |
| Gemini | Evidence-strength/generalizability upgrade | 3 | 1 |
| Gemini | Critical omission | 5 | 3 (includes one orphan flag) |
| Gemini | Framing distortion | 18 | 6 |
| C03 | Unsupported factual content / unsupported fact | 0 | 0 |
| C03 | Inferential upgrade | 0 | 0 |
| C03 | Semantic-reference inadequacy | 7 | 3 |
| C03 | Critical omission | 9 | 4 (includes one orphan flag) |
| C03 | Framing distortion | 8 | 3 |
| C03 | Downstream provenance/connective policy violation | 5 | 2 |

Gemini's failures were concentrated in unsupported/inferential upgrading: causal, significance, treatment/temporal,
and evidence-strength/generalization predicates. C03's protocol failures were concentrated in reference adequacy and
selective omission/framing, with no frozen unsupported-fact or inferential-upgrade flag. Both also had three Q24
operational failures.

## 12. Repetition / Duplicate Structure

| Candidate | Candidate-fixture cells | Cells with 1 unique text | Cells with 2 | Cells with 3 | Unique texts / 72 slots |
|---|---:|---:|---:|---:|---:|
| Gemini | 24 | 24 | 0 | 0 | 24 |
| C03 | 24 | 17 | 7 | 0 | 31 |

There were 55 unique texts across 144 slots and no cross-candidate exact-text overlap. Every Gemini repetition was
text-identical within its fixture. C03 varied in seven fixtures, each with two unique texts; Q15 was the only fixture
with within-candidate protocol instability, while Q06 and Q15 showed policy instability. This is evidence about
conditional stability under fixed settings, not 144 independent population observations.

## 13. Q24 / Maximal-Context Interpretation

Historical qualification conclusion: both exact configurations fail the frozen maximal-context reliability rule.
Each produced 0/3 usable Q24 outputs with truncation/structural failure at the fixed 256-token cap.

Calibration interpretation: convergent concentration at the same maximal-context condition makes the output
contract/fixture a plausible material contributor. This cannot distinguish an unrealistic cap from two models'
inability to compress within it, and it does not rescue either historical verdict.

Future-study implication: preregister a new benchmark version that experimentally varies the output contract while
holding claims and evaluation fixed. Do not alter `synthesis-overview-v1` or Phase 5A retrospectively.

## 14. Codebook Redundancy / Lean-v2 Findings

Among 138 complete outputs:

- `supported_factual_content=fail` coincided exactly with `unsupported_fact=yes` in all 15 cases; neither occurred
  alone. These are redundant in this sample.
- Semantic-reference inadequacy occurred 22 times but never as the sole component-level failure. It remains
  conceptually distinct and product-relevant, especially because five further C03 provenance/connective failures
  existed only in the downstream policy layer.
- Critical omission and framing distortion coincided 12 times; omission occurred alone twice and framing occurred
  alone 14 times. They overlap substantially but are not identical.
- All 26 complete protocol FAIL rows had at least one component flag. No complete FAIL depended only on the overall
  verdict. Two complete PASS rows nevertheless retained orphan component flags, exposing an internal-consistency
  risk when overall verdicts are entered separately.
- Five policy FAIL rows were protocol PASS, confirming that the downstream product judgment carries unique
  information and must remain separate.

A lean `benchmark-calibration-v2` review schema should use the smallest distinct human judgments:

1. one unsupported/inferential-addition judgment with subtype(s), replacing the duplicate support/fact fields;
2. one semantic reference/provenance adequacy judgment;
3. one material omission/framing judgment with `omission`, `framing`, or `both` subtype;
4. one explicitly separate Callosum product-policy judgment for stricter provenance/connective rules;
5. concise notes only for a failure or genuine ambiguity.

Mechanical completeness should stay automated. Scientific and product verdicts should be derived from component
fields, not independently re-entered, while retaining an explicit adjudicator override with rationale if needed.
This is a future design recommendation; it does not change Phase 5A.

## 15. Blinding / Reviewer Limitations

- The final reviewer UI canonicalized raw provider formatting, preventing trivial provider-class identification from
  code fences/whitespace. Substantive synthesis style was not normalized because it is model behavior.
- Repeated identical outputs could become recognizable during review.
- One human reviewer completed the final coding; there is no inter-rater estimate or independent fixture authorship
  validation.
- The reviewer received explicit training before controls.
- Fixtures are synthetic adversarial stress opportunities, not a random sample of ordinary scholarly use.
- Detectability here was not collected. No inference about evidence-present expert detectability or ordinary-use
  detectability is supported.
- Two candidate rows contain frozen component/note inconsistencies. They are disclosed rather than repaired.
- Hosted Gemini behavior is time-bound; local results attach only to the exact artifact/runtime/backend receipt.

## 16. Product Interpretation

**Frozen protocol:** C03 performed better: three fewer failed fixtures and ten more PASS slots. The difference was
not merely Q24. Gemini had six exclusive failure fixtures dominated by inferential upgrades; C03 had three exclusive
protocol failure fixtures dominated by omission/reference behavior.

**Callosum policy:** C03 still performed better, but only by one failed fixture and five PASS slots after its two
additional provenance/connective failure fixtures were applied. The stricter product layer therefore changes the
size, not the direction, of the descriptive comparison.

The tiny local model is best characterized as **approximately comparable on many fixtures with specific failure
pockets, but still unreliable**. It passed every repetition on 20/24 fixtures under the semantic protocol and
outperformed the incumbent cloud condition on these counts. It nevertheless failed the frozen mechanical battery,
failed four semantic fixtures, incurred additional product-policy failures, and cannot be treated as qualified.

For Automatic AI, these results support task- and exact-configuration-specific qualification plus visible evidence;
they do not support routing C03 or Gemini as a scientifically qualified Overview target, selecting a default, or
transferring conclusions to primary synthesis, Help, another backend, or another provider alias date.

## 17. What Users Would Need To Verify

If either condition were used experimentally for Overview, users would need to check:

- every causal, significance, efficacy/safety, persistence, and generalizability statement against the claims;
- null, adverse, replication, population, and limitation evidence that compression may omit;
- whether each sentence's cited claim indices genuinely support that sentence and preserve provenance;
- whether connective language manufactures an evidential relation not present in the source claims;
- whether a long Overview is complete rather than truncated at the output cap.

These are verification targets, not a claim that ordinary users will reliably detect every problem.

## 18. What This Does Not Establish

This study does not establish a normal-use hallucination rate, severity distribution, detectability, correction
burden, practical utility score, universal model ranking, backend equivalence, production default, or qualification
for any task beyond this frozen synthetic Synthesis Overview assay. It does not qualify either candidate. The
challenge holdout is unopened; no OpenAI/Anthropic comparison or primary-synthesis transfer test occurred.

## 19. Recommended Next Scientific Step

Preserve Phase 5A unchanged forever. Use the measured redundancy to preregister a leaner human-review schema for
future calibration, then perform the already-planned **tiny primary-synthesis transferability probe** before scaling
cross-provider/local recommendation work. The probe must be a new task-specific study and must not inherit Overview
qualification. This analysis does not start it.

## 20. Repository Impact

Commit A added only the privacy-safe pre-decode freeze receipt. Commit B adds only this analysis and the decode
receipt. The XLSX, raw packet, and decode key remain gitignored and untracked. No production source, provider,
router, default, prompt, parser, holdout, or human rating was changed. Existing unrelated demo/backlog worktree edits
were left untouched.

## 21. Validation

- Workbook SHA-256 matched before freeze, immediately before Commit A, and after decode.
- Historical `synthesis-overview-v1` and `benchmark-calibration-v1` freeze manifests were re-hashed successfully.
- Commit A predates the decode receipt and contains only `human-adjudication-freeze.json`.
- All 144 workbook rows join uniquely to the original packet/key; all 48 candidate-fixture cells contain three
  response mappings.
- Omitted exploratory dimensions remain unscored in all 144 candidate and 9 control rows.
- No identity label was present in the frozen workbook; no raw key, packet, private path, or secret is tracked.
- The challenge holdout remains unopened and no model/provider call occurred.
- JSON, pre-commit documentation hooks, private-path/secret scans, and `git diff --check` were run for touched files.
- A full application suite was intentionally not run because no application code or executable benchmark logic
  changed.

## 22. Decision / Hand-Off

**POST-DECODE ANALYSIS COMPLETE**

Exact next scientific action: preregister the lean review schema, then conduct the bounded primary-synthesis
transferability probe before broader recommendation/routing work. Do not open the Overview challenge holdout or
change production routing as part of that probe.
