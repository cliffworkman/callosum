"""LMM-reporting completeness auditor (backlog #23, inc 247).

Reads a paper's extracted text and flags whether it *reports* what a careful reader needs to evaluate a linear
mixed model — random-effects structure, df/inference method, convergence, estimation, ICC, marginal/conditional
R², and (for longitudinal designs with dropout) a missing-data sensitivity analysis. FLAG-not-ADJUDICATE: each
check is present / not-found / not-applicable, never a verdict, never a score. It reads reported text only — it
NEVER runs a model, an imputation, or a sensitivity analysis, and never ingests raw data (the identity boundary).
The deterministic sibling of statcheck / the Bayesian completeness checklist. Local, no AI, no egress.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LmmCheck:
    key: str  # random_effects | df_method | convergence | estimation | icc | r2 | missing_data
    label: str
    status: str  # present | not-found | not-applicable
    evidence: str | None  # the matched snippet (present → what was found), so the reader can verify
    page: int | None
    note: str | None  # status-specific: the grounded recommendation when not-found; a short confirmation when present
    explainer: str  # always-on "what this is / why it matters" literacy note
    basis: str  # the cited methodological source (in-context attribution)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LmmReport:
    is_lmm: bool
    checks: list  # list[LmmCheck]

    def to_dict(self) -> dict:
        return {"is_lmm": self.is_lmm, "checks": [c.to_dict() for c in self.checks]}


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


# The gate — is this detectably a mixed-model paper?
_LMM = _rx(
    r"linear mixed[-\s]?effects?\s+model|linear mixed model|mixed[-\s]?effects?\s+(model|regression|analysis)"
    r"|\bmixed model|multilevel\s+(model|regression|analysis)|hierarchical linear model|\bHLM\b"
    r"|lmer\s*\(|glmer\s*\(|\blme\s*\(|\blme4\b|\bnlme\b|MixedLM|random[-\s]?(intercept|slope|effect)"
)

_RANDOM = _rx(
    r"\(\s*[^()|]*\|\s*[^()]+\)|random[-\s]?(intercept|slope)|random effects?\s+(of|for|structure|specification)"
    r"|by[-\s](subject|item|participant|speaker|stimulus)s?\s+random"
)
_DF = _rx(
    r"Satterthwaite|Kenward[-–\s]?Roger|lmerTest|pbkrtest|likelihood[-\s]ratio test|\bLRT\b|\bWald\b"
    r"|asymptotic|degrees of freedom"
)
_CONVERGENCE = _rx(r"converg(e|ed|ence)|singular|isSingular|boundary \(singular\)|failed to converge|did not converge")
_ESTIMATION = _rx(r"\bREML\b|restricted maximum likelihood|maximum[-\s]likelihood|\bML estimation\b")
_CLUSTERING = _rx(
    r"multilevel|nested|clustered|hierarchical|level[-\s]?[12]\b"
    r"|within[-\s](school|clinic|site|cluster|group|classroom|hospital|team|ward)s?"
)
_ICC = _rx(r"\bICC\b|intra[-\s]?class correlation")
_R2 = _rx(r"marginal\s+R|conditional\s+R|\bR2m\b|\bR2c\b|Nakagawa|variance explained")
_LONGITUDINAL = _rx(
    r"longitudinal|repeated[-\s]measures|over time|\bwaves?\b|time[-\s]points?|follow[-\s]?up|\bvisits?\b"
    r"|baseline and"
)
_DROPOUT = _rx(
    r"dropout|drop(?:ped|s)?[-\s]?out|attrition|missing data|lost to follow[-\s]?up|withdrew|incomplete (case|data)"
)
_SENSITIVITY = _rx(
    r"sensitivity analys[ie]s|multiple imputation|\bMI\b|pattern[-\s]mixture|reference[-\s]based|tipping[-\s]point"
    r"|controlled imputation|delta[-\s](adjusted|based)|\bMNAR\b|jump to reference"
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


def _simple(
    key: str, label: str, pattern: re.Pattern, rows, *, basis: str, missing_note: str, explainer: str
) -> LmmCheck:
    """A check with a single presence precondition: present (with evidence) or not-found (with a grounded note)."""
    hit = _first(pattern, rows)
    if hit:
        return LmmCheck(key, label, "present", hit[0], hit[1], None, explainer, basis)
    return LmmCheck(key, label, "not-found", None, None, f"{missing_note} ({_NOT_DETECTED})", explainer, basis)


def audit_lmm(chunks: list) -> LmmReport:
    """Presence/absence checklist over a paper's extracted text; runs only if it detectably uses a mixed model.
    Each check present / not-found / not-applicable — never a verdict, never a score, never runs a model."""
    rows = _chunk_rows(chunks)
    if not _has(_LMM, rows):
        return LmmReport(is_lmm=False, checks=[])

    checks: list[LmmCheck] = []

    checks.append(
        _simple(
            "random_effects",
            "Random-effects structure",
            _RANDOM,
            rows,
            basis="Barr et al. 2013 (keep it maximal); Matuschek et al. 2017",
            missing_note=(
                "the random-effects structure (which grouping factors carry random intercepts/slopes) isn't "
                "stated — a reader needs it, and the field debates maximal vs parsimonious, so the choice matters"
            ),
            explainer=(
                "Which grouping factors carry random intercepts and slopes. The maximal-vs-parsimonious debate "
                "(Barr et al. vs Matuschek et al.) makes the structure a modelling choice worth seeing — this "
                "flags absence, never adjudicates the choice."
            ),
        )
    )
    checks.append(
        _simple(
            "df_method",
            "Degrees-of-freedom / inference method",
            _DF,
            rows,
            basis="Luke 2017",
            missing_note=(
                "the df / inference method (Satterthwaite / Kenward-Roger / Wald / LRT) isn't reported — it "
                "materially changes the p-values"
            ),
            explainer=(
                "How p-values/CIs for fixed effects were obtained — Satterthwaite or Kenward-Roger approximate the "
                "denominator df; Wald/LRT/asymptotic don't. Luke (2017) shows the choice changes results."
            ),
        )
    )
    checks.append(
        _simple(
            "convergence",
            "Convergence / singular fit",
            _CONVERGENCE,
            rows,
            basis="Bates et al. 2015 (lme4)",
            missing_note="whether the model converged, or the fit was singular, isn't mentioned",
            explainer=(
                "A mixed model can fail to converge or return a singular fit (a random-effects variance estimated "
                "at the boundary) — either undermines the estimates, so a careful reader looks for a convergence "
                "statement."
            ),
        )
    )
    checks.append(
        _simple(
            "estimation",
            "Estimation method (REML vs ML)",
            _ESTIMATION,
            rows,
            basis="Bates et al. 2015 (lme4)",
            missing_note="REML vs ML isn't stated — it matters for likelihood-ratio tests on fixed effects",
            explainer=(
                "REML gives less-biased variance estimates but its likelihoods can't be compared across different "
                "fixed-effects structures; ML can. Which was used affects the validity of LRTs on fixed effects."
            ),
        )
    )

    # ICC — only expected when a clustering/multilevel structure is claimed.
    icc_explainer = (
        "In a multilevel design the intraclass correlation is how much variance sits between clusters — it "
        "motivates the multilevel model and gauges dependence."
    )
    icc_basis = "multilevel-modelling literature (e.g. Nakagawa & Schielzeth 2013)"
    if not _has(_CLUSTERING, rows):
        checks.append(
            LmmCheck(
                "icc",
                "Intraclass correlation (ICC)",
                "not-applicable",
                None,
                None,
                "no multilevel/clustering structure is claimed, so an ICC isn't expected",
                icc_explainer,
                icc_basis,
            )
        )
    else:
        checks.append(
            _simple(
                "icc",
                "Intraclass correlation (ICC)",
                _ICC,
                rows,
                basis=icc_basis,
                missing_note=(
                    "a multilevel/clustering structure is claimed but no ICC is reported — it's the natural measure "
                    "of between-cluster dependence"
                ),
                explainer=icc_explainer,
            )
        )

    checks.append(
        _simple(
            "r2",
            "Marginal vs conditional R²",
            _R2,
            rows,
            basis="Nakagawa & Schielzeth 2013",
            missing_note="the variance explained (marginal vs conditional R²) isn't reported",
            explainer=(
                "Marginal R² is variance explained by fixed effects; conditional R² by fixed + random. Reporting "
                "which (Nakagawa & Schielzeth) tells the reader how much the model actually accounts for."
            ),
        )
    )

    # Missing-data sensitivity — the Troendle-grounded flag, tightly scoped to longitudinal + evident dropout.
    md_explainer = (
        "For a longitudinal model with dropout, the primary analysis assumes the missingness is ignorable (MAR). A "
        "sensitivity analysis (controlled/delta imputation, pattern-mixture, reference-based, tipping-point) checks "
        "whether the conclusion survives plausible departures."
    )
    md_basis = "FDA ICH E9(R1); Troendle et al. 2025; Cro et al. 2020; Moreno-Betancur & Chavance 2016"
    if not (_has(_LONGITUDINAL, rows) and _has(_DROPOUT, rows)):
        checks.append(
            LmmCheck(
                "missing_data",
                "Missing-data sensitivity analysis",
                "not-applicable",
                None,
                None,
                "not a longitudinal design with evident dropout, so a missing-data sensitivity analysis isn't "
                "expected here",
                md_explainer,
                md_basis,
            )
        )
    else:
        hit = _first(_SENSITIVITY, rows)
        if hit:
            checks.append(
                LmmCheck(
                    "missing_data",
                    "Missing-data sensitivity analysis",
                    "present",
                    hit[0],
                    hit[1],
                    None,
                    md_explainer,
                    md_basis,
                )
            )
        else:
            checks.append(
                LmmCheck(
                    "missing_data",
                    "Missing-data sensitivity analysis",
                    "not-found",
                    None,
                    None,
                    "a longitudinal model with dropout, but no missing-data sensitivity analysis detected — FDA ICH "
                    "E9(R1) recommends assessing robustness to the missing-at-random assumption (controlled/delta "
                    "imputation, pattern-mixture, reference-based, tipping-point). Not a claim the analysis is wrong "
                    f"({_NOT_DETECTED})",
                    md_explainer,
                    md_basis,
                )
            )

    return LmmReport(is_lmm=True, checks=checks)
