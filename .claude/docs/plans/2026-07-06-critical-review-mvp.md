# Critical-review supplement (MVP) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A single-paper "Critical read" METHODS-pane feature that assembles a grounded *scrutiny surface* (signal, never verdict): a deterministic backbone (composed method/citation signals + a new cross-corpus contradiction detector) plus opt-in, egress-gated LLM candidate critiques the user accepts/rejects.

**Architecture:** Reuse-heavy. A new deterministic `methods/critical_review.py` (Tier 1) composes existing per-paper producers + a novel contradiction detector built on the existing NLI stance scorer + vector store. A new egress-gated `integrations/gemini/critical_review.py` (Tier 2) proposes candidates, each gated through the verbatim-quote bar (`canonical_text_contains`). A sibling router exposes an async job (Tier 1) + candidate generate/accept/reject; candidates persist to a dedicated `critical_review_candidates` table (mirrors inc-259 `ma_proposals`). A new frontend chunk renders the two tiers via `registerPaneSection`.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy Core + Alembic; `sentence-transformers` CrossEncoder NLI (already present); React JSX chunk (esbuild). No new dependency.

## Global Constraints

- **Signal, not verdict.** No composite/quality score anywhere; facts (Tier 1) vs candidates (Tier 2) are visually + epistemically distinct; the user judges. (PRINCIPLES #2/#3/#7.)
- **No author-directed judgment (A-A veto).** All copy + the Tier-2 prompt critique *claims and methods*, never a person. A test asserts no author-directed language token in output/copy.
- **#13 auditability bar for every AI (Tier-2) point:** it carries a **verbatim** anchor quote (`canonical_text_contains` must be True), a source span, an NLI stance, and a visible confidence; a candidate that can't be grounded verbatim is **dropped** (honest shortfall).
- **Egress gate (invariant #3):** Tier 1 makes **no** external call. Tier 2 rides the existing `EgressGatedSummaryGenerator` consent path — default off; a loopback provider = zero egress; egress-off ⇒ Tier 2 refuses with an honest message, Tier 1 still works.
- **600-line cap (rule #1)** on every `app/`/`integrations/` file — now enforced by `tools/git-hooks/pre-commit`; a commit fails if any exceeds it.
- **Parameterised SQL only; validate at the boundary; secrets in env/keychain.**
- **Naming:** UI label = **"Critical read"** (not "critical review").

---

## File Structure

- `app/backend/persistence/schema_critical_review.py` (NEW) — the `critical_review_candidates` table on the shared `schema_base` metadata; re-exported from `schema.py` (inc-137 leaf pattern).
- `alembic/versions/00XX_critical_review_candidates.py` (NEW) — the migration.
- `app/backend/persistence/critical_review_repo.py` (NEW) — candidate CRUD (insert / list-by-paper / set-status / rejected-signatures).
- `app/backend/methods/critical_review.py` (NEW) — Tier 1: `find_contested_claims` + `build_scrutiny_backbone` (deterministic, local).
- `integrations/gemini/critical_review.py` (NEW) — Tier 2: `CriticalReviewCandidateGenerator` (+ an `EgressGated` wrapper) → verified candidates.
- `app/backend/api/routers/critical_review.py` (NEW) — async job (Tier 1) + candidate generate/accept/reject; mounted in `app/backend/api/app.py`.
- `app/frontend/js/08x_methods_critical.jsx` (NEW) — the METHODS-pane section.
- Tests: `tests/test_critical_review.py` (NEW).
- Docs/gates: `.claude/security-audits/2026-07-06_critical-review.md`, `.claude/qa-routes/route_67_critical_review.md`, `app/backend/help/help_content.md`, increment notes, `changes.md`, CLAUDE bump.

---

### Task 1: Candidate-store schema + migration + repo

**Files:**
- Create: `app/backend/persistence/schema_critical_review.py`, `alembic/versions/00XX_critical_review_candidates.py`, `app/backend/persistence/critical_review_repo.py`
- Modify: `app/backend/persistence/schema.py` (re-export, `# noqa: E402,F401`)
- Test: `tests/test_critical_review.py`

**Interfaces produced:**
- Table `critical_review_candidates(id, paper_id FK papers.id CASCADE, concern TEXT, anchor_quote TEXT, page INT, stance STRING, confidence FLOAT, status STRING default 'pending', signature STRING, created_at)`. `status ∈ {pending, accepted, rejected}` (enum_check). `signature` = a stable hash of `(paper_id, normalized concern+quote)` so a rejected candidate is never re-proposed.
- Repo: `insert_candidates(conn, paper_id, cands) -> list[int]`; `list_candidates(conn, paper_id, *, statuses=None) -> list[dict]`; `set_status(conn, cand_id, status) -> bool`; `rejected_signatures(conn, paper_id) -> set[str]`.

- [ ] **Step 1 — failing test (schema registers + repo round-trips):**
```python
# tests/test_critical_review.py
from sqlalchemy import create_engine
from app.backend.persistence import schema, critical_review_repo as repo

def test_candidate_store_roundtrip():
    eng = create_engine("sqlite://"); schema.metadata.create_all(eng)
    with eng.begin() as c:
        # a paper row is required (FK); reuse create_paper
        from app.backend.persistence.repository import create_paper
        pid = create_paper(c, title="P", csl_json={"title": "P"})
        ids = repo.insert_candidates(c, pid, [
            {"concern": "overstated", "anchor_quote": "we prove causation", "page": 3,
             "stance": "contrast", "confidence": 0.8, "signature": "sig1"}])
        assert len(ids) == 1
        rows = repo.list_candidates(c, pid, statuses=["pending"])
        assert rows[0]["concern"] == "overstated" and rows[0]["status"] == "pending"
        assert repo.set_status(c, ids[0], "rejected") is True
        assert repo.rejected_signatures(c, pid) == {"sig1"}
```
- [ ] **Step 2 — run it, expect ImportError/NoSuchTable.** `pytest tests/test_critical_review.py::test_candidate_store_roundtrip -v`
- [ ] **Step 3 — implement the table** (mirror `schema_workbench.ma_proposals`; leaf module importing only `metadata`/`enum_check` from `schema_base`):
```python
# schema_critical_review.py
from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text, func
from app.backend.persistence.schema_base import enum_check, metadata
CRITICAL_REVIEW_STATUSES = ("pending", "accepted", "rejected")
critical_review_candidates = Table(
    "critical_review_candidates", metadata,
    Column("id", Integer, primary_key=True),
    Column("paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("concern", Text, nullable=False),
    Column("anchor_quote", Text, nullable=False),
    Column("page", Integer),
    Column("stance", String(20)),
    Column("confidence", Float),
    Column("status", String(20), nullable=False, server_default="pending"),
    Column("signature", String(80), nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    enum_check("status", CRITICAL_REVIEW_STATUSES, "cr_status_valid"),
    Index("ix_cr_candidates_paper_id", "paper_id"),
)
```
  Re-export from `schema.py` (append to the existing re-export block). Add the repo (parameterised Core inserts/selects — mirror `wanted_repo`). Write the migration by copying the newest `alembic/versions/*` header and `op.create_table(...)` with the same columns (no down-migration, per project).
- [ ] **Step 4 — run the test, expect PASS.**
- [ ] **Step 5 — `alembic upgrade head` on a temp DB; `python -m pytest tests/test_critical_review.py -v`; commit** `feat(critical-review): candidate store schema + repo (#12 t1)`.

---

### Task 2: Cross-corpus contradiction detector (the novel deterministic core)

**Files:** Create `app/backend/methods/critical_review.py`; Test: `tests/test_critical_review.py`.

**Interfaces:**
- Consumes: `default_stance_scorer()` → `.classify_stance(*, sentence, passage) -> Stance|None` (`Stance.label ∈ {"support","contrast","mention"}`); `VectorStore.search(conn, *, vector, top_k, candidate_embedding_ids)`; an `EmbeddingModel` to embed a claim; repo helpers to map embedding hits → `(paper_id, chunk_text, page)` and to list *other* papers' chunk-embedding ids.
- Produces:
```python
@dataclass(frozen=True)
class ContestedClaim:
    claim: str            # a sentence from THIS paper
    passage: str          # the contradicting passage (verbatim, from another paper)
    other_paper_id: int
    page: int | None
    stance: str           # always "contrast" here
    confidence: float
def find_contested_claims(conn, paper_id, *, embed_model, vector_store, stance_scorer,
                          claim_sentences, other_chunk_ids, contradiction_threshold=0.55,
                          top_k=5, max_claims=12) -> list[ContestedClaim]: ...
```
- Logic: for each of ≤`max_claims` `claim_sentences` → embed → `vector_store.search(..., candidate_embedding_ids=other_chunk_ids, top_k=top_k)` → for each hit map to `(other_paper_id, passage, page)` → `stance_scorer.classify_stance(sentence=claim, passage=passage)` → keep where `stance.label == "contrast"` and `stance.confidence >= contradiction_threshold`; one contested entry per claim (highest-confidence contradicter). **No LLM, no network.**

- [ ] **Step 1 — failing test** with fake injected `stance_scorer` (returns `Stance("contrast", 0.82, {...})` for the contradicting pair, `Stance("mention", 0.3, …)` otherwise), a fake `vector_store` returning a hit for paper B, and a fake `embed_model`:
```python
def test_find_contested_claims_surfaces_contradiction(fake_embed, fake_store, fake_stance):
    contested = find_contested_claims(conn, paper_id=A,
        embed_model=fake_embed, vector_store=fake_store, stance_scorer=fake_stance,
        claim_sentences=["X causes Y."], other_chunk_ids={B_chunk_id})
    assert len(contested) == 1
    assert contested[0].other_paper_id == B and contested[0].stance == "contrast"
    assert contested[0].confidence >= 0.55 and contested[0].passage  # grounded
# and: a claim whose only stance is "mention" is NOT surfaced.
```
- [ ] **Step 2 — run, expect fail (function undefined).**
- [ ] **Step 3 — implement `find_contested_claims`** exactly as the Logic above; keep the module import-light (no gemini import).
- [ ] **Step 4 — run, expect PASS.**
- [ ] **Step 5 — commit** `feat(critical-review): cross-corpus contradiction detector (#12 t2)`.

---

### Task 3: Tier-1 scrutiny backbone (compose existing signals)

**Files:** Modify `app/backend/methods/critical_review.py`; Test: `tests/test_critical_review.py`.

**Interfaces:**
```python
@dataclass(frozen=True)
class ScrutinyBackbone:
    method_signals: list[dict]     # from the existing per-paper producers that APPLY (statcheck/GRIM/retraction/
                                   # open-science/LMM/Bayes/meta) — each {kind, label, detail, evidence?}
    citation_signal: dict | None   # citation-concentration/overlooked (inc-229/230) if computable
    contested_claims: list[ContestedClaim]
def build_scrutiny_backbone(conn, paper_id, *, deps) -> ScrutinyBackbone: ...
```
- Composition reads the **already-stored** findings/signals for the paper (the inc-130 `paper_findings` / `open_science_signals` the auditors persist) + calls `find_contested_claims`. Non-applicable auditors contribute nothing (precondition-scoped). **No new judgement is invented** — it gathers.

- [ ] **Step 1 — failing test:** seed a paper with a stored statcheck finding + a contested claim (fake stance) → `build_scrutiny_backbone` returns both; a paper with neither → empty backbone (all lists empty; honest "nothing surfaced by these checks", not "clean").
- [ ] **Step 2–4 — run/implement/run** (read the findings via the existing `signals_repo`/`findings_repo`; assemble).
- [ ] **Step 5 — commit** `feat(critical-review): tier-1 scrutiny backbone composition (#12 t3)`.

---

### Task 4: Router — async Tier-1 job + accept/reject

**Files:** Create `app/backend/api/routers/critical_review.py`; Modify `app/backend/api/app.py` (import + `include_router`); Test: `tests/test_critical_review.py`.

**Interfaces (endpoints):** mirror the acquire-oa async-job pattern (`routers/acquisition.py`) + a `JobStore` on `app.state.critical_review_jobs`.
- `POST /papers/{paper_id}/critical-read` → `{job_id, status}` (runs `build_scrutiny_backbone` in a background task).
- `GET /critical-read/{job_id}` → the backbone (or status).
- `GET /papers/{paper_id}/critical-read/candidates` → stored candidates (Tier 2).
- `POST /critical-read/candidates/{cand_id}/accept` and `/reject` → `set_status`.

- [ ] **Step 1 — failing test (TestClient):** `POST /papers/{id}/critical-read` → 202 + job_id; poll `GET /critical-read/{job_id}` → done + backbone shape; accept/reject transitions a seeded candidate's status; 404 on unknown ids.
- [ ] **Step 2–4 — implement** (async job like `_run_acquire_job`; wire `app.state.critical_review_jobs = JobStore()` in `app.py` lifespan beside the others; inject the deterministic deps from `app.state`). Keep the file < 600 lines.
- [ ] **Step 5 — commit** `feat(critical-review): router + async tier-1 job + accept/reject (#12 t4)`.

---

### Task 5: Tier-2 LLM candidates through the #13 bar

**Files:** Create `integrations/gemini/critical_review.py`; Modify `routers/critical_review.py` (+`POST /papers/{id}/critical-read/candidates/generate`, egress-gated); Test: `tests/test_critical_review.py`.

**Interfaces:**
```python
@dataclass(frozen=True)
class CandidateDraft:      # what the model proposes (pre-verification)
    concern: str
    anchor_quote: str
class CriticalReviewCandidateGenerator(Protocol):
    def propose(self, *, paper_text: str) -> list[CandidateDraft]: ...
def verify_candidates(drafts, *, paper_text, stance_scorer) -> list[dict]:
    # KEEP a draft only if canonical_text_contains(needle=draft.anchor_quote, haystack=paper_text) is True.
    # attach stance + confidence + signature; DROP the rest (honest shortfall).
```
- The generate endpoint is wrapped in the **same egress seam** as `summaries.py::_summary_generator` (consent required unless loopback; cache inside the gate). Verified candidates persist as `status="pending"`, skipping any `signature ∈ rejected_signatures(paper_id)`.

- [ ] **Step 1 — failing test (fake generator):** one draft whose `anchor_quote` IS a verbatim substring of the paper text → persisted pending; one whose quote is **not** present → dropped. A previously-rejected signature is not re-created. Egress-off path → the endpoint returns the honest "AI is off" refusal (reuse the `summaries` gate message), no candidates.
- [ ] **Step 2–4 — implement** `verify_candidates` (the `canonical_text_contains` gate) + the generator wrapper + the endpoint.
- [ ] **Step 5 — commit** `feat(critical-review): tier-2 verified candidates (egress-gated) (#12 t5)`.

---

### Task 6: Frontend METHODS-pane section

**Files:** Create `app/frontend/js/08x_methods_critical.jsx`; Test: manual (`tools/build_frontend.py` + port 8888).

- `registerPaneSection({ id: "critical_read", label: "Critical read", paneId: "methods", order: <after the auditors>, render, hideInReadOnly: true })` (mirror `08i_methods_effectsize.jsx`).
- Tier 1: a button → `POST /papers/{id}/critical-read` → poll → render the backbone (method signals + citation + contested claims, each with its grounding + confidence; facts styled as facts).
- Tier 2 (only when AI enabled — read `/settings`): a **separate** "Suggest critiques (AI)" button → `.../candidates/generate` → list candidates **marked as candidates**, each with Accept / Reject.
- Honesty copy: *"What a skeptical reader should check — signal, not a verdict. AI suggestions are candidates you confirm."* No score; no author-directed language.

- [ ] **Step 1 — build:** `python tools/build_frontend.py` (esbuild must succeed).
- [ ] **Step 2 — manual (port 8888):** on a paper with a statcheck flag + a corpus contradicter, Tier 1 shows both grounded; enable AI → Tier 2 proposes a candidate with a verbatim quote → Accept persists (survives reload), Reject never returns. Confirm **0 console errors** + **0 genai-host requests with AI off**.
- [ ] **Step 3 — commit** `feat(critical-review): METHODS-pane Critical-read panel (#12 t6)`.

---

### Task 7: Gates + docs

**Files:** `.claude/security-audits/2026-07-06_critical-review.md`, `.claude/qa-routes/route_67_critical_review.md`, `app/backend/help/help_content.md`, `tests/test_critical_review.py` (guard test), CLAUDE.md, `changes.md`, `INCREMENT-NN-NOTES.md`.

- [ ] **Principles guard test:** assert the API response contains **no** composite/numeric "quality" field and that neither the copy nor a candidate carries author-directed language (a token check on a fixed banned list, e.g. "the authors are", "sloppy", "dishonest"). Run.
- [ ] **Security audit** (`2026-07-06_critical-review.md`): Tier-2 egress gated (default off, loopback zero-egress, egress-off ⇒ refuse); Tier 1 no external call; candidate storage local; input caps (claim/candidate counts, quote length) → 422; output React-escaped. Negative-path results recorded. End **PASS**.
- [ ] **QA route** `route_67_critical_review.md`: coverage header (`/critical-read/*` API + `08x_methods_critical.jsx`); assertions — 0 genai-host with egress off; facts-vs-candidates distinct; no score; no author accusation; adversarial (bad ids → 404, oversized → 422). Run `python tools/qa/build_surface_map.py check` clean.
- [ ] **Experience pass** (rule #11, the deadline citer): the panel appears where a citer looks, degrades honestly (AI off → Tier 1 only), no dead-end. Fix-cheap or backlog.
- [ ] **Help corpus** ("Critically reading a paper") + move the `HELP-DOCS-SYNCED` marker; **credit-lineage note** (NLI stance lineage already credited; contradiction-as-signal is native).
- [ ] **CLAUDE.md** inc bump + test count; `changes.md` entry; `INCREMENT-NN-NOTES.md`.
- [ ] **Final:** full `pytest --ignore=tests/test_mcp_server.py` green; `ruff format`/`check` clean; pre-commit gate green; commit + push.

---

## Self-Review (author checklist — done)

- **Spec coverage:** Tier 1 backbone (T3) + contradiction detector (T2) + Tier 2 verified candidates (T5) + persistence (T1) + METHODS panel (T6) + all gates (T7) — every spec section maps to a task. ✓
- **Placeholder scan:** the `order:` in T6 and the migration number are the only "fill from context" values (both determined by reading one neighbouring file at build); no logic placeholders. ✓
- **Type consistency:** `ContestedClaim` (T2) consumed by `ScrutinyBackbone` (T3) + rendered (T6); `CandidateDraft`→verified-dict (T5) persisted via the T1 repo shape (`concern/anchor_quote/page/stance/confidence/signature/status`) — consistent across tasks. ✓
- **Scope:** single-paper MVP only; multi-paper stress-test explicitly out (increment 2). ✓
