"""z-curve — collection-level replication/discovery-rate estimator (inc 470).

Bartoš & Schimmack (2022, Meta-Psychology 6, MP.2021.2720): given a SET of statistically-significant z-values
(from focal NHST tests across selected papers), z-curve 2.0 fits a mixture of 7 fixed-mean truncated folded-normal
components to estimate:
  - EDR (Expected Discovery Rate): the model's estimate of what share of ALL conducted tests (significant or not)
    would be significant — compared against the Observed Discovery Rate (ODR), a gap is a signature consistent
    with selective reporting.
  - ERR (Expected Replication Rate): the model's estimate of how often the SIGNIFICANT results specifically would
    replicate if exactly repeated.

It is **collection-level only** — never per-paper, and it never labels a paper or author. The tool presents the
estimate + its (wide, honestly-disclosed) uncertainty; the **interpretation is the user's**
(PRINCIPLES #2 signal-not-verdict; the A-A veto-level no-accusation boundary). z-curve needs a much larger sample
than p-curve to be reliable — the reference implementation's own author warns N < 300 significant results "might
produce undercoverage and biased estimates" (`zcurve` R package, `main.R`), so results below that threshold carry
a hard, non-dismissable reliability warning rather than a soft note.

Deterministic, local, **no LLM, no egress**. Reuses the exact same statcheck-derived significant-z extraction as
p-curve (`methods/pcurve.py`) — every extracted significant test is included, never an LLM-picked "focal
statistic" per study (the source design doc's proposed "auto-zcurve" shape, declined — see backlog #55 /
INCREMENT-470-NOTES.md). Algorithm verified against the reference `zcurve` R package's own source
(github.com/FBartos/zcurve, R/tools.R + R/zcurve_EM.R), not derived from memory.

Lineage (credit-the-lineage): Bartoš, F., & Schimmack, U. (2022). Z-curve 2.0: Estimating replication rates and
discovery rates. Meta-Psychology, 6, MP.2021.2720. https://doi.org/10.15626/MP.2021.2720
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

SIG_LEVEL = 0.05
A = float(norm.ppf(1 - SIG_LEVEL / 2))  # ~1.959964 — the two-sided significance z-cutoff
B = 6.0  # upper end of the EM fitting region (R default); z above this is tallied as prop_high, not EM-fit
MU = np.arange(7.0)  # 7 FIXED component means 0..6 (not re-estimated — only their weights are fit)
MIN_RELIABLE_N = 300  # the reference implementation's own hard threshold for a reliable estimate
N_BOOT_DEFAULT = 400  # tuned down from the R default of 1000 for a from-scratch Python EM in a background job
N_RESTARTS = 8
MAX_ITER = 500
CRITERION = 1e-6  # convergence on the largest per-component weight change (scale-invariant, see _fit_weights_em)
ERR_ADJ = 0.03  # calibrated CI-widening adjustments from the published method (Bartoš & Schimmack 2022)
EDR_ADJ = 0.05


def _power_two_sided(z: np.ndarray, a: float = A) -> np.ndarray:
    return norm.cdf(z - a) + norm.cdf(-z - a)


def _power_one_sided(z: np.ndarray, a: float = A) -> np.ndarray:
    return norm.cdf(z - a)


def _truncated_norm_const(mu: np.ndarray, a: float = A, b: float = B) -> np.ndarray:
    return (norm.cdf(b - mu) - norm.cdf(a - mu)) + (norm.cdf(b + mu) - norm.cdf(a + mu))


def _component_densities(z: np.ndarray, mu: np.ndarray = MU, a: float = A, b: float = B) -> np.ndarray:
    """Truncated folded-normal density matrix, shape (n_obs, n_components)."""
    z_col = z[:, None]
    mu_row = mu[None, :]
    raw = norm.pdf(z_col - mu_row) + norm.pdf(z_col + mu_row)
    return raw / _truncated_norm_const(mu_row, a, b)


def _fit_weights_em(
    z_in: np.ndarray,
    mu: np.ndarray = MU,
    n_restarts: int = N_RESTARTS,
    max_iter: int = MAX_ITER,
    criterion: float = CRITERION,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """EM fit of mixture weights over FIXED components. Weight-only EM on a fixed-component mixture is a concave
    problem (a sum of logs of affine functions of theta), so it has no local optima; multiple restarts here are a
    numerical-robustness check, not a correctness requirement, unlike the general (free-means) mixture-EM case."""
    if rng is None:
        rng = np.random.default_rng(0)
    k = len(mu)
    if z_in.size == 0:
        return np.zeros(k)
    dens = _component_densities(z_in, mu)
    best_theta = np.full(k, 1.0 / k)
    best_ll = -np.inf
    for _ in range(max(1, n_restarts)):
        theta = rng.dirichlet(np.full(k, 0.5))
        for _ in range(max_iter):
            weighted = dens * theta[None, :]
            row_sums = np.clip(weighted.sum(axis=1, keepdims=True), 1e-300, None)
            resp = weighted / row_sums
            theta_new = resp.mean(axis=0)
            theta_new = theta_new / theta_new.sum()
            # Scale-invariant convergence: the largest per-component weight change. An absolute log-likelihood
            # criterion never converges for large N (the total log-likelihood scales with N), so this compares
            # the parameters themselves instead — the fix caught by a real timeout on a ~7k-observation dataset.
            if np.max(np.abs(theta_new - theta)) < criterion:
                theta = theta_new
                break
            theta = theta_new
        weighted = dens * theta[None, :]
        row_sums = np.clip(weighted.sum(axis=1, keepdims=True), 1e-300, None)
        prev_ll = float(np.log(row_sums).sum())
        if prev_ll > best_ll:
            best_ll = prev_ll
            best_theta = theta
    return best_theta


def _compute_edr_err(
    theta: np.ndarray, prop_high: float, mu: np.ndarray = MU, a: float = A
) -> tuple[float, float, float]:
    """The population-weight extrapolation + EDR/ERR formulas, verified against `.get_pop_weights`/`.get_EDR`/
    `.get_ERR` in the reference `zcurve` R package's `R/tools.R`."""
    weights = np.append(theta * (1 - prop_high), prop_high)  # length 8: 7 components + the "beyond b" bucket

    power2 = np.append(_power_two_sided(mu, a), 1.0)  # the "beyond b" bucket has ~certain (1.0) power
    power1 = np.append(_power_one_sided(mu, a), 1.0)
    power_n = power2 - power1

    pop_weights_raw = weights / np.clip(power2, 1e-12, None)
    pop_weights = pop_weights_raw / pop_weights_raw.sum()

    edr = float(np.sum(pop_weights * power2))
    err_num = float(np.sum(pop_weights * (power_n**2 + power1**2)))
    err = err_num / edr if edr > 0 else float("nan")
    z0 = float(weights[0])
    return edr, err, z0


def _percentile_ci(
    boot: np.ndarray, adj: float, lo_bound: float, hi_bound: float = 1.0, conf: float = 0.95
) -> tuple[float, float]:
    lo = float(np.percentile(boot, 100 * (0.5 - conf / 2)))
    hi = float(np.percentile(boot, 100 * (0.5 + conf / 2)))
    return (max(lo - adj, lo_bound), min(hi + adj, hi_bound))


@dataclass(frozen=True)
class _ZcurveFit:
    edr: float
    edr_ci: tuple[float, float] | None
    err: float
    err_ci: tuple[float, float] | None
    z0: float


def fit_zcurve(
    z_values: list[float], bootstrap: int = N_BOOT_DEFAULT, rng: np.random.Generator | None = None
) -> _ZcurveFit | None:
    """Fit the z-curve 2.0 mixture model to a set of already-significant z-values (each >= A)."""
    z = np.asarray(z_values, dtype=float)
    z = z[np.isfinite(z) & (z >= A)]
    n_sig = z.size
    if n_sig == 0:
        return None
    if rng is None:
        rng = np.random.default_rng(0)

    z_in = z[z <= B]
    z_high = z[z > B]
    prop_high = float(z_high.size) / n_sig

    theta = _fit_weights_em(z_in, MU, rng=rng)
    edr, err, z0 = _compute_edr_err(theta, prop_high)

    edr_ci: tuple[float, float] | None = None
    err_ci: tuple[float, float] | None = None
    if bootstrap and n_sig >= 2:
        boot_edr = np.empty(bootstrap)
        boot_err = np.empty(bootstrap)
        for i in range(bootstrap):
            resample = rng.choice(z, size=n_sig, replace=True)
            r_in = resample[resample <= B]
            r_high = resample[resample > B]
            r_prop_high = float(r_high.size) / n_sig
            r_theta = _fit_weights_em(r_in, MU, n_restarts=1, rng=rng)
            b_edr, b_err, _ = _compute_edr_err(r_theta, r_prop_high)
            boot_edr[i] = b_edr
            boot_err[i] = b_err
        edr_ci = _percentile_ci(boot_edr, EDR_ADJ, lo_bound=SIG_LEVEL)
        err_ci = _percentile_ci(boot_err, ERR_ADJ, lo_bound=SIG_LEVEL / 2)

    return _ZcurveFit(edr=edr, edr_ci=edr_ci, err=err, err_ci=err_ci, z0=z0)


@dataclass(frozen=True)
class IncludedTest:
    paper_id: int
    page: int | None
    z: float
    p: float
    raw: str


@dataclass
class ZcurveResult:
    n_papers: int = 0
    k_total_extracted: int = 0  # all inline NHST tests found across the selection
    k_significant: int = 0  # those with 0 < p < .05 (the z-curve input)
    odr: float | None = None  # observed discovery rate = k_significant / k_total_extracted
    edr: float | None = None
    edr_ci: tuple[float, float] | None = None
    err: float | None = None
    err_ci: tuple[float, float] | None = None
    z0: float | None = None  # estimated share of significant results attributable to the null (mu=0) component
    included_tests: list[IncludedTest] = field(default_factory=list)
    low_reliability: bool = True
    note: str = ""


def _note(n_papers: int, k_total: int, k_sig: int) -> str:
    if k_sig == 0:
        return (
            f"No significant inline NHST results (p < .05) were found across the {n_papers} selected "
            f"paper{'s' if n_papers != 1 else ''}. z-curve reads only inline APA-style tests with exact "
            "statistics — tables, Bayesian reporting, and confidence-interval-only results are invisible."
        )
    base = (
        f"{k_sig} significant inline NHST result{'s' if k_sig != 1 else ''} "
        f"(of {k_total} extracted) across {n_papers} paper{'s' if n_papers != 1 else ''}. "
        "Automated extraction includes every inline significant test; z-curve methodology asks the analyst to "
        "choose each study's focal test — review the included set below."
    )
    if k_sig < MIN_RELIABLE_N:
        base += (
            f" Only {k_sig} significant result{'s' if k_sig != 1 else ''} — z-curve needs at least "
            f"{MIN_RELIABLE_N} for a reliable estimate; treat EDR/ERR here as exploratory, not a stable estimate."
        )
    return base


def run_zcurve(
    per_paper: list[tuple[int, list]], bootstrap: int = N_BOOT_DEFAULT, rng: np.random.Generator | None = None
) -> ZcurveResult:
    """Build a z-curve over per-paper statcheck results. ``per_paper`` is a list of (paper_id, list[StatResult]) —
    the identical shape `run_pcurve` takes. Each StatResult's ``computed_p`` is converted to a z-value; significant
    ones are carried with their provenance (paper_id, page, raw) so every included test stays inspectable."""
    included: list[IncludedTest] = []
    k_total = 0
    for paper_id, results in per_paper:
        for r in results:
            k_total += 1
            if 0 < r.computed_p < SIG_LEVEL:
                z = float(norm.ppf(1 - r.computed_p / 2))
                included.append(IncludedTest(paper_id=paper_id, page=r.page, z=z, p=r.computed_p, raw=r.raw))
    n_sig = len(included)
    odr = (n_sig / k_total) if k_total else None
    fit = fit_zcurve([t.z for t in included], bootstrap=bootstrap, rng=rng) if n_sig else None
    return ZcurveResult(
        n_papers=len(per_paper),
        k_total_extracted=k_total,
        k_significant=n_sig,
        odr=odr,
        edr=fit.edr if fit else None,
        edr_ci=fit.edr_ci if fit else None,
        err=fit.err if fit else None,
        err_ci=fit.err_ci if fit else None,
        z0=fit.z0 if fit else None,
        included_tests=included,
        low_reliability=n_sig < MIN_RELIABLE_N,
        note=_note(len(per_paper), k_total, n_sig),
    )
