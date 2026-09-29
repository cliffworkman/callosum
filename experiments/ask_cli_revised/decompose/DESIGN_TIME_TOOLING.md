# Design-time hierarchy-construction tooling (preserved, non-runtime)

This directory (`decompose/`) holds two things that are easy to conflate but must stay distinct:

## Runtime primitives (10 files) — imported by the Ask pipeline

`__init__.py`, `calllog.py`, `execution.py`, `ledger.py`, `lexical.py`, `model.py`, `parent.py`,
`requirements.py`, `structure.py`, `tree.py`.

These are the only `decompose/` modules the executable Ask pipeline touches. Confirmed by exhaustive
grep across every `.py` file in the repository (`experiments/ask_cli_revised/hierarchy_contract.py` is
the *only* caller of `decompose` anywhere outside this directory, and it imports exactly
`execution` and `tree`):

```
experiments/ask_cli_revised/hierarchy_contract.py:42:from experiments.ask_cli_revised.decompose import execution, tree
experiments/ask_cli_revised/hierarchy_contract.py:43:from experiments.ask_cli_revised.decompose.tree import CLOSURE_RULE
```

## Design-time construction/review tooling (30 files) — NOT imported by the Ask pipeline

`__main__.py`, `checks.py`, `children.py`, `clarifications.py`, `engine.py`, `gate.py`,
`integrated.py`, `nosplit_check.py`, `passthrough.py`, `prepare.py`, `prompts.py`,
`prompts_prepared.py`, `reconcile.py`, `reference_compare.py`, `relations.py`, `report.py`,
`scaffold.py`, `views.py`, `wording_check.py`, plus 12 `test_*.py` files
(`test_closure.py`, `test_closure_v8.py`, `test_correction_pass.py`, `test_decompose.py`,
`test_integrated.py`, `test_ledger.py`, `test_policy.py`, `test_prepared.py`, `test_prompts.py`,
`test_relations.py`, `test_scoped_wording.py`, `test_tree.py`).

**What this is:** the actual engine that generated and iteratively reviewed the approved v8 hierarchy
(the child-question writer, its deterministic traceability/diagnostic checks, the relational-obligation
parser, and the span-linked user-clarification applier — see each file's own module docstring). It
produced `hierarchy_contract.frozen.json` (sha256 `1e1b1630291dcb6e81a73640ae44c07bec6eec7f92cf906c27f5e87637729e8d`,
verified byte-identical to the dirty `ask-e2e` working copy this was preserved from) through the iterative
v2→v8 development/review runs recorded under `.local/decompose-runs/aib-dev/` (gitignored; not part of
this commit — independently preserved in a separate, non-git snapshot; see the Phase 2 integration
manifest for its location and manifest hash).

**Why it's here and not deleted:** Phase 2, Section 4 required investigating whether these files (named
explicitly: `children.py`, `checks.py`, `relations.py`, `clarifications.py`) are design-time tooling or a
runtime dependency, and to "preserve them and their provenance regardless" of the answer. The answer is
design-time tooling — confirmed by call-path grep, not assumed. The other 26 files in this set were
preserved alongside the four explicitly named ones because they form one interconnected dependency
closure with them (e.g. `children.py` imports `checks`, `relations`, `clarifications`, `engine`-adjacent
modules directly) — cherry-picking only the four named files would have left an unimportable partial copy.

**Confirmed via this repository's own commit history:** `git log --oneline -- decompose/` shows exactly
one commit, `2b340ff1`, which added only the 10 runtime primitives above. The person who made that commit
deliberately did not commit this tooling — consistent with treating it as design-time-only from the start.

**Do not import from this tooling in any runtime module.** If a future change needs one of its primitives
at runtime, that is a deliberate architectural decision to make explicitly (add the import, and explain
why in the commit message and the increment/handback notes) — not something to do by moving files around
silently.
