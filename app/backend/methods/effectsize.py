"""Effect-size converter — the deterministic core of the meta-analysis extraction workbench (SP1, inc 252).

Converts ONE study's reported statistics into a common meta-analytic metric (Hedges' g, Fisher's z, log OR/RR, risk
difference) + its variance + a 95% CI, via standard cited formulas. Each result shows its **path**, cites its
**formula source**, and records the per-study **choices** (which SD-derivation, which zero-cell continuity correction,
which cross-metric approximation).

THE LOAD-BEARING BOUNDARY — convert, never synthesize. This module converts one study at a time. It NEVER pools,
models heterogeneity, meta-regresses, or does bias inference — that is metafor/JASP/RevMan territory, and there is no
code path here that aggregates across studies (test-pinned). It is deterministic, local, no-LLM. The output is an
analysis-ready datum + provenance the researcher hands off to a synthesis tool.

Formula lineage (credited in-context + THIRD-PARTY-NOTICES): Borenstein, Hedges, Higgins & Rothstein (2009,
*Introduction to Meta-Analysis*); metafor (Viechtbauer 2010); Fisher (1915, the z transform); Hedges (1981, the small-
sample J correction); Wan et al. (2014, IQR→SD refinement); Haldane (1940) / Anscombe (1956, the 0.5 continuity
correction); Hasselblad & Hedges (1995, the log-odds↔d approximation).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from scipy.stats import norm

# This module converts a SINGLE study at a time. It defines no pooling / heterogeneity / meta-regression / bias-
# inference function — those are the synthesis tools' job (metafor/JASP/RevMan), a line Callosum does not cross.
NO_AGGREGATION = True

_Z975 = float(norm.ppf(0.975))  # 1.959964…, the 95% CI multiplier
MAX_N = 10_000_000  # bound inputs (rule #4)


@dataclass(frozen=True)
class Conversion:
    """One study's converted effect size + everything needed to trust and audit it."""

    metric: str  # e.g. "Hedges' g", "Fisher's z", "log odds ratio"
    value: float
    variance: float
    se: float
    ci_low: float
    ci_high: float
    path: list[str] = field(default_factory=list)  # ordered human-readable steps
    formula_source: str = ""  # the cited primary/textbook source
    caveats: list[str] = field(default_factory=list)  # e.g. an "approximation" flag
    choices: list[str] = field(default_factory=list)  # the recorded per-study decisions

    def to_dict(self) -> dict:
        return asdict(self)


def _fnum(x, name: str) -> float:
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number")
    return v


def _int_n(x, name: str) -> int:
    n = int(x)
    if n < 1 or n > MAX_N:
        raise ValueError(f"{name} out of range")
    return n


def _result(metric, value, variance, path, source, *, caveats=None, choices=None) -> Conversion:
    if not math.isfinite(value) or not math.isfinite(variance) or variance < 0:
        raise ValueError("degenerate conversion (non-finite value or negative variance)")
    se = math.sqrt(variance)
    return Conversion(
        metric=metric,
        value=round(value, 6),
        variance=round(variance, 6),
        se=round(se, 6),
        ci_low=round(value - _Z975 * se, 6),
        ci_high=round(value + _Z975 * se, 6),
        path=path,
        formula_source=source,
        caveats=list(caveats or []),
        choices=list(choices or []),
    )


# --- SD derivations (the auditable "which path" decision) ----------------------------------------------------------


def sd_from_se(se, n) -> tuple[float, str]:
    """SD = SE·√n. Returns (sd, choice)."""
    se = _fnum(se, "SE")
    n = _int_n(n, "n")
    if se <= 0:
        raise ValueError("SE must be positive")
    return se * math.sqrt(n), "SD derived from SE (SD = SE·√n)"


def sd_from_ci(lo, hi, n) -> tuple[float, str]:
    """SD from a 95% CI of the mean: SD = (hi−lo)·√n / (2·z.975)."""
    lo, hi = _fnum(lo, "CI lower"), _fnum(hi, "CI upper")
    n = _int_n(n, "n")
    if hi <= lo:
        raise ValueError("CI upper must exceed lower")
    return (hi - lo) * math.sqrt(n) / (2 * _Z975), "SD derived from a 95% CI (SD = (hi−lo)·√n / (2·1.96))"


def sd_from_iqr(iqr) -> tuple[float, str]:
    """SD ≈ IQR / 1.349 (normal-quantile rule, Cochrane Handbook; Wan et al. 2014 refines this by sample size)."""
    iqr = _fnum(iqr, "IQR")
    if iqr <= 0:
        raise ValueError("IQR must be positive")
    return iqr / 1.349, "SD estimated from IQR (÷1.349, normal-quantile / Cochrane; Wan et al. 2014 refines by n)"


def sd_derivation(inputs: dict) -> Conversion:
    """Expose the SD derivations as their own family (a value + its recorded choice), no effect size yet."""
    method = inputs.get("method")
    if method == "se":
        sd, choice = sd_from_se(inputs["se"], inputs["n"])
    elif method == "ci":
        sd, choice = sd_from_ci(inputs["lo"], inputs["hi"], inputs["n"])
    elif method == "iqr":
        sd, choice = sd_from_iqr(inputs["iqr"])
    else:
        raise ValueError("SD derivation method must be se / ci / iqr")
    # An SD is not an effect size; report it as a value with zero placeholder variance and its provenance.
    return Conversion(
        metric="standard deviation",
        value=round(sd, 6),
        variance=0.0,
        se=0.0,
        ci_low=round(sd, 6),
        ci_high=round(sd, 6),
        path=[choice, f"SD = {sd:.4f}"],
        formula_source="Cochrane Handbook (Higgins et al.); Wan et al. 2014",
        choices=[choice],
        caveats=["An estimated SD carries extra uncertainty not reflected downstream — record the derivation."],
    )


# --- SMD (standardized mean difference) → Hedges' g ----------------------------------------------------------------


def _d_to_g(d: float, n1: int, n2: int, path: list[str]) -> tuple[float, float, float]:
    """Apply the Hedges small-sample correction J; return (g, Var(d), Var(g))."""
    dfree = 4 * (n1 + n2) - 9
    j = 1.0 - 3.0 / dfree
    var_d = (n1 + n2) / (n1 * n2) + d * d / (2 * (n1 + n2))
    var_g = j * j * var_d
    path.append(f"J = 1 − 3/(4·{n1 + n2}−9) = {j:.5f}  (Hedges 1981 small-sample correction)")
    path.append(f"g = J·d = {j * d:.4f};  Var(d) = {var_d:.5f}, Var(g) = J²·Var(d) = {var_g:.5f}")
    return j * d, var_d, var_g


def smd(m1, s1, n1, m2, s2, n2) -> Conversion:
    """Two-group standardized mean difference → Hedges' g, from group means + SDs + Ns (Borenstein 2009 Ch. 4)."""
    m1, m2 = _fnum(m1, "M1"), _fnum(m2, "M2")
    s1, s2 = _fnum(s1, "SD1"), _fnum(s2, "SD2")
    n1, n2 = _int_n(n1, "n1"), _int_n(n2, "n2")
    if n1 < 2 or n2 < 2:
        raise ValueError("each group needs n ≥ 2")
    if s1 <= 0 or s2 <= 0:
        raise ValueError("group SDs must be positive")
    sp = math.sqrt(((n1 - 1) * s1 * s1 + (n2 - 1) * s2 * s2) / (n1 + n2 - 2))
    d = (m1 - m2) / sp
    path = [
        f"pooled SD s_p = √(((n1−1)·SD1² + (n2−1)·SD2²)/(n1+n2−2)) = {sp:.4f}",
        f"Cohen's d = (M1−M2)/s_p = {d:.4f}",
    ]
    g, _var_d, var_g = _d_to_g(d, n1, n2, path)
    return _result("Hedges' g", g, var_g, path, "Borenstein et al. 2009, Ch. 4; Hedges 1981")


def smd_from_t(t, n1, n2) -> Conversion:
    """Cohen's d from an independent-samples t + group Ns (d = t·√(1/n1 + 1/n2)) → Hedges' g."""
    t = _fnum(t, "t")
    n1, n2 = _int_n(n1, "n1"), _int_n(n2, "n2")
    if n1 < 2 or n2 < 2:
        raise ValueError("each group needs n ≥ 2")
    d = t * math.sqrt(1.0 / n1 + 1.0 / n2)
    path = [f"d = t·√(1/n1 + 1/n2) = {t:.3f}·√(1/{n1}+1/{n2}) = {d:.4f}"]
    g, _var_d, var_g = _d_to_g(d, n1, n2, path)
    return _result("Hedges' g", g, var_g, path, "Borenstein et al. 2009 (from t); Hedges 1981")


def smd_from_f(f, n1, n2) -> Conversion:
    """Cohen's d from a two-group one-way F (t = √F, then the t path) → Hedges' g."""
    f = _fnum(f, "F")
    if f < 0:
        raise ValueError("F must be ≥ 0")
    out = smd_from_t(math.sqrt(f), n1, n2)
    return Conversion(
        metric=out.metric,
        value=out.value,
        variance=out.variance,
        se=out.se,
        ci_low=out.ci_low,
        ci_high=out.ci_high,
        path=[f"two-group one-way F → t = √F = √{f:.3f} = {math.sqrt(f):.3f}", *out.path],
        formula_source=out.formula_source,
        caveats=["Assumes a two-group one-way F (F = t²); not valid for a >2-group omnibus F."],
        choices=out.choices,
    )


# --- Correlation → Fisher's z --------------------------------------------------------------------------------------


def correlation(r, n) -> Conversion:
    """Pearson r → Fisher's z = atanh(r), Var = 1/(n−3) (Fisher 1915)."""
    r = _fnum(r, "r")
    n = _int_n(n, "n")
    if not (-1.0 < r < 1.0):
        raise ValueError("r must be in (−1, 1)")
    if n <= 3:
        raise ValueError("n must be > 3 for Var(z)")
    z = math.atanh(r)
    return _result(
        "Fisher's z",
        z,
        1.0 / (n - 3),
        [f"z = atanh(r) = atanh({r}) = {z:.4f}", f"Var(z) = 1/(n−3) = 1/{n - 3} = {1.0 / (n - 3):.4f}"],
        "Fisher 1915; Borenstein et al. 2009, Ch. 6",
    )


# --- Binary (2×2) → log OR / log RR / risk difference --------------------------------------------------------------


def binary(a, b, c, d, measure="or") -> Conversion:
    """2×2 counts (a,b = events/non in group 1; c,d = group 2) → log OR / log RR / RD, each with variance.

    A zero cell triggers the Haldane–Anscombe +0.5 continuity correction (a recorded, cited choice)."""
    vals = [float(a), float(b), float(c), float(d)]
    if any((not math.isfinite(v)) or v < 0 for v in vals):
        raise ValueError("cell counts must be non-negative finite numbers")
    if sum(vals) <= 0:
        raise ValueError("the 2×2 table is empty")
    choices, caveats = [], []
    if 0 in vals:
        vals = [v + 0.5 for v in vals]
        choices.append("Zero cell → Haldane–Anscombe +0.5 continuity correction (Haldane 1940; Anscombe 1956)")
    a, b, c, d = vals
    if (a + b) <= 0 or (c + d) <= 0:
        raise ValueError("each group needs at least one participant")
    if measure == "or":
        if b == 0 or c == 0:
            raise ValueError("odds ratio undefined (a zero in the denominator cross-product)")
        val = math.log((a * d) / (b * c))
        var = 1 / a + 1 / b + 1 / c + 1 / d
        path = [f"log OR = ln(ad/bc) = ln(({a}·{d})/({b}·{c})) = {val:.4f}", f"Var = 1/a+1/b+1/c+1/d = {var:.4f}"]
        return _result(
            "log odds ratio", val, var, path, "Borenstein et al. 2009, Ch. 5", caveats=caveats, choices=choices
        )
    if measure == "rr":
        r1, r2 = a / (a + b), c / (c + d)
        if r1 <= 0 or r2 <= 0:
            raise ValueError("risk ratio undefined (a zero risk)")
        val = math.log(r1 / r2)
        var = 1 / a - 1 / (a + b) + 1 / c - 1 / (c + d)
        path = [f"log RR = ln((a/(a+b))/(c/(c+d))) = {val:.4f}", f"Var = 1/a − 1/(a+b) + 1/c − 1/(c+d) = {var:.5f}"]
        return _result(
            "log risk ratio", val, var, path, "Borenstein et al. 2009, Ch. 5", caveats=caveats, choices=choices
        )
    if measure == "rd":
        r1, r2 = a / (a + b), c / (c + d)
        val = r1 - r2
        var = a * b / (a + b) ** 3 + c * d / (c + d) ** 3
        path = [f"risk difference = a/(a+b) − c/(c+d) = {val:.5f}", f"Var = ab/(a+b)³ + cd/(c+d)³ = {var:.6f}"]
        return _result(
            "risk difference", val, var, path, "Borenstein et al. 2009, Ch. 5", caveats=caveats, choices=choices
        )
    raise ValueError("binary measure must be or / rr / rd")


# --- Cross-metric (APPROXIMATIONS) ---------------------------------------------------------------------------------

_APPROX = "This is an APPROXIMATION with its own assumptions — record it and prefer a direct extraction when possible."


def d_to_r(d, n1, n2) -> Conversion:
    """Cohen's d → point-biserial r (Borenstein 7.x): r = d/√(d²+a), a = (n1+n2)²/(n1·n2)."""
    d = _fnum(d, "d")
    n1, n2 = _int_n(n1, "n1"), _int_n(n2, "n2")
    a = (n1 + n2) ** 2 / (n1 * n2)
    r = d / math.sqrt(d * d + a)
    return _result(
        "correlation r (from d)",
        r,
        0.0,  # cross-metric point estimate; r's variance is design-dependent and not computed here
        [f"a = (n1+n2)²/(n1·n2) = {a:.4f}", f"r = d/√(d²+a) = {r:.4f}"],
        "Borenstein et al. 2009, Ch. 7",
        caveats=[_APPROX],
        choices=["Cross-metric conversion d → r (correction factor a from the group sizes)"],
    )


def r_to_d(r) -> Conversion:
    """Point-biserial r → Cohen's d (Borenstein 7.x): d = 2r/√(1−r²)."""
    r = _fnum(r, "r")
    if not (-1.0 < r < 1.0):
        raise ValueError("r must be in (−1, 1)")
    d = 2 * r / math.sqrt(1 - r * r)
    return _result(
        "Cohen's d (from r)",
        d,
        0.0,
        [f"d = 2r/√(1−r²) = 2·{r}/√(1−{r}²) = {d:.4f}"],
        "Borenstein et al. 2009, Ch. 7",
        caveats=[_APPROX],
        choices=["Cross-metric conversion r → d"],
    )


def logor_to_d(logor, var_logor=None) -> Conversion:
    """log odds ratio → Cohen's d via the logistic-normal factor: d = logOR·√3/π (Hasselblad & Hedges 1995)."""
    logor = _fnum(logor, "log OR")
    factor = math.sqrt(3) / math.pi
    d = logor * factor
    var = _fnum(var_logor, "Var(log OR)") * 3 / (math.pi**2) if var_logor is not None else 0.0
    path = [f"d = log OR · √3/π = {logor:.4f}·{factor:.5f} = {d:.5f}"]
    if var_logor is not None:
        path.append(f"Var(d) = Var(log OR)·3/π² = {var:.6f}")
    return _result(
        "Cohen's d (from log OR)",
        d,
        var,
        path,
        "Hasselblad & Hedges 1995; Borenstein et al. 2009, Ch. 7",
        caveats=[_APPROX + " Assumes an underlying logistic distribution."],
        choices=["Cross-metric conversion log OR → d (logistic-normal √3/π factor)"],
    )


def cross(inputs: dict) -> Conversion:
    kind = inputs.get("kind")
    if kind == "d_to_r":
        return d_to_r(inputs["d"], inputs["n1"], inputs["n2"])
    if kind == "r_to_d":
        return r_to_d(inputs["r"])
    if kind == "logor_to_d":
        return logor_to_d(inputs["logor"], inputs.get("var_logor"))
    raise ValueError("cross-metric kind must be d_to_r / r_to_d / logor_to_d")


# --- Dispatch ------------------------------------------------------------------------------------------------------


def convert(family: str, inputs: dict) -> Conversion:
    """Convert one study's stats. Raises ValueError/KeyError on bad input (the router maps to 422)."""
    if family == "smd":
        method = inputs.get("method", "means")
        if method == "means":
            return smd(inputs["m1"], inputs["s1"], inputs["n1"], inputs["m2"], inputs["s2"], inputs["n2"])
        if method == "t":
            return smd_from_t(inputs["t"], inputs["n1"], inputs["n2"])
        if method == "f":
            return smd_from_f(inputs["f"], inputs["n1"], inputs["n2"])
        raise ValueError("SMD method must be means / t / f")
    if family == "sd_derivation":
        return sd_derivation(inputs)
    if family == "correlation":
        return correlation(inputs["r"], inputs["n"])
    if family == "binary":
        return binary(inputs["a"], inputs["b"], inputs["c"], inputs["d"], inputs.get("measure", "or"))
    if family == "cross":
        return cross(inputs)
    raise ValueError(f"unknown effect-size family: {family!r}")
