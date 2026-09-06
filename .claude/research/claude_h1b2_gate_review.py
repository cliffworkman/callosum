"""Cross-agent adversarial H1b.2 gate review -- sections 2, 4, 5, 6.

Builds fresh adversarial states against the COMMITTED code at aab95f27. Uses throwaway temp
databases; touches no production data and modifies no production code.
"""

import math
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path("C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum")
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import func, or_, select  # noqa: E402

from app.backend.pdf_processing.source_components import (  # noqa: E402
    GEOMETRY_INVALID,
    GEOMETRY_PAGE_TOLERANCE_PT,
    GEOMETRY_UNKNOWN,
    GEOMETRY_VALID,
    build_page,
    classify_geometry,
)
from app.backend.persistence.database import make_engine  # noqa: E402
from app.backend.persistence.repository import create_attachment, create_paper  # noqa: E402
from app.backend.persistence.schema_source_components import (  # noqa: E402
    source_components,
    source_pages,
    source_representations,
)
from app.backend.persistence.source_components_repo import (  # noqa: E402
    attachments_with_current_source,
    is_source_current,
    replace_attachment_source,
)

PASS, FAIL = "PASS", "**FAIL**"
results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{PASS if ok else FAIL}] {name}{('  -- ' + detail) if detail else ''}")


def fresh_db():
    path = Path(tempfile.mkdtemp()) / "gate.sqlite"
    url = f"sqlite:///{path.as_posix()}"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")
    return make_engine(url), path


def seed(engine, checksum="live-sha"):
    with engine.begin() as conn:
        pid = create_paper(conn, title="gate", csl_json={"title": "gate"})
        aid = create_attachment(
            conn,
            paper_id=pid,
            storage_mode="managed",
            availability="available",
            original_path="/tmp/x.pdf",
            resolved_path="/tmp/x.pdf",
            checksum=checksum,
            file_size=100,
            content_type="application/pdf",
            import_source="gate",
            attachment_type="pdf",
            role="article-fulltext",
        )
    return aid


def block(n, y, text="Participants completed the task."):
    return {
        "type": 0,
        "number": n,
        "bbox": (72.0, y, 400.0, y + 12.0),
        "lines": [
            {
                "spans": [
                    {"text": text, "bbox": (72.0, y, 400.0, y + 12.0), "font": "Times", "size": 10.0, "flags": 0}
                ],
                "bbox": (72.0, y, 400.0, y + 12.0),
                "dir": (1.0, 0.0),
                "wmode": 0,
            }
        ],
    }


def pages(count=3):
    return [
        build_page(
            {"width": 612.0, "height": 792.0, "blocks": [block(i, 100.0 + 20 * i) for i in range(3)]},
            page_number=n + 1,
            width=612.0,
            height=792.0,
        )
        for n in range(count)
    ]


def store(engine, aid, pgs, checksum="live-sha"):
    with engine.begin() as conn:
        return replace_attachment_source(
            conn,
            attachment_id=aid,
            pages=pgs,
            coordinate_system="pdf-points-top-left",
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            source_checksum=checksum,
        )


def current(engine, aid):
    with engine.begin() as conn:
        return aid in attachments_with_current_source(conn), is_source_current(conn, aid)


print("=" * 78)
print("SECTION 2 - adversarial currentness identity coherence (cases A-H)")
print("=" * 78)

# G first: the control must be current, otherwise every other result is meaningless.
engine, _ = fresh_db()
aid = seed(engine)
receipt = store(engine, aid, pages(3))
in_set, scoped = current(engine, aid)
record(
    "G. coherent complete representation is CURRENT",
    in_set and scoped,
    f"state={receipt.state} pages={receipt.written_pages}",
)

CASES = [
    ("A. representation extraction_tool mismatch", "rep", "extraction_tool", "other-extractor"),
    ("B. representation extraction_version mismatch", "rep", "extraction_version", "9.9.9"),
    ("C. page source_checksum mismatch", "page", "source_checksum", "a-different-file"),
    ("D. page derivation_version mismatch", "page", "derivation_version", "source-components-v99"),
    ("E. page extraction_tool mismatch", "page", "extraction_tool", "other-extractor"),
    ("F. page extraction_version mismatch", "page", "extraction_version", "9.9.9"),
]

for label, target, field, value in CASES:
    engine, _ = fresh_db()
    aid = seed(engine)
    store(engine, aid, pages(3))
    pre_in, _ = current(engine, aid)
    with engine.begin() as conn:
        if target == "rep":
            conn.execute(
                source_representations.update()
                .where(source_representations.c.attachment_id == aid)
                .values(**{field: value})
            )
        else:  # mutate exactly ONE page of three -- case H is folded in here
            conn.execute(
                source_pages.update()
                .where(source_pages.c.attachment_id == aid, source_pages.c.page_number == 2)
                .values(**{field: value})
            )
    post_in, post_scoped = current(engine, aid)
    with engine.begin() as conn:
        n_pages = conn.execute(select(func.count()).select_from(source_pages)).scalar_one()
    record(
        label, pre_in and not post_in and not post_scoped, f"before=current after=non-current pages_intact={n_pages}"
    )

print("\nH. one incoherent page in a 5-page graph invalidates the attachment")
engine, _ = fresh_db()
aid = seed(engine)
store(engine, aid, pages(5))
pre_in, _ = current(engine, aid)
with engine.begin() as conn:
    conn.execute(
        source_pages.update()
        .where(source_pages.c.attachment_id == aid, source_pages.c.page_number == 4)
        .values(extraction_version="9.9.9")
    )
post_in, _ = current(engine, aid)
with engine.begin() as conn:
    n = conn.execute(select(func.count()).select_from(source_pages)).scalar_one()
    bad = conn.execute(
        select(func.count())
        .select_from(
            source_pages.join(
                source_representations, source_representations.c.attachment_id == source_pages.c.attachment_id
            )
        )
        .where(or_(source_pages.c.extraction_version != source_representations.c.extraction_version))
    ).scalar_one()
record(
    "H. 1-of-5 incoherent page invalidates the representation", pre_in and not post_in, f"pages={n} incoherent={bad}"
)

print("\nEXTRA. universality: every page position, one at a time")
ok = True
for page_no in (1, 3, 5):
    engine, _ = fresh_db()
    aid = seed(engine)
    store(engine, aid, pages(5))
    with engine.begin() as conn:
        conn.execute(
            source_pages.update()
            .where(source_pages.c.attachment_id == aid, source_pages.c.page_number == page_no)
            .values(source_checksum="drifted")
        )
    still, _ = current(engine, aid)
    ok &= not still
record("EXTRA. first/middle/last page drift each invalidate", ok)

print("\nEXTRA. existing H1b.1 checks are not weakened")
engine, _ = fresh_db()
aid = seed(engine)
store(engine, aid, pages(2))
checks = []
for field, value in (
    ("state", "truncated"),
    ("skipped_pages", 1),
    ("written_components", 999999),
    ("written_pages", 99),
):
    with engine.begin() as conn:
        conn.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(**{field: value})
        )
    still, _ = current(engine, aid)
    checks.append(not still)
    with engine.begin() as conn:  # restore
        conn.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == aid)
            .values(state="complete", skipped_pages=0, written_pages=2, written_components=receipt.written_components)
        )
# restore correct component count for this 2-page graph
with engine.begin() as conn:
    real = conn.execute(
        select(func.count())
        .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
        .where(source_pages.c.attachment_id == aid)
    ).scalar_one()
    conn.execute(
        source_representations.update()
        .where(source_representations.c.attachment_id == aid)
        .values(written_components=real)
    )
restored, _ = current(engine, aid)
record("EXTRA. state/skipped/counts still rejected; healthy state restorable", all(checks) and restored)

print("\n" + "=" * 78)
print("SECTION 4 - NaN / non-finite classification")
print("=" * 78)
nan, inf = float("nan"), float("inf")
geo = [
    ("NaN x0", (nan, 10.0, 100.0, 50.0), GEOMETRY_INVALID),
    ("NaN y0", (10.0, nan, 100.0, 50.0), GEOMETRY_INVALID),
    ("NaN x1", (10.0, 10.0, nan, 50.0), GEOMETRY_INVALID),
    ("NaN y1", (10.0, 10.0, 100.0, nan), GEOMETRY_INVALID),
    ("+infinity", (10.0, 10.0, inf, 50.0), GEOMETRY_INVALID),
    ("-infinity", (-inf, 10.0, 100.0, 50.0), GEOMETRY_INVALID),
    ("all-NaN", (nan, nan, nan, nan), GEOMETRY_INVALID),
]
for label, bbox, want in geo:
    state, reason = classify_geometry(bbox, page_width=612.0, page_height=792.0)
    record(f"4. {label} -> invalid", state == want, f"reason={reason}")

print("\n  guard ordering: partial None must not raise TypeError")
for label, bbox in (
    ("x0 None", (None, 10.0, 100.0, 50.0)),
    ("y1 None", (10.0, 10.0, 100.0, None)),
    ("bbox None", None),
):
    try:
        state, reason = classify_geometry(bbox, page_width=612.0, page_height=792.0)
        record(f"4. {label} -> unknown, no raise", (state, reason) == (GEOMETRY_UNKNOWN, "missing"))
    except Exception as exc:
        record(f"4. {label} -> unknown, no raise", False, f"RAISED {type(exc).__name__}: {exc}")

# the nastiest ordering case: None AND NaN together
try:
    state, reason = classify_geometry((None, nan, 100.0, 50.0), page_width=612.0, page_height=792.0)
    record(
        "4. None+NaN together -> fail-closed, no raise",
        state in (GEOMETRY_UNKNOWN, GEOMETRY_INVALID),
        f"{state}/{reason}",
    )
except Exception as exc:
    record("4. None+NaN together -> fail-closed, no raise", False, f"RAISED {type(exc).__name__}")

print("\n" + "=" * 78)
print("SECTION 5 - NaN persistence seam through real SQLite")
print("=" * 78)
raw = sqlite3.connect(":memory:")
raw.execute("create table t (v real)")
raw.execute("insert into t values (?)", (nan,))
stored_nan = raw.execute("select v, typeof(v) from t").fetchone()
raw.execute("delete from t")
raw.execute("insert into t values (?)", (inf,))
stored_inf = raw.execute("select v, typeof(v) from t").fetchone()
raw.close()
print(f"  SQLite stores NaN as {stored_nan[0]!r} (typeof={stored_nan[1]}), inf as {stored_inf[0]!r}")

engine, dbpath = fresh_db()
aid = seed(engine)
page = build_page(
    {
        "width": 612.0,
        "height": 792.0,
        "blocks": [
            {"type": 1, "number": 0, "bbox": (10.0, nan, 100.0, 50.0), "width": 1, "height": 1, "ext": "png"},
            {"type": 1, "number": 1, "bbox": (nan, nan, nan, nan), "width": 1, "height": 1, "ext": "png"},
            block(2, 100.0),
        ],
    },
    page_number=1,
    width=612.0,
    height=792.0,
)
pre = [(c.kind, c.geometry_state) for c in page.components]
store(engine, aid, [page])
with engine.begin() as conn:
    rows = conn.execute(select(source_components).where(source_components.c.kind == "image")).mappings().all()
    forbidden = conn.execute(
        select(func.count())
        .select_from(source_components)
        .where(
            source_components.c.geometry_state == GEOMETRY_VALID,
            or_(
                source_components.c.x0.is_(None),
                source_components.c.y0.is_(None),
                source_components.c.x1.is_(None),
                source_components.c.y1.is_(None),
            ),
        )
    ).scalar_one()
    valid_ok = conn.execute(
        select(func.count()).select_from(source_components).where(source_components.c.geometry_state == GEOMETRY_VALID)
    ).scalar_one()
for r in rows:
    print(f"    persisted image: x0={r['x0']} y0={r['y0']} x1={r['x1']} y1={r['y1']} state={r['geometry_state']}")
record(
    "5. pre-persistence classification is invalid", all(s == GEOMETRY_INVALID for _, s in pre if _ == "image"), str(pre)
)
record(
    "5. persisted NaN rows are never geometry_state=valid", all(r["geometry_state"] == GEOMETRY_INVALID for r in rows)
)
record("5. FORBIDDEN (NULL coord AND state=valid) count == 0", forbidden == 0, f"count={forbidden}")
record(
    "5. surviving finite coordinates untouched",
    (rows[0]["x0"], rows[0]["x1"], rows[0]["y1"]) == (10.0, 100.0, 50.0) and rows[0]["y0"] is None,
    f"legit valid rows elsewhere={valid_ok}",
)

print("\n" + "=" * 78)
print("SECTION 6 - finite geometry regression")
print("=" * 78)
finite = [
    ("ordinary finite -> valid", (72.0, 100.0, 400.0, 112.0), GEOMETRY_VALID, None),
    ("inverted -> invalid", (100.0, 10.0, 10.0, 50.0), GEOMETRY_INVALID, "inverted"),
    ("out-of-page -> invalid", (10.0, 10.0, 900.0, 50.0), GEOMETRY_INVALID, "out_of_page"),
    ("inside 2.0pt tolerance -> valid", (-1.5, 0.0, 612.0, 792.0), GEOMETRY_VALID, None),
    ("just past tolerance -> invalid", (-2.5, 0.0, 612.0, 792.0), GEOMETRY_INVALID, "out_of_page"),
    ("zero-area -> valid (H1c qualification)", (10.0, 10.0, 10.0, 50.0), GEOMETRY_VALID, None),
]
for label, bbox, want_state, want_reason in finite:
    state, reason = classify_geometry(bbox, page_width=612.0, page_height=792.0)
    record(f"6. {label}", (state, reason) == (want_state, want_reason), f"got {state}/{reason}")
record("6. frozen tolerance unchanged at 2.0pt", GEOMETRY_PAGE_TOLERANCE_PT == 2.0, str(GEOMETRY_PAGE_TOLERANCE_PT))

print("\n" + "=" * 78)
failed = [n for n, ok, _ in results if not ok]
print(f"SUMMARY: {len(results) - len(failed)}/{len(results)} passed")
if failed:
    print("FAILURES:")
    for n in failed:
        print("  -", n)
print("=" * 78)
