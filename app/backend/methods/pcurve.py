"""p-curve — collection-level evidential-value check (inc 126).

Given a SET of statistically-significant focal NHST results (0 < p < .05) across selected papers, p-curve
(Simonsohn, Nelson & Simmons, 2014) tests whether their p-value distribution is RIGHT-SKEWED (more very-small
p-values → evidential value) versus flat/left-skewed (→ no / inadequate evidential value). It is
**collection-level only** — never per-paper, and it never labels a paper or author "p-hacked." The tool presents
the curve + the statistic; the **interpretation is the user's** (PRINCIPLES #2 signal-not-verdict; the A-A
veto-level no-accusation boundary).

Deterministic, local, **no LLM, no egress**. It reuses the statcheck extractor
(`methods/statcheck.run_statcheck` → `StatResult.computed_p`, the exact p recomputed from the test statistic + df)
for its inputs. v1 = the **right-skew (Stouffer) test** + a **binomial robustness check** + the
**observed-vs-null plot**. The full "33% power" flatness test is **deferred** — it needs the test statistic + df
(noncentral distributions), which `StatResult` does not expose.

Lineage (credit-the-lineage): Simonsohn, U., Nelson, L. D., & Simmons, J. P. (2014). P-curve: A key to the
file-drawer. *Journal of Experimental Psychology: General*, 143(2), 534–547.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from scipy.stats import binomtest, norm

ALPHA = 0.05
MIN_RELIABLE = 5  # below this many significant tests, the curve is too sparse to interpret


@dataclass(frozen=True)
class IncludedTest:
    paper_id: int
    page: int | None
    p: float
    raw: str


@dataclass
class PcurveResult:
    n_papers: int = 0
    k_total_extracted: int = 0  # all inline NHST tests found across the selection
    k_significant: int = 0  # those with 0 < p < .05 (the p-curve input)
    right_skew_z: float | None = None
    right_skew_p: float | None = None  # one-tailed; < .05 → significant right skew (evidential value)
    binomial_p: float | None = None  # share of p < .025 vs 50% (one-tailed "greater")
    bins: list[float] = field(default_factory=list)  # 5 percentages {.01,.02,.03,.04,.05}, summing ~100
    included_tests: list[IncludedTest] = field(default_factory=list)
    low_power: bool = False  # k_significant < MIN_RELIABLE
    note: str = ""


def _pp_value(p: float) -> float:
    """The pp-value under H0: the conditional probability of a p at least this small given significance."""
    pp = p / ALPHA
    return min(max(pp, 1e-12), 1 - 1e-12)  # clamp so norm.ppf stays finite


def _bin_index(p: float) -> int:
    """p ≤ .01 → 0; (.01,.02] → 1; (.02,.03] → 2; (.03,.04] → 3; (.04,.05) → 4."""
    return min(4, max(0, math.ceil(p / 0.01) - 1))


def compute_pcurve(p_values: list[float]) -> dict:
    """The p-curve statistics over a list of p-values (non-significant / non-positive are filtered out)."""
    sig = [p for p in p_values if 0 < p < ALPHA]
    k = len(sig)
    out: dict = {
        "k_significant": k,
        "right_skew_z": None,
        "right_skew_p": None,
        "binomial_p": None,
        "bins": [],
        "low_power": k < MIN_RELIABLE,
    }
    if k == 0:
        return out
    z = sum(norm.ppf(_pp_value(p)) for p in sig) / math.sqrt(k)
    out["right_skew_z"] = float(z)
    out["right_skew_p"] = float(norm.cdf(z))  # right skew is significant when z < 0
    below = sum(1 for p in sig if p < ALPHA / 2)
    out["binomial_p"] = float(binomtest(below, k, 0.5, alternative="greater").pvalue)
    counts = [0, 0, 0, 0, 0]
    for p in sig:
        counts[_bin_index(p)] += 1
    out["bins"] = [round(100.0 * c / k, 1) for c in counts]
    return out


def _note(n_papers: int, k_total: int, k_sig: int) -> str:
    if k_sig == 0:
        return (
            f"No significant inline NHST results (p < .05) were found across the {n_papers} selected "
            f"paper{'s' if n_papers != 1 else ''}. p-curve reads only inline APA-style tests with exact "
            "statistics — tables, Bayesian reporting, and confidence-interval-only results are invisible."
        )
    base = (
        f"{k_sig} significant inline NHST result{'s' if k_sig != 1 else ''} "
        f"(of {k_total} extracted) across {n_papers} paper{'s' if n_papers != 1 else ''}. "
        "Automated extraction includes every inline test; p-curve methodology asks the analyst to choose each "
        "study's focal test — review the included set below."
    )
    if k_sig < MIN_RELIABLE:
        base += f" Only {k_sig} significant result{'s' if k_sig != 1 else ''} — too few to interpret reliably "
        base += f"(≥ {MIN_RELIABLE} recommended)."
    return base


def run_pcurve(per_paper: list[tuple[int, list]]) -> PcurveResult:
    """Build a p-curve over per-paper statcheck results. ``per_paper`` is a list of (paper_id, list[StatResult]).
    Each StatResult's ``computed_p`` (the exact recomputed p) is the input; significant ones are carried with
    their provenance (paper_id, page, raw) so every included test stays inspectable."""
    included: list[IncludedTest] = []
    k_total = 0
    for paper_id, results in per_paper:
        for r in results:
            k_total += 1
            if 0 < r.computed_p < ALPHA:
                included.append(IncludedTest(paper_id=paper_id, page=r.page, p=r.computed_p, raw=r.raw))
    stats = compute_pcurve([t.p for t in included])
    return PcurveResult(
        n_papers=len(per_paper),
        k_total_extracted=k_total,
        k_significant=stats["k_significant"],
        right_skew_z=stats["right_skew_z"],
        right_skew_p=stats["right_skew_p"],
        binomial_p=stats["binomial_p"],
        bins=stats["bins"],
        included_tests=included,
        low_power=stats["low_power"],
        note=_note(len(per_paper), k_total, stats["k_significant"]),
    )
