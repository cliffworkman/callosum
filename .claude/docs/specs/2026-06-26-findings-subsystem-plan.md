# Findings subsystem (inc 130) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The shared per-paper findings store + the FACT-vs-CANDIDATE contract + a typed review workflow + the
library "N to review" badge, exercised by a seeded fake finding (no real producers).

**Architecture:** A `paper_findings` table (migration 0016) + `persistence/findings_repo.py` (the idempotent,
review-state-preserving contract producers call) + `routers/findings.py` (3 endpoints) + a `08_methods_findings.jsx`
METHODS "Review" section + a per-paper-card badge threaded from a `/findings/overview` fetch.

**Tech Stack:** Python (SQLAlchemy Core, Alembic, hashlib/json), FastAPI, React JSX (esbuild), pytest.

## Global Constraints
- Per `2026-06-26-findings-subsystem-design.md`. **Foundation only** — no real producers; the fake is just
  `upsert_findings(...)` called by tests + the headed driver.
- **FACT vs CANDIDATE:** facts → `review_state` NULL, **not resolvable**; candidates → reviewable. Badges =
  **WORK STATE** ("N to review" = unreviewed candidates), **never paper quality**; **zero unreviewed shows NO
  badge**. State lives in the table, not localStorage.
- **`upsert_findings` is idempotent + review-state-preserving** (non-negotiable): a re-run must not reset reviews
  on unchanged findings. `content_key = sha256(source + canonical_json(payload))`.
- statcheck's existing `open_science_signals` + chip are **untouched** (separate subsystem). Local, no egress, no
  LLM. New endpoints → audit gate; new surface → QA route (rule #10) + route-surface test.
- Read `.claude/DESIGN.md` before CSS (tokens only; FactMark and the review badge distinct, not color-only).
  Migration head 0015 → **0016** (head derived by tests, inc 99). This is **increment 130**. Commit per task.

---

### Task 1: schema + migration + `findings_repo.py` (the contract)

**Files:** Create `alembic/versions/0016_paper_findings.py`, `app/backend/persistence/findings_repo.py`,
`tests/test_findings.py`; Modify `app/backend/persistence/schema.py`.

**Interfaces — Produces:** `upsert_findings(conn, paper_id, source, findings)`,
`get_paper_findings(conn, paper_id) -> {facts, candidates}`, `findings_overview(conn) -> list[dict]`,
`set_review_state(conn, finding_id, state, reason=None) -> str`, `get_finding_dict(conn, finding_id) -> dict|None`.

- [ ] **Step 1: Add the table to `schema.py`** — after the `open_science_signals` table:

```python
paper_findings = Table(
    "paper_findings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("source", String(100), nullable=False),  # the producing check
    Column("kind", String(20), nullable=False),  # 'fact' | 'candidate'
    Column("tier", String(20)),  # 'primary' | 'speculative' | NULL
    Column("payload", JSON, nullable=False),
    Column("content_key", String(64), nullable=False),  # sha256(source + canonical payload) — idempotency
    Column("review_state", String(20)),  # 'unreviewed'|'confirmed'|'accepted'|'noted' | NULL (facts)
    Column("review_reason", Text),
    Column("reviewed_at", DateTime),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    UniqueConstraint("paper_id", "source", "content_key", name="uq_paper_findings_paper_source_key"),
    Index("ix_paper_findings_paper_id", "paper_id"),
)
```

(`Table`, `Column`, `Integer`, `String`, `Text`, `JSON`, `DateTime`, `ForeignKey`, `UniqueConstraint`, `Index`,
`func` are all already imported in `schema.py`.)

- [ ] **Step 2: Create the migration** `alembic/versions/0016_paper_findings.py`:

```python
"""Findings subsystem (inc 130): the ``paper_findings`` table — the shared FACT-vs-CANDIDATE store every METHODS
check emits into.

Additive + idempotent (like 0002-0015): a fresh DB already has the table from 0001's ``metadata.create_all``, so
the create is guarded and skipped there; an existing DB gets it here.

Revision ID: 0016_paper_findings
Revises: 0015_summary_overview
Create Date: 2026-06-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0016_paper_findings"
down_revision = "0015_summary_overview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paper_findings" not in inspector.get_table_names():
        op.create_table(
            "paper_findings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(length=100), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("tier", sa.String(length=20)),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("content_key", sa.String(length=64), nullable=False),
            sa.Column("review_state", sa.String(length=20)),
            sa.Column("review_reason", sa.Text()),
            sa.Column("reviewed_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.UniqueConstraint("paper_id", "source", "content_key", name="uq_paper_findings_paper_source_key"),
            sa.Index("ix_paper_findings_paper_id", "paper_id"),
        )


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
```

- [ ] **Step 3: Write the failing tests** (`tests/test_findings.py`):

```python
from __future__ import annotations

from app.backend.persistence.database import make_engine
from app.backend.persistence.findings_repo import (
    findings_overview,
    get_finding_dict,
    get_paper_findings,
    set_review_state,
    upsert_findings,
)
from app.backend.persistence.repository import create_paper


def _paper(conn, title="P") -> int:
    return create_paper(conn, title=title, csl_json={"title": title})


FACT = {"kind": "fact", "payload": {"label": "retracted (demo)"}}
CAND = {"kind": "candidate", "tier": "primary", "payload": {"desc": "reported t(28)=2.10, p=.02", "page": 4}}


def test_upsert_inserts_fact_and_candidate(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        data = get_paper_findings(conn, pid)
    engine.dispose()
    assert len(data["facts"]) == 1 and data["facts"][0]["review_state"] is None
    assert len(data["candidates"]) == 1 and data["candidates"][0]["review_state"] == "unreviewed"
    assert data["candidates"][0]["tier"] == "primary"


def test_upsert_is_idempotent_and_preserves_reviews(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        cand_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
        assert set_review_state(conn, cand_id, "confirmed") == "ok"
        upsert_findings(conn, pid, "demo", [FACT, CAND])  # re-run with the SAME findings
        data = get_paper_findings(conn, pid)
    engine.dispose()
    assert len(data["candidates"]) == 1  # no duplicate
    assert data["candidates"][0]["id"] == cand_id  # same row
    assert data["candidates"][0]["review_state"] == "confirmed"  # review preserved across the re-run


def test_changed_payload_supersedes_old(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [CAND])
        old_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
        changed = {"kind": "candidate", "tier": "primary", "payload": {"desc": "different", "page": 9}}
        upsert_findings(conn, pid, "demo", [changed])  # the old content_key is gone
        data = get_paper_findings(conn, pid)
    engine.dispose()
    assert len(data["candidates"]) == 1  # old superseded (deleted), one fresh
    assert data["candidates"][0]["id"] != old_id
    assert data["candidates"][0]["review_state"] == "unreviewed"


def test_set_review_state_rules(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn)
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        fact_id = get_paper_findings(conn, pid)["facts"][0]["id"]
        cand_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
        assert set_review_state(conn, fact_id, "confirmed") == "not-candidate"  # facts aren't reviewable
        assert set_review_state(conn, cand_id, "bogus") == "bad-state"
        assert set_review_state(conn, cand_id, "accepted") == "needs-reason"
        assert set_review_state(conn, cand_id, "accepted", "real but minor") == "ok"
        assert set_review_state(conn, 999999, "noted") == "not-found"
        d = get_finding_dict(conn, cand_id)
    engine.dispose()
    assert d["review_state"] == "accepted" and d["review_reason"] == "real but minor"


def test_findings_overview_counts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "A")
        b = _paper(conn, "B")
        upsert_findings(conn, a, "demo", [FACT, CAND])  # 1 unreviewed, has fact
        upsert_findings(conn, b, "demo", [FACT])  # 0 unreviewed, has fact
        ov = {o["paper_id"]: o for o in findings_overview(conn)}
    engine.dispose()
    assert ov[a]["unreviewed_count"] == 1 and ov[a]["has_facts"] is True
    assert ov[b]["unreviewed_count"] == 0 and ov[b]["has_facts"] is True
```

- [ ] **Step 4: Run to verify it fails** — `python -m pytest tests/test_findings.py -q` → ImportError.

- [ ] **Step 5: Implement `app/backend/persistence/findings_repo.py`:**

```python
"""The findings contract every METHODS check emits into (inc 130).

A Finding is a FACT (an established truth — a persistent mark, NOT resolvable, review_state NULL) or a CANDIDATE
(a possible concern for the user to check — reviewable, with an optional tier + payload anchors). Producers call
``upsert_findings``, which is IDEMPOTENT and REVIEW-STATE-PRESERVING: re-running a producer must never wipe the
user's reviews on unchanged findings. Badges describe the user's WORK STATE ("N to review"), never paper quality.
State lives in this table, not localStorage.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import Connection, and_, case, delete, func, insert, select, update
from sqlalchemy.engine import RowMapping

from app.backend.persistence.schema import paper_findings

REVIEW_STATES = ("confirmed", "accepted", "noted")  # settable candidate states (plus the 'unreviewed' default)


def _content_key(source: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(f"{source}\x00{canonical}".encode()).hexdigest()


def upsert_findings(conn: Connection, paper_id: int, source: str, findings: list[dict]) -> None:
    """Replace a (paper_id, source)'s findings, PRESERVING reviews on unchanged ones. Each finding is
    {kind: 'fact'|'candidate', tier?: str|None, payload: dict}. Idempotent: re-running with the same payloads
    touches nothing (same content_key); a changed payload is a new finding and supersedes the old."""
    keyed = [(_content_key(source, f["payload"]), f) for f in findings]
    new_keys = {ck for ck, _ in keyed}
    existing = {
        row.content_key
        for row in conn.execute(
            select(paper_findings.c.content_key).where(
                paper_findings.c.paper_id == paper_id, paper_findings.c.source == source
            )
        )
    }
    superseded = existing - new_keys
    if superseded:
        conn.execute(
            delete(paper_findings).where(
                paper_findings.c.paper_id == paper_id,
                paper_findings.c.source == source,
                paper_findings.c.content_key.in_(superseded),
            )
        )
    for content_key, f in keyed:
        if content_key in existing:
            continue  # unchanged → leave it (review_state preserved)
        kind = f["kind"]
        conn.execute(
            insert(paper_findings).values(
                paper_id=paper_id,
                source=source,
                kind=kind,
                tier=f.get("tier"),
                payload=f["payload"],
                content_key=content_key,
                review_state="unreviewed" if kind == "candidate" else None,
            )
        )


def _finding_dict(row: RowMapping) -> dict:
    return {
        "id": int(row["id"]),
        "paper_id": int(row["paper_id"]),
        "source": row["source"],
        "kind": row["kind"],
        "tier": row["tier"],
        "payload": row["payload"],
        "review_state": row["review_state"],
        "review_reason": row["review_reason"],
    }


def get_paper_findings(conn: Connection, paper_id: int) -> dict:
    rows = list(
        conn.execute(
            select(paper_findings).where(paper_findings.c.paper_id == paper_id).order_by(paper_findings.c.id)
        ).mappings()
    )
    facts = [_finding_dict(r) for r in rows if r["kind"] == "fact"]
    candidates = [_finding_dict(r) for r in rows if r["kind"] == "candidate"]
    tier_rank = {"primary": 0, "speculative": 1}
    candidates.sort(key=lambda c: (tier_rank.get(c["tier"], 0), c["review_state"] != "unreviewed", c["id"]))
    return {"facts": facts, "candidates": candidates}


def findings_overview(conn: Connection) -> list[dict]:
    rows = conn.execute(
        select(
            paper_findings.c.paper_id,
            func.sum(
                case(
                    (and_(paper_findings.c.kind == "candidate", paper_findings.c.review_state == "unreviewed"), 1),
                    else_=0,
                )
            ).label("unreviewed_count"),
            func.max(case((paper_findings.c.kind == "fact", 1), else_=0)).label("has_facts"),
        ).group_by(paper_findings.c.paper_id)
    )
    return [
        {
            "paper_id": int(r.paper_id),
            "unreviewed_count": int(r.unreviewed_count or 0),
            "has_facts": bool(r.has_facts),
        }
        for r in rows
    ]


def get_finding_dict(conn: Connection, finding_id: int) -> dict | None:
    row = conn.execute(select(paper_findings).where(paper_findings.c.id == finding_id)).mappings().first()
    return _finding_dict(row) if row is not None else None


def set_review_state(conn: Connection, finding_id: int, state: str, reason: str | None = None) -> str:
    """Returns 'ok' | 'not-found' | 'not-candidate' | 'bad-state' | 'needs-reason'. Candidates only; 'accepted'
    requires a non-empty reason."""
    row = conn.execute(select(paper_findings).where(paper_findings.c.id == finding_id)).mappings().first()
    if row is None:
        return "not-found"
    if row["kind"] != "candidate":
        return "not-candidate"
    if state not in REVIEW_STATES:
        return "bad-state"
    if state == "accepted" and not (reason and reason.strip()):
        return "needs-reason"
    conn.execute(
        update(paper_findings)
        .where(paper_findings.c.id == finding_id)
        .values(
            review_state=state,
            review_reason=(reason.strip() if reason else None),
            reviewed_at=func.current_timestamp(),
        )
    )
    return "ok"
```

- [ ] **Step 6: Run** — `python -m pytest tests/test_findings.py -q` → PASS (5). Also
  `python -m pytest tests/test_health.py tests/test_startup_migration.py -q` (head 0015→0016 derived, inc 99) → PASS.

- [ ] **Step 7: Commit** — `git add app/backend/persistence/schema.py alembic/versions/0016_paper_findings.py app/backend/persistence/findings_repo.py tests/test_findings.py && git commit -m "feat(findings): paper_findings table + idempotent findings_repo contract (inc 130 t1)"`.

---

### Task 2: `routers/findings.py` endpoints

**Files:** Create `app/backend/api/routers/findings.py`; Modify `app/backend/api/app.py` (import + include_router),
`tests/test_health.py` (route-surface), `tests/test_findings.py` (endpoint tests).

**Interfaces — Consumes:** the repo functions (Task 1). **Produces:** `GET /papers/{paper_id}/findings`,
`GET /findings/overview`, `POST /findings/{finding_id}/review`.

- [ ] **Step 1: Write the failing endpoint tests** — append to `tests/test_findings.py`:

```python
from fastapi.testclient import TestClient

from app.backend.api import create_app


def test_findings_endpoints(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Endpoint")
        upsert_findings(conn, pid, "demo", [FACT, CAND])
        cand_id = get_paper_findings(conn, pid)["candidates"][0]["id"]
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    got = client.get(f"/papers/{pid}/findings").json()
    assert len(got["facts"]) == 1 and len(got["candidates"]) == 1
    assert client.get("/papers/999999/findings").status_code == 404

    ov = {o["paper_id"]: o for o in client.get("/findings/overview").json()}
    assert ov[pid]["unreviewed_count"] == 1 and ov[pid]["has_facts"] is True

    # accepted needs a reason; a valid review drops the count
    assert client.post(f"/findings/{cand_id}/review", json={"state": "accepted"}).status_code == 422
    ok = client.post(f"/findings/{cand_id}/review", json={"state": "accepted", "reason": "minor"})
    assert ok.status_code == 200 and ok.json()["review_state"] == "accepted"
    assert {o["paper_id"]: o for o in client.get("/findings/overview").json()}[pid]["unreviewed_count"] == 0
    assert client.post("/findings/999999/review", json={"state": "noted"}).status_code == 404
```

- [ ] **Step 2: Run** → 404 (routes missing).

- [ ] **Step 3: Create `app/backend/api/routers/findings.py`:**

```python
"""Findings subsystem endpoints (inc 130): per-paper findings, the library overview, and the candidate review
workflow. Sync, local, no egress. Facts are not reviewable (review targets candidates only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Connection
from sqlalchemy.exc import NoResultFound

from app.backend.api.dependencies import get_connection
from app.backend.persistence.findings_repo import (
    findings_overview,
    get_finding_dict,
    get_paper_findings,
    set_review_state,
)
from app.backend.persistence.repository import get_paper

router = APIRouter()


class FindingModel(BaseModel):
    id: int
    paper_id: int
    source: str
    kind: str
    tier: str | None = None
    payload: dict
    review_state: str | None = None
    review_reason: str | None = None


class PaperFindingsResponse(BaseModel):
    facts: list[FindingModel]
    candidates: list[FindingModel]


class FindingsOverviewItem(BaseModel):
    paper_id: int
    unreviewed_count: int
    has_facts: bool


class ReviewRequest(BaseModel):
    state: str
    reason: str | None = None


@router.get("/papers/{paper_id}/findings", response_model=PaperFindingsResponse)
def paper_findings_get(paper_id: int, conn: Connection = Depends(get_connection)) -> PaperFindingsResponse:
    try:
        get_paper(conn, paper_id)
    except NoResultFound:
        raise HTTPException(status_code=404, detail="Paper not found") from None
    data = get_paper_findings(conn, paper_id)
    return PaperFindingsResponse(
        facts=[FindingModel(**f) for f in data["facts"]],
        candidates=[FindingModel(**c) for c in data["candidates"]],
    )


@router.get("/findings/overview", response_model=list[FindingsOverviewItem])
def findings_overview_get(conn: Connection = Depends(get_connection)) -> list[FindingsOverviewItem]:
    return [FindingsOverviewItem(**o) for o in findings_overview(conn)]


@router.post("/findings/{finding_id}/review", response_model=FindingModel)
def finding_review(finding_id: int, payload: ReviewRequest, conn: Connection = Depends(get_connection)) -> FindingModel:
    result = set_review_state(conn, finding_id, payload.state, payload.reason)
    errors = {
        "not-found": (404, "Finding not found"),
        "not-candidate": (422, "Facts are not reviewable"),
        "bad-state": (422, "state must be one of: confirmed, accepted, noted"),
        "needs-reason": (422, "Accepted requires a reason"),
    }
    if result in errors:
        raise HTTPException(status_code=errors[result][0], detail=errors[result][1])
    conn.commit()  # get_connection yields a non-autocommitting connection
    return FindingModel(**get_finding_dict(conn, finding_id))
```

- [ ] **Step 4: Register in `app.py`** — add `findings` to the routers import line and
  `api.include_router(findings.router)` after `api.include_router(methods.router)`.

- [ ] **Step 5: Route-surface** — in `tests/test_health.py`: add `"/papers/{paper_id}/findings"` and
  `"/findings/overview"` to `allowed_route_paths`, and `("/findings/{finding_id}/review", frozenset({"POST"}))`
  to `allowed_mutation_routes`.

- [ ] **Step 6: Run** — `python -m pytest tests/test_findings.py tests/test_health.py -q` → PASS.

- [ ] **Step 7: Commit** — `git add app/backend/api/routers/findings.py app/backend/api/app.py tests/test_findings.py tests/test_health.py && git commit -m "feat(findings): findings endpoints + review workflow (inc 130 t2)"`.

---

### Task 3: frontend — Review section + library badge

**Files:** Create `app/frontend/js/08_methods_findings.jsx`; Modify `app/frontend/js/40_app.jsx`,
`app/frontend/js/10_pdf_layer.jsx`, `app/frontend/styles.css`; rebuild `callosum-app.html`.

**Interfaces — Consumes:** the 3 endpoints (Task 2); `registerPaneSection`; `ctx.selectedPaper` /
`ctx.onOpenPaper` / a new `ctx.onFindingsChanged`; globals `useState`/`useEffect`/`api`/`apiPost`.

- [ ] **Step 1: Read `.claude/DESIGN.md`** (rule #8). FactMark = a neutral persistent chip; the review badge =
  a distinct work-state count; both differentiated by icon+label, not color alone.

- [ ] **Step 2: Create `08_methods_findings.jsx`:**

```jsx
// inc 130: the findings subsystem UI — the FACT-vs-CANDIDATE review surface. FACTs render as neutral persistent
// marks (FactMark); CANDIDATEs as reviewable cards (FindingCard) with Confirmed/Accepted(needs reason)/Noted.
// Badges describe the user's WORK STATE ("N to review"), never paper quality. Anchors reuse the existing
// page-open (ctx.onOpenPaper) — no new highlighter.

function findingText(f) {
  const p = f.payload || {};
  return p.desc || p.label || p.text || p.title || JSON.stringify(p);
}

function FactMark({ finding }) {
  return <span className="fact-mark" title={finding.source}>◆ {findingText(finding)}</span>;
}

function FindingCard({ finding, onReviewed, onOpenPaper }) {
  const [reasonOpen, setReasonOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const reviewed = finding.review_state && finding.review_state !== "unreviewed";
  const page = finding.payload && finding.payload.page;
  const review = async (state, why) => {
    setBusy(true);
    const r = await apiPost(`/findings/${finding.id}/review`, why ? { state, reason: why } : { state });
    setBusy(false);
    if (r.ok && onReviewed) onReviewed();
  };
  return (
    <div className={"finding-card" + (finding.tier === "speculative" ? " speculative" : "") + (reviewed ? " reviewed" : "")}>
      <div className="finding-head">
        <span className="finding-text">{findingText(finding)}</span>
        {finding.tier === "speculative" && <span className="finding-tier">speculative</span>}
      </div>
      {page != null && onOpenPaper &&
        <button className="btn-link finding-anchor" onClick={() => onOpenPaper({ id: finding.paper_id, title: "" }, { page, precision: "region" })}>show in paper · p.{page}</button>}
      {reviewed
        ? <div className="finding-reviewed">✓ {finding.review_state}{finding.review_reason ? ` — ${finding.review_reason}` : ""}</div>
        : <div className="finding-actions">
            <button className="btn-link" disabled={busy} onClick={() => review("confirmed")}>Confirmed</button>
            <button className="btn-link" disabled={busy} onClick={() => setReasonOpen(v => !v)}>Accepted…</button>
            <button className="btn-link" disabled={busy} onClick={() => review("noted")}>Noted</button>
          </div>}
      {reasonOpen && !reviewed &&
        <div className="finding-reason">
          <input className="grim-in finding-reason-in" placeholder="why (required)" value={reason} onChange={e => setReason(e.target.value)} />
          <button className="btn-link" disabled={busy || !reason.trim()} onClick={() => review("accepted", reason.trim())}>save</button>
        </div>}
    </div>
  );
}

function FindingsSection({ ctx }) {
  const [state, setState] = useState({ status: "idle" });
  const pid = ctx.selectedPaper;
  const load = () => {
    if (pid == null) { setState({ status: "idle" }); return; }
    setState({ status: "loading" });
    api(`/papers/${pid}/findings`).then(r => setState(r.ok ? { status: "ready", data: r.data } : { status: "error", error: r.error }));
  };
  useEffect(load, [pid]);
  const onReviewed = () => { load(); if (ctx.onFindingsChanged) ctx.onFindingsChanged(); };
  if (pid == null) return <div className="axis-hint">Select a paper to review its findings.</div>;
  if (state.status !== "ready") return <div className="tag-suggest-empty">{state.status === "error" ? state.error : "Loading…"}</div>;
  const { facts, candidates } = state.data;
  if (!facts.length && !candidates.length) return <div className="tag-suggest-empty">No findings for this paper yet.</div>;
  return (
    <div className="findings-section">
      {facts.length > 0 && <div className="findings-facts">{facts.map(f => <FactMark key={f.id} finding={f} />)}</div>}
      {candidates.map(c => <FindingCard key={c.id} finding={c} onReviewed={onReviewed} onOpenPaper={ctx.onOpenPaper} />)}
    </div>
  );
}

registerPaneSection({ id: "findings", label: "Review", paneId: "methods", order: 40, render: (ctx) => <FindingsSection ctx={ctx} /> });
```

(GRIM moves to order 50 so Review sits at 40 — Step 3. Or keep GRIM at 30 and Review at 35; here Review=40, GRIM stays 30 → order DETAILS 10, STATISTICS 20, GRIM 30, Review 40. Fine — leave GRIM at 30.)

- [ ] **Step 3: Thread the badge in `40_app.jsx`.** Add state + a fetch + the ctx/libraryProps wiring (the file is
  ~514 lines post-inc-128; this adds ~6 lines):

```jsx
  // inc 130: per-paper findings overview → the library "N to review" badge + FactMark. Re-fetched after a review.
  const [findingsByPaper, setFindingsByPaper] = useState({});
  const [findingsRefresh, setFindingsRefresh] = useState(0);
  useEffect(() => {
    api("/findings/overview").then(r => {
      if (!r.ok) return;
      const m = {}; r.data.forEach(o => { m[o.paper_id] = o; }); setFindingsByPaper(m);
    });
  }, [findingsRefresh, libRefresh]);
```

  Add to `paneCtx`: `onFindingsChanged: () => setFindingsRefresh(n => n + 1),`. Add to the `libraryProps` bundle:
  `findingsByPaper,`.

- [ ] **Step 4: Render the badge in `10_pdf_layer.jsx`.** Add `findingsByPaper` to the `PaperList` destructure;
  pass `findings={findingsByPaper && findingsByPaper[p.id]}` to each `<PaperCard …>`; add `findings` to the
  `PaperCard` signature and render in `paper-foot` (after the existing chips):

```jsx
        {findings && findings.has_facts && <span className="fact-mark fact-mark-card" title="Has a fact finding (e.g. retracted)">◆ fact</span>}
        {findings && findings.unreviewed_count > 0 && <span className="finding-badge" title="Unreviewed candidate findings to review">{findings.unreviewed_count} to review</span>}
```

  (Zero `unreviewed_count` → no badge, by the `> 0` guard.)

- [ ] **Step 5: CSS** (`styles.css`, after the grim block, tokens only):

```css
  /* inc 130: findings subsystem (FactMark + review cards + library badge). */
  .findings-section { font-size: 12px; }
  .findings-facts { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 10px; }
  .fact-mark { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: var(--ink); background: var(--panel-2); border: 1px solid var(--line-2); border-radius: var(--radius-sm); padding: 2px 7px; }
  .fact-mark-card { font-size: 10px; padding: 1px 6px; color: var(--ink-3); }
  .finding-badge { font-size: 10px; color: var(--accent); background: var(--accent-soft); border: 1px solid var(--accent-line); border-radius: var(--radius-pill); padding: 1px 7px; margin-left: 6px; }
  .finding-card { background: var(--panel-2); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 8px 10px; margin: 6px 0; }
  .finding-card.speculative { border-style: dashed; }
  .finding-card.reviewed { opacity: .7; }
  .finding-head { display: flex; align-items: baseline; gap: 8px; }
  .finding-text { font-size: 12.5px; color: var(--ink); }
  .finding-tier { font-size: 10px; color: var(--flag); text-transform: uppercase; letter-spacing: .04em; }
  .finding-anchor { display: inline-block; margin: 4px 0; font-size: 11px; }
  .finding-actions { display: flex; gap: 10px; margin-top: 4px; }
  .finding-reason { display: flex; gap: 6px; margin-top: 6px; }
  .finding-reason-in { width: 180px; }
  .finding-reviewed { font-size: 11.5px; color: var(--verified); margin-top: 4px; }
```

  (Confirm `--radius-pill` exists; if not, use `--radius-sm`.)

- [ ] **Step 6: Rebuild + assembly + check sizes** — `python tools/build_frontend.py && python -m pytest tests/test_frontend_assembly.py -q`; `wc -l app/frontend/js/40_app.jsx` (< 600).

- [ ] **Step 7: Headed Playwright** — `.local/visual/drive_inc130_findings.py`: seed a FACT + a CANDIDATE on a
  real paper via `upsert_findings` on a copy DB, start a server, select that paper → the **Review** METHODS
  section shows the FactMark + the FindingCard; **Confirmed** drops the card to reviewed; **Accepted** requires a
  reason; the **library card** shows "N to review" + "◆ fact"; after reviewing, reload → the review persists and
  the badge count drops; **0 console/page errors, 0 genai requests**.

- [ ] **Step 8: Commit** — `git add app/frontend/js/08_methods_findings.jsx app/frontend/js/40_app.jsx app/frontend/js/10_pdf_layer.jsx app/frontend/styles.css callosum-app.html && git commit -m "feat(findings): Review METHODS section + library 'N to review' badge (inc 130 t3)"`.

---

### Task 4: gates + docs + verify + push

**Files:** Create `.claude/security-audits/2026-06-26_findings.md`, `.claude/qa-routes/route_38_findings.md`,
`.claude/docs/increment-notes/INCREMENT-130-NOTES.md`; Modify `app/backend/help/help_content.md`, `.claude/DESIGN.md`,
`.claude/changes.md`, `RECOVERY-LOG.md`, `.claude/CLAUDE.md`.

- [ ] **Step 1: Security audit** `2026-06-26_findings.md` — input validation (review-state allowlist,
  accepted-needs-reason, FK CASCADE, JSON payload is app/test-supplied not user-free-text in v1), bound-param SQL,
  no egress/LLM/external fetch, idempotency, facts-not-reviewable enforced. Negative paths: review a fact → 422;
  accepted without reason → 422; missing finding/paper → 404. **PASS**.
- [ ] **Step 2: QA route** `route_38_findings.md` (`api: /papers/{paper_id}/findings, /findings/*`;
  `fe: 08_methods_findings.jsx`) — assert FACT renders as a persistent mark distinct from the review badge; the
  review workflow (Confirmed/Noted one-click; Accepted needs a reason); the badge = work-state, **zero shows no
  badge** (never "passed"); facts not reviewable; anchors open the page; re-running a producer doesn't reset a
  review (idempotency is not user-visibly resettable). Then `build_surface_map.py extract && check` → 0 uncovered.
- [ ] **Step 3: DESIGN.md §5** — add the **finding output contract** (FACT = persistent mark / CANDIDATE =
  reviewable, tiered; badges = WORK STATE not quality; zero ≠ passed; state in the table) as the realized
  FACT-vs-CANDIDATE forward-note.
- [ ] **Step 4: Help corpus** — a "Reviewing findings" section (facts vs candidates; the review states;
  Accepted needs a reason; the badge counts work to do, not paper quality; zero shows nothing). Move the
  `HELP-DOCS-SYNCED` marker to inc 130.
- [ ] **Step 5: Docs** — `INCREMENT-130-NOTES.md` (Implemented / Key detail: the idempotent review-state-preserving
  upsert via content_key + delete-superseded; facts NULL review_state; badge=work-state, zero=no-badge / Manual
  verification / Pytest) + `changes.md` + `RECOVERY-LOG.md` + `.claude/CLAUDE.md` footer & "Increment 130" bump.
- [ ] **Step 6: Verify** — `ruff check . && ruff format --check . && python -m pytest -q` (expect ~482; record the
  count); apply `ruff format` if it flags new files; surface check 0 uncovered.
- [ ] **Step 7: Commit + push** — commit gates/docs; `git push origin main`; confirm CI green.

---

## Self-Review
**Spec coverage:** §1 contract (FACT/CANDIDATE/tier/badges) → Tasks 1+3; §2a table+migration → Task 1; §2b repo
(idempotent/review-preserving upsert, reads, overview, set_review_state accepted-needs-reason) → Task 1; §2c
endpoints → Task 2; §3 frontend (FactMark/FindingCard/Review section/library badge/zero-shows-nothing) → Task 3;
§4 gates (Principles/audit/QA/DESIGN/help) → Tasks 1–4; §5 verification (hermetic + headed) → Tasks 1–4. The fake
producer = `upsert_findings` called by tests + the headed driver (no shipped seed endpoint). ✔
**Placeholder scan:** full code for the migration, repo, endpoints, and the section; tests with concrete expected
values; the headed-driver body is described concretely (seed via `upsert_findings`). ✔
**Type/name consistency:** `upsert_findings`/`get_paper_findings`/`findings_overview`/`set_review_state`/
`get_finding_dict` defined Task 1, consumed Task 2 (the Pydantic `FindingModel` mirrors `_finding_dict`'s keys) +
Task 3 (`finding.id/payload/tier/review_state`). `findingsByPaper[p.id] = {paper_id, unreviewed_count, has_facts}`
consistent across the overview repo → endpoint → App → PaperCard. `ctx.onFindingsChanged` defined in App, consumed
in the section. ✔
