"""Stat-package export formats for the meta-analysis extraction workspace (workbench SP2b, inc 258).

Pure ``project_view`` -> CSV-text builders, one per target synthesis tool. The load-bearing boundary is unchanged
(SP1/SP2a): each format hands a downstream tool its *native inputs* and NEVER a pooled/synthesized result —

  * generic  : the general dataset (row label + template columns + the converted per-study effect/variance).
  * metafor  : ``escalc``/``rma`` convention — one row per study: yi/vi (+ sei + 95% CI) + the metric + moderator
               columns. A clean numeric table; the researcher runs ``rma(yi, vi, data=...)`` themselves.
  * revman   : RevMan's *raw* study data per outcome type (RevMan computes the effect itself) — continuous
               (mean/SD/N per group) / dichotomous (events/total per group) / correlation via a generic-IV effect
               (Fisher's z + SE, since RevMan has no native correlation outcome).

No builder pools, weights, meta-regresses, or aggregates across rows. A row with no computed effect exports blank
yi/vi (an honest gap, never a fabricated 0). Every emitted cell is neutralised against spreadsheet formula injection
(rule #4) while legitimate numbers — including negatives — pass through unchanged. No DB, no egress: the view is
passed in.
"""

from __future__ import annotations

import csv
import io


def _csv_safe(v) -> str:
    """Neutralise genuine formula-like text (a leading =/+/-/@ that is NOT a plain number) with a ' prefix, while
    passing legitimate numbers — including a negative effect size or mean — through unchanged so R/RevMan parse them."""
    s = "" if v is None else str(v)
    if not s or s[0] not in ("=", "+", "-", "@"):
        return s
    try:
        float(s)  # a plain (possibly negative/signed) number is data, not a formula
        return s
    except ValueError:
        return "'" + s


def _writer() -> tuple[io.StringIO, "csv._writer"]:
    buf = io.StringIO()
    return buf, csv.writer(buf)


def _study(row: dict) -> str:
    """A usable study label: the row's own label, else the linked paper's title, else empty."""
    return row.get("label") or row.get("paper_title") or ""


def _cell(row: dict, key: str):
    return (row["cells"].get(key) or {}).get("value")


def _num(x):
    """Parse a cell value as a float, or None if blank/non-numeric (an honest gap, never a fabricated 0)."""
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def _fmt(x):
    """Render a derived count/total as an int when whole (RevMan totals), else as-is."""
    if x is None:
        return None
    return int(x) if float(x).is_integer() else x


# --- generic (the SP2a-1 format) -----------------------------------------------------------------------------------
def generic_csv(view: dict) -> str:
    keys = [f["key"] for f in view["template"]]
    labels = [f["label"] for f in view["template"]]
    buf, w = _writer()
    w.writerow(["row_label", *labels, "metric", "effect_size", "variance"])
    for row in view["rows"]:
        cells = row["cells"]
        conv = row["converted"] or {}
        w.writerow(
            [
                _csv_safe(row["label"]),
                *[_csv_safe(cells.get(k, {}).get("value")) for k in keys],
                _csv_safe(conv.get("metric")),
                _csv_safe(conv.get("value")),
                _csv_safe(conv.get("variance")),
            ]
        )
    return buf.getvalue()


# --- metafor (escalc/rma: per-study yi/vi + moderators) ------------------------------------------------------------
def metafor_csv(view: dict) -> str:
    # Moderator/notes columns only — the role columns are the raw stats, redundant with yi/vi for metafor.
    mods = [f for f in view["template"] if not f.get("role")]
    buf, w = _writer()
    w.writerow(["study", "yi", "vi", "sei", "ci_lb", "ci_ub", "metric", *[m["label"] for m in mods]])
    for row in view["rows"]:
        conv = row["converted"] or {}
        w.writerow(
            [
                _csv_safe(_study(row)),
                _csv_safe(conv.get("value")),
                _csv_safe(conv.get("variance")),
                _csv_safe(conv.get("se")),
                _csv_safe(conv.get("ci_low")),
                _csv_safe(conv.get("ci_high")),
                _csv_safe(conv.get("metric")),
                *[_csv_safe(_cell(row, m["key"])) for m in mods],
            ]
        )
    return buf.getvalue()


# --- RevMan (raw study data, per outcome type — RevMan computes the effect) ----------------------------------------
def _revman_continuous(view: dict) -> str:
    buf, w = _writer()
    w.writerow(["Study", "Mean 1", "SD 1", "Total 1", "Mean 2", "SD 2", "Total 2"])
    for row in view["rows"]:
        w.writerow([_csv_safe(_study(row)), *[_csv_safe(_cell(row, k)) for k in ("m1", "s1", "n1", "m2", "s2", "n2")]])
    return buf.getvalue()


def _revman_dichotomous(view: dict) -> str:
    # RevMan dichotomous wants events + group *total*; our cells are events (a,c) + non-events (b,d), so total = a+b.
    buf, w = _writer()
    w.writerow(["Study", "Events 1", "Total 1", "Events 2", "Total 2"])
    for row in view["rows"]:
        a, b, c, d = (_num(_cell(row, k)) for k in ("a", "b", "c", "d"))
        t1 = a + b if a is not None and b is not None else None
        t2 = c + d if c is not None and d is not None else None
        w.writerow(
            [
                _csv_safe(_study(row)),
                _csv_safe(_cell(row, "a")),
                _csv_safe(_fmt(t1)),
                _csv_safe(_cell(row, "c")),
                _csv_safe(_fmt(t2)),
            ]
        )
    return buf.getvalue()


def _revman_generic_iv(view: dict) -> str:
    # RevMan has no native correlation outcome → hand the converted Fisher's z + SE to a Generic-IV outcome.
    buf, w = _writer()
    w.writerow(["Study", "Effect", "SE"])
    for row in view["rows"]:
        conv = row["converted"] or {}
        w.writerow([_csv_safe(_study(row)), _csv_safe(conv.get("value")), _csv_safe(conv.get("se"))])
    return buf.getvalue()


_REVMAN = {
    "two_group_continuous": _revman_continuous,
    "binary_2x2": _revman_dichotomous,
    "correlation": _revman_generic_iv,
}


def revman_csv(view: dict) -> str:
    return _REVMAN[view["design"]](view)


FORMATS = {"csv": generic_csv, "metafor": metafor_csv, "revman": revman_csv}
