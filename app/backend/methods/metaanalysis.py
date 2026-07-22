"""Meta-analysis reporting auditor (backlog #36 consumer-side, inc 249).

Reads a published meta-analysis's extracted text and flags whether it *reports* what a careful reader needs to
evaluate it — the effect-size metric, the model (fixed vs random-effects), heterogeneity, publication-bias
assessment, sensitivity/influence analysis, the number of studies pooled, and (for a systematic review) the search
& selection process. FLAG-not-ADJUDICATE: each check is present / not-found / not-applicable, never a verdict, never
a score. It reads reported text only — it NEVER pools, models heterogeneity, meta-regresses, computes an effect
size, or does bias inference (the identity boundary; those are metafor / JASP / RevMan territory). The deterministic
sibling of statcheck / the LMM auditor. Local, no AI, no egress.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from sqlalchemy import Connection

from app.backend.persistence.findings_repo import upsert_findings
from app.backend.persistence.signals_repo import store_meta


@dataclass(frozen=True)
class MetaCheck:
    key: str
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None
    page: int | None
    note: str | None
    explainer: str
    basis: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MetaReport:
    is_meta_analysis: bool
    checks: list  # list[MetaCheck]

    def to_dict(self) -> dict:
        return {"is_meta_analysis": self.is_meta_analysis, "checks": [c.to_dict() for c in self.checks]}


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# The gate — a meta-analysis WORD cue AND an ANALYTIC cue (so a paper merely *citing* a meta-analysis doesn't trip).
_META_WORD = _rx(r"meta[-\s]?analy(s[ie]s|tic|z[e]?d?|s[e]?d?)")
_ANALYTIC = _rx(
    r"random[-\s]?effects?|fixed[-\s]?effects?|common[-\s]?effect|forest plot|pooled (effect|estimate|odds ratio|"
    r"risk ratio|OR|RR|mean|prevalence|proportion)|funnel plot|I²|I2\b|I-squared|τ²|tau2\b|tau-squared|Hedges'?\s?g"
    r"|DerSimonian|inverse[-\s]?variance|(standardi[sz]ed )?mean difference|\bSMD\b|effect sizes?"
)

_EFFECT = _rx(
    r"Hedges'?\s?g|Cohen'?s?\s?d\b|(log[-\s]?)?(odds ratio|\bOR\b|risk ratio|\bRR\b|relative risk|hazard ratio|"
    r"\bHR\b|rate ratio|incidence rate ratio)|Fisher'?s?\s?z|(standardi[sz]ed )?mean difference|\bSMD\b|\bWMD\b|"
    r"raw mean difference|correlation coefficient|pooled (prevalence|proportion)|(log )?response ratio"
)
_MODEL = _rx(
    r"fixed[-\s]?effects?\s+(model|meta|analysis)|random[-\s]?effects?\s+(model|meta|analysis)|DerSimonian[-–\s]?Laird"
    r"|\bREML\b|restricted maximum likelihood|Hartung[-–\s]?Knapp|Sidik[-–\s]?Jonkman|Paule[-–\s]?Mandel|"
    r"inverse[-\s]?variance|Mantel[-–\s]?Haenszel|three[-\s]?level meta|multilevel meta|common[-\s]?effect model|"
    r"equal[-\s]?effects? model"
)
_HETEROGENEITY = _rx(
    r"I²|I2\b|I-squared|I\^2|τ²|tau2\b|tau-squared|tau\^2|Cochran'?s?\s?Q|Q[-\s]?statistic|Q\s*=|\bH2\b|H-statistic|"
    r"between[-\s]?study (variance|heterogeneity)|heterogeneity (statistic|test|was|were|of|assess)|prediction interval"
)
_PUBBIAS = _rx(
    r"funnel plot|Egger'?s?|Begg'?s?|trim[-\s]?and[-\s]?fill|PET[-\s]?PEESE|PET-PEESE|fail[-\s]?safe (N|number)|"
    r"Rosenthal'?s?|Orwin|p[-\s]?curve|p[-\s]?uniform|selection model|small[-\s]?study (effect|bias)|publication bias|"
    r"Duval (and|&) Tweedie"
)
_META_SENSITIVITY = _rx(
    r"leave[-\s]?one[-\s]?out|leave-1-out|influence (diagnostic|analys[ie]s|case)|Baujat|\boutlier|"
    r"sensitivity analys[ie]s|robustness (check|analys[ie]s|test)|jackknife|Cook'?s? distance|studentized residual|"
    r"\bGOSH\b|subgroup analys[ie]s"
)
_STUDYCOUNT = _rx(
    r"\bk\s*=\s*\d+|\b\d+\s+(included\s+)?(studies|trials|samples|effect sizes|articles|papers|comparisons|datasets|"
    r"cohorts)|(number of|total (number of)?)\s+(studies|trials|effect sizes)|\b\d+\s+(independent\s+)?effect sizes"
)
_SEARCH_STRATEGY = _rx(
    r"PRISMA|systematic (review|search|literature search)|databases?\s+(searched|were searched|search)|"
    r"\b(PubMed|MEDLINE|Embase|EMBASE|Web of Science|Scopus|PsycINFO|PsycInfo|Cochrane (Library|CENTRAL)|CINAHL|"
    r"Google Scholar)\b|search (strategy|string|terms)|inclusion (and exclusion )?criteria|eligibility criteria|"
    r"PROSPERO|pre[-\s]?regist(ered|ration)|protocol (was )?regist|study selection|title.{0,6}abstract screening"
)
_MINI_META = _rx(
    r"(internal|mini|within[-\s]?(study|paper|subject)|single[-\s]?paper) meta[-\s]?analy(s[ie]s|tic)|"
    r"meta[-\s]?analy(s[ie]s|z[e]?d?|s[e]?d?) (of )?(our|the present|the current|these) (\d+ )?(studies|experiments|"
    r"samples)"
)


def _chunk_rows(chunks: list) -> list[tuple[str, int | None]]:
    return [(getattr(c, "text", "") or "", getattr(c, "page_start", None)) for c in chunks]


def _snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    lo, hi = max(0, start - pad), min(len(text), end + pad)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()[:200]


def _first(pattern: re.Pattern, rows: list[tuple[str, int | None]]) -> tuple[str, int | None] | None:
    for text, page in rows:
        m = pattern.search(text)
        if m:
            return _snippet(text, m.start(), m.end()), page
    return None


def _has(pattern: re.Pattern, rows: list[tuple[str, int | None]]) -> bool:
    return any(pattern.search(text) for text, _ in rows)


_NOT_DETECTED = "not detected in the extracted text — check the paper"


def _simple(key, label, pattern, rows, *, basis, missing_note, explainer) -> MetaCheck:
    hit = _first(pattern, rows)
    if hit:
        return MetaCheck(key, label, "present", hit[0], hit[1], None, explainer, basis)
    return MetaCheck(key, label, "not-found", None, None, f"{missing_note} ({_NOT_DETECTED})", explainer, basis)


def audit_meta_analysis(chunks: list) -> MetaReport:
    """Presence/absence checklist over a published meta-analysis's extracted text; runs only if the paper is
    detectably a meta-analysis. Each check present / not-found / not-applicable — never a verdict, never a score,
    never pools/models/re-computes."""
    rows = _chunk_rows(chunks)
    if not (_has(_META_WORD, rows) and _has(_ANALYTIC, rows)):
        return MetaReport(is_meta_analysis=False, checks=[])

    checks: list[MetaCheck] = []

    checks.append(
        _simple(
            "effect_size_metric",
            "Effect-size metric",
            _EFFECT,
            rows,
            basis="Borenstein et al. 2009 (Introduction to Meta-Analysis); Viechtbauer 2010 (metafor)",
            missing_note=(
                "the effect-size index (e.g. Hedges' g, log odds ratio, Fisher's z) isn't stated — you can't "
                "interpret the pooled estimate without knowing what metric it's on"
            ),
            explainer=(
                "The common metric the study effects were converted to before pooling (Hedges' g, log OR, Fisher's "
                "z, …). A reader needs it to interpret the pooled estimate and its direction."
            ),
        )
    )
    checks.append(
        _simple(
            "model",
            "Model (fixed vs random-effects)",
            _MODEL,
            rows,
            basis="DerSimonian & Laird 1986; IntHout et al. 2014 (Hartung-Knapp)",
            missing_note=(
                "fixed- vs random-effects (and the between-study variance estimator, e.g. DerSimonian-Laird or REML) "
                "isn't stated — it changes the weights, the confidence interval, and what the pooled estimate "
                "generalizes to"
            ),
            explainer=(
                "A fixed-effect model assumes one true effect; a random-effects model allows the true effect to vary "
                "across studies. The choice (and the τ² estimator) changes the CI and the interpretation."
            ),
        )
    )
    checks.append(
        _simple(
            "heterogeneity",
            "Heterogeneity (I² / τ² / Q)",
            _HETEROGENEITY,
            rows,
            basis="Higgins, Thompson, Deeks & Altman 2003",
            missing_note=(
                "heterogeneity (I² / τ² / Cochran's Q) isn't reported — it tells the reader how much the true effects "
                "vary across studies, which governs how much a single pooled number can be trusted"
            ),
            explainer=(
                "How much the true effects differ across studies. I² is the share of variance due to heterogeneity "
                "rather than chance; τ² is the between-study variance; a prediction interval shows the spread."
            ),
        )
    )
    checks.append(
        _simple(
            "publication_bias",
            "Publication-bias assessment",
            _PUBBIAS,
            rows,
            basis="Egger et al. 1997; Duval & Tweedie 2000 (trim-and-fill); Sterne et al. 2011",
            missing_note=(
                "no publication-bias assessment (funnel plot, Egger's test, trim-and-fill, PET-PEESE, …) is reported. "
                "For k ≥ 10 studies a funnel-based check is commonly recommended (Sterne et al. 2011); with fewer "
                "studies these tests are underpowered, so absence may be appropriate — check the paper"
            ),
            explainer=(
                "Whether the meta-analysis checked for the tendency of significant results to be published more "
                "readily (which inflates the pooled effect) — funnel plots, Egger's regression, trim-and-fill, "
                "PET-PEESE."
            ),
        )
    )
    checks.append(
        _simple(
            "sensitivity",
            "Sensitivity / influence analysis",
            _META_SENSITIVITY,
            rows,
            basis="Viechtbauer & Cheung 2010",
            missing_note=(
                "no sensitivity / influence analysis (leave-one-out, outlier/influence diagnostics, robustness to an "
                "included study or choice) is reported — it shows whether the pooled result hinges on one study"
            ),
            explainer=(
                "Whether the pooled result is robust — leave-one-out, outlier/influence diagnostics (Baujat, Cook's "
                "distance), or subgroup checks reveal if one study or choice is driving the conclusion."
            ),
        )
    )
    checks.append(
        _simple(
            "study_count",
            "Number of studies (k) and participants",
            _STUDYCOUNT,
            rows,
            basis="PRISMA 2020 (Page et al. 2021)",
            missing_note=(
                "the number of studies (k) — and, ideally, the total participants pooled — isn't clearly stated; it's "
                "the first thing a reader needs to weigh the meta-analysis"
            ),
            explainer=(
                "How many studies (and participants) were pooled. k governs the power of heterogeneity and "
                "publication-bias checks and how much any single study can dominate."
            ),
        )
    )

    # Search & selection — precondition-scoped: n/a for a within-study mini-meta that isn't a systematic review.
    search_explainer = (
        "For a systematic review, how the literature was searched and studies selected — databases, inclusion/"
        "eligibility criteria, a PRISMA flow diagram, a registered protocol (PROSPERO). It's what makes the included "
        "set auditable."
    )
    search_basis = "PRISMA 2020 (Page et al. 2021)"
    if _has(_MINI_META, rows) and not _has(_SEARCH_STRATEGY, rows):
        checks.append(
            MetaCheck(
                "search_selection",
                "Search & selection reporting",
                "not-applicable",
                None,
                None,
                "a within-study meta-analysis of the paper's own experiments — not a systematic review, so a "
                "systematic literature search isn't expected here",
                search_explainer,
                search_basis,
            )
        )
    else:
        checks.append(
            _simple(
                "search_selection",
                "Search & selection reporting",
                _SEARCH_STRATEGY,
                rows,
                basis=search_basis,
                missing_note=(
                    "the search & selection process (databases searched, inclusion/eligibility criteria, a PRISMA "
                    "flow, or a registered protocol) isn't reported — a reader can't judge what was and wasn't included"
                ),
                explainer=search_explainer,
            )
        )

    return MetaReport(is_meta_analysis=True, checks=checks)


def apply_meta_analysis(conn: Connection, paper_id: int, report: MetaReport) -> None:
    """Persist a paper's meta-analysis audit (backlog #23, F1/F4). Mirrors `apply_lmm` exactly: the #23-signal
    status always, and — only when incomplete — a review-queue CANDIDATE (never a fact). One shared function,
    callable from both the ad-hoc per-paper view and the library-wide batch."""
    incomplete = [c.key for c in report.checks if c.status == "not-found"]
    store_meta(conn, paper_id, is_meta_analysis=report.is_meta_analysis, incomplete_keys=incomplete)
    if report.is_meta_analysis and incomplete:
        n = len(incomplete)
        upsert_findings(
            conn,
            paper_id,
            "meta",
            [
                {
                    "kind": "candidate",
                    "tier": "primary",
                    "payload": {
                        "desc": f"{n} meta-analysis reporting item{'s' if n != 1 else ''} not detected in the text — review",
                        "missing": incomplete,
                    },
                }
            ],
        )
    else:
        upsert_findings(conn, paper_id, "meta", [])
