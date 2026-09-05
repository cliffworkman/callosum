"""Hand adjudication of the 44 mechanically "recovered" cases (study sections 4 and 6A).

Every case below was read individually against its own page context. The verdicts are recorded
here rather than in a notebook so the claim in the report is reproducible and contestable: a
reader can pull any chunk id out of the frozen corpus and disagree with a specific line.

Three outcomes, because two would hide the most important distinction:

  correct        -- the join reunified a genuine scientific unit that was split by extraction
  not_evidence   -- the join is structurally right but the result is not scientific evidence
                    (acknowledgements, CRediT statements, licence text, contributor biographies).
                    These are the dangerous "successes": the proposition test now PASSES, so a
                    naive recovery metric counts them as wins while they add non-evidence to the
                    retrievable pool.
  false          -- the join asserted a continuity that does not exist in the document

`mechanism` records WHY a false join happened, because the distribution of mechanisms -- not the
headline rate -- is what determines whether the failure is fixable.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / ".local" / "evidence-units-geom"

CORRECT, NOT_EVIDENCE, FALSE, UNRESOLVED = "correct", "not_evidence", "false", "unresolved"

# chunk_id -> (verdict, mechanism, note)
ADJ: dict[int, tuple[str, str, str]] = {
    29369: (FALSE, "boilerplate", "page number '13' glued to an unrelated paragraph"),
    16643: (FALSE, "empty_self", "self text is empty; the 'recovery' is entirely the neighbour"),
    31280: (FALSE, "caption_to_wrong_body", "Table 1 caption joined to Methods prose; its real referent is the table"),
    33885: (NOT_EVIDENCE, "", "'Acknowledgements' + funding text: right join, not scientific evidence"),
    14958: (FALSE, "section_boundary", "'Methods' heading joined to DISCUSSION prose"),
    31125: (FALSE, "section_boundary", "'Acknowledgments' joined to Discussion prose"),
    26591: (FALSE, "boilerplate", "table footnote + row label + page number"),
    15055: (CORRECT, "", "genuine truncated-statistic reunification; referents restored"),
    22907: (FALSE, "section_boundary", "table significance footnote joined across to Methods prose"),
    32067: (FALSE, "section_boundary", "'Author Statement' joined to Discussion prose"),
    26243: (UNRESOLVED, "", "'2.5. Network analysis' heading; joined body may belong to 2.4"),
    23827: (FALSE, "boilerplate", "'Journal Pre-proof' running head joined to Discussion prose"),
    41790: (NOT_EVIDENCE, "", "'Notes on contributors' + biography"),
    41599: (FALSE, "boilerplate", "journal running footer joined to real results prose"),
    25052: (NOT_EVIDENCE, "", "CRediT authorship statement"),
    31058: (FALSE, "boilerplate", "running footer joined to reference entries"),
    35987: (FALSE, "section_boundary", "'2.2. Stimuli' heading joined to the Participants body"),
    30447: (CORRECT, "", "real prose reunified with its preceding sentence"),
    33299: (CORRECT, "", "lmer model formula rejoined to its heading and predicate"),
    26475: (CORRECT, "", "participants sentence correctly reunified"),
    40442: (NOT_EVIDENCE, "", "Acknowledgement + supplementary-material pointer"),
    27038: (CORRECT, "", "real prose reunified across a block boundary"),
    35004: (FALSE, "boilerplate", "running head glued to a figure caption"),
    27630: (FALSE, "boilerplate", "correct left join, but a running head is absorbed on the right"),
    24775: (FALSE, "boilerplate", "'1512 THE AMERICAN ECONOMIC REVIEW June 2011' prefixed to prose"),
    44898: (NOT_EVIDENCE, "", "copyright line + Creative Commons licence text"),
    25950: (FALSE, "boilerplate", "journal running head prefixed to prose"),
    39151: (FALSE, "boilerplate", "Scientific Reports running footer joined to Discussion prose"),
    23179: (FALSE, "boilerplate", "running head joined to a funding statement"),
    33652: (CORRECT, "", "truncated finding reunified; trailing page number is minor contamination"),
    44514: (CORRECT, "", "prose continuation correctly reunified"),
    14538: (CORRECT, "", "cross-block prose correctly reunified"),
    27120: (FALSE, "boilerplate", "article running head joined to Methods prose"),
    34934: (CORRECT, "", "genuine table-note reunification (kappa / ICC definitions)"),
    15756: (FALSE, "section_boundary", "Acknowledgments joined to statistical-methods prose"),
    44004: (CORRECT, "", "quotation correctly reunified with its attribution"),
    25449: (FALSE, "boilerplate", "'2 H. HAN ET AL.' running head prefixed to continuous prose"),
    27544: (FALSE, "boilerplate", "Cambridge download footer joined to Discussion prose"),
    25702: (FALSE, "stimulus_boundary", "two separately numbered vignettes merged into one unit"),
    34157: (CORRECT, "", "metabolite list rejoined to its methods sentence"),
    41500: (FALSE, "boilerplate", "running head joined to the Findings statement"),
    22856: (FALSE, "topic_boundary", "heading joined to prose on a different measurement"),
    41550: (FALSE, "boilerplate", "running head joined to results prose"),
    14453: (CORRECT, "", "'Table 1 presents ...' correctly reunified with its continuation"),
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def main() -> None:
    data = json.loads((OUT / "fixtures.json").read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    mechanisms: dict[str, int] = {}
    for case in data["cases"]:
        entry = ADJ.get(case["chunk_id"])
        if not case["mechanically_recovered"]:
            continue
        verdict, mechanism, note = entry if entry else (UNRESOLVED, "", "not adjudicated")
        case["adjudicated_join_correct"] = verdict
        case["adjudication_note"] = note
        case["false_join_mechanism"] = mechanism
        counts[verdict] = counts.get(verdict, 0) + 1
        if mechanism:
            mechanisms[mechanism] = mechanisms.get(mechanism, 0) + 1

    n = sum(counts.values())
    print(f"ADJUDICATED JOINS (bounded one-neighbour reconstruction), n = {n}\n")
    for verdict in (CORRECT, NOT_EVIDENCE, FALSE, UNRESOLVED):
        k = counts.get(verdict, 0)
        lo, hi = wilson(k, n)
        print(f"  {verdict:<14}{k:>4}{100 * k / n:>7.1f}%   95% CI [{100 * lo:.0f}, {100 * hi:.0f}]")

    k = counts.get(FALSE, 0)
    lo, hi = wilson(k, n)
    print(f"\n  FALSE-JOIN RATE: {100 * k / n:.1f}%  95% CI [{100 * lo:.0f}%, {100 * hi:.0f}%]")
    useful = counts.get(CORRECT, 0)
    lo2, hi2 = wilson(useful, n)
    print(f"  genuinely useful: {100 * useful / n:.1f}%  95% CI [{100 * lo2:.0f}%, {100 * hi2:.0f}%]")

    print("\n  false-join mechanism:")
    for mech, count in sorted(mechanisms.items(), key=lambda kv: -kv[1]):
        print(f"    {mech:<24}{count:>4}{100 * count / max(k, 1):>7.0f}% of false joins")

    boiler = mechanisms.get("boilerplate", 0)
    print(f"\n  attributable to boilerplate already DETECTED by H1a: {boiler}/{k} ({100 * boiler / max(k, 1):.0f}%)")

    (OUT / "fixtures_adjudicated.json").write_text(
        json.dumps({**data, "adjudication_counts": counts, "mechanisms": mechanisms}, indent=1),
        encoding="utf-8",
    )
    print("\nwrote fixtures_adjudicated.json")


if __name__ == "__main__":
    main()
