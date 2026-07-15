"""statcheck — recompute reported NHST p-values from a paper's extracted text (inc 95).

A *deterministic*, local, **no-LLM** Methods producer (PRINCIPLES Example 3; extends value A6). It scans the
running prose for APA-style null-hypothesis-significance-test results, recomputes the p-value from the reported
test statistic + degrees of freedom, and reports where the reported and recomputed values disagree.

It is a **signal, never a verdict** (PRINCIPLES #2) and **never an accusation** (the A-A veto): an inconsistency
is most often innocent (a typo, rounding, a one-tailed test, an adjusted value), and the recomputation accounts
for the test statistic's rounding + tries the one-tailed reading so it does not naively flag correct reporting.
Results carry the **verbatim matched string** + the **page** (PRINCIPLES #8/#1), and coverage is stated honestly
(#6): this reads only inline APA NHST — tables, Bayesian stats, and CIs are invisible, so a clean result is not a
clean bill. There is **no composite score** (#7) — only per-test results and transparent counts.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from scipy.stats import chi2 as chi2_dist
from scipy.stats import f as f_dist
from scipy.stats import norm
from scipy.stats import t as t_dist

ALPHA = 0.05
MAX_RESULTS = 500  # bound the work on an untrusted/huge text (rule #4)

# A number: "2.10", ".04", "45", "-2.1". Test-statistic comparator is required to be "=" (the dominant APA form;
# the rare "t(28) < 2.1" is out of v1 scope). The p comparator may be <, >, =, ≤, ≥.
_NUM = r"-?\d*\.?\d+"
_P = r"([<>=≤≥])\s*(\d*\.?\d+)"
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("t", re.compile(rf"(?<![A-Za-z])t\s*\(\s*(\d+(?:\.\d+)?)\s*\)\s*=\s*({_NUM})\s*,\s*p\s*{_P}")),
    ("F", re.compile(rf"(?<![A-Za-z])F\s*\(\s*(\d+)\s*,\s*(\d+(?:\.\d+)?)\s*\)\s*=\s*({_NUM})\s*,\s*p\s*{_P}")),
    ("r", re.compile(rf"(?<![A-Za-z])r\s*\(\s*(\d+)\s*\)\s*=\s*({_NUM})\s*,\s*p\s*{_P}")),
    (
        "chi2",
        re.compile(rf"(?:χ²|χ2|chi2|X²|X2)\s*\(\s*(\d+)\s*(?:,\s*[Nn]\s*=\s*\d+\s*)?\)\s*=\s*({_NUM})\s*,\s*p\s*{_P}"),
    ),
    ("z", re.compile(rf"(?<![A-Za-z])z\s*=\s*({_NUM})\s*,\s*p\s*{_P}")),
]


@dataclass(frozen=True)
class StatResult:
    raw: str  # the verbatim matched string (so the user sees PDF-conversion artifacts too)
    context: str  # bounded extracted-text context around the match; not an exact PDF-coordinate claim
    test_type: str  # t | F | r | chi2 | z
    reported_p: str  # e.g. "p = .04" / "p < .05"
    computed_p: float  # the recomputed p-value (point estimate)
    consistency: str  # "consistent" | "inconsistent" | "decision-error"
    page: int | None
    page_end: int | None = None
    attachment_id: int | None = None
    chunk_bbox_json: object | None = None
    section: str | None = None


@dataclass
class StatcheckReport:
    checked: int = 0
    inconsistent: int = 0
    decision_errors: int = 0
    results: list[StatResult] = field(default_factory=list)


def _context_snippet(text: str, start: int, end: int, *, max_chars: int = 320) -> str:
    """Bounded context around one regex match, preserving uncertainty from the extracted text.

    This is an inspectable text neighborhood, not a sentence classifier and not an exact PDF-location claim.
    """
    if not text:
        return ""
    if len(text) <= max_chars:
        return re.sub(r"\s+", " ", text).strip()
    left_bounds = [text.rfind(sep, 0, start) for sep in (".", "!", "?", "\n")]
    left = max(left_bounds)
    left = 0 if left < 0 else left + 1
    right_candidates = [idx + 1 for sep in (".", "!", "?", "\n") if (idx := text.find(sep, end)) >= 0]
    right = min(right_candidates) if right_candidates else len(text)
    if right - left > max_chars:
        raw_len = max(1, end - start)
        side = max(40, (max_chars - raw_len) // 2)
        left = max(0, start - side)
        right = min(len(text), end + side)
    snippet = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet += "..."
    return snippet[: max_chars + 6]


def _decimals(num_str: str) -> int:
    return len(num_str.split(".", 1)[1]) if "." in num_str else 0


def _to_float(num_str: str) -> float:
    return float(num_str)


def recompute_p(test_type: str, stat: float, df1: float, df2: float | None) -> float | None:
    """Two-tailed p for t/r/z; one-sided for F/χ². Returns None on a degenerate input."""
    try:
        a = abs(stat)
        if test_type == "t":
            return float(2 * t_dist.sf(a, df1))
        if test_type == "F":
            return float(f_dist.sf(stat, df1, df2))
        if test_type == "r":
            if a >= 1 or df1 <= 0:
                return None
            tval = a * math.sqrt(df1 / (1 - a * a))
            return float(2 * t_dist.sf(tval, df1))
        if test_type == "chi2":
            return float(chi2_dist.sf(stat, df1))
        if test_type == "z":
            return float(2 * norm.sf(a))
    except (ValueError, ZeroDivisionError, FloatingPointError):
        return None
    return None


def _normalize_comparator(comp: str) -> str:
    return {"≤": "<", "≥": ">"}.get(comp, comp)


def _reported_significant(p_comp: str, p_value: float) -> bool | None:
    """Whether the *reported* p clearly claims significance (True), non-significance (False), or is ambiguous."""
    if p_comp == "=":
        return p_value < ALPHA
    if p_comp == "<":
        return True if p_value <= ALPHA else None  # "p < .05" → sig; "p < .10" → ambiguous
    if p_comp == ">":
        return False if p_value >= ALPHA else None  # "p > .05" → non-sig; "p > .001" → ambiguous
    return None


def _p_consistent(p_comp: str, p_value: float, p_decimals: int, p_lo: float, p_hi: float) -> bool:
    """Does the reported p (with its comparator) agree with the computed p-range [p_lo, p_hi]?"""
    if p_comp == "=":
        return round(p_lo, p_decimals) <= p_value <= round(p_hi, p_decimals)
    if p_comp == "<":
        return p_lo < p_value  # the computed p *could* be below the reported threshold
    if p_comp == ">":
        return p_hi > p_value
    return True


def _classify(test_type, stat, stat_dec, p_comp, p_value, p_dec, df1, df2) -> tuple[str, float] | None:
    """Return (consistency, computed_p_point) or None if the stat can't be recomputed."""
    a = abs(stat)
    half = 0.5 * (10**-stat_dec) if stat_dec > 0 else 0.5
    lo, hi = max(0.0, a - half), a + half
    p_point = recompute_p(test_type, a, df1, df2)
    p_at_lo = recompute_p(test_type, lo, df1, df2)  # smaller stat → larger p
    p_at_hi = recompute_p(test_type, hi, df1, df2)  # larger stat → smaller p
    if p_point is None or p_at_lo is None or p_at_hi is None:
        return None
    p_min, p_max = min(p_at_lo, p_at_hi), max(p_at_lo, p_at_hi)
    consistent = _p_consistent(p_comp, p_value, p_dec, p_min, p_max)
    if not consistent and test_type in ("t", "r", "z"):  # try the one-tailed reading before flagging
        consistent = _p_consistent(p_comp, p_value, p_dec, p_min / 2, p_max / 2)
    if consistent:
        return "consistent", p_point
    reported_sig = _reported_significant(p_comp, p_value)
    if reported_sig is not None and reported_sig != (p_point < ALPHA):
        return "decision-error", p_point
    return "inconsistent", p_point


def _scan_text(
    text: str,
    page: int | None,
    out: list[StatResult],
    *,
    page_end: int | None = None,
    attachment_id: int | None = None,
    chunk_bbox_json: object | None = None,
    section: str | None = None,
) -> None:
    for test_type, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if len(out) >= MAX_RESULTS:
                return
            groups = list(m.groups())
            # groups layout: [df1, (df2 for F), stat, p_comp, p_value]
            if test_type == "F":
                df1, df2, stat_s, p_comp, p_value_s = groups
                df2_f: float | None = float(df2)
            elif test_type == "z":
                df1, df2_f = 0.0, None
                stat_s, p_comp, p_value_s = groups
            else:
                df1, stat_s, p_comp, p_value_s = groups
                df2_f = None
            try:
                stat = _to_float(stat_s)
                df1_f = float(df1)
                p_value = _to_float(p_value_s)
            except ValueError:
                continue
            if test_type != "z" and df1_f <= 0:
                continue
            p_comp = _normalize_comparator(p_comp)
            classified = _classify(
                test_type, stat, _decimals(stat_s), p_comp, p_value, _decimals(p_value_s), df1_f, df2_f
            )
            if classified is None:
                continue
            consistency, computed_p = classified
            out.append(
                StatResult(
                    raw=re.sub(r"\s+", " ", m.group(0)).strip(),
                    context=_context_snippet(text, m.start(), m.end()),
                    test_type=test_type,
                    reported_p=f"p {p_comp} {p_value_s}",
                    computed_p=round(computed_p, 4),
                    consistency=consistency,
                    page=page,
                    page_end=page_end,
                    attachment_id=attachment_id,
                    chunk_bbox_json=chunk_bbox_json,
                    section=section,
                )
            )


def run_statcheck(chunks: list) -> StatcheckReport:
    """Scan a paper's chunk rows (each carrying `text` + `page_start`) for APA NHST results and recompute each.
    Per-chunk so every match carries its page; a stat split across a chunk boundary is missed (a v1 caveat)."""
    results: list[StatResult] = []
    for chunk in chunks:
        if len(results) >= MAX_RESULTS:
            break
        text = chunk["text"] if isinstance(chunk, dict) or hasattr(chunk, "__getitem__") else getattr(chunk, "text", "")
        if not text:
            continue
        page = None
        try:
            page = chunk["page_start"]
        except (KeyError, TypeError, IndexError):
            page = getattr(chunk, "page_start", None)
        try:
            page_end = chunk["page_end"]
        except (KeyError, TypeError, IndexError):
            page_end = getattr(chunk, "page_end", None)
        try:
            attachment_id = chunk["attachment_id"]
        except (KeyError, TypeError, IndexError):
            attachment_id = getattr(chunk, "attachment_id", None)
        try:
            chunk_bbox_json = chunk["bbox_json"]
        except (KeyError, TypeError, IndexError):
            chunk_bbox_json = getattr(chunk, "bbox_json", None)
        try:
            section = chunk["section"]
        except (KeyError, TypeError, IndexError):
            section = getattr(chunk, "section", None)
        _scan_text(
            str(text),
            page,
            results,
            page_end=page_end,
            attachment_id=attachment_id,
            chunk_bbox_json=chunk_bbox_json,
            section=section,
        )
    report = StatcheckReport(checked=len(results), results=results)
    report.inconsistent = sum(1 for r in results if r.consistency == "inconsistent")
    report.decision_errors = sum(1 for r in results if r.consistency == "decision-error")
    return report
