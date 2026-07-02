"""Bayesian auditor — recompute reported default Bayes factors from a paper's extracted text (inc 241; SP1 recompute
+ inc 242 completeness checklist + inc 243 Pearson-correlation recompute).

The deterministic sibling of statcheck (PRINCIPLES Example 3), for Bayesian t-tests and Pearson correlations. It scans
the running prose for an inline result reported *with* its Bayes factor (``t(df) = …, BF10 = …`` or ``r(df) = …,
BF10 = …``), recomputes the **default** Bayes factor — the **JZS** t-test BF (Rouder, Speckman, Sun, Morey & Iverson,
2009 — a Cauchy prior on effect size, scale r = √2/2) via ``scipy.integrate.quad``, or the default **correlation** BF
(Ly, Verhagen & Wagenmakers, 2016 — a stretched-beta prior, κ = 1) via the exact ₂F₁ closed form — from the reported
statistic + df, and reports where the reported and recomputed values disagree.

It is a **signal, never a verdict** (PRINCIPLES #2) and **never an accusation** (the A-A veto): a mismatch is most
often innocent — the paper may have used a *different prior scale* (which we cannot know from the text), a different
BF definition, or a design we couldn't determine. So the recompute is honest about its assumptions:

- The reported BF was computed under the authors' prior; we recompute under the **default** JZS prior (r = 0.707).
  A mismatch is framed "couldn't reproduce **under the default prior**", never "wrong" (#6 silence-≠-certificate).
- ``t(df)`` alone doesn't reveal whether the test was one-sample/paired (n = df+1) or two-sample (needs the group
  sizes). We recompute under **both** standard interpretations (paired; two-sample assuming equal groups) and mark
  the BF **reproduced if it matches either** — erring toward "reproduced", the non-accusatory direction (like
  statcheck's one-tailed leniency). Only a BF matching *neither* is flagged. A correlation ``r(df)`` is unambiguous
  (n = df+2), so it has a single recomputed value.

Results carry the **verbatim matched string** + the **recomputed value(s)** + the **assumed prior** + the **page**
(#8/#1/#4). Coverage is stated honestly (#6): this reads only inline ``t(df) = …`` / ``r(df) = …`` reported with an
adjacent BF — BFs in tables, ANOVA/regression BFs (the default BF is not faithfully recoverable from F + df alone —
see inc 243 notes), and BFs with no adjacent statistic are invisible, so a clean result is not a clean bill. There is
**no composite score** (#7) — only per-BF results + transparent counts. Fully local, no LLM, no egress.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from scipy.integrate import quad
from scipy.special import betaln, hyp2f1

DEFAULT_R = math.sqrt(2) / 2  # ≈ 0.7071 — the JZS/Cauchy default prior scale (Rouder et al. 2009)
DEFAULT_KAPPA = 1.0  # the default stretched-beta prior width for the correlation test (JASP/BayesFactor default)
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
# A Pearson correlation with its df (APA `r(df)`, df = n − 2): r(48) = .42  (r ∈ [-1, 1], value may be a leading-dot).
_RSTAT = re.compile(r"(?<![A-Za-z])r\s*\(\s*(\d+)\s*\)\s*=\s*(-?" + _NUM + r")")
_WINDOW = 90  # a BF is associated with a statistic only if their matched spans are within this many characters


@dataclass(frozen=True)
class BayesResult:
    raw: str  # the verbatim matched region (statistic + BF)
    reported_bf10: float  # the reported BF, normalized to BF10 (BF01 inverted)
    computed_paired: float | None  # recomputed BF10 assuming a one-sample/paired t-test (n = df+1)
    computed_two_sample: float | None  # recomputed BF10 assuming a two-sample equal-groups t-test
    computed_correlation: float | None  # recomputed default correlation BF10 (Ly et al. 2016; n = df+2)
    consistency: str  # "reproduced" | "not-reproduced"
    matched_design: (
        str | None
    )  # which interpretation reproduced it ("paired" | "two-sample" | "correlation") — None if neither
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


def corr_bf10(r: float, n: float, kappa: float = DEFAULT_KAPPA) -> float | None:
    """The default (Jeffreys) Bayes factor (BF10) for a Pearson correlation — the exact Ly, Verhagen & Wagenmakers
    (2016) / Wetzels & Wagenmakers (2012, eq. 25) closed form via the Gaussian hypergeometric ₂F₁. `n` is the sample
    size (from an APA `r(df)`, n = df+2); `kappa` is the stretched-beta prior width (JASP/BayesFactor default 1).
    Returns None on a degenerate input. Verified exactly against the pingouin `bayesfactor_pearson` anchor."""
    if not (-1.0 <= r <= 1.0) or n < 3:
        return None
    k = kappa
    try:
        log_pre = ((k - 2) / k) * math.log(2) + 0.5 * math.log(math.pi) - betaln(1 / k, 1 / k)
        log_gamma_ratio = math.lgamma((2 + k * (n - 1)) / (2 * k)) - math.lgamma((2 + n * k) / (2 * k))
        hyp = float(hyp2f1((n - 1) / 2.0, (n - 1) / 2.0, (2 + n * k) / (2 * k), r * r))
        bf = math.exp(log_pre + log_gamma_ratio) * hyp
        return bf if math.isfinite(bf) and bf > 0 else None
    except (ValueError, OverflowError, ZeroDivisionError):
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
    # Collect both t-test and correlation statistics; each BF is checked against whichever is nearest (within the
    # window), and recomputed under the matching design — t-test (paired/two-sample) or correlation (n = df+2).
    stats: list[tuple[int, int, str, float, float]] = [
        (m.start(), m.end(), "t", float(m.group(1)), float(m.group(2))) for m in _TSTAT.finditer(text)
    ] + [(m.start(), m.end(), "r", float(m.group(1)), float(m.group(2))) for m in _RSTAT.finditer(text)]
    if not stats:
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
        # associate the nearest statistic whose span is within the window
        bf_start = bf.start()
        near = [st for st in stats if abs(st[0] - bf_start) <= _WINDOW or abs(st[1] - bf_start) <= _WINDOW]
        if not near:
            continue
        st = min(near, key=lambda s: min(abs(s[0] - bf_start), abs(s[1] - bf_start)))
        _, _, kind, df, val = st
        if df <= 0:
            continue
        paired = two_sample = correlation = None
        if kind == "t":
            paired, two_sample = _bf_candidates(val, df)
            if _reproduces(reported_bf10, paired):
                consistency, design = "reproduced", "paired"
            elif _reproduces(reported_bf10, two_sample):
                consistency, design = "reproduced", "two-sample"
            else:
                consistency, design = "not-reproduced", None
            if paired is None and two_sample is None:
                continue
        else:  # correlation: n = df + 2 (APA r(df)), a single unambiguous recompute
            correlation = corr_bf10(val, n=df + 2)
            if correlation is None:
                continue
            if _reproduces(reported_bf10, correlation):
                consistency, design = "reproduced", "correlation"
            else:
                consistency, design = "not-reproduced", None
        lo, hi = sorted((min(st[0], bf.start()), max(st[1], bf.end())))
        out.append(
            BayesResult(
                raw=re.sub(r"\s+", " ", text[lo:hi]).strip()[:200],
                reported_bf10=round(reported_bf10, 4),
                computed_paired=round(paired, 4) if paired is not None else None,
                computed_two_sample=round(two_sample, 4) if two_sample is not None else None,
                computed_correlation=round(correlation, 4) if correlation is not None else None,
                consistency=consistency,
                matched_design=design,
                page=page,
            )
        )


def _chunk_rows(chunks: list) -> list[tuple[str, int | None]]:
    """Normalize a paper's chunk rows to (text, page). Tolerant of dict rows + ORM rows (the run_statcheck shape)."""
    rows: list[tuple[str, int | None]] = []
    for chunk in chunks:
        text = chunk["text"] if isinstance(chunk, dict) or hasattr(chunk, "__getitem__") else getattr(chunk, "text", "")
        if not text:
            continue
        try:
            page = chunk["page_start"]
        except (KeyError, TypeError, IndexError):
            page = getattr(chunk, "page_start", None)
        rows.append((str(text), page))
    return rows


def run_bayes(chunks: list) -> BayesReport:
    """Scan a paper's chunk rows (each carrying `text` + `page_start`) for inline t-test Bayes factors and recompute
    each under the default JZS prior. Per-chunk so every match carries its page; a result split across a chunk
    boundary is missed (a v1 caveat)."""
    results: list[BayesResult] = []
    for text, page in _chunk_rows(chunks):
        if len(results) >= MAX_RESULTS:
            break
        _scan_text(text, page, results)
    report = BayesReport(checked=len(results), results=results)
    report.not_reproduced = sum(1 for r in results if r.consistency == "not-reproduced")
    return report


# ── SP2 (inc 242): the Tier-2 completeness/coherence checklist (BARG / WAMBS / JASP). Presence/absence of the core
# reporting elements + a coherence flag when a *reported* diagnostic breaches a convention. FLAG-not-ADJUDICATE:
# it runs ONLY on a paper that detectably does Bayesian analysis; "not found" means "not detected in the extracted
# text — check the paper" (tables aren't read), never "missing" / an accusation; thresholds are cited as
# conventions, not laws; convergence is n/a when no MCMC/sampler is reported (a closed-form BF has no chains). ──

# Is this paper doing Bayesian analysis at all? (Gate the whole checklist — else every non-Bayesian paper "fails".)
_BAYESIAN = re.compile(
    r"\bbayesian\b|\bbayes factor|\bBF\s*(?:10|01|₁₀|₀₁)?\s*=|\bposterior (?:distribution|probabilit|mean|median|"
    r"odds|sd|interval|predictive)|\bcredible interval\b|\bMCMC\b|\bmarkov chain\b|\bStan\b|\bbrms\b|\bJAGS\b|"
    r"\bGibbs\b|\bNUTS\b|\bHMC\b",
    re.I,
)
# Does it use MCMC/a sampler? (Convergence diagnostics only apply to sampled posteriors, not closed-form BFs.)
_MCMC = re.compile(
    r"\bMCMC\b|\bmarkov chain\b|\bStan\b|\bbrms\b|\bJAGS\b|\bGibbs\b|\bNUTS\b|\bHMC\b|\bposterior sampl|"
    r"\bwarm-?up\b|\bburn-?in\b|\bsampler\b|\bposterior draws?\b",
    re.I,
)
# 1) Prior stated (family and/or scale). "default prior(s)" alone is present-but-under-specified (the BARG point).
_PRIOR = re.compile(
    r"\bcauchy\b|\bprior scale\b|\brscale\b|\bhalf-cauchy\b|\b(?:informative|weakly[- ]informative|uninformative|"
    r"flat|diffuse|vague|reference|jeffreys) prior|\bprior distribution\b|\bprior on (?:the )?|"
    r"\bwe (?:used|placed|specified|assigned|set|chose|adopted) (?:an? )?[\w-]* ?prior|\bnormal prior\b|"
    r"\bbeta prior\b|\bscale of 0?\.7",
    re.I,
)
_DEFAULT_PRIOR = re.compile(r"\bdefault priors?\b", re.I)
# 2) Convergence diagnostics reported, + numeric coherence (a reported value that breaches the convention).
_CONVERGENCE = re.compile(
    r"\bR[-\s]?hat\b|\bR̂\b|\bRhat\b|\bpotential scale reduction\b|\bgelman[- ]rubin\b|\bPSRF\b|"
    r"\beffective sample size\b|\bESS\b|\bn_?eff\b|\bdivergent transition",
    re.I,
)
_RHAT_VAL = re.compile(r"(?:R[-\s]?hat|R̂|Rhat|PSRF)\s*(?:was|were|of|=|<|>|:)?\s*(\d\.\d+)", re.I)
_ESS_VAL = re.compile(
    r"(?:effective sample size|bulk[- ]?ESS|tail[- ]?ESS|ESS|n_?eff)\s*(?:was|of|=|<|>|:)?\s*(\d{1,6})", re.I
)
_DIVERGENT_VAL = re.compile(r"(\d+)\s+divergent transition", re.I)
# 3) Prior sensitivity / robustness analysis. Prior-scoped phrases only (so "robust standard errors" won't fire).
_SENSITIVITY = re.compile(
    r"\bsensitivity analysis\b|\bprior (?:sensitivity|robustness)\b|\brobustness (?:check|analysis)\b|"
    r"\brobust to (?:the )?prior|\bvary(?:ing)? the prior|\b(?:different|alternative|a range of|multiple) prior "
    r"(?:scales|widths|specifications|settings)\b|\bBayes factor robustness\b|"
    r"\brobustness (?:of|to) (?:the )?(?:results?|conclusions?|inference) (?:to|across) (?:the )?prior",
    re.I,
)


@dataclass(frozen=True)
class CompletenessItem:
    key: str  # prior | convergence | sensitivity
    label: str
    status: str  # present | not-found | not-applicable | coherence-flag
    evidence: str | None  # the matched snippet (so the reader can see + verify)
    page: int | None
    note: str | None


@dataclass(frozen=True)
class BayesCompleteness:
    is_bayesian: bool
    items: list  # list[CompletenessItem]


def _snippet(text: str, start: int, end: int, pad: int = 60) -> str:
    lo, hi = max(0, start - pad), min(len(text), end + pad)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()[:200]


def _first(pattern: re.Pattern, rows: list[tuple[str, int | None]]) -> tuple[str, int | None] | None:
    """First match of `pattern` across the (text, page) rows → (snippet, page), else None."""
    for text, page in rows:
        m = pattern.search(text)
        if m:
            return _snippet(text, m.start(), m.end()), page
    return None


def _has(pattern: re.Pattern, rows: list[tuple[str, int | None]]) -> bool:
    return any(pattern.search(text) for text, _ in rows)


def _convergence_breach(rows: list[tuple[str, int | None]]) -> tuple[str, int | None, str] | None:
    """A reported diagnostic that breaches a convention → (snippet, page, note). Conservative (prefer false
    negatives): R-hat > 1.1 (breaches even the lenient older convention), ESS < 400 (the Vehtari recommendation),
    or > 0 divergent transitions. Cited as conventions, not laws."""
    for text, page in rows:
        for m in _RHAT_VAL.finditer(text):
            try:
                v = float(m.group(1))
            except ValueError:
                continue
            if v > 1.1:
                return (
                    _snippet(text, m.start(), m.end()),
                    page,
                    f"a reported R-hat of {v} exceeds the conventional R-hat < 1.1 (modern practice uses < 1.01)",
                )
        for m in _ESS_VAL.finditer(text):
            try:
                v = int(m.group(1))
            except ValueError:
                continue
            if v < 400:
                return (
                    _snippet(text, m.start(), m.end()),
                    page,
                    f"a reported ESS of {v} is below the conventional > 400",
                )
        for m in _DIVERGENT_VAL.finditer(text):
            try:
                v = int(m.group(1))
            except ValueError:
                continue
            if v > 0:
                return (
                    _snippet(text, m.start(), m.end()),
                    page,
                    f"{v} divergent transitions were reported (> 0 is a convergence warning)",
                )
    return None


def audit_completeness(chunks: list) -> BayesCompleteness:
    """A presence/absence + coherence checklist over a paper's extracted text, keyed to BARG / WAMBS / JASP. Runs
    only if the paper detectably does Bayesian analysis. Each item is present / not-found / not-applicable / a
    coherence-flag; "not found" = "not detected in the text — check the paper", never "missing"."""
    rows = _chunk_rows(chunks)
    if not _has(_BAYESIAN, rows):
        return BayesCompleteness(is_bayesian=False, items=[])

    items: list[CompletenessItem] = []

    # 1) Prior stated
    hit = _first(_PRIOR, rows)
    if hit:
        items.append(CompletenessItem("prior", "Prior stated (family/scale)", "present", hit[0], hit[1], None))
    else:
        dflt = _first(_DEFAULT_PRIOR, rows)
        if dflt:
            items.append(
                CompletenessItem(
                    "prior",
                    "Prior stated (family/scale)",
                    "present",
                    dflt[0],
                    dflt[1],
                    "stated as “default” — a scale/family isn't given (under-specified per BARG)",
                )
            )
        else:
            items.append(CompletenessItem("prior", "Prior stated (family/scale)", "not-found", None, None, None))

    # 2) Convergence diagnostics — only apply to a sampled posterior (MCMC); a closed-form BF has no chains.
    if not _has(_MCMC, rows):
        items.append(
            CompletenessItem(
                "convergence",
                "Convergence diagnostics (R-hat / ESS)",
                "not-applicable",
                None,
                None,
                "no MCMC/sampler reported — closed-form Bayes factors have no chains to diagnose",
            )
        )
    else:
        breach = _convergence_breach(rows)
        if breach:
            items.append(
                CompletenessItem(
                    "convergence",
                    "Convergence diagnostics (R-hat / ESS)",
                    "coherence-flag",
                    breach[0],
                    breach[1],
                    breach[2],
                )
            )
        else:
            hit = _first(_CONVERGENCE, rows)
            items.append(
                CompletenessItem(
                    "convergence",
                    "Convergence diagnostics (R-hat / ESS)",
                    "present" if hit else "not-found",
                    hit[0] if hit else None,
                    hit[1] if hit else None,
                    None,
                )
            )

    # 3) Prior sensitivity / robustness analysis
    hit = _first(_SENSITIVITY, rows)
    items.append(
        CompletenessItem(
            "sensitivity",
            "Prior sensitivity / robustness analysis",
            "present" if hit else "not-found",
            hit[0] if hit else None,
            hit[1] if hit else None,
            None,
        )
    )

    return BayesCompleteness(is_bayesian=True, items=items)
