# Increment 607 — Reference-exclusion repair: narrow-path bibliography demotion + duplicate-DOI ownership

## Implemented

- **Problem (q_lld reference-leakage investigation, 2026-10-28).** Two defects let bibliography entries fill
  evidence slots in the narrow synthesis path:
  - The anchored `chunk_structure` detector's labels (inc 577) were computed but never consumed there.
  - A merged duplicate paper (202) had captured live paper 171's DOI, so 171 received no anchored reference region.
- **`app/backend/summarization/evidence_eligibility.py` (new).** The shared pure policy. Precedence:
  1. a verified native exclusion mapping (union coverage ≥ 0.85) → withheld (research route only);
  2. a current anchored `bibliographic` label → disputed (demoted);
  3. otherwise eligible or eligible_mixed.

  A stale classification is ignored.
- **`app/backend/summarization/evidence_selection.py` (new).** The narrow-path seam. It orders eligible chunks before
  disputed ones; a disputed chunk fills slots only when eligible candidates run out, and that fallback is logged.
- **`app/backend/summarization/pipeline.py`.** Calls the seam before slicing the reading budget; query scope fetches
  3× top_k.
- **`app/backend/persistence/chunk_structure_repo.py`.** Adds `structure_role_states`, a batched read that reports
  why a label is stale.
- **`tools/backfill_chunk_structure.py`.** Adds `doi_owners`: a DOI resolves to the live canonical paper or papers,
  merge chains are followed, and ambiguous live groups are reported.
- **Research route** (`experiments/ask_cli_revised/focused_discovery/reference_eligibility*.py`): the adapter for
  Docling native regions, the frozen read-only counterfactual and validation CLI, and the post-generation
  `validate_claims`.
- **Documentation:** `.claude/CLAUDE.md` corrects the inc-577 statement "nothing on the retrieval path reads it";
  `.claude/changes.md`; audit record `.claude/security-audits/2026-10-29_reference-evidence-eligibility.md` (PASS).
- **Drift-gate receipts.** `demo/experience-coverage-v1.json` and `www/showcase-coverage.json` extend Cliff's existing
  demo/showcase deferral from 606 to 607, via each tool's `--decline --note`. Cliff authorized this on 2026-10-29.
  - Why it was needed: the gates key on the increment counter, so advancing to 607 failed them although this repair
    changes no demo or website surface.
  - What it is not: no visual review or snapshot refresh is claimed, and no review fingerprint changed.
- **Commit scope.** 18 files: the 15 reviewed repair files, this note, and the 2 receipts above. The 15-file
  readiness list grew by these 3; nothing else is included.

## Key technical detail

- **Labels demote; they never delete.** The anchored detector has about 77% precision, so the application treats a
  label as an ordering signal only. The application has no native region authority, so nothing is withheld there.
- **H1 latency fix (from the pre-commit review).** The seam had built a canonical comparison key for every
  candidate, but `decide` reads it only in the native coverage branch, which the application never reaches. The
  seam now passes `key_length=0`.
  - Equivalence: identical eligible lists, disputed lists, order and log lines over 180 cases on the frozen MiniLM
    library.
  - Median seam cost for 50 selected papers (18,970 candidates): 25.0 s before, 0.51 s after.
  - Guard: `test_app_seam_never_builds_comparison_keys_and_decides_identically`.
- **Withdrawn corrections.** Two native-downgrade rules and one guarded-join localization change failed
  preregistered paper-level held-out criteria (scientific rates 0.03 / 0.07 / 0.20) and were not implemented.
  - Limits of that evaluation: one library, one annotator; not an independent library.
  - Evidence: `.local/reference-exclusion-repair-20261029Z/holdout/HOLDOUT_EVALUATION.md`.
- **Known scientific limitation (research route).** Native exclusion withholds some genuine science:
  - 23431 and 38379 (Methods) and 35671 (Results) are withheld;
  - the mislabelled Methods regions a11 `#/texts/39` and a57 `#/texts/79` are harmless today only because their
    mapping fails.

  These are permanent diagnostic fixtures. Strict expected-failure tests assert the scientifically correct outcome,
  so a future general fix shows up as XPASS; no production code names any unit.
- **The displaced passages are 4 distinct genuine passages (5 unit identities)**, all through anchored false
  positives. They are demoted, not deleted.
- **Unresolved diagnostic observation.** One read-only counterfactual run segfaulted natively, while it ran
  concurrently with the full suite, and wrote no output. Two separate complete runs were byte-identical to each other
  and to the recorded outputs. The cause of the segfault is not established.

## Manual verification script

1. Run `pytest tests/test_evidence_eligibility.py tests/test_reference_eligibility_selection.py tests/test_backfill_doi_owners.py -q`.
2. With the local frozen q_lld artifacts present, run
   `pytest experiments/ask_cli_revised/focused_discovery/tests/test_reference_eligibility_frozen.py -rxX -q`.
   Expect 4 XFAIL, each failing on its scientific assertion. `--runxfail` shows `'withheld' != 'withheld'` and one
   `exact_quote_inside_excluded_span` finding.
3. On a library with `chunk_structure` rows, run a papers-scope synthesis and check the backend log for
   `reference eligibility: N of M candidates demoted as disputed bibliography`. A library without rows is an exact
   no-op.
4. **Not performed; needs separate authorization:** a live `tools/backfill_chunk_structure.py --force --paper-id <id>`
   re-derivation for the DOI-affected papers.

## Pytest

- **Targeted + summarization + frozen-fixture set:** 148 passed, 4 xfailed.
- **The 15 repair files applied to a clean `git archive HEAD` export:** 26 passed, 15 skipped (frozen data absent).
- **Full suite** (`-n 4`): 3,467 passed, 41 failed, 12 skipped. The 41 failures are the same test IDs as the
  pre-change run. Each failure is environmental: Node/citeproc unavailable (503), esbuild not installed, or
  `dist-demo` absent. They were not re-run in an environment that has Node.
