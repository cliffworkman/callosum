"""G3A (R1) and G3B (R2): is normalized text safe, and does it degrade PDF highlighting?

R1 asks whether a proposed normalized representation stays faithfully relatable to raw source under
the CURRENT quote-matching semantics -- `canonical_text_contains`, which expands both sides into at
most two variants (all line-break hyphens removed, or all kept). Per-occurrence resolution can
produce a string in NEITHER variant, which would flip a citation from verified to unverified.

R2 uses the REAL `locate_quote_for_attachment`. It is never monkeypatched: the whole point is that
a normalization could improve retrieval while silently degrading in-PDF highlighting, and the
existing test suite cannot see that because it patches the locator away.

No default JOIN anywhere. An unresolved occurrence stays a candidate set.
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict

from app.backend.pdf_processing.extraction import (
    _canonical_characters,
    canonical_text_contains,
)
from app.backend.pdf_processing.location import locate_quote_for_attachment
from app.backend.persistence.database import make_engine
from tools.evidence_hygiene.corpus import load_chunks
from tools.evidence_hygiene.store import LIBRARY_DB, study_dir

ARTIFACT = re.compile(r"\b([a-z]{2,})-\s+([a-z]{2,})\b")


def paper_blobs(chunks):
    blob = defaultdict(list)
    for c in chunks:
        blob[c.paper_id].append((c.text or "").lower())
    return {p: " ".join(v) for p, v in blob.items()}


def resolve(paper_blob: str, left: str, right: str) -> str:
    """join | keep | unresolved. Paper-local evidence only; never a default."""
    joined, hyph = f"{left}{right}", f"{left}-{right}"
    j, h = joined in paper_blob, hyph in paper_blob
    if j and not h:
        return "join"
    if h and not j:
        return "keep"
    return "unresolved"


def normalize_chunk(text: str, paper_blob: str) -> tuple[str, Counter]:
    """Character canonicalization + per-occurrence hyphen resolution. Unresolved left untouched."""
    out, counts, pos = [], Counter(), 0
    for m in ARTIFACT.finditer(text or ""):
        out.append(text[pos:m.start()])
        d = resolve(paper_blob, m.group(1).lower(), m.group(2).lower())
        counts[d] += 1
        if d == "join":
            out.append(f"{m.group(1)}{m.group(2)}")
        elif d == "keep":
            out.append(f"{m.group(1)}-{m.group(2)}")
        else:
            out.append(m.group(0))          # unresolved: leave the raw form in place
        pos = m.end()
    out.append(text[pos:])
    return _canonical_characters("".join(out)), counts


def main() -> None:
    chunks = load_chunks()
    blobs = paper_blobs(chunks)

    # ---------------- G3A / R1 ----------------
    print("=" * 76)
    print("G3A (R1): does normalized text stay faithfully relatable to raw?")
    print("=" * 76)
    levels = {"char_only": 0, "char+hyphen": 0}
    fails = {"char_only": [], "char+hyphen": []}
    decisions = Counter()
    touched = 0
    for c in chunks:
        raw = c.text or ""
        if not raw.strip():
            continue
        char_only = _canonical_characters(raw)
        if not canonical_text_contains(needle=char_only, haystack=raw):
            levels["char_only"] += 1
            fails["char_only"].append(c)
        full, counts = normalize_chunk(raw, blobs[c.paper_id])
        decisions.update(counts)
        if counts:
            touched += 1
            if not canonical_text_contains(needle=full, haystack=raw):
                levels["char+hyphen"] += 1
                fails["char+hyphen"].append((c, counts))

    print(f"  chunks examined                     : {len(chunks)}")
    print(f"  chunks with >=1 hyphen artifact     : {touched}")
    print(f"  hyphen decisions                    : {dict(decisions)}")
    print(f"  FAIL, character canonicalization only : {levels['char_only']}")
    print(f"  FAIL, character + per-occurrence hyphen: {levels['char+hyphen']} "
          f"({100 * levels['char+hyphen'] / max(touched, 1):.1f}% of touched chunks)")
    by_mix = Counter()
    for c, counts in fails["char+hyphen"][:2000]:
        mix = "+".join(sorted(k for k in counts if counts[k]))
        by_mix[mix] += 1
    print(f"  failure causes by decision mix      : {dict(by_mix)}")
    for c, counts in fails["char+hyphen"][:3]:
        full, _ = normalize_chunk(c.text, blobs[c.paper_id])
        print(f"    e.g. c{c.chunk_id} {dict(counts)}")
        print(f"       raw : {' '.join((c.text or '').split())[:88]}")
        print(f"       norm: {' '.join(full.split())[:88]}")

    # ---------------- G3B / R2 ----------------
    print()
    print("=" * 76)
    print("G3B (R2): exact-anchor rate through the REAL locate_quote_for_attachment")
    print("=" * 76)
    random.seed(99)
    engine = make_engine(f"sqlite:///{LIBRARY_DB.as_posix()}")
    pool = [c for c in chunks if len((c.text or "").split()) >= 12]
    with_art = [c for c in pool if ARTIFACT.search(c.text or "")]
    sample = random.sample(pool, 150) + random.sample(with_art, min(100, len(with_art)))

    stats = {"raw": Counter(), "normalized": Counter()}
    regressions = []
    with engine.begin() as conn:
        for c in sample:
            raw = " ".join((c.text or "").split())
            quote = " ".join(raw.split()[:22])
            norm_full, counts = normalize_chunk(c.text, blobs[c.paper_id])
            nquote = " ".join(" ".join(norm_full.split()).split()[:22])
            try:
                m_raw = locate_quote_for_attachment(conn, c.attachment_id, quote)
                m_norm = locate_quote_for_attachment(conn, c.attachment_id, nquote)
            except Exception as exc:
                stats["raw"]["error"] += 1
                continue
            k_raw = "exact" if (m_raw.found and m_raw.rectangles) else ("region" if m_raw.found else "miss")
            k_norm = "exact" if (m_norm.found and m_norm.rectangles) else ("region" if m_norm.found else "miss")
            stats["raw"][k_raw] += 1
            stats["normalized"][k_norm] += 1
            if k_raw == "exact" and k_norm != "exact":
                regressions.append((c, k_norm, dict(counts)))

    n = sum(stats["raw"].values())
    print(f"  quotes probed against real PDFs: {n}")
    for surface in ("raw", "normalized"):
        s = stats[surface]
        ex = s.get("exact", 0)
        print(f"  {surface:<11} exact {ex:>4} ({100 * ex / max(n, 1):>5.1f}%)  "
              f"region {s.get('region', 0):>4}  miss {s.get('miss', 0):>4}")
    print(f"  exact -> non-exact REGRESSIONS: {len(regressions)}")
    for c, k, counts in regressions[:5]:
        print(f"    c{c.chunk_id} p{c.paper_id} -> {k}  decisions={counts}")
        print(f"       {' '.join((c.text or '').split())[:86]}")

    (study_dir() / "safety_r1_r2.json").write_text(json.dumps({
        "r1": {"touched": touched, "decisions": dict(decisions),
               "fail_char_only": levels["char_only"], "fail_char_hyphen": levels["char+hyphen"],
               "failure_mix": dict(by_mix)},
        "r2": {"n": n, "raw": dict(stats["raw"]), "normalized": dict(stats["normalized"]),
               "regressions": len(regressions)},
    }, indent=1), encoding="utf-8")
    print("\nwrote safety_r1_r2.json")


if __name__ == "__main__":
    main()
