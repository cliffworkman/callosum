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

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from integrations.doaj.journals import DoajJournal
from integrations.openalex.sources import SourceMeta
from integrations.scielo.journals import ScieloJournal

MAX_CANDIDATES = 60  # defensive cap on the pool to embed (rule #4)
MAX_PROFILES = 25  # cap on profiles returned

# Legitimacy sources this version does NOT check — shown as neutral fact so silence isn't read as a clean bill (#6).
# The remaining multi-route + regional set (COPE/OASPA, Redalyc/Latindex, self-archiving) has no data source
# yet — deferred, named honestly, never inferred. SciELO, TOP Factor, AJOL, and MEDLINE indexing were wired in
# and removed from this list (backlog #40). Neither Scopus nor a broader "any PubMed presence" check (PubMed
# includes non-MEDLINE-curated content MEDLINE indexing alone doesn't capture) is named here at all — the former
# is proprietary with no free API, the latter was never promised; MEDLINE indexing is the wired, well-defined signal.
LEGITIMACY_DEFERRED = [
    "COPE / OASPA membership",
    "regional indexes (Redalyc, Latindex)",
    "self-archiving policy",
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
    legitimacy_signals: list[str]  # positive signals present (DOAJ inclusion, Seal, SciELO, TOP Factor)
    legitimacy_absent: list[str]  # sources not checked in this version — neutral fact, never a flag
    elevated_for: list[str]  # goods the weighting rewarded (empty when weighting == 0)
    scielo_collections: list[str]  # raw SciELO collection codes this journal appears under; [] = not confirmed
    top_factor: dict[str, Any] | None  # {"total", "categories": [{"name","score","max","justification"}, ...]}
    ajol_status: dict[str, Any] | None  # {"country","jpps_status","is_diamond","source_url"}; shown as-is, plain
    # (jpps_status ranges from positive to cautionary — e.g. "Ceased" — never filtered or softened, per #6)
    indexed_in_medline: bool  # currently MEDLINE-indexed per the NLM Catalog — a coverage fact only, never
    # elevated (an indexing/discoverability fact, not an open-science good; matches SciELO's precedent)
    fit_rank: int  # 1-based rank among the full considered pool, sorted by fit alone — the neutral, pre-weighting
    # order (thumb auditability). A transparent ordinal derivation of the already-shown `fit`, never a new score.
    weighted_rank: int  # 1-based rank in the full blended-sort order — this profile's actual position

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
            "scielo_collections": self.scielo_collections,
            "top_factor": self.top_factor,
            "ajol_status": self.ajol_status,
            "indexed_in_medline": self.indexed_in_medline,
            "fit_rank": self.fit_rank,
            "weighted_rank": self.weighted_rank,
        }


@dataclass(frozen=True)
class PublishersReport:
    profiles: list[JournalProfile]
    considered: int  # distinct candidate journals profiled
    shown: int  # how many returned (= len(profiles))
    weighting: float
    # {count, retrieved_at} of the local TOP Factor mirror — the disambiguator between "this journal has no TOP
    # Factor row" (mirror downloaded, absent) and "the mirror was never downloaded" (every profile's top_factor
    # is None either way). Never affects ranking or the candidate list — a display honesty caption only.
    top_factor_coverage: dict[str, Any] = field(default_factory=lambda: {"count": 0, "retrieved_at": None})
    # Same shape/purpose as top_factor_coverage, for the AJOL mirror. Never affects ranking/listing.
    ajol_coverage: dict[str, Any] = field(default_factory=lambda: {"count": 0, "retrieved_at": None})

    def to_dict(self) -> dict[str, Any]:
        return {
            "profiles": [p.to_dict() for p in self.profiles],
            "considered": self.considered,
            "shown": self.shown,
            "weighting": self.weighting,
            "top_factor_coverage": self.top_factor_coverage,
            "ajol_coverage": self.ajol_coverage,
        }


def derive_oa_color(meta: SourceMeta, doaj: DoajJournal | None) -> str:
    """Coarse, honest OA color from the shown facts (OpenAlex sources have no clean color field): diamond (in DOAJ,
    no APC) / gold (in DOAJ, an APC) / oa-other (open access, not in DOAJ) / closed."""
    if meta.is_in_doaj:
        # diamond = free to publish AND free to read; needs the DOAJ record to confirm no APC (else default gold).
        return "diamond" if (doaj is not None and doaj.apc_amount == 0.0) else "gold"
    return "oa-other" if meta.is_oa else "closed"


def _by_issn(meta: SourceMeta, table: dict[str, Any]) -> Any | None:
    """Try `issn_l` then each alternate ISSN against a per-ISSN lookup table (DOAJ/SciELO/TOP Factor all share
    this shape)."""
    for issn in [meta.issn_l, *meta.issns]:
        if issn and issn in table:
            return table[issn]
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


_AJOL_STAR_TIERS = {"1 Star", "2 Stars", "3 Stars"}  # never Inactive Title/Ceased/Pending/NA/No Stars (elevate,
# don't denigrate — a cautionary or neutral AJOL status must never read as a weighting boost)


def _elevated_goods(oa_color: str, doaj: DoajJournal | None, ajol: dict[str, Any] | None = None) -> list[str]:
    goods: list[str] = []
    if oa_color == "diamond":
        goods.append("diamond OA (free to publish + free to read)")
    elif oa_color == "gold":
        goods.append("gold OA (free to read)")
    elif oa_color == "oa-other":
        goods.append("open access")
    if doaj is not None and doaj.seal:
        goods.append("DOAJ Seal")
    if ajol is not None:
        jpps = ajol.get("jpps_status")
        if jpps in _AJOL_STAR_TIERS:
            goods.append(f"AJOL {jpps} rating")
        if ajol.get("is_diamond") is True:  # a second, independently-sourced diamond-OA claim — kept its own
            goods.append("AJOL-confirmed diamond OA")  # label, never folded into the DOAJ-derived bucket above
    return goods


def build_profiles(
    candidates: list[SourceMeta],
    doaj_by_issn: dict[str, DoajJournal],
    scielo_by_issn: dict[str, ScieloJournal] | None = None,
    top_factor_by_issn: dict[str, dict[str, Any]] | None = None,
    ajol_by_issn: dict[str, dict[str, Any]] | None = None,
    medline_by_issn: dict[str, bool] | None = None,
    *,
    abstract: str,
    embedding_model: Any,
    weighting: float = 0.0,
    top_k: int = MAX_PROFILES,
    top_factor_db_status: dict[str, Any] | None = None,
    ajol_db_status: dict[str, Any] | None = None,
) -> PublishersReport:
    """Assemble a uniform profile per candidate + rank by local fit, moved by `weighting` (0.0 = fit-only).
    Every candidate is returned (top_k by the blended order). No composite score, no predatory label."""
    scielo_by_issn = scielo_by_issn or {}
    top_factor_by_issn = top_factor_by_issn or {}
    ajol_by_issn = ajol_by_issn or {}
    medline_by_issn = medline_by_issn or {}
    coverage = dict(top_factor_db_status) if top_factor_db_status else {"count": 0, "retrieved_at": None}
    ajol_coverage = dict(ajol_db_status) if ajol_db_status else {"count": 0, "retrieved_at": None}
    pool = list(candidates)[:MAX_CANDIDATES]
    weighting = max(0.0, min(1.0, float(weighting)))
    if not pool:
        return PublishersReport(
            profiles=[],
            considered=0,
            shown=0,
            weighting=weighting,
            top_factor_coverage=coverage,
            ajol_coverage=ajol_coverage,
        )

    doaj_for = [_by_issn(m, doaj_by_issn) for m in pool]
    scielo_for = [_by_issn(m, scielo_by_issn) for m in pool]
    top_factor_for = [_by_issn(m, top_factor_by_issn) for m in pool]
    ajol_for = [_by_issn(m, ajol_by_issn) for m in pool]
    medline_for = [_by_issn(m, medline_by_issn) for m in pool]
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

    # The neutral, fit-only order (thumb auditability) — independent of `rows`' blended sort, over the full
    # considered pool so a journal only shown because the weighting elevated it still exposes its true, worse
    # fit-only rank rather than one truncated to the returned top_k slice.
    fit_order = sorted(range(len(pool)), key=lambda i: fits[i], reverse=True)
    fit_rank_by_index = {i: r for r, i in enumerate(fit_order, start=1)}

    profiles: list[JournalProfile] = []
    for weighted_rank, (i, _) in enumerate(rows[:top_k], start=1):
        meta, doaj, color = pool[i], doaj_for[i], colors[i]
        scielo, top_factor, ajol = scielo_for[i], top_factor_for[i], ajol_for[i]
        medline_indexed = bool(medline_for[i])
        signals: list[str] = []
        if meta.is_in_doaj:
            signals.append("Indexed in DOAJ")
        if doaj is not None and doaj.seal:
            signals.append("DOAJ Seal")
        if scielo is not None and scielo.collections:
            signals.append(f"Indexed in SciELO ({', '.join(scielo.collections)})")
        if top_factor is not None:
            signals.append("Has a TOP Factor transparency assessment")
        if ajol is not None:
            signals.append("Indexed in AJOL")  # a coverage fact only -- the jpps_status VALUE stays out of this
            # same-valence list (it ranges positive-to-cautionary); shown instead via ajol_status, always.
        if medline_indexed:
            signals.append("Indexed in MEDLINE")
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
                elevated_for=(_elevated_goods(color, doaj, ajol) if weighting > 0 else []),
                scielo_collections=list(scielo.collections) if scielo is not None else [],
                top_factor=top_factor,
                ajol_status=ajol,
                indexed_in_medline=medline_indexed,
                fit_rank=fit_rank_by_index[i],
                weighted_rank=weighted_rank,
            )
        )
    return PublishersReport(
        profiles=profiles,
        considered=len(pool),
        shown=len(profiles),
        weighting=weighting,
        top_factor_coverage=coverage,
        ajol_coverage=ajol_coverage,
    )
