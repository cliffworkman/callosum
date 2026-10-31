# G1: DeBERTa exact-threshold safety check (receipt)

**Date:** 2026-10-31.
**Authority:** the "Increment 614 and Bounded DeBERTa Qualification" instruction, §2.
**Bounds:** one offline rescore of existing labelled pairs. No model download, no new claims, no threshold change,
no adjudication, no model selection.

**Recommendation for the G1 component: CONDITIONAL** (predeclared reading rule; see §6).
- The primary safety criterion holds on both sets.
- One secondary measure is worse by one pair on the human-labelled set.
- Not HOLD.

## 1. What ran
- **Predeclaration** `.local/inc614-g1/PREDECLARATION.md`, SHA-256 `fb80ff73…27b24`, was written and hashed before
  any score existed. The harness refuses to run if the hash differs.
- **Path:** the application's own verification code, for both models.
  - `LocalCitationVerifier.verify_many` with `VerificationConfig()` defaults;
  - `resolve_embedding_model` (MiniLM, pinned);
  - `resolve_support_scorer(app, nli_profile=…)` called as `routers/summaries.py:351-352` calls it;
  - `SQLiteVecVectorStore` and `embed_chunks`;
  - a disposable alembic-head DB at `.local/inc614-g1/g1_disposable.sqlite`.
  - Statuses come from `_status` unchanged.
  - Offline throughout: sockets refused, HF offline, `local_files_only`.
- **Effective thresholds** (the same for both models): retrieval ≥ 0.70 (MiniLM cosine), quote = 1.0 (canonical
  containment), support ≥ 0.55, contradiction ≥ 0.55 and greater than support.
  - `contradicted` is checked first;
  - `verified` needs all three gates;
  - `weak` needs retrieval or support;
  - otherwise `unverified`.
- **Models:**
  - `cross-encoder/nli-MiniLM2-L6-H768` @ `b95119ce…`;
  - `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` @ `6f5cf0a2…`;
  - embeddings `all-MiniLM-L6-v2` @ `1110a243…`.
  - Recorded provenance: `thresholds_calibrated_on = nli-MiniLM2`, `embedding_fallback = False`.
- **Wiring check.** On the 99 Set A pairs:
  - MiniLM2 support/contradiction through the app path equal the frozen Phase 34 stored values exactly (max diff
    0.0);
  - DeBERTa equals the frozen standalone bakeoff scores within 1.7 × 10⁻⁶.

  The rescore therefore measures the app's decision logic applied to the same model outputs.

## 2. Inputs (identity verified by hash before scoring)
| Set | Source | Labels | Hashes |
|---|---|---|---|
| **A**, AI-adjudicated | Phase 34 99 pairs. The cited chunk is the original library chunk text, with the quote contained in it (99/99) | One blinded ChatGPT adjudication pass: 59 supported, 27 negative (20 contradicted, 7 unsupported; **all negatives synthetic**), 5 partial, 5 unresolved, 3 meta | pairs `577b0338…`, key `ec06f238…`, labels `d75e3086…`, rows `0cca1148…` |
| **B**, human-labelled | SciFact dev gold-rationale pairs, rebuilt exactly as Phase 34 m5 did (138 SUPPORT, 71 CONTRADICT, counts asserted). Chunk = premise | SciFact human labels; natural contradictions | `claims_dev.jsonl` and `corpus.jsonl` hashes recorded in `g1_raw.json` |

The sets were scored and reported separately and never pooled.

**Outputs:**
- `.local/inc614-g1/g1_raw.json` (`2a7ba846…`): every per-pair score and status;
- `g1_summary.json` (`9542539f…`).

## 3. Primary criterion: serious false admissions (a negative pair receives `verified`)
| | MiniLM2 (current app) | DeBERTa |
|---|---|---|
| Set A negatives `verified` (of 27) | **5**: E004, E064, E078, E092, E096 | **1**: E064 |
| Set B CONTRADICT `verified` (of 71) | **1**: S219 | **1**: S219 (the same pair) |

**The predeclared non-inferiority (margin 0) holds on both sets.** DeBERTa introduces no serious false admission that
MiniLM2 does not already make.

The two remaining admissions are shared by both models:
- **E064, referent swap.** The claim says "more trustworthy" where the source says "more trusting". Support is
  MiniLM2 0.962 and DeBERTa 0.989.
- **S219.** The claim says "CX3CR1 on Th2 cells *suppresses* airway inflammation". The abstract shows the opposite.
  Support is MiniLM2 0.730 and DeBERTa 0.867.

Both are genuine verifier blind spots. The existing app already admits them today.

MiniLM2 admits these that DeBERTa rejects:
- **E078, reversed comparison:** DeBERTa marks it `contradicted`, 0.952.
- **E092, cognitive changed to affective empathy:** `contradicted`, 0.970.
- **E004, added outcome "and against people of color":** `weak`.
- **E096, a stated aim presented as a finding:** `weak`.

## 4. Secondary measures
| | MiniLM2 | DeBERTa |
|---|---|---|
| Set A contradicted controls marked `contradicted` (of 20) | 12 | **18** |
| Set B CONTRADICT marked `contradicted` (of 71) | 28 | **47** |
| Set A supported `verified` (of 59) | 14 | 17 |
| Set B SUPPORT `verified` (of 138) | 21 | 33 |
| **Set A supported marked `contradicted`** (false "the source disagrees") | 1 (E082) | **0** |
| **Set B SUPPORT marked `contradicted`** | 6 | **7** |

**Set B false contradictions.**
- 2 are shared (S1335, S218).
- 4 are MiniLM2 only (S1132, S1298, S148, S501).
- **5 are DeBERTa only:**
  - S1290: "inverse relationship between hip fractures and statin use", against a reduced risk with statins;
    contradiction 0.988.
  - S1389: mTORC2 / xCT inhibition; contradiction 0.788.
  - S1104: lower mortality with DOACs than warfarin; contradiction 0.656.
  - S279: a typo-laden genome-length claim, "baise pairs"; contradiction 0.847.
  - S1385: a claim whose quote literally says the opposite ("enhancing cSMAC formation **reduced** stimulatory
    capacity"). The SciFact label may be questionable here, but it is used as given.

A false `contradicted` is shown with its quote and is a signal, not an admission. It nonetheless tells the user the
source disagrees when it does not. That is why it was predeclared as a secondary measure.

**By failure type (Set A negatives; status counts).**

| Type (n) | MiniLM2 | DeBERTa |
|---|---|---|
| Negation / reversed (10) | 8 contradicted, 1 weak, 1 unverified | **10 contradicted** |
| Referent swap (4) | **3 verified**, 1 contradicted | 1 verified (E064), 3 contradicted |
| Fabricated / causal overstatement (3) | 1 verified (E004), 1 weak (E009 correlation→cause), 1 contradicted | 2 weak, 1 contradicted |
| Incorrect population (5) | 1 contradicted, 1 weak, 3 unverified | 2 contradicted, 1 weak, 2 unverified |
| Omitted qualification (2) | 1 contradicted, 1 weak | 2 contradicted |
| Magnitude (1) | contradicted | contradicted |
| Attribution (1) | weak | weak |
| Aim as finding (1) | **verified** (E096) | weak |

**Note on E009** (correlation stated as cause). Phase 34 found that both models admit it at a pure support threshold.
In the app it is `weak` for both, because its MiniLM retrieval similarity is below 0.70. **It is the retrieval gate,
not NLI, that keeps this causal overstatement out**, so it is a fragile protection. The same holds generally:
- 49 of 99 Set A pairs and 142 of 209 Set B pairs fall below the retrieval gate, so they cannot be `verified` under
  either model.
- Most `weak` outcomes are retrieval-limited.

**Other Set A classes.**
- Partial pairs (5): the same statuses under both models (3 verified, 2 weak). **Lost qualifications are not
  improved.**
- Unresolved (5): the same statuses.
- Meta (3): E017 changes from `contradicted` to `unverified`; E036, a "does not support" meta statement, is
  `verified` under both.

**Supported lost.** E050 changes from `verified` to `weak`: a study-aim statement, DeBERTa support 0.339.

**Disagreements.** 15 in Set A and 66 in Set B, all listed with scores in `g1_summary.json` → `disagreements`.

## 5. What this does and does not establish
**It establishes:**
- At the app's exact thresholds and decision logic, DeBERTa does not increase scientifically serious false admissions
  on either set.
- It removes four of MiniLM2's five Set A false admissions.
- It recognizes markedly more contradictions on both sets: 18 vs 12, and 47 vs 28.
- It verifies more supported claims.

**Not established:**
- **General superiority.**
- **Calibration.** 0.55/0.55 remains a MiniLM2-calibrated value. DeBERTa's probabilities are more extreme, so the
  thresholds act as a different operating point. This sample shows that point is not less safe on serious admissions.
  It does not show it is the right point.
- **Performance on natural (non-synthetic) negatives of Callosum's own claim style.** Set A has none.

**Limits:**
- **Small samples:** 27 and 71 negatives; a 1-pair difference is within noise.
- **Set A labels:** one AI adjudication pass, and its synthetic negatives were built from MiniLM-verified claims,
  which biases them towards the challenger.
- **Set B:** seen post hoc in Phase 34 (under a pure-threshold rule, not this app logic). No threshold was chosen on
  either set here, and none may be chosen on them later and then called confirmed.

## 6. Reading under the predeclared rule
- **Primary:** holds on A and on B, so it is not HOLD.
- **GO** required, in addition, no more supported pairs marked `contradicted` than MiniLM2 on either set. That fails
  on B, 7 against 6. **Result: CONDITIONAL.**

**Is there a consequential reason to delay automatic activation?**
- **Not on admission safety.** That is the outcome the gate exists to protect, and it holds.
- **The conditional element is a precision cost of the contradiction signal:** five new false "source disagrees"
  labels, against four removed, on biomedical inference pairs.

**Smallest proportionate options** (none is a new adjudication):
1. **Accept as is.** Activate DeBERTa when G2 passes, and disclose in the provenance line that thresholds are
   MiniLM2-calibrated (already recorded).
2. **Accept with a display hedge.** Keep `contradicted` under DeBERTa visibly framed as "the model judges this source
   to disagree, check the quote", as the existing signal-not-verdict copy does. No threshold change.
3. **Defer to a fresh, natural-negative human-labelled set.** The Phase 34 §7 qualification. Larger, and not needed for
   admission safety.

The threshold and default-on decision remains Cliff's.
