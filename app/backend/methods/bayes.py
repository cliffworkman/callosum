"""Bayesian auditor SP1 — recompute reported default Bayes factors from a paper's extracted text (inc 241).

The deterministic sibling of statcheck (PRINCIPLES Example 3), for Bayesian t-tests. It scans the running prose for
an inline t-test result reported *with* its Bayes factor (``t(df) = …, BF10 = …``), recomputes the **default JZS**
Bayes factor (Rouder, Speckman, Sun, Morey & Iverson, 2009 — a Cauchy prior on effect size, scale r = √2/2) from the
reported ``t`` + ``df`` via ``scipy.integrate.quad``, and reports where the reported and recomputed values disagree.

It is a **signal, never a verdict** (PRINCIPLES #2) and **never an accusation** (the A-A veto): a mismatch is most
often innocent — the paper may have used a *different prior scale* (which we cannot know from the text), a different
BF definition, or a design we couldn't determine. So the recompute is honest about its assumptions:

- The reported BF was computed under the authors' prior; we recompute under the **default** JZS prior (r = 0.707).
  A mismatch is framed "couldn't reproduce **under the default prior**", never "wrong" (#6 silence-≠-certificate).
- ``t(df)`` alone doesn't reveal whether the test was one-sample/paired (n = df+1) or two-sample (needs the group
  sizes). We recompute under **both** standard interpretations (paired; two-sample assuming equal groups) and mark
  the BF **reproduced if it matches either** — erring toward "reproduced", the non-accusatory direction (like
  statcheck's one-tailed leniency). Only a BF matching *neither* is flagged.

Results carry the **verbatim matched string** + the **recomputed value(s)** + the **assumed prior** + the **page**
(#8/#1/#4). Coverage is stated honestly (#6): this reads only inline ``t(df) = …, BF = …`` — BFs in tables, ANOVA/
correlation BFs, and BFs reported without an adjacent test statistic are invisible, so a clean result is not a clean
bill. There is **no composite score** (#7) — only per-BF results + transparent counts. Fully local, no LLM, no egress.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from scipy.integrate import quad

DEFAULT_R = math.sqrt(2) / 2  # ≈ 0.7071 — the JZS/Cauchy default prior scale (Rouder et al. 2009)
MAX_RESULTS = 500  # bound the work on an untrusted/huge text (rule #4)
# A reproduction tolerance on the log10 scale: BFs are reported to ~2–3 sig figs and are prior-scale-sensitive, so we
# flag only gross discrepancies. 0.3 ≈ a factor of 2 — a reported 3 that recomputes to 30 is a real mismatch; 3 vs 4
# is not. Stated in the panel. (Errs toward "reproduced" — the non-accusatory direction.)
LOG10_TOLERANCE = 0.3

_NUM = r"\d*\.?\d+"
# A reported Bayes factor: BF10 / BF₁₀ / BF01 / BF, "=", then a number with optional scientific notation
# (3.2, 1.4e3, 2.0 × 10^4, 250). Comparator forms (BF10 > 100) are out of v1 scope (not deterministically checkable).
_BF = re.compile(
    r"BF\s*(10|01|₁₀|₀₁)?\s*=\s*(" + _NUM + r")\s*(?:(?:[eE]|×\s*10\s*\^?|x\s*10\s*\^?)\s*([+-]?\d+))?",
)
# A t-test statistic with its df: t(19) = 2.53  (df must be a positive number; the t value may be negative).
_TSTAT = re.compile(r"(?<![A-Za-z])t\s*\(\s*(\d+(?:\.\d+)?)\s*\)\s*=\s*(-?" + _NUM + r")")
_WINDOW = 90  # a BF is associated with a t-stat only if their matched spans are within this many characters


@dataclass(frozen=True)
class BayesResult:
    raw: str  # the verbatim matched region (t-stat + BF)
    reported_bf10: float  # the reported BF, normalized to BF10 (BF01 inverted)
    computed_paired: float | None  # recomputed BF10 assuming a one-sample/paired design (n = df+1)
    computed_two_sample: float | None  # recomputed BF10 assuming a two-sample equal-groups design
    consistency: str  # "reproduced" | "not-reproduced"
    matched_design: str | None  # which interpretation reproduced it ("paired" | "two-sample") — None if neither
    page: int | None


@dataclass
class BayesReport:
    checked: int = 0
    not_reproduced: int = 0
    results: list[BayesResult] = field(default_factory=list)


def jzs_bf10(t: float, n: float, df: float, r: float = DEFAULT_R) -> float | None:
    """The default JZS Bayes factor (BF10) for a t-test (Rouder et al. 2009), via 1-D quadrature over the Cauchy
    prior. `n` is the design's effective n (one-sample/paired: n = df+1; two-sample: n1*n2/(n1+n2)). Returns None on
    a degenerate input. This is the same closed form JASP / the BayesFactor R package use — so it is the honest
    comparison for a paper's reported default BF."""
    if df <= 0 or n <= 0:
        return None
    try:

        def integrand(g: float) -> float:
            a = 1.0 + n * g * r * r
            return (
                a ** (-0.5)
                * (1.0 + t * t / (a * df)) ** (-(df + 1) / 2)
                * (2 * math.pi) ** (-0.5)
                * g ** (-1.5)
                * math.exp(-1.0 / (2 * g))
            )

        marginal_h1, _ = quad(integrand, 0, math.inf)
        marginal_h0 = (1.0 + t * t / df) ** (-(df + 1) / 2)
        if marginal_h0 <= 0 or marginal_h1 <= 0 or not math.isfinite(marginal_h1):
            return None
        return marginal_h1 / marginal_h0
    except (ValueError, ZeroDivisionError, FloatingPointError, OverflowError):
        return None


def _bf_candidates(t: float, df: float) -> tuple[float | None, float | None]:
    """Recompute BF10 under the two standard t-test interpretations of a bare `t(df)`:
    paired/one-sample (n = df+1) and two-sample assuming equal groups (n1 = n2 = (df+2)/2 → n_eff = (df+2)/4)."""
    paired = jzs_bf10(t, n=df + 1, df=df)
    two_sample = jzs_bf10(t, n=(df + 2) / 4.0, df=df)
    return paired, two_sample


def _reproduces(reported: float, computed: float | None) -> bool:
    if computed is None or reported <= 0 or computed <= 0:
        return False
    return abs(math.log10(reported) - math.log10(computed)) <= LOG10_TOLERANCE


def _normalize_bf10(subscript: str | None, value: float) -> float | None:
    """Return the reported BF as BF10. BF01 is inverted; a bare "BF" is assumed BF10 (the dominant convention)."""
    if value <= 0:
        return None
    if subscript in ("01", "₀₁"):
        return 1.0 / value
    return value


def _scan_text(text: str, page: int | None, out: list[BayesResult]) -> None:
    tstats = [(m.start(), m.end(), float(m.group(1)), float(m.group(2))) for m in _TSTAT.finditer(text)]
    if not tstats:
        return
    for bf in _BF.finditer(text):
        if len(out) >= MAX_RESULTS:
            return
        try:
            base = float(bf.group(2))
            reported = base * (10 ** int(bf.group(3))) if bf.group(3) else base
        except (ValueError, OverflowError):
            continue
        reported_bf10 = _normalize_bf10(bf.group(1), reported)
        if reported_bf10 is None:
            continue
        # associate the nearest t-stat whose span is within the window
        bf_start = bf.start()
        near = [ts for ts in tstats if abs(ts[0] - bf_start) <= _WINDOW or abs(ts[1] - bf_start) <= _WINDOW]
        if not near:
            continue
        ts = min(near, key=lambda ts: min(abs(ts[0] - bf_start), abs(ts[1] - bf_start)))
        _, _, df, tval = ts
        if df <= 0:
            continue
        paired, two_sample = _bf_candidates(tval, df)
        if paired is None and two_sample is None:
            continue
        if _reproduces(reported_bf10, paired):
            consistency, design = "reproduced", "paired"
        elif _reproduces(reported_bf10, two_sample):
            consistency, design = "reproduced", "two-sample"
        else:
            consistency, design = "not-reproduced", None
        lo, hi = sorted((min(ts[0], bf.start()), max(ts[1], bf.end())))
        out.append(
            BayesResult(
                raw=re.sub(r"\s+", " ", text[lo:hi]).strip()[:200],
                reported_bf10=round(reported_bf10, 4),
                computed_paired=round(paired, 4) if paired is not None else None,
                computed_two_sample=round(two_sample, 4) if two_sample is not None else None,
                consistency=consistency,
                matched_design=design,
                page=page,
            )
        )


def run_bayes(chunks: list) -> BayesReport:
    """Scan a paper's chunk rows (each carrying `text` + `page_start`) for inline t-test Bayes factors and recompute
    each under the default JZS prior. Per-chunk so every match carries its page; a result split across a chunk
    boundary is missed (a v1 caveat)."""
    results: list[BayesResult] = []
    for chunk in chunks:
        if len(results) >= MAX_RESULTS:
            break
        text = chunk["text"] if isinstance(chunk, dict) or hasattr(chunk, "__getitem__") else getattr(chunk, "text", "")
        if not text:
            continue
        try:
            page = chunk["page_start"]
        except (KeyError, TypeError, IndexError):
            page = getattr(chunk, "page_start", None)
        _scan_text(str(text), page, results)
    report = BayesReport(checked=len(results), results=results)
    report.not_reproduced = sum(1 for r in results if r.consistency == "not-reproduced")
    return report
