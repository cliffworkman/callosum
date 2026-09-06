"""Gate review sections 7, 8, 11 -- live corpus coherence, geometry, and currentness timing."""

import sqlite3
import statistics
import sys
import time
from pathlib import Path

ROOT = Path("C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum")
sys.path.insert(0, str(ROOT))
DB = ROOT / ".local/h1b1-validation/validation.sqlite"

from sqlalchemy import func, select  # noqa: E402

from app.backend.pdf_processing.source_components import (  # noqa: E402
    GEOMETRY_PAGE_TOLERANCE_PT,
    classify_geometry,
)
from app.backend.persistence.database import make_engine  # noqa: E402
from app.backend.persistence.schema_source_components import source_components  # noqa: E402
from app.backend.persistence.source_components_repo import attachments_with_current_source  # noqa: E402

c = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
q = lambda sql: c.execute(sql).fetchall()  # noqa: E731

print("=" * 78)
print("SECTION 7 - live corpus identity coherence")
print("=" * 78)
engine = make_engine("sqlite:///.local/h1b1-validation/validation.sqlite")
with engine.begin() as conn:
    current = attachments_with_current_source(conn)
live_ids = {
    r[0]
    for r in q("""SELECT a.id FROM attachments a JOIN papers p ON p.id=a.paper_id
                               WHERE a.content_type='application/pdf' AND p.deleted_at IS NULL""")
}
trashed = q("""SELECT COUNT(*) FROM attachments a JOIN papers p ON p.id=a.paper_id
               WHERE a.content_type='application/pdf' AND p.deleted_at IS NOT NULL""")[0][0]
print(f"  live PDF attachments             : {len(live_ids)}")
print(f"  CURRENT under the H1b.2 rule     : {len(live_ids & current)}")
print(f"  falsely non-current              : {len(live_ids - current)}   (must be 0)")
print(f"  trashed PDFs (outside coverage)  : {trashed}")
print(f"  trashed with a representation    : {len(current - live_ids)}")

pages_total = q("SELECT COUNT(*) FROM source_pages")[0][0]
incoherent = q("""
  SELECT COUNT(*) FROM source_pages p JOIN source_representations r ON r.attachment_id=p.attachment_id
  WHERE p.source_checksum <> r.source_checksum OR p.extraction_tool <> r.extraction_tool
     OR p.extraction_version <> r.extraction_version OR p.derivation_version <> r.derivation_version""")[0][0]
orphan = q("""SELECT COUNT(*) FROM source_pages p
              LEFT JOIN source_representations r ON r.attachment_id=p.attachment_id WHERE r.id IS NULL""")[0][0]
print(f"  pages compared to their envelope : {pages_total}")
print(f"  pages DISAGREEING                : {incoherent}   (must be 0)")
print(f"  pages with no envelope           : {orphan}")
print(
    f"  distinct (tool,version,derivation) across all pages: "
    f"{q('SELECT COUNT(*) FROM (SELECT DISTINCT extraction_tool, extraction_version, derivation_version FROM source_pages)')[0][0]}"
)

print("\n" + "=" * 78)
print("SECTION 8 - live corpus geometry")
print("=" * 78)
total = q("SELECT COUNT(*) FROM source_components")[0][0]
print(f"  components represented           : {total}")
print(f"  frozen tolerance                 : {GEOMETRY_PAGE_TOLERANCE_PT}pt")
for state, n in q("SELECT geometry_state, COUNT(*) FROM source_components GROUP BY 1 ORDER BY 2 DESC"):
    print(f"  stored {str(state):<12}{n:>10}  {100 * n / total:7.3f}%")
forbidden = q("""SELECT COUNT(*) FROM source_components WHERE geometry_state='valid'
                 AND (x0 IS NULL OR y0 IS NULL OR x1 IS NULL OR y1 IS NULL)""")[0][0]
print(f"  FORBIDDEN (NULL coord + valid)   : {forbidden}   (must be 0)")

# recompute every row with the COMMITTED H1b.2 classifier
mismatch, recomputed, non_finite = 0, {}, 0
for x0, y0, x1, y1, stored, w, h in c.execute("""
        SELECT cc.x0, cc.y0, cc.x1, cc.y1, cc.geometry_state, p.width, p.height
        FROM source_components cc JOIN source_pages p ON p.id=cc.source_page_id"""):
    bbox = None if (x0 is None and y0 is None and x1 is None and y1 is None) else (x0, y0, x1, y1)
    state, reason = classify_geometry(bbox, page_width=w, page_height=h)
    recomputed[state] = recomputed.get(state, 0) + 1
    non_finite += reason == "non_finite"
    mismatch += state != stored
print(f"  recomputed with H1b.2 classifier : {recomputed}")
print(f"  disagreements with stored state  : {mismatch}   (must be 0)")
print(f"  non-finite stored geometry       : {non_finite}   (must be 0)")
inv = q("SELECT COUNT(*) FROM source_components WHERE geometry_state='invalid' AND (x1<x0 OR y1<y0)")[0][0]
oop = q("""SELECT COUNT(*) FROM source_components cc JOIN source_pages p ON p.id=cc.source_page_id
           WHERE cc.geometry_state='invalid' AND NOT (cc.x1<cc.x0 OR cc.y1<cc.y0)""")[0][0]
zero = q("SELECT COUNT(*) FROM source_components WHERE x0 IS NOT NULL AND (x1=x0 OR y1=y0)")[0][0]
zero_img = q("""SELECT COUNT(*) FROM source_components WHERE kind='image'
                AND x0 IS NOT NULL AND (x1=x0 OR y1=y0)""")[0][0]
print(f"  inverted {inv}  (expect 363)")
print(f"  out-of-page beyond 2.0pt {oop}  (expect 1113)")
print(f"  zero-area {zero} (of which image: {zero_img})  -- H1c qualification, not a defect")
c.close()

print("\n" + "=" * 78)
print("SECTION 11 - currentness timing with the coherence clause")
print("=" * 78)
with engine.begin() as conn:
    attachments_with_current_source(conn)  # warm-up, as the frozen audit did
    samples = []
    for _ in range(10):
        t = time.perf_counter()
        ids = attachments_with_current_source(conn)
        samples.append((time.perf_counter() - t) * 1000)
    components = conn.execute(select(func.count()).select_from(source_components)).scalar_one()
print(f"  attachments {len(ids)}   pages {pages_total}   components {components}")
print(f"  min {min(samples):.2f} ms   median {statistics.median(samples):.2f} ms   max {max(samples):.2f} ms")
print("  frozen H1b.1 audit baseline : min 162.66 / median 169.72 / max 192.42 ms")
print("  implementer reported H1b.2  : min 163.30 / median 177.37 / max 272.67 ms")
