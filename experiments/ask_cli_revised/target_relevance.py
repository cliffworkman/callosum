"""PHASE 34 / I4-1j -- pure, instance-local target-relevance primitives.

Answers a question strictly narrower than, and independent of, local assertion attachment (I4-1d) or
evidence-provenance admissibility (I4-1e/f/g): given one role-instance's own target value (a sibling
identification role's already-bound referent, e.g. c8's `"attractiveness"`), WHICH of the local assertions
already found in some bounded, relationship-derived scope actually bear on it?

This module imports nothing from the I4-1 pure/unwired assertion classifier family's two sibling modules, and
nothing from the production sufficiency engine/mapping modules -- it is a standalone, three-layer-separated
primitive (I4-1i's own §7 instruction). (Deliberately kept out of every comment/docstring below, including
this one: naming either classifier-family module by name here would trip their own unwired static guards, a
plain text-substring scan with no distinction between an import and a comment -- the exact self-inflicted
trip I4-1g's own report already documents and fixed the same way.)

    A. ALLOWED EVIDENCE SCOPE   -- a caller-supplied set of proposition ids (`allowed_proposition_ids`),
                                    derived from a relationship (e.g. `same_proposition`'s own sibling
                                    support set); this module never computes or interprets that scope itself.
    B. TARGET TEXT              -- a caller-supplied literal string (a sibling role's own `exact_text`).
    C. LOCAL ASSERTION CANDIDATES -- a caller-supplied list of already-resolved local assertions, each
                                    `{"proposition_id": str, "text": str, ...}` (extra keys are passed
                                    through untouched; this module only ever reads `proposition_id`/`text`).
    D. MATCHING                 -- literal/canonical containment, case-insensitive, with the existing
                                    `dehyphenate_for_matching` fallback -- no stemming, no embeddings, no
                                    synonym expansion, no model call, no domain lexicon.

Nothing here decides WHERE candidate assertions come from (that is I4-2a's own future wiring of
`locate_containing_assertion` against each unit in a role's own scope) or WHETHER a relevant-but-excluded
assertion is admissible (I4-1e/g's `support_policy`, deliberately out of scope here per the directive).
"""

from __future__ import annotations

from experiments.ask_cli_revised.contract_directed import attribution as attr

MATCH_OUTCOMES = ("unmatched", "unique", "multiple")


def local_assertion_relevance(target_text: str, assertion_text: str) -> bool:
    """Pure literal/canonical containment, case-insensitive. Tries the literal text first; falls back to
    `attribution.dehyphenate_for_matching` only when the literal check fails -- the exact same two-step
    discipline `sufficiency_mapping._match_instrument` already uses for this identical class of sealed-PDF
    line-wrap artifact (e.g. the real preserved `"attrac- tiveness"` case), never a new mechanism. No
    stemming, no fuzzy matching, no synonym expansion."""
    if not target_text or not assertion_text:
        return False
    needle = target_text.lower()
    if needle in assertion_text.lower():
        return True
    cleaned = attr.dehyphenate_for_matching(assertion_text)
    if cleaned != assertion_text and needle in cleaned.lower():
        return True
    return False


def match_target_to_assertions(
    *,
    target_text: str,
    candidate_assertions: list,
    allowed_proposition_ids=None,
) -> dict:
    """The one pure matcher. `allowed_proposition_ids`, when supplied, is a plain scope FILTER applied before
    any lexical matching -- this function never knows or cares why that scope exists (it might be
    `same_proposition`'s own sibling support set, per I4-1i §8/§9's real generic-anatomical-noun
    over-matching contrast, or `None` for an unscoped search); it is purely a relevance-derived constraint
    on which candidates are even considered, handed in by the caller.

    Returns ALL matching candidates, never a first match:

    - zero matches  -> `{"relevance": "unmatched", "matches": []}`
    - exactly one    -> `{"relevance": "unique", "matches": [that one]}`
    - two or more     -> `{"relevance": "multiple", "matches": [all of them]}`  -- genuine evidence
      plurality, preserved, never collapsed into an ambiguous state merely because there is more than one.
    """
    scoped = candidate_assertions
    if allowed_proposition_ids is not None:
        allowed = set(allowed_proposition_ids)
        scoped = [a for a in candidate_assertions if a.get("proposition_id") in allowed]
    matches = [a for a in scoped if local_assertion_relevance(target_text, a.get("text", ""))]
    if not matches:
        relevance = "unmatched"
    elif len(matches) == 1:
        relevance = "unique"
    else:
        relevance = "multiple"
    return {"relevance": relevance, "matches": matches}


def verify_shared_local_assertion(*, sibling_target_text: str, evidence_assertion_text: str) -> bool:
    """The pure, CORRECTLY-SCOPED `same_local_assertion` verifier primitive (I4-1i §5, I4-1j §13): does the
    evidence role's own already-resolved LOCAL assertion text (never a whole passage) contain the sibling
    role's own target text?

    Deliberately NOT registered into `sufficiency_engine._VERIFIER_FUNCS` in this increment -- see the I4-1j
    results report's own section on this. In short: the `(role_bindings, roles)` signature every existing
    verifier uses CAN represent this function's real inputs (both already live on `role_bindings` as
    `exact_text`) with no hidden global read, satisfying the directive's own registration test -- but for
    every real `achieved_outcome_predicate` binding today, `exact_text` is still the WHOLE PASSAGE (I4-1d's
    own disclosed, unfixed limitation), not a narrowed local assertion. Calling this function with a whole
    passage as `evidence_assertion_text` does not fail loudly; it returns a NON-DISCRIMINATING, frequently-
    true answer (every one of c8's five real instances would pass, because each trait term DOES occur
    SOMEWHERE in the shared whole passage, regardless of which of its two assertions), which would be
    actively misleading if ever consulted -- worse than leaving the check unregistered. Registration becomes
    safe the moment a caller can supply this function's second argument as a genuinely narrowed local
    assertion text (I4-2a's own future span-narrowing work), with zero change needed here."""
    return local_assertion_relevance(sibling_target_text, evidence_assertion_text)
