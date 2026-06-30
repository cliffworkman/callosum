"""Citation-equity audit — the identity-agnostic, structural shape of a paper's reference list (inc 227).

A *descriptive* Methods producer (the statcheck/p-curve class; PRINCIPLES Example 3 + value A8 access-equity).
It measures the **machinery** that reproduces inequitable citation — self-citation, reliance on already-famous
work (the Matthew effect), venue + institutional concentration, and geographic (Global-South) spread — each shown
against a sample of the focal paper's *field*, with the basis inspectable.

What it is **not** (load-bearing — the canonical spec `…/future-tracks/opus4.8_future-tracks_citationequitytool.md`):
- **No author-identity inference.** There is no gender/race code path here. Name→gender inference is cis-normative,
  systematically wrong for non-Western names (Lockhart, King & Munsch 2023), and would cross the no-accusation veto;
  the structural reframe measures the machinery directly. A gender-balance number is deliberately not produced.
- **Never a pass/fail score, a target, a quota, or an accusation** (PRINCIPLES #2 signal-not-verdict, #7 no opaque
  composite — each signal is a raw shape, never folded into one number). The field comparison is *context*, not a
  verdict; the human reads it and decides (#5).
- **Honest coverage** (#6): every signal reports how many references it could resolve; a reference with no
  affiliation/country data is recorded as *unknown* — never assumed domestic (silence ≠ certificate).

Pure + local + no-LLM + no-I/O (the analyzer takes already-fetched OpenAlex meta dicts). Bounded inputs (rule #4).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

MAX_REFS = 1000  # defensive cap on the analyzed reference list (the fetch already caps at 500; rule #4)
MAX_FIELD = 1000  # defensive cap on the field sample
MAX_BASIS = 10  # how many inspectable basis lines to surface per signal

# "Global North" = a conventional grouping of the high-income, historically citation-dominant reference economies
# (anglosphere + Western/Northern Europe + high-income East Asia + Israel), by ISO-2 country code. The "Global
# South" line counts references with ≥1 author affiliated OUTSIDE this set. The grouping is contestable — so the
# full country breakdown is always shown as the inspectable basis, and the signal is framed as "outside the
# high-income reference economies," never as a verdict about a paper or an author.
GLOBAL_NORTH: frozenset[str] = frozenset(
    {
        # North America + anglosphere
        "US",
        "CA",
        "GB",
        "IE",
        "AU",
        "NZ",
        # Western / Northern Europe (high-income)
        "FR",
        "DE",
        "NL",
        "BE",
        "LU",
        "CH",
        "AT",
        "IT",
        "ES",
        "PT",
        "SE",
        "NO",
        "DK",
        "FI",
        "IS",
        "MC",
        "LI",
        "MT",
        "CY",
        # High-income East Asia + Israel
        "JP",
        "KR",
        "SG",
        "IL",
    }
)


def _family(name: str) -> str:
    """Last whitespace token, lower-cased (the `_family_tokens` convention) — for name-based self-citation."""
    parts = str(name).strip().split()
    return parts[-1].lower() if parts else ""


def _median(values: list[int]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    return float(s[mid]) if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def _percentile(values: list[int], p: float) -> float:
    """The p-th percentile (0..100) by nearest-rank — for the field's "top-decile" cited-by threshold."""
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[k])


def _pct(x: float | None) -> str:
    return f"{round(x * 100)}%" if x is not None else "—"


@dataclass(frozen=True)
class SignalView:
    key: str  # self_citation | matthew | venue | institution | geography
    label: str
    summary: str  # the descriptive headline (never a verdict)
    list_pct: float | None  # 0..1 — the reference list's value, for the bar (None = not computable)
    field_pct: float | None  # 0..1 — the field sample's value (None = no field baseline / N/A)
    basis: list[str]  # inspectable lines (the refs / venues / countries behind the number)
    coverage: str  # how many references this signal could resolve (honest #6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "summary": self.summary,
            "list_pct": self.list_pct,
            "field_pct": self.field_pct,
            "basis": self.basis,
            "coverage": self.coverage,
        }


@dataclass(frozen=True)
class CitationEquityReport:
    references_total: int  # referenced_works ids OpenAlex listed for the paper
    references_resolved: int  # how many we got OpenAlex metadata for
    field_topic: dict[str, Any] | None  # {id, display_name} the field sample is drawn from (None = no comparison)
    field_sample_size: int  # works in the field sample (0 if none)
    signals: list[SignalView]

    def to_dict(self) -> dict[str, Any]:
        return {
            "references_total": self.references_total,
            "references_resolved": self.references_resolved,
            "field_topic": self.field_topic,
            "field_sample_size": self.field_sample_size,
            "signals": [s.to_dict() for s in self.signals],
        }


def _coverage(resolved: int, total: int, *, with_data: int | None = None, datum: str = "") -> str:
    base = f"computed over {resolved} of {total} references with an OpenAlex record"
    if with_data is not None and with_data < resolved:
        base += f"; {with_data} had {datum}"
    return base + "."


def _self_citation(refs: list[dict], families: set[str], total: int) -> SignalView:
    n = len(refs)
    if not families:
        return SignalView(
            "self_citation",
            "Self-citation",
            "No author names are recorded for this paper, so self-citation was not computed.",
            None,
            None,
            [],
            _coverage(n, total),
        )
    matched = [r for r in refs if families & {_family(a) for a in (r.get("authors") or [])}]
    pct = (len(matched) / n) if n else None
    basis = [f"{r.get('title') or 'untitled'}" + (f" ({r['year']})" if r.get("year") else "") for r in matched][
        :MAX_BASIS
    ]
    return SignalView(
        "self_citation",
        "Self-citation",
        f"{len(matched)} of {n} resolved references ({_pct(pct)}) include an author of this paper "
        "(King et al. 2017; based on author-name overlap). A descriptive count — there is no field baseline for "
        "self-citation, and this is not a judgment.",
        pct,
        None,
        basis,
        _coverage(n, total),
    )


def _matthew(refs: list[dict], field: list[dict], total: int, topic_name: str | None) -> SignalView:
    n = len(refs)
    cited = [int(r.get("cited_by_count") or 0) for r in refs]
    top_refs = sorted(refs, key=lambda r: int(r.get("cited_by_count") or 0), reverse=True)
    basis = [
        f"{r.get('title') or 'untitled'} — cited {int(r.get('cited_by_count') or 0):,}×" for r in top_refs[:MAX_BASIS]
    ]
    field_label = topic_name or "the field"
    if field:
        field_cited = [int(w.get("cited_by_count") or 0) for w in field]
        threshold = _percentile(field_cited, 90)
        above = [c for c in cited if c >= threshold]
        list_pct = (len(above) / n) if n else None
        summary = (
            f"{_pct(list_pct)} of your references rank among the most-cited tenth of recent {field_label} work "
            f"(≥{int(threshold):,} citations); in a like-sized field sample, ~10% do. Median citations — your list: "
            f"{int(_median(cited)):,}, field: {int(_median(field_cited)):,}."
        )
        return SignalView(
            "matthew", "Reliance on highly-cited work", summary, list_pct, 0.10, basis, _coverage(n, total)
        )
    summary = (
        f"Median citations of your references: {int(_median(cited)):,}. No field comparison is shown "
        "(OpenAlex has no topic for this paper)."
    )
    return SignalView("matthew", "Reliance on highly-cited work", summary, None, None, basis, _coverage(n, total))


def _top_share(items: list[str], top_k: int) -> tuple[float | None, int, list[str]]:
    """(top-k share of the non-empty items, distinct count, basis lines). Each ref contributes its set."""
    counts = Counter(items)
    n = sum(counts.values())
    if not n:
        return None, 0, []
    top = sum(c for _, c in counts.most_common(top_k))
    basis = [f"{name} — {c}" for name, c in counts.most_common(MAX_BASIS)]
    return top / n, len(counts), basis


def _venue(refs: list[dict], field: list[dict], total: int) -> SignalView:
    n = len(refs)
    venues = [str(r["venue"]) for r in refs if r.get("venue")]
    list_pct, distinct, basis = _top_share(venues, 3)
    field_pct, _, _ = _top_share([str(w["venue"]) for w in field if w.get("venue")], 3)
    if list_pct is None:
        return SignalView(
            "venue",
            "Venue concentration",
            "No venue data was available for these references.",
            None,
            None,
            [],
            _coverage(n, total, with_data=0, datum="venue data"),
        )
    summary = (
        f"Your references span {distinct} venues; the top 3 account for {_pct(list_pct)} "
        f"(field sample: {_pct(field_pct)})."
    )
    return SignalView(
        "venue",
        "Venue concentration",
        summary,
        list_pct,
        field_pct,
        basis,
        _coverage(n, total, with_data=len(venues), datum="venue data"),
    )


def _institution(refs: list[dict], field: list[dict], total: int) -> SignalView:
    n = len(refs)
    inst_items = [inst for r in refs for inst in set(r.get("institutions") or [])]
    refs_with = sum(1 for r in refs if r.get("institutions"))
    list_pct, distinct, basis = _top_share(inst_items, 1)
    field_pct, _, _ = _top_share([inst for w in field for inst in set(w.get("institutions") or [])], 1)
    if list_pct is None:
        return SignalView(
            "institution",
            "Institutional concentration",
            "No affiliation data was available for these references.",
            None,
            None,
            [],
            _coverage(n, total, with_data=0, datum="affiliation data"),
        )
    summary = (
        f"References cite authors from {distinct} institutions; the most common appears on {_pct(list_pct)} of "
        f"references with affiliation data (field sample: {_pct(field_pct)})."
    )
    return SignalView(
        "institution",
        "Institutional concentration",
        summary,
        list_pct,
        field_pct,
        basis,
        _coverage(n, total, with_data=refs_with, datum="affiliation data"),
    )


def _geography(refs: list[dict], field: list[dict], total: int) -> SignalView:
    n = len(refs)
    with_country = [r for r in refs if r.get("country_codes")]
    nc = len(with_country)

    def gs_share(rows: list[dict]) -> float | None:
        rc = [w for w in rows if w.get("country_codes")]
        if not rc:
            return None
        gs = sum(1 for w in rc if any(cc not in GLOBAL_NORTH for cc in w["country_codes"]))
        return gs / len(rc)

    list_pct = gs_share(refs)
    field_pct = gs_share(field)
    country_counts = Counter(cc for r in with_country for cc in r["country_codes"])
    basis = [f"{cc} — {c}" for cc, c in country_counts.most_common(MAX_BASIS)]
    coverage = _coverage(n, total, with_data=nc, datum="no affiliation/country data (shown as unknown, not assumed)")
    if list_pct is None:
        return SignalView(
            "geography",
            "Geographic spread (affiliation outside high-income economies)",
            "No affiliation/country data was available for these references.",
            None,
            None,
            [],
            coverage,
        )
    summary = (
        f"{_pct(list_pct)} of references with affiliation data include an author outside the high-income reference "
        f"economies (field sample: {_pct(field_pct)}). 'Global South' is a conventional grouping — see the country "
        "breakdown."
    )
    return SignalView(
        "geography",
        "Geographic spread (affiliation outside high-income economies)",
        summary,
        list_pct,
        field_pct,
        basis,
        coverage,
    )


def audit_reference_list(
    *,
    refs: list[dict[str, Any]],
    focal_author_families: set[str],
    field: list[dict[str, Any]] | None,
    field_topic: dict[str, Any] | None,
    references_total: int,
) -> CitationEquityReport:
    """Compute the 5 descriptive structural signals over a paper's resolved reference list (`refs` = OpenAlex
    `_meta_from_work` dicts) against an optional `field` sample. Each signal carries its list value, the field
    value, the inspectable basis, and an honest coverage count. **No score, no verdict, no identity inference.**"""
    refs = refs[:MAX_REFS]
    field = (field or [])[:MAX_FIELD]
    topic_name = (field_topic or {}).get("display_name") or None
    signals = [
        _self_citation(refs, focal_author_families, references_total),
        _matthew(refs, field, references_total, topic_name),
        _venue(refs, field, references_total),
        _institution(refs, field, references_total),
        _geography(refs, field, references_total),
    ]
    return CitationEquityReport(
        references_total=references_total,
        references_resolved=len(refs),
        field_topic=field_topic if field else None,
        field_sample_size=len(field),
        signals=signals,
    )
