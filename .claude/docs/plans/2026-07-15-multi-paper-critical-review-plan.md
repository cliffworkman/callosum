# Multi-paper (set) critical review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A set-based critical-review mode (backlog #12) that, over a chosen set of papers, surfaces where they contradict each other, a per-paper fact-matrix, and egress-gated cross-paper AI critique candidates through the #13 verbatim bar — launched from a synthesis's sources or a library multi-selection, rendered in one modal.

**Architecture:** A shared engine keyed on `paper_ids`, run as one async job, reusing the inc-266 primitives (`find_contested_claims`, `_stored_method_signals`, `verify_candidates`, `critical_review_repo`, the `critical_review_deps` test seam). Tier-1 is fully local; Tier-2 rides the existing Gemini egress gate. Two thin entry points, one modal.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy Core / Alembic (SQLite/sqlite-vec) / sentence-transformers + local NLI / React JSX (esbuild).

**Spec:** `.claude/docs/specs/2026-07-15-multi-paper-critical-review-design.md`.

## Global Constraints

- **Egress gate (#3):** Tier-1 makes NO network/LLM call. Tier-2 sends set text to the LLM only through `requires_egress(config) && config.data_egress_enabled` (else HTTP 422) + a resolved key; loopback providers = zero egress. Copy the single-paper `generate_candidates` gate verbatim.
- **#13 auditability bar:** every AI candidate carries a verbatim `anchor_quote` (verified via `canonical_text_contains` against a set paper's full text), a local-NLI `stance`, a `confidence`, and its anchoring `paper_id`; ungrounded/rejected/duplicate drafts are dropped. Only the anchor quote is verified — `related_paper_ids` is the model's framing, never a verified link.
- **No accusation of individuals (A-A veto):** the prompt forbids "about the authors as people"; concerns are about the WORK. A banned-phrase test guards it.
- **No composite score / no ranking:** the aggregate is a fact-matrix (per-paper check statuses). No summed score, no "most-flawed" ordering, no `score`/`quality`/`grade`/`rank` field anywhere in the payload.
- **Silence ≠ certificate:** empty results render "nothing surfaced," never "these papers are sound."
- **600-line cap** on every `app/` + `integrations/` `.py`/`.jsx` file. Run `PYTHONIOENCODING=utf-8 python tools/check_line_budget.py` before every commit (the pre-commit hook is skipped by `--no-verify`).
- **Parameterized SQL only** (SQLAlchemy Core bound params). **Migrations:** additive, guarded, no down-migration.
- **Caps:** `MAX_SET_PAPERS = 12`; `_MAX_SET_PROMPT_CHARS = 20000`.
- After any `app/frontend/` edit: `python tools/build_frontend.py`. Verify: `pytest` green; `ruff check .` + `ruff format --check .`.

## File structure

| File | Responsibility |
|---|---|
| `alembic/versions/0045_cr_candidate_related_papers.py` (NEW) | additive `related_paper_ids_json` column |
| `app/backend/persistence/schema_critical_review.py` (MOD) | add the column to the table def |
| `app/backend/persistence/critical_review_repo.py` (MOD) | `insert_candidates`/`list_candidates` `related_paper_ids` passthrough |
| `app/backend/methods/critical_review_set.py` (NEW) | Tier-1 set engine: `set_chunk_embedding_ids`, `set_contested_claims`, `set_aggregate` |
| `integrations/gemini/critical_review_set.py` (NEW) | Tier-2: `SetCandidateDraft`, `parse_set_drafts`, `verify_set_candidates`, `GeminiSetCriticalReviewGenerator`, `_set_prompt` |
| `app/backend/api/routers/critical_review.py` (MOD) | set models + `POST/GET /critical-read/set` + `_run_set_critical_read_job` |
| `app/backend/api/app.py` (MOD) | `critical_review_set_jobs` JobStore + `critical_review_set_generator` seam |
| `app/frontend/js/08y_critical_set.jsx` (NEW) | the modal + entry-point buttons |
| `app/frontend/js/20_synthesis.jsx`, the library bulk-bar chunk (MOD) | wire the two entry points |
| `app/frontend/styles.css` (MOD) | modal + fact-matrix styles |
| `tests/test_critical_review_set.py` (NEW) | engine + Tier-2 + endpoint tests |
| docs: security audit, QA route, changes.md, help, increment notes | gates |

---

### Task 1: Migration + repo passthrough for `related_paper_ids_json`

**Files:**
- Create: `alembic/versions/0045_cr_candidate_related_papers.py`
- Modify: `app/backend/persistence/schema_critical_review.py`, `app/backend/persistence/critical_review_repo.py`
- Test: `tests/test_critical_review_set.py`

**Interfaces:**
- Produces: `critical_review_candidates.related_paper_ids_json` (nullable JSON); `insert_candidates(conn, paper_id, candidates)` now reads `cand.get("related_paper_ids")`; `list_candidates(...)` rows include `related_paper_ids_json`.

- [ ] **Step 1: Write the failing test** (append to `tests/test_critical_review_set.py`)
```python
from app.backend.persistence import critical_review_repo as repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema_critical_review import critical_review_candidates as cands


def test_related_paper_ids_roundtrips(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        from app.backend.persistence.repository import create_paper
        pid = create_paper(conn, title="A", csl_json={"title": "A"})
        [cid] = repo.insert_candidates(conn, pid, [{
            "concern": "small sample", "anchor_quote": "n = 12", "signature": "sig1",
            "stance": "contrast", "confidence": 0.7, "related_paper_ids": [pid + 1, pid + 2],
        }])
        rows = repo.list_candidates(conn, pid)
    engine.dispose()
    assert rows[0]["related_paper_ids_json"] == [pid + 1, pid + 2]
```

- [ ] **Step 2: Run it, verify it fails** — `pytest tests/test_critical_review_set.py::test_related_paper_ids_roundtrips -v` → FAIL (no such column / kwarg).

- [ ] **Step 3: Write the migration** (`0045_cr_candidate_related_papers.py`)
```python
"""cr_candidate_related_papers — the other set papers a cross-paper critique candidate spans (set critical review, #12).

Additive + guarded; no down-migration. The value is the MODEL's framing (validated to the set), not a verified link.
"""
from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0045_cr_candidate_related_papers"
down_revision = "0044_paper_tag_locks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("critical_review_candidates")}
    if "related_paper_ids_json" not in cols:
        op.add_column("critical_review_candidates", sa.Column("related_paper_ids_json", sa.JSON()))


def downgrade() -> None:
    return
```

- [ ] **Step 4: Add the column to the schema** (`schema_critical_review.py`, after the `signature` column, before `created_at`)
```python
    Column("related_paper_ids_json", JSON),  # set critical review (#12): the model's related set papers — not a verified link
```
(Add `JSON` to the existing `from sqlalchemy import (...)` import in that file if absent.)

- [ ] **Step 5: Thread it through the repo** (`critical_review_repo.py`) — in `insert_candidates`, add to `.values(...)`: `related_paper_ids_json=cand.get("related_paper_ids")`. `list_candidates` already selects `*`, so the new column returns automatically.

- [ ] **Step 6: Run the test** — `pytest tests/test_critical_review_set.py::test_related_paper_ids_roundtrips -v` → PASS.

- [ ] **Step 7: Commit** — `git add alembic/versions/0045_cr_candidate_related_papers.py app/backend/persistence/schema_critical_review.py app/backend/persistence/critical_review_repo.py tests/test_critical_review_set.py && git commit -m "feat(#12): related_paper_ids_json on cr candidates (migration 0045 + repo)"`

---

### Task 2: Tier-1 engine — set-scoped contradictions

**Files:**
- Create: `app/backend/methods/critical_review_set.py`
- Test: `tests/test_critical_review_set.py`

**Interfaces:**
- Consumes: `find_contested_claims`, `make_chunk_resolver`, `extract_claim_sentences`, `ContestedClaim` (from `app.backend.methods.critical_review`); `EmbeddingModel`, `VectorStore`, `StanceScorer`.
- Produces:
  - `set_chunk_embedding_ids(conn, set_ids: list[int], exclude_id: int) -> set[int]`
  - `set_contested_claims(conn, set_ids, *, embed_model, vector_store, stance_scorer) -> list[dict]` — each `{claim, passage, claim_paper_id, other_paper_id, page, stance, confidence}`.

- [ ] **Step 1: Write the failing test** — a hermetic test with a fake vector store + fake stance scorer where paper A's claim is contradicted by a chunk in set-paper B (surfaces) but NOT by a non-set paper C (does not).
```python
def test_set_contested_only_surfaces_intra_set(temp_db_url):
    # seed 3 papers A,B,C with one chunk each + chunk embeddings; fake stance: contrast for (A-claim, B-chunk) and
    # (A-claim, C-chunk). Set = {A, B}. Expect exactly one contested claim, other_paper_id == B (C excluded).
    ...  # see helpers below; assert len == 1 and rows[0]["other_paper_id"] == b_id
```
(Reuse the injection pattern from `tests/test_critical_review.py`: a fake `embed_model` with `encode_texts`, a fake `vector_store` whose `search(...candidate_embedding_ids=...)` returns hits limited to the candidate set, a fake `stance_scorer.classify_stance` returning a `Stance(label="contrast", confidence=0.8, probs={})` for the seeded pairs.)

- [ ] **Step 2: Run it, verify it fails** (module doesn't exist).

- [ ] **Step 3: Implement `critical_review_set.py`**
```python
"""Set critical review (backlog #12) — Tier-1 engine over a CHOSEN SET of papers.

Reuses the inc-266 single-paper primitives, scoping the cross-corpus contradiction detector to the SET (so only
INTRA-set disagreement surfaces) and composing each paper's ALREADY-STORED signals into an honest fact-matrix.
Fully local, no LLM, no network. Every heavy dep is injected (test seam)."""
from __future__ import annotations
from sqlalchemy import select
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.vector_store import VectorStore
from app.backend.methods.critical_review import (
    extract_claim_sentences, find_contested_claims, make_chunk_resolver,
)
from app.backend.methods.critical_review import _stored_method_signals  # noqa: F401 (reused below)
from app.backend.persistence.repository import get_paper
from app.backend.persistence.schema import chunks, embeddings, papers
from app.backend.summarization.verification import StanceScorer


def set_chunk_embedding_ids(conn, set_ids: list[int], exclude_id: int) -> set[int]:
    """Chunk-embedding ids for the OTHER papers IN THE SET (mirror of other_paper_chunk_embedding_ids, set-scoped)."""
    corpus = embeddings.join(chunks, embeddings.c.target_id == chunks.c.id).join(
        papers, papers.c.id == chunks.c.paper_id
    )
    rows = conn.execute(
        select(embeddings.c.id).select_from(corpus).where(
            embeddings.c.target_type == "chunk",
            chunks.c.paper_id.in_(set_ids),
            chunks.c.paper_id != exclude_id,
            papers.c.deleted_at.is_(None),
        )
    )
    return {int(r[0]) for r in rows}


def set_contested_claims(conn, set_ids, *, embed_model: EmbeddingModel, vector_store: VectorStore,
                         stance_scorer: StanceScorer) -> list[dict]:
    resolve = make_chunk_resolver(conn)
    out: list[dict] = []
    for paper_id in set_ids:
        others = set_chunk_embedding_ids(conn, set_ids, paper_id)
        contested = find_contested_claims(
            conn, paper_id, embed_model=embed_model, vector_store=vector_store, stance_scorer=stance_scorer,
            resolve_chunk=resolve, claim_sentences=extract_claim_sentences(conn, paper_id), other_chunk_ids=others,
        )
        for c in contested:
            out.append({
                "claim": c.claim, "passage": c.passage, "claim_paper_id": paper_id,
                "other_paper_id": c.other_paper_id, "page": c.page, "stance": c.stance, "confidence": c.confidence,
            })
    return out
```

- [ ] **Step 4: Run the test** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(#12): Tier-1 set-scoped contradiction engine"`

---

### Task 3: Tier-1 engine — aggregate fact-matrix

**Files:** Modify `app/backend/methods/critical_review_set.py`; Test `tests/test_critical_review_set.py`.

**Interfaces:**
- Produces: `set_aggregate(conn, set_ids: list[int], contested_claims: list[dict]) -> list[dict]` — one row per set paper `{paper_id, title, method_signals: list[dict], contested_count: int}` (NO score/rank field).

- [ ] **Step 1: Failing test** — seed a paper with one stored `open_science_signals` row (e.g. statcheck "inconsistent") + a contested claim; assert the aggregate row carries `method_signals` (the statcheck label) and `contested_count == 1`, and that a paper with nothing stored yields `method_signals == []` (honest empty), and that **no** row key matches `{"score","quality","grade","rank"}`.

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement** (append to `critical_review_set.py`)
```python
def set_aggregate(conn, set_ids: list[int], contested_claims: list[dict]) -> list[dict]:
    by_paper: dict[int, int] = {}
    for c in contested_claims:
        by_paper[c["claim_paper_id"]] = by_paper.get(c["claim_paper_id"], 0) + 1
    rows: list[dict] = []
    for paper_id in set_ids:
        paper = get_paper(conn, paper_id)
        rows.append({
            "paper_id": paper_id,
            "title": str(paper["title"] or f"Paper {paper_id}"),
            "method_signals": _stored_method_signals(conn, paper_id),  # facts, never a score
            "contested_count": by_paper.get(paper_id, 0),
        })
    return rows
```

- [ ] **Step 4: Run → PASS. Step 5: Commit** — `git commit -m "feat(#12): Tier-1 aggregate fact-matrix"`

---

### Task 4: Tier-2 — set candidate generator + extended #13 verify

**Files:**
- Create: `integrations/gemini/critical_review_set.py`
- Test: `tests/test_critical_review_set.py`

**Interfaces:**
- Consumes: `complete` (`app.backend.llm.providers`), `canonical_text_contains` (`app.backend.pdf_processing.extraction`), `candidate_signature` (`integrations.gemini.critical_review`).
- Produces:
  - `SetCandidateDraft(concern: str, anchor_quote: str, related_indices: list[int])`
  - `parse_set_drafts(raw: str) -> list[SetCandidateDraft]`
  - `verify_set_candidates(drafts, *, set_papers: list[dict], stance_scorer, rejected_signatures=frozenset()) -> list[dict]` where each `set_papers` item is `{"index": int, "paper_id": int, "text": str}`; returns dicts `{paper_id, concern, anchor_quote, page, stance, confidence, signature, related_paper_ids}`.
  - `GeminiSetCriticalReviewGenerator(config)` with `.propose(set_papers) -> list[SetCandidateDraft]`.

- [ ] **Step 1: Failing tests** — (a) a draft whose `anchor_quote` is verbatim in set-paper 2's text is kept, anchored to paper 2, with `related_paper_ids` = the mapped-and-set-validated indices minus the anchor; (b) an ungrounded quote is dropped; (c) a rejected signature is skipped; (d) `verify_set_candidates` output contains no author-directed phrase and no score field (reuse the inc-266 banned-set `{"the authors are","sloppy","dishonest","fraud",...}` scan + `{"quality","score","grade","rating","verdict"}` field scan).

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement `integrations/gemini/critical_review_set.py`**
```python
"""Set critical review Tier-2 (#12) — egress-gated cross-paper LLM candidates through the #13 verbatim bar.

The model proposes concerns that SPAN the set; each is admitted only if its anchor_quote is verbatim in SOME set
paper (canonical_text_contains) → recorded against that paper_id. related_paper_ids is the model's framing (its named
indices, validated to the set), NOT a verified link. Untrusted output → defensive parse, zero drafts on failure."""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field
from typing import Any
from app.backend.llm.providers import complete
from app.backend.pdf_processing.extraction import canonical_text_contains
from integrations.gemini.critical_review import candidate_signature

_MAX_DRAFTS = 8
_MAX_CONCERN = 400
_MAX_QUOTE = 400
_MAX_SET_PROMPT_CHARS = 20000


@dataclass(frozen=True)
class SetCandidateDraft:
    concern: str
    anchor_quote: str
    related_indices: list[int] = field(default_factory=list)


def _anchor_paper(quote: str, set_papers: list[dict]) -> dict | None:
    for p in set_papers:
        if canonical_text_contains(needle=quote, haystack=p["text"]):
            return p
    return None


def verify_set_candidates(drafts, *, set_papers, stance_scorer, rejected_signatures=frozenset()) -> list[dict]:
    index_to_id = {p["index"]: p["paper_id"] for p in set_papers}
    set_ids = set(index_to_id.values())
    out: list[dict] = []
    seen: set[str] = set()
    for d in drafts:
        concern, quote = (d.concern or "").strip(), (d.anchor_quote or "").strip()
        if not concern or not quote:
            continue
        anchor = _anchor_paper(quote, set_papers)
        if anchor is None:
            continue  # not grounded verbatim in any set paper → dropped (honest shortfall)
        sig = candidate_signature(anchor["paper_id"], concern, quote)
        if sig in rejected_signatures or sig in seen:
            continue
        seen.add(sig)
        related = sorted(
            {index_to_id[i] for i in d.related_indices if i in index_to_id and index_to_id[i] != anchor["paper_id"]}
            & set_ids
        )
        stance = stance_scorer.classify_stance(sentence=concern, passage=quote)
        out.append({
            "paper_id": anchor["paper_id"], "concern": concern[:_MAX_CONCERN], "anchor_quote": quote[:_MAX_QUOTE],
            "page": None, "stance": stance.label if stance else None,
            "confidence": stance.confidence if stance else None, "signature": sig,
            "related_paper_ids": related or None,
        })
    return out


def _set_prompt(set_papers: list[dict]) -> str:
    budget = max(1, _MAX_SET_PROMPT_CHARS // max(1, len(set_papers)))
    blocks = [f"[{p['index']}] {p['text'][:budget]}" for p in set_papers]
    return (
        "You are a skeptical methodological reviewer reading several papers a user is citing together. List up to "
        f"{_MAX_DRAFTS} specific concerns that SPAN these papers — a shared limitation, or a claim in one contradicted "
        "by another — about the CLAIMS and METHODS ONLY, never the authors as people. For each concern, quote the "
        "EXACT sentence (verbatim) it is anchored in, and give the bracketed paper numbers it relates to. Return ONLY "
        'a JSON array of {"concern": "...", "anchor_quote": "...", "related": [1,2]} objects, no prose.\n\n'
        + "\n\n".join(blocks)
    )


class GeminiSetCriticalReviewGenerator:
    def __init__(self, config: Any) -> None:
        self.config = config

    def propose(self, set_papers: list[dict]) -> list[SetCandidateDraft]:
        result = complete(self.config, _set_prompt(set_papers))
        return parse_set_drafts(str(getattr(result, "text", "") or ""))


def parse_set_drafts(raw: str) -> list[SetCandidateDraft]:
    data = _loads_lenient(raw)
    if not isinstance(data, list):
        return []
    out: list[SetCandidateDraft] = []
    for item in data[:_MAX_DRAFTS]:
        if not isinstance(item, dict):
            continue
        concern = str(item.get("concern") or "").strip()
        quote = str(item.get("anchor_quote") or "").strip()
        related = [int(x) for x in (item.get("related") or []) if isinstance(x, (int, float))]
        if concern and quote:
            out.append(SetCandidateDraft(concern[:_MAX_CONCERN], quote[:_MAX_QUOTE], related))
    return out


def _loads_lenient(raw: str) -> Any:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        start, end = text.find("["), text.rfind("]")
        if 0 <= start < end:
            try:
                return json.loads(text[start:end + 1])
            except (ValueError, TypeError):
                return None
    return None
```

- [ ] **Step 4: Run tests → PASS. Step 5: Commit** — `git commit -m "feat(#12): Tier-2 set candidate generator + extended #13 verify"`

---

### Task 5: API — set endpoints + async job + app wiring

**Files:**
- Modify: `app/backend/api/routers/critical_review.py`, `app/backend/api/app.py`
- Test: `tests/test_critical_review_set.py`

**Interfaces:**
- Produces: `POST /critical-read/set {paper_ids: list[int], llm: bool=false}` → `{job_id, status}`; `GET /critical-read/set/{job_id}` → `{job_id, status, detail, report}` where `report = {aggregate, contested_claims, candidates, llm_status}`.
- Consumes: `_cr_deps(app)` (existing), `set_contested_claims`/`set_aggregate` (Task 2/3), `verify_set_candidates`/`GeminiSetCriticalReviewGenerator` (Task 4), `critical_review_repo`.

- [ ] **Step 1: Failing tests** — (a) `POST /critical-read/set` with `<2` or `>MAX_SET_PAPERS` ids → 422; unknown id → 404. (b) Tier-1 job (llm=false) over a seeded set (with `critical_review_deps` fakes) returns `aggregate` + `contested_claims`, `llm_status.status == "not_searched"`. (c) With `llm=true` and NO egress consent → the job's `llm_status.status == "unavailable"` (Tier-1 still completes). (d) With a `critical_review_set_generator` fake seam + consent, Tier-2 candidates are verified + persisted + returned.

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: app.py wiring** — after line 169 (`critical_review_jobs = JobStore()`):
```python
    api.state.critical_review_set_jobs = JobStore()  # backlog #12: set (multi-paper) critical review
    api.state.critical_review_set_generator = None  # test seam for the Tier-2 set generator
```
(The router is already mounted; no new `include_router`.)

- [ ] **Step 4: Add to `critical_review.py`** — the models, endpoints, and job. Reuse the existing `_cr_deps`, egress-gate block from `generate_candidates`, and `MAX_SET_PAPERS`.
```python
MAX_SET_PAPERS = 12


class SetCriticalReadRequest(BaseModel):
    paper_ids: list[int]
    llm: bool = False


class SetCriticalReadResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "done", "error"]
    detail: str | None = None
    report: dict | None = None


@router.post("/critical-read/set", response_model=SetCriticalReadResponse,
             status_code=http_status.HTTP_202_ACCEPTED)
def set_critical_read_start(body: SetCriticalReadRequest, background_tasks: BackgroundTasks,
                            request: Request, conn: Connection = Depends(get_connection)) -> SetCriticalReadResponse:
    ids = list(dict.fromkeys(int(p) for p in body.paper_ids))
    if not (2 <= len(ids) <= MAX_SET_PAPERS):
        raise HTTPException(status_code=422, detail=f"Select 2–{MAX_SET_PAPERS} papers for a set critical read.")
    for pid in ids:
        try:
            get_paper(conn, pid)
        except NoResultFound:
            raise HTTPException(status_code=404, detail=f"Paper {pid} not found") from None
    job_id = request.app.state.critical_review_set_jobs.create()
    background_tasks.add_task(_run_set_critical_read_job, request.app, job_id, ids, bool(body.llm))
    return SetCriticalReadResponse(job_id=job_id, status="pending")


@router.get("/critical-read/set/{job_id}", response_model=SetCriticalReadResponse)
def set_critical_read_status(job_id: str, request: Request) -> SetCriticalReadResponse:
    job = request.app.state.critical_review_set_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Set critical-read job not found")
    if job.status == "done" and job.result is not None:
        return job.result
    return SetCriticalReadResponse(job_id=job_id, status=job.status, detail=job.detail)


def _run_set_critical_read_job(app: FastAPI, job_id: str, set_ids: list[int], want_llm: bool) -> None:
    from app.backend.methods.critical_review import paper_full_text
    from app.backend.methods.critical_review_set import set_aggregate, set_contested_claims
    jobs = app.state.critical_review_set_jobs
    jobs.mark_running(job_id)
    try:
        embed_model, vector_store, stance_scorer = _cr_deps(app)
        engine: Engine = app.state.engine
        with engine.connect() as conn:
            contested = set_contested_claims(conn, set_ids, embed_model=embed_model,
                                             vector_store=vector_store, stance_scorer=stance_scorer)
            aggregate = set_aggregate(conn, set_ids, contested)
        llm_status = {"status": "not_searched", "detail": "AI critique was not requested."}
        candidates: list[dict] = []
        if want_llm:
            llm_status, candidates = _run_set_tier2(app, set_ids, stance_scorer)
        jobs.mark_done(job_id, SetCriticalReadResponse(
            job_id=job_id, status="done",
            report={"aggregate": aggregate, "contested_claims": contested,
                    "candidates": candidates, "llm_status": llm_status}))
    except Exception as exc:
        jobs.mark_error(job_id, f"{type(exc).__name__}: {exc}")
```
Add `_run_set_tier2(app, set_ids, stance_scorer)` — mirror the single-paper `generate_candidates` egress gate, build `set_papers = [{"index": i+1, "paper_id": pid, "text": paper_full_text(conn, pid)}]`, `propose` → `verify_set_candidates(..., rejected_signatures=union of repo.rejected_signatures per paper)`, group verified by `paper_id` and `repo.insert_candidates(conn, pid, group)`, commit, return `("success"/…, list of persisted candidate dicts incl. related_paper_ids_json)`. On egress-not-consented → return `({"status":"unavailable","detail":"AI critique needs data-egress consent (Settings → AI features)"}, [])`.

- [ ] **Step 5: Run tests → PASS.** Check `PYTHONIOENCODING=utf-8 python tools/check_line_budget.py` (critical_review.py stays <600; if not, split the set cluster into `routers/critical_review_set.py` — the `library_enrich.py` pattern).
- [ ] **Step 6: Commit** — `git commit -m "feat(#12): set critical-read endpoints + async job + wiring"`

---

### Task 6: Frontend — the modal + two entry points

**Files:**
- Create: `app/frontend/js/08y_critical_set.jsx`
- Modify: `app/frontend/js/20_synthesis.jsx` (synthesis entry), the library bulk-select bar chunk (selection entry), `app/frontend/styles.css`
- Test: `tests/test_frontend_assembly.py`

**Interfaces:** Consumes `POST /critical-read/set` + `GET /critical-read/set/{job_id}` + the existing `/critical-read/candidates/{id}/accept|reject`.

- [ ] **Step 1: Failing assembly test** — assert the built frontend contains `"Critical read ·"`, `"critical-read/set"`, the amber `cr-candidate` class reuse, and (honesty) that it does NOT contain a `"score"`/`"grade"` label in the set modal region; assert the synthesis "Critically review these sources" button string is present.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Build `08y_critical_set.jsx`** — a modal component mirroring the dup-detection modal shell + the `08x_methods_critical.jsx` candidate rendering: (a) an **Aggregate** table (rows = `report.aggregate`, columns = the distinct `method_signals` kinds + a "contested" count; a cell shows the stored detail or "—"; a caption: "Facts each check surfaced — not a score."); (b) a **"Where these papers disagree"** list (`report.contested_claims`, each: claim, the contradicting quote, both titles, page, stance+confidence, click → `onOpenPaper(other_paper_id, page)`); (c) an **"AI cross-paper critiques"** section gated on `/settings` `data_egress_enabled` with a "Suggest cross-paper critiques (AI)" button that re-POSTs with `llm:true`; candidates render in amber with verbatim quote + which paper + "the model relates this to: [titles]" (from `related_paper_ids_json`) + stance/confidence + Accept/Reject (reuse the `08x` accept/reject calls). Empty sections render an honest "Nothing surfaced by this check." Follow `08x` for the poll loop (POST → poll GET until done).
- [ ] **Step 4: Wire entry points** — in `20_synthesis.jsx`, add a "Critically review these sources" button (visible when a synthesis is shown) that opens the modal with the synthesis scope's `paper_ids`; in the library bulk-select bar, add a "Critical read" action opening the modal with the current selection. Gate both on `!readOnly`.
- [ ] **Step 5: CSS** (`styles.css`) — `.cr-set-modal` (reuse `.axis-modal*`), `.cr-matrix` (a bordered table using `--line`/`--panel`; status cells neutral, never colored-by-quality); reuse `.cr-candidate`/`.cr-quote`/`.cr-actions` from `08x`. Read `.claude/DESIGN.md` first (rule #8); use tokens only.
- [ ] **Step 6: Rebuild** — `python tools/build_frontend.py`.
- [ ] **Step 7: Run assembly test → PASS. Step 8: Commit** — `git commit -m "feat(#12): set critical-review modal + synthesis/selection entry points"`

---

### Task 7: Gates — security audit + QA route + docs

**Files:** `.claude/security-audits/2026-07-15_multi-paper-critical-review.md`, `.claude/qa-routes/route_71_critical_review_set.md`, `.claude/changes.md`, `app/backend/help/help_content.md`, `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md`.

- [ ] **Step 1:** Write the security audit (per spec's audit section): input validation on `paper_ids`, egress consent + negative path (422), #13 grounding (no ungrounded candidate persists), prompt-injection posture (defensive parse), no author-directed output, resource caps, SQL bound params. Run the negative-path checks (malformed body, oversized set, egress-off). End **PASS** or **RISK ACCEPTED**.
- [ ] **Step 2:** Write `route_71_critical_review_set.md` per `.claude/QA-POLICY.md`: declare the API surfaces (`/critical-read/set*`) + honesty assertions (egress gate, facts-vs-candidates, no score field, no author accusation). Run `python tools/qa/build_surface_map.py check` — 0 uncovered API.
- [ ] **Step 3:** `changes.md` entry + a `help_content.md` "Critically reviewing a set of papers" section + `INCREMENT-NN-NOTES.md` (bump the number) + CLAUDE.md test-count/increment update.
- [ ] **Step 4: Commit** — `git commit -m "docs(#12): security audit + QA route 71 + help + increment notes"`

---

### Task 8: Experience pass + full verification

- [ ] **Step 1:** Run the rule-#11 experience pass — dispatch a persona-grounded **skeptical synthesizer** experience agent (per `.claude/EXPERIENCE-PASS.md`) against a real synthesis's source set: does the modal help decide whether to trust the synthesis, without moralizing/scoring? Fix cheap findings in-session; backlog the rest.
- [ ] **Step 2:** `pytest` (whole suite) green; `ruff check .` + `ruff format --check .`; `PYTHONIOENCODING=utf-8 python tools/check_line_budget.py`; `python tools/build_frontend.py` (no diff surprises).
- [ ] **Step 3:** Manual verification script (record in the increment notes): open a 3-paper synthesis → "Critically review these sources" → confirm intra-set contradictions open the right PDFs, the aggregate is a fact-matrix (no score), Tier-2 is egress-gated + candidates carry verbatim quote + which paper + stance + confidence + accept/reject; a garbled quote honestly yields no anchor; the empty case reads "nothing surfaced."
- [ ] **Step 4: Commit** — `git commit -m "chore(#12): experience pass + full verification"`, then open the PR.

---

## Self-review (writing-plans)

- **Spec coverage:** engine set-scoping ✓ (T2), aggregate fact-matrix ✓ (T3), Tier-2 #13 extended ✓ (T4), egress gate ✓ (T5), migration+repo ✓ (T1), modal+two entry points ✓ (T6), security audit + QA + experience ✓ (T7/T8), honesty (no score/no accusation) asserted in T3/T4/T6 tests + T7 audit. No spec requirement left unmapped.
- **Type consistency:** `set_contested_claims` returns dicts with `claim_paper_id`/`other_paper_id` used by `set_aggregate` (T3) and the modal (T6); `verify_set_candidates` returns `paper_id`+`related_paper_ids` consumed by `_run_set_tier2` → `repo.insert_candidates` (`related_paper_ids` passthrough from T1) ✓; `set_papers` item shape `{index,paper_id,text}` consistent T4↔T5.
- **Placeholder scan:** the only prose-described code is `_run_set_tier2` (T5 step 4) — its exact behavior (egress gate copy, grouping, insert) is specified; the implementer mirrors the named single-paper `generate_candidates`. Acceptable (names the exact source to copy).
