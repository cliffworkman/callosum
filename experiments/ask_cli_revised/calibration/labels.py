"""Frozen human reference labels for the minimum-sufficient-context calibration (B6).

Assigned by careful reading of the SUPPLIED envelope text only (textual intelligibility, not outside
knowledge). Each case records the smallest sufficient window, an acceptable-set capturing genuine
adjacent-window ambiguity, a type tag, and an `uncertain` flag where the case is genuinely borderline.

Labeling rule for debris (documented, applied consistently): the judgment is about "the scientific idea
expressed by the CENTRAL CHUNK." A central chunk that is a running header, page header, journal line,
author affiliation/biography, funding/copyright/correspondence block, a bare reference-list entry, or a
lone section label expresses no scientific idea, so NO local window makes it intelligible as a complete
scientific idea -> E. This holds even when neighbors are rich scientific text (the neighbors are not the
central chunk). E means "bounded local context is insufficient", never "discard".

Frozen before any Qwen inference. The AIB discard specimen (c34974) is a mandatory dev regression case;
its correct label is A (the full abstract already states the complete idea) — the baseline wrongly
discarded it.
"""

from __future__ import annotations

# case_id -> {label, acceptable[], type, uncertain, note}
LABELS: dict[str, dict] = {
    # ---- paper 68 (Hadza cross-cultural) ----
    "c14379": {
        "label": "B",
        "acceptable": ["B"],
        "type": "sentence-fragment",
        "uncertain": False,
        "note": "A cut at 'about the'; +1 completes the sentence.",
    },
    "c14401": {
        "label": "B",
        "acceptable": ["B"],
        "type": "sentence-fragment",
        "uncertain": False,
        "note": "A cut at '(e.g.,'; +/-1 completes the clause.",
    },
    "c14419": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "prediction-fragment",
        "uncertain": False,
        "note": "if/then prediction; core intelligible at B.",
    },
    "c14422": {
        "label": "B",
        "acceptable": ["B"],
        "type": "sentence-fragment",
        "uncertain": False,
        "note": "WEIRD-bias point; +/-1 completes. Baseline discarded.",
    },
    "c14459": {
        "label": "E",
        "acceptable": ["D", "E"],
        "type": "table-cell",
        "uncertain": True,
        "note": "Central is the table cell 'Trait'; table debris, no complete idea within +/-3.",
    },
    "c14496": {
        "label": "C",
        "acceptable": ["C"],
        "type": "results-running-header-interrupt",
        "uncertain": False,
        "note": "+1 after is a running header; C reaches the completing clause.",
    },
    "c14564": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "reasoning-fragment",
        "uncertain": False,
        "note": "moral-character-not-stable-traits point complete at B.",
    },
    "c14570": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "contrast-fragment",
        "uncertain": False,
        "note": "broad vs moral-specific trait contrast complete at B.",
    },
    "c14586": {
        "label": "B",
        "acceptable": ["B"],
        "type": "key-finding-fragment",
        "uncertain": False,
        "note": "'evidence against pathogen-adaptation' completes at B.",
    },
    # ---- paper 60 (proportionality) ----
    "c14955": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "hypothesis-fragment",
        "uncertain": False,
        "note": "typical-faces hypothesis completes at B.",
    },
    "c14963": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "methods-measures",
        "uncertain": False,
        "note": "character-traits-assessed list starts at B.",
    },
    "c15116": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "results-fragment",
        "uncertain": False,
        "note": "proportionality->traits result complete at B. Baseline discarded.",
    },
    "c15180": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "conclusion-fragment",
        "uncertain": False,
        "note": "'influence ... on attractiveness and character traits' completes at B.",
    },
    # ---- paper 7 (Kamala Harris) ----
    "c22869": {
        "label": "B",
        "acceptable": ["B"],
        "type": "measure-heading",
        "uncertain": False,
        "note": "heading 'Gender stereotypicality'; +1 after gives the full item definition.",
    },
    # ---- paper 4 (CRediT commentary) ----
    "c23171": {
        "label": "E",
        "acceptable": ["E"],
        "type": "running-header",
        "uncertain": False,
        "note": "central is the journal running-head/citation line.",
    },
    "c23178": {
        "label": "E",
        "acceptable": ["E"],
        "type": "running-header",
        "uncertain": False,
        "note": "central is the journal running-head line. Baseline discarded.",
    },
    "c23192": {
        "label": "E",
        "acceptable": ["E"],
        "type": "running-header",
        "uncertain": False,
        "note": "central is the journal running-head line (document end).",
    },
    # ---- paper 6 (stigma) ----
    "c23201": {
        "label": "E",
        "acceptable": ["E"],
        "type": "funding-correspondence",
        "uncertain": False,
        "note": "central is a funding+correspondence block; no scientific idea.",
    },
    # ---- paper 8 (trustworthiness stereotypes) ----
    "c23472": {
        "label": "C",
        "acceptable": ["B", "C", "D"],
        "type": "table-subheading",
        "uncertain": True,
        "note": "table sub-heading; caption+columns+rows give partial meaning.",
    },
    # ---- paper 9 (dehumanization/RME) ----
    "c23557": {
        "label": "E",
        "acceptable": ["E"],
        "type": "orcid-funding-correspondence",
        "uncertain": False,
        "note": "central is ORCID+funding+correspondence; no scientific idea.",
    },
    # ---- paper 20 (empathy/AD) ----
    "c25396": {
        "label": "E",
        "acceptable": ["E"],
        "type": "running-header",
        "uncertain": False,
        "note": "central is the journal running-head line.",
    },
    "c25412": {
        "label": "E",
        "acceptable": ["E"],
        "type": "running-header",
        "uncertain": False,
        "note": "central is the journal running-head line. Baseline discarded.",
    },
    "c25417": {
        "label": "E",
        "acceptable": ["E"],
        "type": "running-header",
        "uncertain": False,
        "note": "central is the journal running-head line.",
    },
    # ---- paper 25 (LMM vignettes, supplementary tables) ----
    "c26503": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "table-caption",
        "uncertain": False,
        "note": "LMM fixed-effects table caption completes at B (before-neighbor).",
    },
    "c26505": {
        "label": "C",
        "acceptable": ["C", "D", "E"],
        "type": "table-sublabel",
        "uncertain": True,
        "note": "'a. Attractiveness' table sub-label; needs caption+cols to interpret.",
    },
    "c26648": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is a reference-list entry. Baseline discarded.",
    },
    "c26661": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is a reference-list entry.",
    },
    # ---- paper 27 (RTPJ/ASD) ----
    "c26831": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "complete-results-paragraph",
        "uncertain": False,
        "note": "self-contained ASD/RTPJ results paragraph.",
    },
    # ---- paper 35 (neuroscience of moral judgment) ----
    "c28099": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "intro-fragment",
        "uncertain": False,
        "note": "'first thread = brain abnormalities' completes at B. Baseline discarded.",
    },
    "c28180": {
        "label": "C",
        "acceptable": ["C"],
        "type": "fragment-running-header-interrupt",
        "uncertain": False,
        "note": "+1 after is a running header; C reaches 'associated with abnormal structure'.",
    },
    "c28332": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "finding-fragment",
        "uncertain": False,
        "note": "psychopathy->lower amygdala completes at B.",
    },
    "c28752": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "reasoning-fragment",
        "uncertain": False,
        "note": "moral circuits overlap self-processing completes at B.",
    },
    # ---- paper 41 (social prediction-error) ----
    "c30603": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is reference-list entries.",
    },
    "c30644": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is reference-list entries. Baseline discarded.",
    },
    "c30655": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is reference-list entries. Baseline discarded.",
    },
    # ---- paper 42 (scars/palsies warmth/competence) ----
    "c30677": {
        "label": "E",
        "acceptable": ["E"],
        "type": "copyright-license",
        "uncertain": False,
        "note": "central is a CC-license/copyright block. Baseline discarded.",
    },
    "c30770": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "complete-results-conclusion",
        "uncertain": False,
        "note": "self-contained findings paragraph (scars/palsies less warm/competent/dehumanized).",
    },
    "c30784": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is a reference-list entry.",
    },
    # ---- paper 45 (dmPFC/social behavior) ----
    "c31089": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "methods-paragraph",
        "uncertain": False,
        "note": "self-contained ROI methods description.",
    },
    "c31091": {
        "label": "C",
        "acceptable": ["C", "D"],
        "type": "section-heading-body-gap",
        "uncertain": False,
        "note": "heading 'Brain regions sensitive to social scenes'; body is 2 chunks after (another heading intervenes) -> C.",
    },
    "c31113": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "table-caption-selfcontained",
        "uncertain": False,
        "note": "table caption states the whole-brain-contrast subject; interpretable alone.",
    },
    # ---- paper 61 (visual attention/facial anomalies) ----
    "c33601": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "limitations-summary",
        "uncertain": False,
        "note": "self-contained limitations+what-the-study-characterized paragraph. Baseline discarded.",
    },
    # ---- paper 67 (AIB — the specimen paper) ----
    "c34974": {
        "label": "A",
        "acceptable": ["A"],
        "type": "SPECIMEN-full-abstract",
        "uncertain": False,
        "note": "MANDATORY REGRESSION: full AIB abstract (amygdala/economic-games/attitudes/just-world/empathy). Complete idea at A; baseline wrongly discarded it.",
    },
    "c34984": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "hypothesis-statement",
        "uncertain": False,
        "note": "self-contained H1 (stereotype in negative attitudes + predictions). Baseline discarded.",
    },
    "c35068": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "discussion-summary",
        "uncertain": False,
        "note": "self-contained discussion summary of AIB findings across levels.",
    },
    # ---- paper 73 (Young et al. ToM/moral) ----
    "c35904": {
        "label": "E",
        "acceptable": ["E"],
        "type": "author-affiliations",
        "uncertain": False,
        "note": "central is an author-affiliations block. Baseline discarded.",
    },
    "c35935": {
        "label": "E",
        "acceptable": ["E"],
        "type": "section-label",
        "uncertain": False,
        "note": "central is the bare section label 'PSYCHOLOGY' (rich neighbors, but the central expresses no idea).",
    },
    "c35955": {
        "label": "E",
        "acceptable": ["E"],
        "type": "section-label",
        "uncertain": False,
        "note": "central is the bare section label 'PSYCHOLOGY' (rich neighbors, but the central expresses no idea).",
    },
    # ---- paper 76 (menstrual-cycle/personality methods) ----
    "c36239": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "methods-exclusion-criteria",
        "uncertain": False,
        "note": "exclusion-criteria fragment; intelligible as one criterion at B. Baseline discarded.",
    },
    # ---- paper 107 (empathy/disgust readers) ----
    "c36413": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "theory-paragraph",
        "uncertain": False,
        "note": "self-contained face-overgeneralization theory paragraph. Baseline discarded.",
    },
    # ---- paper 1 (typical-is-trustworthy) ----
    "c42652": {
        "label": "E",
        "acceptable": ["E"],
        "type": "author-affiliations",
        "uncertain": False,
        "note": "central is an author-affiliations block.",
    },
    "c42713": {
        "label": "E",
        "acceptable": ["E"],
        "type": "page-running-header",
        "uncertain": False,
        "note": "central is a page running header (rich results neighbors, but central expresses no idea).",
    },
    "c42739": {
        "label": "E",
        "acceptable": ["E"],
        "type": "author-biography",
        "uncertain": False,
        "note": "central is an author biography; no scientific idea.",
    },
    # ---- paper 60 (Villavisanis proportionality, title page) ----
    "c43434": {
        "label": "A",
        "acceptable": ["A", "B"],
        "type": "finding-sentence",
        "uncertain": False,
        "note": "self-contained finding sentence (proportionality -> negative attributions).",
    },
    # ---- paper 240 (mind-brain survey) ----
    "c44450": {
        "label": "B",
        "acceptable": ["B", "C"],
        "type": "survey-item",
        "uncertain": True,
        "note": "survey-instrument item; heading+siblings make it a survey construct at B. Baseline discarded.",
    },
    # ---- paper 248 (Bilici stories-reduce-bias intervention) ----
    "c45897": {
        "label": "E",
        "acceptable": ["E"],
        "type": "journal-running-header",
        "uncertain": False,
        "note": "central is the journal running-head line (title-page top).",
    },
    "c46071": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is reference-list entries.",
    },
    "c46097": {
        "label": "E",
        "acceptable": ["E"],
        "type": "reference-entry",
        "uncertain": False,
        "note": "central is reference-list entries.",
    },
}

_ORDER = ["A", "B", "C", "D", "E"]


def label_for(case_id: str) -> dict | None:
    return LABELS.get(case_id)


def ordinal(label: str) -> int:
    return _ORDER.index(label)
