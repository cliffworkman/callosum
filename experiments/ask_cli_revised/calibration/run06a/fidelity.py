"""Run 0.6a HUMAN fidelity reference (Phase 2) — authored from source + candidate text ONLY.

Textual-fidelity judgment: does the candidate faithfully represent what the user asked in THIS source unit,
using the full question only to resolve references? No domain knowledge, no AIB/scientific answer targets, no
truth judgment. Labels are frozen before any policy runs (the orchestrator hashes `fidelity_labels.json` at
start and re-asserts at end). Debatable calls carry an inline uncertainty note; they are never edited to move
a policy's measured performance.

Label set: FAITHFUL | LOSS | ADDITION | LOSS_AND_ADDITION | MALFORMED_OR_UNUSABLE.

This module is the reference standard and is NEVER imported by the metric-only policy (`policy_a` / the Hm
path in `hybrid`); a self-check enforces that.
"""

from __future__ import annotations

LABELS = ("FAITHFUL", "LOSS", "ADDITION", "LOSS_AND_ADDITION", "MALFORMED_OR_UNUSABLE")

# case -> style -> item_id -> {"label", "reason"}.  style "selected" holds H0 items whose text is NOT in the
# 02 candidate pool (only q_depr u8-r1, the repaired minimal). Baselines are FAITHFUL by construction
# (exact source text) and generated in code, not listed here.
ITEM: dict[str, dict[str, dict[str, dict[str, str]]]] = {
    "q_aib": {
        "minimal": {
            "u1-r1": {"label": "FAITHFUL", "reason": "brain/behavior/attitudes preserved; only standardizes wording."},
            "u2-r1": {"label": "LOSS_AND_ADDITION", "reason": "drops the which-kinds-of-behaviors/attitudes granularity; adds 'measuring tools' (u3's scales)."},
            "u3-r1": {"label": "FAITHFUL", "reason": "scales request preserved; 'its effects' resolves the reference."},
            "u4-r1": {"label": "FAITHFUL", "reason": "cross-cultural-evidence request preserved (minor 'abbias' token garble)."},
            "u5-r1": {"label": "LOSS", "reason": "keeps 'which cultures' but drops 'how was this measured'."},
            "u6-r1": {"label": "FAITHFUL", "reason": "effective interventions to reduce it — preserved."},
        },
        "relation": {
            "u1-r1": {"label": "ADDITION", "reason": "merges personality-traits + scales (other units) into u1 and instantiates example behaviors; trailing truncation."},
            "u2-r1": {"label": "LOSS", "reason": "drops the kinds-of-behaviors/attitudes granularity and the personality-traits request."},
            "u3-r1": {"label": "LOSS_AND_ADDITION", "reason": "replaces the scales request wholesale with a personality-traits question (u2)."},
            "u4-r1": {"label": "LOSS", "reason": "generalizes 'the bias' to 'particular biases' — loses the specific referent."},
            "u5-r1": {"label": "ADDITION", "reason": "keeps cultures+measurement but misnames the bias ('anomalous imbalance') and adds behavior/attitudes."},
            "u6-r1": {"label": "LOSS_AND_ADDITION", "reason": "misnames the bias as 'negativity bias' and softens 'effective interventions'."},
        },
        "multi": {
            "u1-r1": {"label": "ADDITION", "reason": "SPECIMEN: instantiates 'aggression, impulsivity, decision-making' + cultural/personality traits at sls 0.91."},
            "u2-r1": {"label": "LOSS", "reason": "drops the personality-traits request and 'which kinds of attitudes'."},
            "u3-r1": {"label": "FAITHFUL", "reason": "scales request preserved (minor 'bad is anomalous' word-order garble)."},
            "u3-r2": {"label": "ADDITION", "reason": "SPECIMEN: 'which personality traits relate' — not in 'and using which scales?' (sls 0.16)."},
            "u3-r3": {"label": "ADDITION", "reason": "SPECIMEN: 'who has these traits' — invented sub-request (sls 0.17)."},
            "u4-r1": {"label": "FAITHFUL", "reason": "cross-cultural + specific AIB bias preserved."},
            "u5-r1": {"label": "ADDITION", "reason": "keeps cultures+methods but adds 'validity', 'individual differences / trait-like characteristics'."},
            "u5-r2": {"label": "ADDITION", "reason": "new cross-cultural-comparison sub-question; trailing-comma garble."},
            "u5-r3": {"label": "ADDITION", "reason": "SPECIMEN: 'economic status, education level, etc.' — not in source."},
            "u6-r1": {"label": "ADDITION", "reason": "keeps interventions+effective but adds 'on brain and behavior, and attitudes' (other units)."},
        },
    },
    "q_depr": {
        "minimal": {
            "u1-r1": {"label": "FAITHFUL", "reason": "full systems-synthesis + cognitive-decline/dementia + my-library preserved."},
            "u2-r1": {"label": "MALFORMED_OR_UNUSABLE", "reason": "SPECIMEN: construct survives but framed as a first-person meta-question ('Do I need more information...'). UNCERTAIN: borderline LOSS vs unusable."},
            "u3-r1": {"label": "FAITHFUL", "reason": "'amyloid' -> 'amyloid deposition'; canonical facet, construct preserved. UNCERTAIN: mild specification."},
            "u4-r1": {"label": "FAITHFUL", "reason": "'glucose metabolism in late-life depression' — bare term reference-resolved to the question topic."},
            "u5-r1": {"label": "FAITHFUL", "reason": "'gray matter structure' preserved."},
            "u6-r1": {"label": "FAITHFUL", "reason": "'memory and executive function' preserved as cognitive functions."},
            "u7-r1": {"label": "FAITHFUL", "reason": "open-ended kept open-ended ('and more specific findings related to these'); no instantiation."},
            "u8-r1": {"label": "LOSS", "reason": "drops 'what role each plays' AND 'mixed/null/uncertain findings' (u8's distinctive requests); overlaps u1. Low sls (0.27) correctly flags it."},
        },
        "relation": {
            "u1-r1": {"label": "LOSS_AND_ADDITION", "reason": "narrows whole-systems synthesis to amyloidosis (loss) and adds an amyloid focus not in u1."},
            "u2-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses 'serotonergic' entirely; substitutes the other units' constructs."},
            "u3-r1": {"label": "ADDITION", "reason": "'amyloid metabolism' adds a facet not in bare 'amyloid' (and collides with u4)."},
            "u4-r1": {"label": "MALFORMED_OR_UNUSABLE", "reason": "'Amyloid{' — garbled and wrong construct (not glucose)."},
            "u5-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses 'gray-matter structure'; substitutes 'midlife brain aging'."},
            "u6-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses memory/executive; substitutes 'cognitive decline and dementia' (u1)."},
            "u7-r1": {"label": "FAITHFUL", "reason": "open-ended preserved as 'additional neurological/mental-health aspects noted in studies'."},
            "u8-r1": {"label": "FAITHFUL", "reason": "SPECIMEN (low-sls-faithful, sls 0.13): preserves the structured account + 'varying results' (=mixed/null/uncertain). UNCERTAIN: adds a memory/executive example."},
        },
        "multi": {
            "u1-r1": {"label": "ADDITION", "reason": "adds age-matched-controls / early-stage / quantitative-vs-qualitative; core preserved."},
            "u2-r1": {"label": "ADDITION", "reason": "keeps serotonergic but adds 'amyloid' (u3); trailing ']' garble."},
            "u2-r2": {"label": "ADDITION", "reason": "'glutamate metabolism' — off-topic, never requested."},
            "u3-r1": {"label": "ADDITION", "reason": "large instantiation (Aβ, memory performance, age-matched controls); amyloid preserved."},
            "u4-r1": {"label": "ADDITION", "reason": "keeps glucose metabolism but adds 'memory and executive function' (u6)."},
            "u5-r1": {"label": "FAITHFUL", "reason": "'gray-matter structure change and late-life depression' — construct preserved (mild 'change' facet)."},
            "u6-r1": {"label": "FAITHFUL", "reason": "memory + executive function preserved; 'late-life depression' resolves the reference."},
            "u7-r1": {"label": "FAITHFUL", "reason": "open-ended 'additional aspects' preserved without instantiation."},
            "u8-r1": {"label": "ADDITION", "reason": "instantiates all u2-u6 constructs into u8; keeps 'inconsistent findings'; trailing garble."},
        },
        "selected": {
            "u8-r1": {"label": "FAITHFUL", "reason": "REPAIRED minimal u8: restores 'what role each plays' + 'mixed/null/uncertain findings'. Repair FIXED the pre-repair minimal-u8 LOSS."},
        },
    },
    "q_builtenv": {
        "minimal": {
            "u1-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses 'built environment / fMRI / EEG / synthesis'; pulls in the whole interest list (u2-u7)."},
            "u2-r1": {"label": "FAITHFUL", "reason": "aesthetic appreciation preserved; 'brain regions' is the question's own frame."},
            "u3-r1": {"label": "FAITHFUL", "reason": "'brain areas involved in coherence' — construct preserved."},
            "u4-r1": {"label": "MALFORMED_OR_UNUSABLE", "reason": "'sensation' != fascination; '} {' garble."},
            "u5-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses 'hominess'; substitutes coherence/built-environment."},
            "u6-r1": {"label": "MALFORMED_OR_UNUSABLE", "reason": "truncated 'ce...'."},
            "u7-r1": {"label": "MALFORMED_OR_UNUSABLE", "reason": "'}{' — pure garble."},
            "u8-r1": {"label": "FAITHFUL", "reason": "'List of brain areas involved and their role' — preserved."},
        },
        "relation": {
            "u1-r1": {"label": "FAITHFUL", "reason": "SPECIMEN (faithful Qwen rewrite discarded by whole-question baseline fallback): built environment + fMRI + EEG + synthesis preserved (mild 'Do I need to' framing)."},
            "u2-r1": {"label": "MALFORMED_OR_UNUSABLE", "reason": "'brain area involvement}{ {' — garbled; loses aesthetic appreciation."},
            "u3-r1": {"label": "LOSS_AND_ADDITION", "reason": "'functional connectivity maps' misinterprets 'coherence'."},
            "u4-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses 'fascination'; dumps an unrelated list of sensory modalities."},
            "u5-r1": {"label": "LOSS", "reason": "loses 'hominess'; vague 'visual understanding'."},
            "u6-r1": {"label": "LOSS_AND_ADDITION", "reason": "loses 'ceiling height'; adds 'cognitive map formation'."},
            "u7-r1": {"label": "FAITHFUL", "reason": "echoes the source verbatim ('visuospatial processing and more.'); 'and more' preserved."},
            "u8-r1": {"label": "FAITHFUL", "reason": "list + role preserved; adds the question's own 'built environment perception' scope."},
        },
        "multi": {
            "u1-r1": {"label": "LOSS_AND_ADDITION", "reason": "'natural environments' distorts 'built environment' (loss); adds interest list; drops fMRI/EEG."},
            "u2-r1": {"label": "FAITHFUL", "reason": "aesthetic appreciation preserved."},
            "u2-r2": {"label": "ADDITION", "reason": "pulls the whole interest list into u2."},
            "u2-r3": {"label": "ADDITION", "reason": "instantiates 'natural scenes and complex designs'."},
            "u3-r1": {"label": "FAITHFUL", "reason": "coherence preserved."},
            "u4-r1": {"label": "LOSS", "reason": "'pursuit of aesthetics' != fascination."},
            "u4-r2": {"label": "LOSS_AND_ADDITION", "reason": "'eye for beauty / visual art' != fascination."},
            "u4-r3": {"label": "FAITHFUL", "reason": "'regions experience fascination during aesthetic appreciation' — construct preserved."},
            "u5-r1": {"label": "FAITHFUL", "reason": "'homeliness / home environment perception' faithfully resolves 'hominess' (low sls 0.18 despite fidelity)."},
            "u6-r1": {"label": "FAITHFUL", "reason": "ceiling height preserved (mild aesthetics/comfort addition)."},
            "u6-r2": {"label": "FAITHFUL", "reason": "ceiling height + fMRI preserved."},
            "u7-r1": {"label": "ADDITION", "reason": "adds comparison to coherence/fascination; drops 'and more' open-endedness."},
            "u8-r1": {"label": "FAITHFUL", "reason": "splits into two but preserves both list + role requests."},
        },
    },
}

# case -> unit -> {"label","reason"} for the multi BUNDLE as a whole (Phase 2: label each rewrite AND the bundle).
MULTI_BUNDLE: dict[str, dict[str, dict[str, str]]] = {
    "q_aib": {
        "u3": {"label": "ADDITION", "reason": "scales preserved (r1) but bundled with two unsourced sub-requests (r2/r3)."},
        "u5": {"label": "ADDITION", "reason": "cultures+methods preserved (r1) but augmented + two extra sub-questions."},
    },
    "q_depr": {
        "u2": {"label": "ADDITION", "reason": "serotonergic preserved (r1) but bundled with amyloid + off-topic glutamate."},
    },
    "q_builtenv": {
        "u2": {"label": "ADDITION", "reason": "aesthetic appreciation preserved (r1) but two extra list-pulling sub-questions."},
        "u4": {"label": "LOSS_AND_ADDITION", "reason": "one faithful item (r3) diluted by two that lose the 'fascination' construct."},
        "u6": {"label": "FAITHFUL", "reason": "both items preserve 'ceiling height'."},
    },
}


def item_label(case: str, style: str, item_id: str) -> dict[str, str] | None:
    return ITEM.get(case, {}).get(style, {}).get(item_id)


def representation_label(case: str, style: str, items: list[dict]) -> dict[str, str]:
    """Fidelity of a whole representation (a style's item-set for one unit).

    Baseline is FAITHFUL by construction. A multi bundle (>1 item) uses the authored MULTI_BUNDLE label. A
    single-item representation uses that item's label. Falls back to worst-of-items only if unlisted.
    """
    if style == "baseline":
        return {"label": "FAITHFUL", "reason": "exact source text."}
    if len(items) > 1:
        unit = items[0]["source_unit_id"]
        bundle = MULTI_BUNDLE.get(case, {}).get(unit)
        if bundle:
            return bundle
    if len(items) == 1:
        lab = item_label(case, style, items[0]["item_id"])
        if lab:
            return lab
    # Conservative fallback: worst label among items (should not be hit for the frozen rich set).
    worst = "FAITHFUL"
    reason = "aggregated"
    order = {name: i for i, name in enumerate(LABELS)}
    for it in items:
        lab = item_label(case, style, it["item_id"])
        if lab and order[lab["label"]] > order[worst]:
            worst, reason = lab["label"], lab["reason"]
    return {"label": worst, "reason": reason}
