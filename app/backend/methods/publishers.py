"""PUBLISHERS "where to submit" — uniform journal profiles + local ranking (inc TBD, backlog #40).

Given candidate journals (OpenAlex `SourceMeta` + DOAJ enrichment) and the author's abstract, assemble a
**uniform, fully-sourced factual profile** per journal and rank them by **local** embedding fit — optionally moved
by a user-set **open-science weighting**. Pure + local + no-I/O (takes already-fetched metadata + an embedding
model). Bounded (rule #4).

Load-bearing (the future-track doc's veto-level lines — the Principles + A-A gate output, made structural):
- **No composite score — ever.** `fit` is one labeled similarity; every other fact is shown raw. The weighting
  produces an *ordering*, not a displayed number; the shown rationale is `elevated_for` (the goods a journal offers).
- **No "predatory" label.** There is no such field or string anywhere.
- **Every candidate appears** (top_k by the order; no legitimacy gate on the *listing* — gate the boost, not the
  listing). Closed journals appear with their OpenAlex facts (not an OA-only filter).
- **Elevate, don't denigrate.** `elevated_for` names goods a journal *offers* (diamond OA, DOAJ Seal); absence of a
  legitimacy signal is a neutral `legitimacy_absent` fact, never a flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from integrations.doaj.journals import DoajJournal
from integrations.openalex.sources import SourceMeta

MAX_CANDIDATES = 60  # defensive cap on the pool to embed (rule #4)
MAX_PROFILES = 25  # cap on profiles returned

# Legitimacy sources this version does NOT check — shown as neutral fact so silence isn't read as a clean bill (#6).
# The full multi-route + regional set (COPE/OASPA, PubMed/Scopus indexing, AJOL/SciELO/Redalyc/Latindex,
# self-archiving/TOP) has no data source yet — deferred, named honestly, never inferred.
LEGITIMACY_DEFERRED = [
    "COPE / OASPA membership",
    "PubMed / Scopus indexing",
    "regional indexes (AJOL, SciELO, Redalyc, Latindex)",
    "self-archiving policy / TOP Factor",
]

# OA color → an internal openness ordering weight (used ONLY to re-order; never displayed). +Seal bump below.
_OPENNESS_WEIGHT = {"diamond": 3.0, "gold": 2.0, "oa-other": 1.0, "closed": 0.0}


@dataclass(frozen=True)
class JournalProfile:
    source_id: str
    display_name: str | None
    issns: list[str]
    homepage_url: str | None
    fit: float  # 0..1 — the local embedding cosine (abstract ↔ journal scope), one labeled signal, not a verdict
    oa_color: str  # diamond | gold | oa-other | closed
    is_in_doaj: bool
    apc_amount: float | None
    apc_currency: str | None
    apc_waiver: bool
    license: list[str]
    doaj_seal: bool
    two_year_mean_citedness: float | None
    h_index: int | None
    works_count: int | None
    legitimacy_signals: list[str]  # positive signals present (DOAJ inclusion, Seal)
    legitimacy_absent: list[str]  # sources not checked in this version — neutral fact, never a flag
    elevated_for: list[str]  # goods the weighting rewarded (empty when weighting == 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "display_name": self.display_name,
            "issns": self.issns,
            "homepage_url": self.homepage_url,
            "fit": self.fit,
            "oa_color": self.oa_color,
            "is_in_doaj": self.is_in_doaj,
            "apc_amount": self.apc_amount,
            "apc_currency": self.apc_currency,
            "apc_waiver": self.apc_waiver,
            "license": self.license,
            "doaj_seal": self.doaj_seal,
            "two_year_mean_citedness": self.two_year_mean_citedness,
            "h_index": self.h_index,
            "works_count": self.works_count,
            "legitimacy_signals": self.legitimacy_signals,
            "legitimacy_absent": self.legitimacy_absent,
            "elevated_for": self.elevated_for,
        }


@dataclass(frozen=True)
class PublishersReport:
    profiles: list[JournalProfile]
    considered: int  # distinct candidate journals profiled
    shown: int  # how many returned (= len(profiles))
    weighting: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "considered": self.considered,
            "shown": self.shown,
            "weighting": self.weighting,
        }


def derive_oa_color(meta: SourceMeta, doaj: DoajJournal | None) -> str:
    """Coarse, honest OA color from the shown facts (OpenAlex sources have no clean color field): diamond (in DOAJ,
    no APC) / gold (in DOAJ, an APC) / oa-other (open access, not in DOAJ) / closed."""
    if meta.is_in_doaj:
        # diamond = free to publish AND free to read; needs the DOAJ record to confirm no APC (else default gold).
        return "diamond" if (doaj is not None and doaj.apc_amount == 0.0) else "gold"
    return "oa-other" if meta.is_oa else "closed"


def _doaj_for(meta: SourceMeta, doaj_by_issn: dict[str, DoajJournal]) -> DoajJournal | None:
    for issn in [meta.issn_l, *meta.issns]:
        if issn and issn in doaj_by_issn:
            return doaj_by_issn[issn]
    return None


def _scope_text(meta: SourceMeta, doaj: DoajJournal | None) -> str:
    parts: list[str] = [meta.display_name or ""]
    if doaj is not None:
        parts += doaj.subjects + doaj.keywords
    else:
        parts += meta.concepts
    return " ; ".join(p for p in parts if p).strip()[:2000]


def _unit_rows(vectors: list[list[float]]) -> np.ndarray:
    arr = np.asarray(vectors, dtype=float)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    return arr / (norms + 1e-12)


def _elevated_goods(oa_color: str, doaj: DoajJournal | None) -> list[str]:
    goods: list[str] = []
    if oa_color == "diamond":
        goods.append("diamond OA (free to publish + free to read)")
    elif oa_color == "gold":
        goods.append("gold OA (free to read)")
    elif oa_color == "oa-other":
        goods.append("open access")
    if doaj is not None and doaj.seal:
        goods.append("DOAJ Seal")
    return goods


def build_profiles(
    candidates: list[SourceMeta],
    doaj_by_issn: dict[str, DoajJournal],
    *,
    abstract: str,
    embedding_model: Any,
    weighting: float = 0.0,
    top_k: int = MAX_PROFILES,
) -> PublishersReport:
    """Assemble a uniform profile per candidate + rank by local fit, moved by `weighting` (0.0 = fit-only).
    Every candidate is returned (top_k by the blended order). No composite score, no predatory label."""
    pool = list(candidates)[:MAX_CANDIDATES]
    weighting = max(0.0, min(1.0, float(weighting)))
    if not pool:
        return PublishersReport(profiles=[], considered=0, shown=0, weighting=weighting)

    doaj_for = [_doaj_for(m, doaj_by_issn) for m in pool]
    colors = [derive_oa_color(m, d) for m, d in zip(pool, doaj_for, strict=False)]
    scope_texts = [_scope_text(m, d) for m, d in zip(pool, doaj_for, strict=False)]

    # Local fit: embed the abstract + each journal's scope-text, cosine. The abstract never leaves the machine.
    fits = [0.0] * len(pool)
    if abstract.strip() and any(scope_texts):
        vectors = embedding_model.encode_texts([abstract] + scope_texts)
        units = _unit_rows(vectors)
        focal_u, cand_u = units[0], units[1:]
        sims = cand_u @ focal_u
        fits = [round(float(max(0.0, min(1.0, s))), 3) for s in sims]

    # Internal openness ordering key (never displayed): OA color + a Seal bump, normalized to 0..1.
    max_open = max(_OPENNESS_WEIGHT.values()) + 0.5
    openness = [
        (_OPENNESS_WEIGHT.get(c, 0.0) + (0.5 if (d is not None and d.seal) else 0.0)) / max_open
        for c, d in zip(colors, doaj_for, strict=False)
    ]

    rows: list[tuple[int, float]] = []  # (index, blended sort key)
    for i in range(len(pool)):
        blended = (1.0 - weighting) * fits[i] + weighting * openness[i]
        rows.append((i, blended))
    rows.sort(key=lambda r: (r[1], fits[r[0]]), reverse=True)

    profiles: list[JournalProfile] = []
    for i, _ in rows[:top_k]:
        meta, doaj, color = pool[i], doaj_for[i], colors[i]
        signals: list[str] = []
        if meta.is_in_doaj:
            signals.append("Indexed in DOAJ")
        if doaj is not None and doaj.seal:
            signals.append("DOAJ Seal")
        profiles.append(
            JournalProfile(
                source_id=meta.source_id,
                display_name=meta.display_name,
                issns=meta.issns or ([meta.issn_l] if meta.issn_l else []),
                homepage_url=meta.homepage_url,
                fit=fits[i],
                oa_color=color,
                is_in_doaj=meta.is_in_doaj,
                apc_amount=doaj.apc_amount
                if doaj is not None
                else (float(meta.apc_usd) if meta.apc_usd is not None else None),
                apc_currency=(doaj.apc_currency if doaj is not None else ("USD" if meta.apc_usd else None)),
                apc_waiver=bool(doaj.apc_has_waiver) if doaj is not None else False,
                license=doaj.license if doaj is not None else [],
                doaj_seal=bool(doaj.seal) if doaj is not None else False,
                two_year_mean_citedness=meta.two_year_mean_citedness,
                h_index=meta.h_index,
                works_count=meta.works_count,
                legitimacy_signals=signals,
                legitimacy_absent=list(LEGITIMACY_DEFERRED),
                elevated_for=(_elevated_goods(color, doaj) if weighting > 0 else []),
            )
        )
    return PublishersReport(profiles=profiles, considered=len(pool), shown=len(profiles), weighting=weighting)
