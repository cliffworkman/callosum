"""Empirical calibration study for citation-concentration's self-citation field baseline (backlog #25/#37, inc 456).

`app/backend/methods/citation_equity.py`'s self-citation signal has no field baseline -- computing one for real
requires checking self-citation for every paper in a field sample, and doing that for all 200 papers in the
existing `fetch_field_sample` is real added OpenAlex-request cost. Rather than guess a "small enough" N, this
script gathers a 200-paper pilot per field, then bootstraps the field-average self-citation rate at a grid of
smaller subsample sizes to find where the estimate stabilizes -- the same logic as finding the minimum number of
stimuli/raters needed for stable norms in a stimulus-validation study.

This is a one-off, re-runnable dev-tooling script (the `validation_harness.py` precedent) -- not a shipped
feature. It writes ONLY to `.local/citation-concentration-study/` (gitignored): a scratch SQLite DB (never the
real app DB), one JSONL file of raw per-paper results per field (resumable -- a re-run skips papers already
recorded unless --refresh), and a markdown report. It does not itself declare a single "correct" N -- it shows
the stabilization curve per field so the actual N gets picked by a human looking at the real numbers (Principles
#2 signal-not-verdict, applied to our own tooling decisions too).

Real run (2026-08-07, inc 456), 6 fields x up to 200 raw field-sample papers each: population self-citation
rates varied 3x by field (Cognitive Neuroscience 5.0% .. Genetics 16.0%) -- confirming per-field baselines are
the right call, not a flat constant. "Computable" coverage (papers with both a reference list AND author ids)
also varied hugely by field, 18% (Cognitive Neuroscience, 36/200) to 74% (Genetics/Social Psychology, ~148/200)
-- production code has to treat N as a target COMPUTABLE count, checking as many raw field-sample papers as it
takes (up to the 200 cap) to reach it, not just "the first N papers." At a ~5-percentage-point 95% CI width bar,
the N needed to stabilize ranged ~25 (Cognitive Neuroscience/Public Health) to ~75 (Genetics) -- it does NOT
generalize to one clean number across fields. CHOSEN_N = 40 was picked deliberately favoring Social Psychology's
own crossover point (a real, disclosed judgment call, not a hidden default) -- see report.md for the full table.

Usage (run as a module -- like every other tools/ script here, a bare `python tools/citation_concentration_study.py`
fails with `ModuleNotFoundError: No module named 'app'` because the script's own directory, not the repo root,
lands on sys.path):
    python -m tools.citation_concentration_study
    python -m tools.citation_concentration_study --fields "Cognitive Neuroscience,Genetics" --sample-size 100
    python -m tools.citation_concentration_study --refresh   # re-fetch even if a field's JSONL already exists
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from alembic import command
from alembic.config import Config
from app.backend.app_settings import resolved_mailto
from app.backend.persistence.database import make_engine
from integrations.openalex.adapter import OPENALEX_BASE_URL, OpenAlexClient

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_OUTPUT_DIR = Path(".local/citation-concentration-study")
DEFAULT_FIELDS = [
    "Cognitive Neuroscience",
    "Genetics",
    "Astrophysics",
    "Public Health",
    "Social Psychology",
    "Machine Learning",
]
FIELD_SAMPLE_SIZE = 200
N_GRID = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200]
BOOTSTRAP_REPS = 1000
# The value chosen from the 2026-08-07 real run (see the module docstring + report.md) for the eventual
# production field baseline -- not read by this script itself, kept here as the one place that decision lives.
CHOSEN_N = 40
DEFAULT_PACE_SECONDS = 0.3  # ~3 req/s -- a polite, conservative pace; OpenAlexClient has no built-in throttle
TOPICS_SEARCH_URL = "https://api.openalex.org/topics"


@dataclass(frozen=True)
class PaperRate:
    paper_id: str
    ref_count: int
    hit_count: int
    rate: float


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _paced_fetcher(pace_seconds: float, *, mailto: str | None):
    """A minimal OpenAlexFetcher-shaped callable (mirrors adapter.py's own `_httpx_fetcher`) with a fixed sleep
    before every real HTTP call -- the study's own politeness throttle; the shared OpenAlexClient has none."""

    def fetch(path: str, *, params: dict[str, str], headers: dict[str, str], timeout: float) -> tuple[int, Any]:
        time.sleep(pace_seconds)
        response = httpx.get(OPENALEX_BASE_URL + path, params=params, headers=headers, timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body

    return fetch


def resolve_topic_id(name: str, *, mailto: str | None, pace_seconds: float) -> tuple[str, str] | None:
    """Resolve a human-readable field name -> a real OpenAlex Topic id via a live `/topics?search=` call.
    Returns (bare T... id, the topic's own display_name) or None. No caching here (called once per field per
    run) -- deliberately not added to `adapter.py`, which has no production caller for this lookup."""
    time.sleep(pace_seconds)
    params = {"search": name, "per-page": "1"}
    if mailto:
        params["mailto"] = mailto
    response = httpx.get(TOPICS_SEARCH_URL, params=params, timeout=15.0)
    if response.status_code != 200:
        return None
    results = (response.json() or {}).get("results") or []
    if not results:
        return None
    raw_id = str(results[0].get("id") or "")
    tid = raw_id.rsplit("/", 1)[-1]
    if not re.fullmatch(r"T\d+", tid):
        return None
    return tid, str(results[0].get("display_name") or name)


def gather_field(
    field_name: str,
    *,
    output_dir: Path,
    sample_size: int,
    pace_seconds: float,
    refresh: bool,
) -> list[PaperRate]:
    """Fetch a field's 200-paper sample + each paper's own self-citation rate, persisting to a resumable JSONL
    file. Uses a throwaway scratch SQLite DB under `output_dir` -- never the real app DB's cache table."""
    slug = _slugify(field_name)
    jsonl_path = output_dir / f"{slug}.jsonl"
    existing: dict[str, PaperRate] = {}
    if jsonl_path.exists() and not refresh:
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            existing[row["paper_id"]] = PaperRate(**row)

    mailto = resolved_mailto("CALLOSUM_OPENALEX_MAILTO")
    fetcher = _paced_fetcher(pace_seconds, mailto=mailto)
    client = OpenAlexClient(fetcher=fetcher, mailto=mailto)

    db_path = output_dir / f"{slug}.sqlite"
    db_url = f"sqlite:///{db_path.as_posix()}"
    # Always run upgrade-to-head, unconditionally -- idempotent (a safe no-op on an already-migrated DB, the
    # same self-heal app.py's own lifespan() relies on). A file-existence check is NOT a reliable proxy for
    # "already migrated": SQLite creates the file lazily on first connect even before any table exists, so a
    # prior failed/interrupted run can leave a schema-less file that existence-checking would wrongly skip.
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(config, "head")
    engine = make_engine(db_url)
    results: list[PaperRate] = list(existing.values())
    try:
        with engine.begin() as conn:
            topic = resolve_topic_id(field_name, mailto=mailto, pace_seconds=pace_seconds)
            if topic is None:
                print(f"  [!] could not resolve a topic for {field_name!r} -- skipping", file=sys.stderr)
                return results
            topic_id, resolved_name = topic
            print(f"  resolved {field_name!r} -> {topic_id} ({resolved_name})", file=sys.stderr)

            sample = client.fetch_field_sample(conn, topic_id, size=sample_size)
            print(f"  field sample: {len(sample)} papers", file=sys.stderr)

            with jsonl_path.open("a", encoding="utf-8") as out:
                for i, paper in enumerate(sample):
                    paper_id = str(paper.get("openalex_work_id") or "")
                    if not paper_id or paper_id in existing:
                        continue
                    ref_ids = paper.get("referenced_works") or []
                    author_ids = paper.get("author_ids") or []
                    if not ref_ids or not author_ids:
                        continue  # undefined rate -- not recorded, not fabricated as 0
                    hits = client.fetch_self_citation_hit_count(conn, ref_ids=ref_ids, author_ids=author_ids)
                    if hits is None:
                        continue  # a failed chunk -- honestly skipped, not silently zeroed
                    rate = PaperRate(
                        paper_id=paper_id, ref_count=len(ref_ids), hit_count=hits, rate=hits / len(ref_ids)
                    )
                    results.append(rate)
                    out.write(json.dumps(asdict(rate)) + "\n")
                    out.flush()
                    if (i + 1) % 20 == 0:
                        print(f"  ...{i + 1}/{len(sample)} papers processed", file=sys.stderr)
    finally:
        engine.dispose()
    return results


def bootstrap_curve(rates: list[float], *, n_grid: list[int], reps: int, rng: np.random.Generator) -> dict[int, dict]:
    """For each N in n_grid (<= len(rates)): draw `reps` random subsamples of size N WITHOUT replacement, compute
    each subsample's mean, and report the spread of those means -- the empirical answer to "if production only
    ever checks N field papers, how much would the estimate jitter run to run." Returns {N: {se, ci95_low,
    ci95_high, ci95_width}}."""
    arr = np.asarray(rates, dtype=float)
    out: dict[int, dict] = {}
    for n in n_grid:
        if n > len(arr):
            continue
        means = np.empty(reps)
        for r in range(reps):
            means[r] = rng.choice(arr, size=n, replace=False).mean()
        lo, hi = np.percentile(means, [2.5, 97.5])
        out[n] = {
            "se": float(means.std(ddof=1)),
            "ci95_low": float(lo),
            "ci95_high": float(hi),
            "ci95_width": float(hi - lo),
        }
    return out


def write_report(
    output_dir: Path, field_results: dict[str, tuple[list[PaperRate], dict[int, dict]]], *, sample_size: int
) -> Path:
    lines = [
        "# Citation-concentration self-citation field-baseline calibration study",
        "",
        f"Pilot sample size per field: up to {sample_size}. Bootstrap reps per N: {BOOTSTRAP_REPS}. "
        "Subsamples drawn WITHOUT replacement.",
        "",
        'This report does not declare a single "correct" N -- it shows where each field\'s estimate '
        "stabilizes so N gets picked by a human looking at the real numbers.",
        "",
    ]
    for field_name, (rates, curve) in field_results.items():
        values = [r.rate for r in rates]
        pop_mean = float(np.mean(values)) if values else float("nan")
        lines.append(f"## {field_name}")
        lines.append("")
        lines.append(f"- Papers with a computable rate: {len(values)}")
        lines.append(f"- Population mean self-citation rate (N={len(values)}): {pop_mean:.4f}")
        lines.append("")
        lines.append("| N | SE of the N-sized mean | 95% CI width | 95% CI |")
        lines.append("|---|---|---|---|")
        for n, stats in curve.items():
            lines.append(
                f"| {n} | {stats['se']:.4f} | {stats['ci95_width']:.4f} "
                f"| [{stats['ci95_low']:.4f}, {stats['ci95_high']:.4f}] |"
            )
        lines.append("")
    report_path = output_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fields", type=str, default=",".join(DEFAULT_FIELDS), help="Comma-separated field names")
    parser.add_argument("--sample-size", type=int, default=FIELD_SAMPLE_SIZE)
    parser.add_argument("--reps", type=int, default=BOOTSTRAP_REPS)
    parser.add_argument("--pace-seconds", type=float, default=DEFAULT_PACE_SECONDS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch even if a field's JSONL already exists")
    parser.add_argument("--seed", type=int, default=42, help="Bootstrap RNG seed (reproducible resampling)")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    rng = np.random.default_rng(args.seed)

    field_results: dict[str, tuple[list[PaperRate], dict[int, dict]]] = {}
    for field_name in fields:
        print(f"[{field_name}] gathering...", file=sys.stderr)
        rates = gather_field(
            field_name,
            output_dir=args.output_dir,
            sample_size=args.sample_size,
            pace_seconds=args.pace_seconds,
            refresh=args.refresh,
        )
        if not rates:
            print(f"[{field_name}] no computable rates -- skipping analysis", file=sys.stderr)
            continue
        curve = bootstrap_curve([r.rate for r in rates], n_grid=N_GRID, reps=args.reps, rng=rng)
        field_results[field_name] = (rates, curve)
        print(f"[{field_name}] {len(rates)} papers, done", file=sys.stderr)

    report_path = write_report(args.output_dir, field_results, sample_size=args.sample_size)
    print(f"\nReport written to {report_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
