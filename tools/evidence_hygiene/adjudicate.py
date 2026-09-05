"""G1 freeze + G2 precision. Verdicts are recorded by hand, with rationale, then scored.

Every verdict below was reached by reading the fixture's raw text, NOT by consulting the classifier
-- a fixture whose expected type is copied from the thing being measured proves nothing.

Verdict tuple: (expected_type, scientific_claim_eligible, rationale, status)
  status: "adjudicated"  -- decided here, rationale recorded
          "contestable"  -- a genuine judgment call, surfaced to the maintainer
          "unresolved"   -- excluded from every precision denominator
"""

from __future__ import annotations

import json
import math
from collections import defaultdict

from tools.evidence_hygiene import classify as C
from tools.evidence_hygiene.store import study_dir

# Types that can change retrieval eligibility. `unknown` is never excluded, so it is not scored.
EXCLUDABLE = {
    C.REFERENCE_ENTRY, C.RUNNING_HEAD, C.TABLE_CELL_DEBRIS, C.CITATION_INSTRUCTION,
    C.KEYWORD_LINE, C.PUBLICATION_METADATA, C.HEADING_FRAGMENT, C.CAPTION, C.MATH_OR_SYMBOL,
}

VERDICTS: dict[str, tuple[str, bool, str, str]] = {
    # ---- publication_metadata ----
    "F27073": (C.PUBLICATION_METADATA, False, "Publisher download stamp; states no finding.", "adjudicated"),
    "F33987": (C.PUBLICATION_METADATA, False, "Publisher download stamp with session token.", "adjudicated"),
    "F43114": (C.PUBLICATION_METADATA, False, "Journal masthead line.", "adjudicated"),
    "F43323": (C.PUBLICATION_METADATA, False, "Journal masthead line.", "adjudicated"),
    "F26458": (C.BODY_PROSE, True, (
        "REAL METHODS PROSE describing stimulus preparation ('placed onto a plain white background "
        "using the GIMP 2 software package'). The '(c)' is a sub-figure label, not a copyright mark. "
        "Excluding it would remove legitimate scientific evidence."), "adjudicated"),

    # ---- math_or_symbol ----
    "F43501": (C.MATH_OR_SYMBOL, False, "Orphaned operator glyphs; no proposition.", "adjudicated"),
    "F40631": (C.MATH_OR_SYMBOL, False, "Empty after normalization.", "adjudicated"),
    "F41636": (C.TABLE_CELL_DEBRIS, False, (
        "A table ROW ('56 ADM 14.5 4.87 <0.0001* 0.46'). Carries a real p-value but no referent, so "
        "it cannot support a claim on its own. Type is debris rather than math, but both are "
        "non-evidential, so the eligibility outcome is unaffected."), "maintainer_reviewed"),
    "F40416": (C.TABLE_CELL_DEBRIS, False, "Table cell 'None 392 (38.6)'; no proposition.", "adjudicated"),

    # ---- caption ----
    "F41520": (C.CAPTION, False, "Figure caption describing a schedule; descriptive, not a finding.", "adjudicated"),
    "F44485": (C.CAPTION, True, (
        "Caption that STATES A FINDING: 'The first component explained 18.3% of the variance and "
        "captured support for neuroessentialist/optimistic attitudes'. Evidential."), "maintainer_reviewed"),
    "F39057": (C.CAPTION, True, (
        "Caption reporting effects of injury severity on global network measures with group Ns. "
        "Carries real result content."), "maintainer_reviewed"),
    "F31169": (C.CAPTION, False, "Table caption naming a PICO selection scheme; structural.", "adjudicated"),
    "F14458": (C.CAPTION, False, "Truncated table caption; no finding stated.", "adjudicated"),
    "F45476": (C.BODY_PROSE, True, (
        "BODY PROSE that merely refers to a table ('Table 4 below shows the number of extracted "
        "statistics and the number of identified errors'). The caption opener regex matched a "
        "sentence, not a caption. Excluding it would remove real prose."), "adjudicated"),

    # ---- table_cell_debris ----
    "F29836": (C.TABLE_CELL_DEBRIS, False, (
        "'p = 0.146' -- a bare statistic with no referent. Real but non-propositional alone."), "maintainer_reviewed"),
    "F29976": (C.TABLE_CELL_DEBRIS, False, "'page = 0.565'; bare table cell.", "adjudicated"),
    "F29916": (C.TABLE_CELL_DEBRIS, False, "'page = 0.146'; bare table cell.", "adjudicated"),

    # ---- heading_fragment ----
    "F41335": (C.HEADING_FRAGMENT, False, "'Results Participants' -- two stacked headings.", "adjudicated"),
    "F14958": (C.HEADING_FRAGMENT, False, "Bare 'Methods' heading.", "adjudicated"),
    "F34553": (C.PUBLICATION_METADATA, False, (
        "'Methods in Psychology 5 (2021) 100063' is a JOURNAL NAME running footer, not a section "
        "heading. Misclassified, but non-evidential either way, so eligibility is unaffected."), "adjudicated"),
    "F15105": (C.HEADING_FRAGMENT, False, "Bare 'Discussion' heading.", "adjudicated"),
    "F42678": (C.HEADING_FRAGMENT, False, "'Method Participants and Design' -- stacked headings.", "adjudicated"),
    "F41822": (C.HEADING_FRAGMENT, False, "'2. Methods and materials' -- numbered heading.", "adjudicated"),

    # ---- citation_instruction ----
    "F39198": (C.CITATION_INSTRUCTION, False, "Verbatim 'Citation:' banner.", "adjudicated"),
    "F44891": (C.PUBLICATION_METADATA, False, (
        "Acknowledgements/funding statement, not a citation instruction. Misclassified, but "
        "non-evidential either way."), "adjudicated"),
    "F40889": (C.CITATION_INSTRUCTION, False, "Verbatim 'Citation:' banner.", "adjudicated"),

    # ---- abstract_prose (must stay eligible) ----
    "F44648": (C.ABSTRACT_PROSE, True, "States a simulation finding about HKSJ vs DL error rates.", "adjudicated"),
    "F41292": (C.ABSTRACT_PROSE, True, "Substantive abstract prose about mTBI imaging.", "adjudicated"),
    "F22837": (C.ABSTRACT_PROSE, True, "Substantive prose with citations.", "adjudicated"),
    "F41726": (C.ABSTRACT_PROSE, True, "Substantive descriptive prose.", "adjudicated"),
    "F41725": (C.ABSTRACT_PROSE, True, "Substantive descriptive prose.", "adjudicated"),
    "F41765": (C.ABSTRACT_PROSE, True, "Substantive prose about artistic production and neural pathways.", "adjudicated"),

    # ---- body_prose ----
    "F35947": (C.BODY_PROSE, True, "Methods prose describing region pairings.", "adjudicated"),
    "F39837": (C.BODY_PROSE, True, "Discussion prose stating the study's contribution.", "adjudicated"),
    "F43108": (C.BODY_PROSE, True, "Results prose about moralizing-gods timing.", "adjudicated"),

    # ---- reference_entry ----
    "F40003": (C.REFERENCE_ENTRY, False, "Journal/volume/page tail of a reference entry.", "adjudicated"),
    "F27208": (C.PUBLICATION_METADATA, False, (
        "A correction notice about the article itself, not a cited work. Misclassified; "
        "non-evidential for a scientific claim either way."), "adjudicated"),
    "F33978": (C.REFERENCE_ENTRY, False, "Working-paper reference entry.", "adjudicated"),
    "F36864": (C.REFERENCE_ENTRY, False, "Reference continuation with journal, volume, pages, DOI.", "adjudicated"),

    # ---- label says references but the text is prose (validates the prose veto) ----
    "F35202": (C.BODY_PROSE, True, "Methods prose about participant compensation, mislabeled 'references'.", "adjudicated"),
    "F37579": (C.BODY_PROSE, True, "Supplementary methods prose about model selection.", "adjudicated"),
    "F36125": (C.BODY_PROSE, True, (
        "REAL RESULTS CONTENT ('= 0.15, p = .70, partial h2 = .006; scenarios featuring negative "
        "outcomes contained the same number of words...') that fell inside the inferred reference "
        "region. Excluding it would remove legitimate scientific evidence."), "adjudicated"),
    "F29754": (C.CAPTION, False, "Supplementary table caption.", "adjudicated"),
    "F25828": (C.BODY_PROSE, True, "Stimulus vignette text; substantive study material, not a reference.", "contestable"),
    "F25864": (C.BODY_PROSE, True, "Stimulus vignette text; substantive study material, not a reference.", "contestable"),

    # ---- matched a known citation but is prose (validates region over per-chunk matching) ----
    "F34562": (C.HEADING_FRAGMENT, False, "Numbered sub-heading naming a source; structural.", "contestable"),
    "F30520": (C.BODY_PROSE, True, "Methods prose on volume-of-interest analyses.", "adjudicated"),
    "F29651": (C.BODY_PROSE, True, "Methods prose on spectroscopic data processing.", "adjudicated"),
    "F30644": (C.REFERENCE_ENTRY, False, "Reference continuation with journal and volume.", "adjudicated"),
    "F37422": (C.BODY_PROSE, True, "Footnote prose about Bayesian model fitting.", "adjudicated"),
    "F40363": (C.BODY_PROSE, True, "Methods prose naming an instrument and its citation.", "adjudicated"),

    # ---- NULL-section prose (must stay eligible) ----
    "F26677": (C.BODY_PROSE, True, "Intro prose on disfigurement stereotypes.", "adjudicated"),
    "F15322": (C.BODY_PROSE, True, "Conclusion stating a finding about facial scars.", "adjudicated"),
    "F15365": (C.BODY_PROSE, True, "Discussion prose about the worst scar in the study.", "adjudicated"),
    "F18666": (C.REFERENCE_ENTRY, False, "Numbered reference entries with journal/volume/pages.", "adjudicated"),
    "F42416": (C.BODY_PROSE, True, "Discussion prose on dissemination platforms.", "adjudicated"),
    "F39191": (C.PUBLICATION_METADATA, False, "Author affiliation block.", "adjudicated"),

    # ---- hyphenation stratum ----
    "F32760": (C.REFERENCE_ENTRY, False, "Vancouver-style numbered reference entry.", "adjudicated"),
    "F41795": (C.BODY_PROSE, True, "Author biography prose.", "contestable"),
    "F40472": (C.BODY_PROSE, True, "Intro prose on dynamic reconfiguration.", "adjudicated"),
    "F39154": (C.BODY_PROSE, True, "Methods prose with participant counts.", "adjudicated"),
    "F35756": (C.BODY_PROSE, True, "Results prose reporting a null correlation with statistics.", "adjudicated"),
    "F36174": (C.BODY_PROSE, True, "Intro prose on self-blame in depression.", "adjudicated"),
    "F28958": (C.REFERENCE_ENTRY, False, "Author-date reference entry.", "adjudicated"),
    "F32074": (C.REFERENCE_ENTRY, False, "Manual/test reference entry.", "adjudicated"),

    # ---- short but substantive: bare statistics, all predicted `unknown` (never excluded) ----
    "F34189": (C.UNKNOWN, True, "'between visits (all p > 0.7)' -- a real statistic, fragmentary.", "adjudicated"),
    "F33647": (C.UNKNOWN, True, "Real regression statistics, fragmentary.", "adjudicated"),
    "F34919": (C.UNKNOWN, True, "Real ANOVA statistics, fragmentary.", "adjudicated"),
    "F41314": (C.UNKNOWN, False, "Table significance footnote.", "contestable"),
    "F15077": (C.UNKNOWN, True, "Real correlation statistics, fragmentary.", "adjudicated"),
    "F27630": (C.UNKNOWN, True, "Real correlation statistics, fragmentary.", "adjudicated"),
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval -- correct at small n, unlike the normal approximation."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def main() -> None:
    draft = json.loads((study_dir() / "fixtures_draft.json").read_text(encoding="utf-8"))
    frozen = []
    for f in draft:
        fid = f["fixture_id"]
        if fid in VERDICTS:
            t, elig, why, status = VERDICTS[fid]
            f["expected_type"], f["expected_claim_eligible"] = t, elig
            f["rationale"], f["adjudication"] = why, status
        elif f["adjudication"] == "mechanical":
            f["expected_claim_eligible"] = f["expected_type"] in (C.BODY_PROSE, C.ABSTRACT_PROSE)
            f["adjudication"] = "adjudicated"
        else:
            f["adjudication"] = "unresolved"
            f["rationale"] = "Not individually adjudicated in this pass; excluded from all denominators."
        frozen.append(f)

    path = study_dir() / "fixtures_frozen.json"
    path.write_text(json.dumps(frozen, indent=1), encoding="utf-8")

    scored = [f for f in frozen if f["adjudication"] in ("adjudicated", "contestable", "maintainer_reviewed")]
    print(f"frozen {len(frozen)} fixtures; {len(scored)} adjudicated/contestable, "
          f"{len(frozen) - len(scored)} unresolved (excluded from denominators)\n")

    print(f"{'reason code':<22}{'TP':>4}{'FP':>4}{'n':>4}{'precision':>11}   95% CI        harmful FPs")
    rows = []
    for code in sorted(EXCLUDABLE):
        pos = [f for f in scored if f["predicted_type"] == code]
        tp = [f for f in pos if f["expected_type"] == code]
        fp = [f for f in pos if f["expected_type"] != code]
        harmful = [f for f in fp if f["expected_claim_eligible"]]
        n = len(pos)
        if n == 0:
            continue
        lo, hi = wilson(len(tp), n)
        rows.append((code, len(tp), len(fp), n, len(tp) / n, lo, hi, harmful))
        print(f"{code:<22}{len(tp):>4}{len(fp):>4}{n:>4}{len(tp) / n:>10.0%}   [{lo:.2f}, {hi:.2f}]   "
              f"{len(harmful)}")

    print("\nFALSE POSITIVES THAT WOULD REMOVE LEGITIMATE SCIENTIFIC EVIDENCE:")
    any_harm = False
    for code, _, _, _, _, _, _, harmful in rows:
        for f in harmful:
            any_harm = True
            print(f"  [{code}] {f['fixture_id']} p{f['paper_id']} -> adjudicated {f['expected_type']}")
            print(f"      {' '.join((f['raw_text'] or '').split())[:104]}")
    if not any_harm:
        print("  none")

    # Recall probe: adjudicated excludable types the classifier did NOT flag.
    print("\nFALSE NEGATIVES (adjudicated excludable, classifier said otherwise):")
    fn = [f for f in scored
          if f["expected_type"] in EXCLUDABLE and f["predicted_type"] != f["expected_type"]]
    for f in fn:
        print(f"  expected {f['expected_type']:<22} predicted {f['predicted_type']:<20} {f['fixture_id']}")
    if not fn:
        print("  none")

    print("\nCONTESTABLE -- surfaced for maintainer spot-check:")
    for f in scored:
        if f["adjudication"] == "contestable":
            print(f"  {f['fixture_id']} p{f['paper_id']} predicted={f['predicted_type']} "
                  f"-> proposed {f['expected_type']} (eligible={f['expected_claim_eligible']})")
            print(f"      {' '.join((f['raw_text'] or '').split())[:100]}")


if __name__ == "__main__":
    main()
