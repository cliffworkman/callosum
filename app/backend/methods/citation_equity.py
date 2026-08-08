"""Citation concentration — the structural shape of a paper's reference list (inc 227; reworked inc 229).

A *descriptive* Methods producer (the statcheck/p-curve class). It measures how much a reference list **defers to
concentrated power** — self-citation, reliance on already-famous work (the Matthew effect), and venue + institutional
concentration — each shown against a sample of the focal paper's *field*, with the basis inspectable. The companion
"Find overlooked work" (overlooked_work.py) is the remediation: surface topically-relevant work the list omits.

What it deliberately does **not** do (load-bearing — the inc-229 decision):
- **It never categorizes the people who are cited.** No gender, no race, no nationality, no Global-North/South
  inference — **not deferred, rejected on principle.** Sorting authors into a group to "measure" bias along that
  group re-inscribes the very category the bias runs on: making people *visible by category* (an equity metric) uses
  the same machinery as making them *invisible by category* (the bias). So the tool only ever measures the shape of
  **what** is cited (your own work, famous work, a few venues, a few elite institutions) — never **who** wrote it.
  (The earlier geography "Global South spread" signal was the surviving instance of this error; it was removed.)
- **Never a pass/fail score, a target, a quota, or an accusation** (PRINCIPLES #2 signal-not-verdict, #7 no opaque
  composite — each signal is a raw shape, never folded into one number). The field comparison is *context*, not a
  verdict; the human reads it and decides (#5). Institutional concentration measures deference to a power *structure*
  (elite-affiliation over-emphasis), never the identity of a person.
- **Honest coverage** (#6): every signal reports how many references it could resolve; a signal computed over <50%
  of the references is shown but flagged low-confidence (silence ≠ certificate).

Pure + local + no-LLM + no-I/O (the analyzer takes already-fetched OpenAlex meta dicts). Bounded inputs (rule #4).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

MAX_REFS = 1000  # defensive cap on the analyzed reference list (the fetch already caps at 500; rule #4)
MAX_FIELD = 1000  # defensive cap on the field sample
MAX_BASIS = 10  # how many inspectable basis lines to surface per signal
LOW_COVERAGE = 0.5  # below this effective coverage a signal is flagged low-confidence (honesty #4/#6 — see Coverage)


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
class Coverage:
    """How much of the reference list a signal could actually compute over — the honest #6 datum, carried as both
    the human sentence and a numeric fraction so a thin basis can be *flagged*, not silently shown as comparable."""

    text: str
    fraction: (
        float | None
    )  # effective_resolved / total (the share the number is actually computed over); None if total==0

    @property
    def low(self) -> bool:  # a number computed over <50% of references is shown but flagged low-confidence (#4/#6)
        return self.fraction is not None and self.fraction < LOW_COVERAGE


@dataclass(frozen=True)
class SignalView:
    key: str  # self_citation | matthew | venue | institution
    label: str
    summary: str  # the descriptive headline (never a verdict)
    list_pct: float | None  # 0..1 — the reference list's value, for the bar (None = not computable)
    field_pct: float | None  # 0..1 — the field sample's value (None = no field baseline / N/A)
    basis: list[str]  # inspectable lines (the refs / venues / countries behind the number)
    coverage: Coverage  # how many references this signal could resolve (honest #6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "summary": self.summary,
            "list_pct": self.list_pct,
            "field_pct": self.field_pct,
            "basis": self.basis,
            "coverage": self.coverage.text,
            "coverage_fraction": self.coverage.fraction,
            "low_coverage": self.coverage.low,
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


def _coverage(resolved: int, total: int, *, with_data: int | None = None, datum: str = "") -> Coverage:
    base = f"computed over {resolved} of {total} references with an OpenAlex record"
    if with_data is not None and with_data < resolved:
        base += f"; {with_data} had {datum}"
    effective = with_data if with_data is not None else resolved  # the share the number is *actually* computed over
    fraction = (effective / total) if total else None
    return Coverage(base + ".", fraction)


def _self_citation(
    refs: list[dict],
    families: set[str],
    total: int,
    *,
    field_baseline: float | None = None,
    field_baseline_n: int = 0,
) -> SignalView:
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
    base_summary = (
        f"{len(matched)} of {n} resolved references ({_pct(pct)}) include an author of this paper "
        "(King et al. 2017; based on author-name overlap). A descriptive count — this is not a judgment."
    )
    if field_baseline is not None:
        summary = (
            base_summary
            + f" In a comparable field sample ({field_baseline_n} papers checked, matched by author id), an "
            f"average of {_pct(field_baseline)} of references are self-citations."
        )
    else:
        summary = base_summary + " No field baseline could be computed for this comparison this time."
    return SignalView(
        "self_citation",
        "Self-citation",
        summary,
        pct,
        field_baseline,
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


def audit_reference_list(
    *,
    refs: list[dict[str, Any]],
    focal_author_families: set[str],
    field: list[dict[str, Any]] | None,
    field_topic: dict[str, Any] | None,
    references_total: int,
    self_citation_field_baseline: float | None = None,
    self_citation_field_baseline_n: int = 0,
) -> CitationEquityReport:
    """Compute the 4 descriptive structural signals over a paper's resolved reference list (`refs` = OpenAlex
    `_meta_from_work` dicts) against an optional `field` sample. Each signal carries its list value, the field
    value, the inspectable basis, and an honest coverage count. **No score, no verdict — and crucially, no
    categorization of the people cited (no gender/race/nationality/region): the tool measures what is cited, never
    who wrote it.**

    `self_citation_field_baseline`/`_n` (inc 457) are pre-computed by the caller (a live, count-only per-field-
    paper OpenAlex check — too I/O-heavy to belong in this pure function) and default to `None`/`0`, so an
    existing caller that never computes a field sample at all (e.g. `wip_citation_equity.py`'s own honest
    no-field-comparison path) needs zero changes."""
    refs = refs[:MAX_REFS]
    field = (field or [])[:MAX_FIELD]
    topic_name = (field_topic or {}).get("display_name") or None
    signals = [
        _self_citation(
            refs,
            focal_author_families,
            references_total,
            field_baseline=self_citation_field_baseline,
            field_baseline_n=self_citation_field_baseline_n,
        ),
        _matthew(refs, field, references_total, topic_name),
        _venue(refs, field, references_total),
        _institution(refs, field, references_total),
    ]
    return CitationEquityReport(
        references_total=references_total,
        references_resolved=len(refs),
        field_topic=field_topic if field else None,
        field_sample_size=len(field),
        signals=signals,
    )
