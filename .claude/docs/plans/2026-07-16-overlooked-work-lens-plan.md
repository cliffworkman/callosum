# Overlooked-work lens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A per-axis, pull-not-push discovery lens that surfaces external works highly relevant to an axis but under-cited for their vintage — a surfacing signal with two separable visible inputs (relevance + citations-vs-same-vintage-percentile), never a composite "hidden-gem score."

**Architecture:** Reuse the OpenAlex sources client (topic resolution + a new `fetch_topic_works`), local embedding (axis vector + on-device abstract embedding for relevance), and a local same-year citation percentile as the honest vintage baseline. A pure engine (`methods/overlooked.py`) + a cache table + an async job/endpoints mirroring the gap-finder (fetch-outside-lock via inc-D's cache_engine) + a frontend panel that reuses the gap add/dismiss flow.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy Core (SQLite), sentence-transformers (local embed), OpenAlex (bounded/cached/fail-closed), React JSX (esbuild).

## Global Constraints

- App-source files **< 600 lines** (`python tools/check_line_budget.py`); split before crossing.
- **Parameterized SQL only**; OpenAlex ids validated (`^T\d+$` topic, `^W\d+$` work) before any request; external fetch bounded + cached + fail-closed (rule #4).
- **Egress:** only the axis label + topic id leave the machine; **candidate abstracts are embedded on-device** (never transmitted). No Gemini gate involved (metadata egress, like gap-finder).
- **Honesty invariants (rule #9, gate cleared):** signal-not-verdict; **two separable visible inputs, NEVER fused into one score**; identity-agnostic (measure the *work's* attention-vs-relevance, never who wrote it — no author/identity field anywhere); silence-not-a-certificate (the "possibly just low-impact" caveat); pull-not-push; augment-never-filter (never auto-add/drop). Guard tests pin: no composite-score field, no author/identity field, the "possibly low-impact" copy present.
- `ruff check .` + `ruff format --check .`; full `pytest` green per task.
- **Gates:** security audit (new fetch path + job + endpoint), QA route (new `/overlooked/*` + honesty assertions), credit-the-lineage (Matthew-effect refs in `THIRD-PARTY-NOTICES.md`/credit surface), experience pass (corpus-builder persona), increment notes + changes.md + backlog.

---

### Task 1: `fetch_topic_works` on the OpenAlex sources client

**Files:** Modify `integrations/openalex/sources.py`; Test `tests/test_openalex_sources.py`.

**Interfaces:** Produces `OpenAlexSourcesClient.fetch_topic_works(conn, topic_id, *, cap=200) -> list[TopicWork]` where `TopicWork` is a frozen dataclass `{openalex_work_id: str, doi: str|None, title: str|None, year: int|None, cited_by_count: int, abstract: str|None}` (abstract reconstructed from the inverted index). Consumes the existing `self._get(conn, path, params, cache_key, request_json)` + `_TOPIC_RE`.

- [ ] **Step 1: Write the failing test** — an injected fetcher returns two works (one with an `abstract_inverted_index`); assert `fetch_topic_works` returns `TopicWork`s with the reconstructed abstract, cited_by_count, year; a bad `topic_id` (not `^T\d+$`) → `[]`; a fetch failure → `[]`.

```python
def test_fetch_topic_works_reconstructs_abstract_and_metadata(temp_db_url):
    def fake(url, *, params, headers, timeout):
        return 200, {"results": [
            {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/a", "title": "A",
             "publication_year": 2015, "cited_by_count": 3,
             "abstract_inverted_index": {"neural": [0], "nets": [1]}},
        ]}
    from app.backend.persistence.database import make_engine
    from integrations.openalex.sources import OpenAlexSourcesClient
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works = OpenAlexSourcesClient(fetcher=fake).fetch_topic_works(conn, "T42")
    assert len(works) == 1
    w = works[0]
    assert w.openalex_work_id == "W1" and w.doi == "10.1/a" and w.year == 2015 and w.cited_by_count == 3
    assert w.abstract == "neural nets"
    with engine.begin() as conn:
        assert OpenAlexSourcesClient(fetcher=fake).fetch_topic_works(conn, "not-a-topic") == []
    engine.dispose()
```

- [ ] **Step 2: Run → fail** (`AttributeError: fetch_topic_works`). `python -m pytest tests/test_openalex_sources.py -k topic_works -q`.

- [ ] **Step 3: Implement.** Add to `sources.py`:

```python
@dataclass(frozen=True)
class TopicWork:
    openalex_work_id: str
    doi: str | None
    title: str | None
    year: int | None
    cited_by_count: int
    abstract: str | None


def _abstract_from_inverted_index(index) -> str | None:
    """Reconstruct plain abstract text from OpenAlex's {word: [positions]} inverted index; None if absent."""
    if not isinstance(index, dict) or not index:
        return None
    positions: list[tuple[int, str]] = []
    for word, where in index.items():
        if isinstance(where, list):
            positions.extend((int(p), str(word)) for p in where if isinstance(p, int))
    if not positions:
        return None
    return " ".join(word for _p, word in sorted(positions))
```

and the method (mirrors `fetch_candidate_sources`):

```python
    def fetch_topic_works(self, conn: Connection, topic_id: str, *, cap: int = WORKS_SAMPLE) -> list["TopicWork"]:
        """Works whose primary topic is `topic_id`, with citation counts + reconstructed abstracts — the candidate
        pool for the overlooked-work lens. `topic_id` validated `^T\\d+$`. Bounded, cached, fail-closed → []."""
        if not _TOPIC_RE.fullmatch(topic_id or ""):
            return []
        cap = max(1, min(int(cap), WORKS_SAMPLE))
        body = self._get(
            conn,
            "/works",
            {"filter": f"primary_topic.id:{topic_id}", "per-page": str(cap),
             "select": "id,doi,title,publication_year,cited_by_count,abstract_inverted_index"},
            f"topicworks:{topic_id}",
            {"topic_id": topic_id},
        )
        results = (body or {}).get("results") if isinstance(body, dict) else None
        if not isinstance(results, list):
            return []
        out: list[TopicWork] = []
        for w in results:
            if not isinstance(w, dict):
                continue
            wid = str(w.get("id") or "").rsplit("/", 1)[-1]
            if not _WORK_RE.fullmatch(wid):
                continue
            doi = w.get("doi")
            doi = str(doi).replace("https://doi.org/", "").lower() if doi else None
            out.append(TopicWork(
                openalex_work_id=wid, doi=doi, title=w.get("title"),
                year=w.get("publication_year") if isinstance(w.get("publication_year"), int) else None,
                cited_by_count=int(w.get("cited_by_count") or 0),
                abstract=_abstract_from_inverted_index(w.get("abstract_inverted_index")),
            ))
        return out
```

Add `_WORK_RE = re.compile(r"^W\d+$")` near `_TOPIC_RE` (check it isn't already defined). Confirm `re` + `dataclass` are imported.

- [ ] **Step 4: Run → pass.** **Step 5: ruff + `check_line_budget.py`; commit** `feat(openalex): fetch_topic_works for the overlooked-work lens`.

---

### Task 2: The engine — `methods/overlooked.py::compute_overlooked`

**Files:** Create `app/backend/methods/overlooked.py`; Test `tests/test_overlooked.py`.

**Interfaces:**
- Consumes: `OpenAlexSourcesClient.fetch_topic_for_subject`, `.fetch_topic_works` (Task 1); `axis_scoring._embed_axis(conn, axis=…, model=…, vector_store=…) -> list[float]`; `repository.get_axis`, `find_existing_paper_by_identity`; the embed model (`model.encode_texts([str]) -> [[float]]`).
- Produces: `OverlookedCandidate` frozen dataclass `{openalex_work_id, doi, title, authors:list, year, cited_by_count, relevance:float, year_percentile:float|None}` and `compute_overlooked(conn, *, axis_id, sources_client, model, vector_store, cap=25, low_percentile=0.25, min_year_peers=5) -> list[OverlookedCandidate]`.

**The algorithm (the honest v1):** axis label → topic → topic works → exclude in-library (DOI) → relevance = cosine(axis_vector, local-embed(work.abstract or title)) → per-`year` percentile of `cited_by_count` among the fetched works (only where a year has ≥ `min_year_peers`) → keep works with `year_percentile is not None and year_percentile <= low_percentile`, rank by `relevance` desc, cap. Never fuse relevance + percentile into one number.

- [ ] **Step 1: Write the failing tests** (injected fake client + fake embed model, no network):

```python
def test_compute_overlooked_surfaces_relevant_undercited(temp_db_url):
    # 3 same-year works: high-relevance+low-citations (surface), high-relevance+high-citations (drop),
    # low-relevance+low-citations (drop by ranking/relevance). A 4th already-in-library (excluded).
    ...  # concrete body against the fakes below; asserts the surfaced list is [the overlooked one],
        # each carries a relevance AND a year_percentile, and NO composite score / author-identity field.

def test_compute_overlooked_no_percentile_when_too_few_same_year_peers(temp_db_url):
    ...  # a year with < min_year_peers → those works get year_percentile None → not surfaced (honest: can't rank vintage)

def test_compute_overlooked_excludes_in_library(temp_db_url):
    ...  # a candidate whose DOI is already a library paper is dropped
```

with fakes: `class _FakeSources` (`fetch_topic_for_subject` → "T1"; `fetch_topic_works` → the seeded `TopicWork`s) and `class _FakeEmbed` (`encode_texts` returns vectors so the "overlooked" work is nearest the axis vector). (Reuse the `AxisFakeEmbeddingModel`/`InMemoryVectorStore` pattern from `tests/test_axis_scoring.py`.)

- [ ] **Step 2: Run → fail** (module missing).

- [ ] **Step 3: Implement `compute_overlooked`.** Core (full code in the file; key parts):

```python
def compute_overlooked(conn, *, axis_id, sources_client, model, vector_store, cap=25, low_percentile=0.25, min_year_peers=5):
    axis = get_axis(conn, axis_id)  # RowMapping; None → []
    if axis is None:
        return []
    topic_id = sources_client.fetch_topic_for_subject(conn, str(axis["label"] or "").strip())
    if not topic_id:
        return []
    works = sources_client.fetch_topic_works(conn, topic_id)
    works = [w for w in works if not (w.doi and find_existing_paper_by_identity(conn, doi=w.doi) is not None)]
    if not works:
        return []
    axis_vec = _l2(_embed_axis(conn, axis=axis, model=model, vector_store=vector_store))
    # relevance = cosine(axis, local-embed(abstract or title)); NEVER transmit the abstract
    texts = [(w.abstract or w.title or "") for w in works]
    vecs = [_l2(v) for v in model.encode_texts(texts)]
    relevance = {w.openalex_work_id: _cos(axis_vec, v) for w, v in zip(works, vecs)}
    # per-year percentile of cited_by_count among the fetched sample (honest vintage baseline)
    by_year: dict[int, list[int]] = {}
    for w in works:
        if w.year is not None:
            by_year.setdefault(w.year, []).append(w.cited_by_count)
    pct = {}
    for w in works:
        peers = by_year.get(w.year or -1, [])
        pct[w.openalex_work_id] = _percentile_rank(w.cited_by_count, peers) if len(peers) >= min_year_peers else None
    out = [
        OverlookedCandidate(
            openalex_work_id=w.openalex_work_id, doi=w.doi, title=w.title, authors=[], year=w.year,
            cited_by_count=w.cited_by_count, relevance=round(relevance[w.openalex_work_id], 4),
            year_percentile=(round(pct[w.openalex_work_id], 4) if pct[w.openalex_work_id] is not None else None),
        )
        for w in works
        if pct[w.openalex_work_id] is not None and pct[w.openalex_work_id] <= low_percentile
    ]
    out.sort(key=lambda c: -c.relevance)
    return out[:cap]
```

with helpers `_l2` (L2-normalize; reuse `axis_scoring._l2_normalize` or inline), `_cos(a,b)` (dot of normalized), `_percentile_rank(x, peers)` = fraction of peers with `cited_by_count < x` (a value in [0,1]; low = under-cited). `authors=[]` in v1 (identity-agnostic — we do not fetch/store author identity). Import `get_axis`, `find_existing_paper_by_identity`, `_embed_axis`.

- [ ] **Step 4: Run → pass. Step 5: ruff + budget; commit** `feat(methods): compute_overlooked engine (relevance + same-vintage percentile, no score)`.

---

### Task 3: Migration + `overlooked_repo` (the per-axis cache)

**Files:** Create `alembic/versions/0046_overlooked_candidates.py`, `app/backend/persistence/overlooked_repo.py`; Modify `app/backend/persistence/schema_findings.py` (add the table); Test `tests/test_overlooked_repo.py`.

**Interfaces:** Produces `overlooked_candidates` table `(id, axis_id, openalex_work_id, doi, title, year, cited_by_count, relevance REAL, year_percentile REAL nullable, computed_at)` + `replace_overlooked_candidates(conn, axis_id, candidates, *, computed_at)` + `read_overlooked_candidates(conn, axis_id) -> (rows, computed_at|None)` (mirror `gap_repo`). **No author/identity column** (identity-agnostic, structural).

- [ ] **Step 1..5:** failing repo round-trip test (insert → read back the two visible inputs); add the `Table(...)` to `schema_findings.py` on the shared metadata (the inc-137 pattern); the additive guarded migration (`revision="0046_overlooked_candidates"`, `down_revision="0045_cr_candidate_related_papers"`, create-if-not-exists guarded like 0045); the repo functions (mirror `gap_repo.replace_gap_candidates`/`read_gap_candidates`, scoped by `axis_id`). Run the migration on a scratch DB (`alembic -c` scratch ini → stamp 0046). ruff + budget; commit `feat(db): overlooked_candidates cache (migration 0046 + repo)`.

---

### Task 4: Async job + endpoints

**Files:** Create `app/backend/api/routers/overlooked.py`; Modify `app/backend/api/app.py` (JobStore + mount the router); Test `tests/test_overlooked_api.py`.

**Interfaces:** `POST /overlooked/refresh {axis_id}` (202 → job_id), `GET /overlooked/refresh/{job_id}`, `GET /overlooked?axis_id=` (read cache → candidates with the two visible inputs). Mirrors `routers/gaps.py`. The job runs **fetch-outside-lock** (inc D): `sources_client.with_cache_engine(engine)` for the fetch phase on a read connection, then a short `run_write(engine, replace_overlooked_candidates)`.

- [ ] **Step 1..5:** failing endpoint tests (422 on a bad/missing axis_id; a refresh over a seeded axis with `critical_review_deps`-style injected fakes [inject `app.state.openalex_sources_client` + embed model] → job done → `GET /overlooked` returns the candidates, each with `relevance` + `year_percentile`, no `score`/`author` field). Add `app.state.overlooked_jobs = JobStore()` + a `openalex_sources_client` test seam; mount `overlooked.router` beside `gaps.router` in `app.py` (the inc-226 sibling pattern). Add `with_cache_engine` to `OpenAlexSourcesClient` (mirror the inc-D adapter helper) so the fetch phase is lock-free. ruff + budget; commit `feat(#37): overlooked-work endpoints + async job (fetch-outside-lock)`.

---

### Task 5: Frontend — the "Possibly overlooked" panel

**Files:** Create `app/frontend/js/08z_overlooked.jsx`; Modify the axis/discovery surface that hosts it + `styles.css`; Test `tests/test_frontend_assembly.py`.

**Interfaces:** Consumes `POST/GET /overlooked/refresh`, `GET /overlooked?axis_id=`, and the **existing** `/gaps/add` + `/gaps/dismiss` (Add/Dismiss reuse). Per-axis, opened on demand.

- [ ] **Step 1..7:** failing assembly test (built HTML contains `"/overlooked/refresh"`, the two-input copy `"cited"` + `"percentile for"`, `"possibly overlooked"`, and NOT a `"hidden-gem"`/`"score"` label in the panel). Build `08z_overlooked.jsx`: a panel that (per the selected axis) POSTs refresh → polls → renders each candidate with its **two separate** visible inputs (relevance-to-axis + `cited_by N · Nth-percentile for {year}`), title/year, a DOI link, and **Add** (`/gaps/add`) + **Dismiss** (`/gaps/dismiss`); honest empty state ("nothing surfaced — not evidence none exists; low citations can just mean low-impact"). Never a composite score, never auto-add. CSS reuses tokens (read `DESIGN.md`, rule #8). `python tools/build_frontend.py`; assembly test → pass; commit `feat(#37): overlooked-work panel + two-input rows + gap-flow Add/Dismiss`.

---

### Task 6: Gates — security audit + QA route + credit + docs

**Files:** `.claude/security-audits/2026-07-16_overlooked-work-lens.md`, `.claude/qa-routes/route_72_overlooked_work.md`, `THIRD-PARTY-NOTICES.md` (or the in-app credit surface), `.claude/changes.md`, `app/backend/help/help_content.md`, `.claude/docs/increment-notes/INCREMENT-NN-NOTES.md`, `.claude/CLAUDE.md`.

- [ ] **Security audit** (new OpenAlex fetch path + async job + endpoint): topic/work id validation (`^T\d+$`/`^W\d+$`), egress bounded/cached/fail-closed, **no library text transmitted** (only topic label/id; abstracts embedded on-device), resource caps, bound-param SQL, `axis_id` validation. Negative-path checks (bad axis_id → 422; egress-off is N/A — metadata, not the Gemini gate; malformed OpenAlex → fail-closed []). End **PASS**.
- [ ] **QA route 72** (`/overlooked/*` surfaces + honesty assertions: **no composite score**, **no author/identity signal**, signal-not-verdict, provenance one click, silence-not-a-certificate copy). `build_surface_map.py check` → 0 uncovered API.
- [ ] **Credit-the-lineage:** cite the Matthew-effect source (Merton 1968 "The Matthew Effect in Science") + offer it to the library, in-context on the panel (per `.claude/CREDIT-THE-LINEAGE.md`); record in `THIRD-PARTY-NOTICES.md`.
- [ ] `changes.md` + a help section ("Finding overlooked work") + increment notes (bump the number) + CLAUDE test-count/increment. Commit `docs(#37): overlooked-work security audit + QA route 72 + credit + help + notes`.

---

### Task 7: Experience pass + full verification

- [ ] **Experience pass (rule #11):** the **corpus-builder** persona — does the lens help them find overlooked work without moralizing/scoring, with an obvious next step (Add/Dismiss) and the evidence (relevance + percentile) legible? Fix cheap findings in-session; backlog the rest; record in the notes.
- [ ] Full `pytest` green; `ruff check .` + `ruff format --check .`; `check_line_budget.py`; `build_frontend.py` (no diff surprises).
- [ ] Manual verification script (in the notes): select an axis → open "Possibly overlooked" → refresh → confirm rows show the two separate inputs (relevance + citations-vs-vintage), Add imports metadata-only, Dismiss doesn't resurface, the empty/low-peer cases read honestly, and no composite score anywhere.
- [ ] Commit + open the PR.

---

## Self-review

- **Spec coverage:** topic→works ✓ (T1); relevance-by-local-embedding + same-vintage percentile + exclude-in-library ✓ (T2); cache ✓ (T3); job/endpoints fetch-outside-lock ✓ (T4); panel + two visible inputs + gap add/dismiss ✓ (T5); no-score/no-identity honesty pinned by guard tests (T2/T4/T5) + audit/QA (T6); credit-the-lineage ✓ (T6); experience pass ✓ (T7).
- **Placeholder scan:** T2/T3/T4/T5 test bodies are described against named fakes/patterns rather than fully inlined (the fixtures are established in the referenced test files + the fakes are specified); every code step carries complete implementation code. Acceptable — the load-bearing algorithm (T1 reconstruction, T2 compute_overlooked) is fully coded.
- **Type consistency:** `TopicWork` (T1) → consumed by `compute_overlooked` (T2); `OverlookedCandidate` (T2) → persisted by `replace_overlooked_candidates` (T3) → served by the endpoints (T4) → rendered by the panel (T5); the two visible inputs are `relevance` + `year_percentile` throughout; no composite/score field anywhere.
