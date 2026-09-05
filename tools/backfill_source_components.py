"""Preserve deterministic PDF source structure for existing libraries (inc 578, H1b).

    python tools/backfill_source_components.py [--db-url sqlite:///...] [--paper-id N]
    python tools/backfill_source_components.py [--attachment-id N] [--limit N] [--force]
    python tools/backfill_source_components.py --inspect-page <ATTACHMENT_ID> <PAGE>
    python tools/backfill_source_components.py --summary

New PDF ingests record source components on their own (``pdf_processing/ingest.py``); this tool is
how a library imported *before* inc 578 catches up, and how a failed ingest-time write is repaired.

* **Local PDFs only. No network, no provider, no metadata lookup.** It re-reads the attachment's
  own file from disk and re-runs the same pure extraction ingest uses.
* **Additive and non-destructive.** Raw chunk text, embeddings, sections and every ingest-time
  column are untouched. Only ``source_pages``/``source_components`` are written.
* **Per-attachment commit, so an interrupted run resumes** by simply re-running. Only an attachment
  whose representation is recorded ``complete`` AND current is skipped (inc 579, H1b.1); a
  ``truncated``, ``incomplete``, ``failed``, stale or entirely absent representation is re-derived by
  an ordinary rerun with no extra flag. Ctrl-C mid-attachment rolls back only that attachment, and
  because the completeness record is written last it can never survive a half-written graph.
* **Idempotent.** The write is replace-per-attachment, so a re-run cannot duplicate rows.
* **Live coverage only.** Papers in the Trash (``papers.deleted_at IS NOT NULL``) are outside
  normal coverage by design -- a soft delete keeps chunk rows physically present, but the
  application treats those papers as deleted. ``--include-trashed`` exists purely for debugging one
  such paper and is never the default; a trashed paper without source rows is NOT a coverage gap.
* **Nothing on the retrieval path reads what this writes.**
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Script mode puts only this file's own directory on sys.path, not the project root, so the sibling
# `app` package is invisible without this (the defect inc 508 found in run_https.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.backend.pdf_processing.extraction import EXTRACTION_TOOL, extract_pdf, file_sha256  # noqa: E402
from app.backend.persistence.database import make_engine  # noqa: E402
from app.backend.persistence.schema import attachments, papers  # noqa: E402
from app.backend.persistence.schema_source_components import (  # noqa: E402
    SOURCE_DERIVATION_VERSION,
    paper_figures,
    source_components,
    source_pages,
)
from app.backend.persistence.source_components_repo import (  # noqa: E402
    attachments_with_current_source,
    components_for_page,
    record_source_failure,
    replace_attachment_source,
    source_page_for,
    source_representation_for,
    source_representation_report,
)

DEFAULT_DB_URL = "sqlite:///.local/validation/validation.sqlite"


def _pdf_targets(conn, *, paper_id, attachment_id, include_trashed):
    """Every PDF attachment in live coverage, oldest first. Trashed papers excluded by default."""
    stmt = (
        select(attachments.c.id, attachments.c.paper_id, attachments.c.resolved_path, attachments.c.checksum)
        .select_from(attachments.join(papers, papers.c.id == attachments.c.paper_id))
        .where(attachments.c.content_type == "application/pdf")
        .order_by(attachments.c.id)
    )
    if not include_trashed:
        stmt = stmt.where(papers.c.deleted_at.is_(None))
    if paper_id is not None:
        stmt = stmt.where(attachments.c.paper_id == paper_id)
    if attachment_id is not None:
        stmt = stmt.where(attachments.c.id == attachment_id)
    return [dict(row) for row in conn.execute(stmt).mappings()]


def backfill(engine, *, paper_id=None, attachment_id=None, limit=None, force=False, include_trashed=False):
    stats = {
        "attachments": 0,
        "pages": 0,
        "components": 0,
        "skipped_current": 0,
        "missing_file": 0,
        "checksum_mismatch": 0,
        "no_structure": 0,
        "complete": 0,
        "truncated": 0,
        "incomplete": 0,
        "failed": 0,
        "repaired": 0,
    }
    with engine.begin() as conn:
        targets = _pdf_targets(conn, paper_id=paper_id, attachment_id=attachment_id, include_trashed=include_trashed)
        done = set() if force else attachments_with_current_source(conn, SOURCE_DERIVATION_VERSION)
        # What each non-current attachment is being repaired FROM, captured before anything changes.
        prior = {int(t["id"]): (source_representation_for(conn, int(t["id"])) or {}).get("state") for t in targets}

    for target in targets:
        aid = int(target["id"])
        if aid in done:
            stats["skipped_current"] += 1
            continue
        if limit is not None and stats["attachments"] >= limit:
            break

        path_value = target["resolved_path"]
        path = Path(path_value) if path_value else None
        if path is None or not path.is_file():
            stats["missing_file"] += 1
            continue

        # The stored checksum is what `chunks` and every downstream row were derived from. If the
        # file on disk no longer matches it, the attachment record is out of sync with disk -- an
        # inc-576 PDF-recovery concern, not something this tool should paper over by recording
        # structure from a different document under the old identity.
        actual = file_sha256(path)
        if target["checksum"] and actual != target["checksum"]:
            stats["checksum_mismatch"] += 1
            continue

        try:
            extraction = extract_pdf(path)
        except Exception as error:  # noqa: BLE001 - one bad PDF must not abort the run or vanish
            print(f"  attachment {aid}: extraction failed ({type(error).__name__}); recorded as failed")
            with engine.begin() as conn:
                record_source_failure(
                    conn,
                    attachment_id=aid,
                    source_checksum=actual,
                    extraction_tool=EXTRACTION_TOOL,
                    # The version is only knowable from a successful extraction, and this path is
                    # the one where extraction itself failed. Recorded honestly as unknown rather
                    # than guessed from the installed library, which may not be what ran.
                    extraction_version="unknown",
                    reason=f"extraction_error:{type(error).__name__}",
                )
            stats["failed"] += 1
            continue

        if not extraction.source_pages:
            stats["no_structure"] += 1
            continue

        with engine.begin() as conn:  # per-attachment commit: an interrupted run simply resumes
            receipt = replace_attachment_source(
                conn,
                attachment_id=aid,
                pages=list(extraction.source_pages),
                coordinate_system=extraction.coordinate_system,
                extraction_tool=extraction.extraction_tool,
                extraction_version=extraction.extraction_version,
                source_checksum=actual,
            )
        stats["attachments"] += 1
        stats["pages"] += receipt.written_pages
        stats["components"] += receipt.written_components
        stats[receipt.state] += 1
        if receipt.is_complete and prior.get(aid) in {"truncated", "incomplete", "failed"}:
            stats["repaired"] += 1
        if not receipt.is_complete:
            print(
                f"  attachment {aid}: {receipt.state} ({receipt.state_reason}) -- "
                f"{receipt.written_pages}/{receipt.expected_pages} pages, "
                f"{receipt.skipped_pages} skipped; NOT current, rerun to repair"
            )
    return stats


def inspect_page(engine, attachment_id: int, page_number: int) -> None:
    """The full component graph for one page -- the developer inspection surface (no API, no UI)."""
    with engine.begin() as conn:
        page = source_page_for(conn, attachment_id, page_number)
        if page is None:
            print(f"attachment {attachment_id} page {page_number}: NO SOURCE ROWS (run the backfill)")
            return
        row = (
            conn.execute(
                select(attachments.c.paper_id, attachments.c.resolved_path, attachments.c.checksum).where(
                    attachments.c.id == attachment_id
                )
            )
            .mappings()
            .first()
        )
        print(f"attachment {attachment_id}  paper {row['paper_id'] if row else '?'}")
        print(f"  file            : {Path(row['resolved_path']).name if row and row['resolved_path'] else '(none)'}")
        print(
            f"  checksum stored : {page.source_checksum[:16]}...  live: {(row['checksum'] or '')[:16] if row else ''}..."
        )
        print(f"  page {page.page_number}: {page.width:.1f} x {page.height:.1f} pt, rotation {page.rotation}")
        print(f"  coordinates     : {page.coordinate_system}")
        print(f"  extractor       : {page.extraction_tool} {page.extraction_version}")
        print(f"  derivation      : {page.derivation_version}{'  [STALE]' if page.is_stale else ''}")
        representation = source_representation_for(conn, attachment_id) or {}
        print(
            f"  representation  : {representation.get('state', 'ABSENT')}"
            f"{' (' + representation['state_reason'] + ')' if representation.get('state_reason') else ''}"
            f"  {representation.get('written_pages', '?')}/{representation.get('expected_pages', '?')} pages,"
            f" {representation.get('written_components', '?')} components"
        )

        rows = components_for_page(conn, page.id)
        by_parent: dict[int | None, list[dict]] = {}
        for component in rows:
            by_parent.setdefault(component["parent_id"], []).append(component)

        print(f"  components      : {len(rows)}")
        print("\n  native  sorted  locator path    kind        bbox                                text / style")
        print("  " + "-" * 116)

        def show(component: dict, depth: int) -> None:
            pad = "  " + "   " * depth
            bbox = ""
            if component["x0"] is not None:
                bbox = (
                    f"({component['x0']:7.1f},{component['y0']:7.1f})-({component['x1']:7.1f},{component['y1']:7.1f})"
                )
            native = "" if component["native_order"] is None else str(component["native_order"])
            sorted_o = "" if component["sorted_order"] is None else str(component["sorted_order"])
            if component["geometry_state"] and component["geometry_state"] != "valid":
                bbox += f"  [{component['geometry_state'].upper()}]"
            detail = ""
            if component["text"]:
                detail = repr(component["text"][:46])
            if component["font"]:
                detail += f"  {component['font']} {component['font_size'] or 0:.1f}pt flags={component['flags']}"
            if component["dir_x"] is not None:
                detail += f"  dir=({component['dir_x']:.2f},{component['dir_y']:.2f}) wmode={component['wmode']}"
            path = component["component_path"] or ""
            print(f"  {native:>6}  {sorted_o:>6}  {path:<14}  {pad}{component['kind']:<11} {bbox:<38} {detail}")
            for child in by_parent.get(component["id"], []):
                show(child, depth + 1)

        for top in by_parent.get(None, []):
            show(top, 0)

        figures = (
            conn.execute(
                select(paper_figures).where(
                    paper_figures.c.attachment_id == attachment_id, paper_figures.c.page_number == page_number
                )
            )
            .mappings()
            .all()
        )
        if figures:
            print(f"\n  GROBID figures on this page: {len(figures)}")
            for figure in figures:
                located = (
                    "no coordinates (honest absence)"
                    if figure["x0"] is None
                    else (f"({figure['x0']:.1f},{figure['y0']:.1f})-({figure['x1']:.1f},{figure['y1']:.1f})")
                )
                print(f"    {figure['xml_id']} type={figure['figure_type']} {located}")
                print(f"      head: {(figure['head'] or '')[:80]}")
                if figure["table_grid_json"]:
                    grid = json.loads(figure["table_grid_json"])
                    print(f"      GROBID-supplied grid: {len(grid)} rows, first={grid[0][:4] if grid else None}")


def summarize(engine) -> None:
    """Coverage, with soft-deleted papers accounted for separately rather than reported as missing."""
    with engine.begin() as conn:
        live = conn.execute(
            select(func.count())
            .select_from(attachments.join(papers, papers.c.id == attachments.c.paper_id))
            .where(attachments.c.content_type == "application/pdf", papers.c.deleted_at.is_(None))
        ).scalar_one()
        trashed = conn.execute(
            select(func.count())
            .select_from(attachments.join(papers, papers.c.id == attachments.c.paper_id))
            .where(attachments.c.content_type == "application/pdf", papers.c.deleted_at.is_not(None))
        ).scalar_one()
        report = source_representation_report(conn, SOURCE_DERIVATION_VERSION)
        pages = conn.execute(select(func.count()).select_from(source_pages)).scalar_one()
        counts = dict(
            conn.execute(select(source_components.c.kind, func.count()).group_by(source_components.c.kind)).all()
        )
        geometry = dict(
            conn.execute(
                select(source_components.c.geometry_state, func.count()).group_by(source_components.c.geometry_state)
            ).all()
        )
        figures = conn.execute(select(func.count()).select_from(paper_figures)).scalar_one()

    total = sum(counts.values())
    print(f"derivation version : {SOURCE_DERIVATION_VERSION}")
    print(f"live PDF attachments with a CURRENT source representation : {report['current']} / {live}")
    print(f"soft-deleted (Trash) PDF attachments          : {trashed}  <- outside live coverage BY DESIGN")
    print("representation state over live PDF attachments:")
    for state in ("complete", "truncated", "incomplete", "failed", "absent"):
        note = ""
        if state == "complete" and report[state] != report["current"]:
            note = "  <- some are complete but STALE (checksum/derivation moved)"
        elif state not in ("complete", "absent") and report[state]:
            note = "  <- NOT current; an ordinary rerun repairs these"
        print(f"  {state:<12}{report[state]:>6}{note}")
    print(f"source pages       : {pages}")
    print(f"source components  : {total}")
    for kind, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {kind:<14}{n:>10}{100 * n / total if total else 0:>7.1f}%")
    print("geometry validity  : an explicit judgment; raw coordinates are never rewritten")
    for state, n in sorted(geometry.items(), key=lambda kv: -kv[1]):
        print(f"  {str(state):<14}{n:>10}{100 * n / total if total else 0:>7.1f}%")
    print(f"GROBID figure rows : {figures}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db-url", default=os.environ.get("CALLOSUM_DB_URL", DEFAULT_DB_URL))
    parser.add_argument("--paper-id", type=int)
    parser.add_argument("--attachment-id", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true", help="re-derive even where rows are current")
    parser.add_argument(
        "--include-trashed",
        action="store_true",
        help="debugging only: also process soft-deleted papers, which are outside live coverage by design",
    )
    parser.add_argument("--inspect-page", nargs=2, type=int, metavar=("ATTACHMENT_ID", "PAGE"))
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    engine = make_engine(args.db_url)
    if args.inspect_page:
        inspect_page(engine, args.inspect_page[0], args.inspect_page[1])
        return
    if args.summary:
        summarize(engine)
        return

    stats = backfill(
        engine,
        paper_id=args.paper_id,
        attachment_id=args.attachment_id,
        limit=args.limit,
        force=args.force,
        include_trashed=args.include_trashed,
    )
    print(
        f"recorded {stats['components']} components across {stats['pages']} pages "
        f"of {stats['attachments']} attachments "
        f"({stats['complete']} complete, {stats['truncated']} truncated, "
        f"{stats['incomplete']} incomplete, {stats['failed']} failed, "
        f"{stats['repaired']} repaired from a prior incomplete state)"
    )
    print(
        f"  skipped: {stats['skipped_current']} already current, {stats['missing_file']} file missing, "
        f"{stats['checksum_mismatch']} checksum mismatch, {stats['no_structure']} no structure"
    )


if __name__ == "__main__":
    sys.exit(main())
