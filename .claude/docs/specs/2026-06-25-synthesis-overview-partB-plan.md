# Synthesis evidence-traceable Overview (inc 124, Part B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a synthesis is generated and verified, a second LLM pass narrativizes ONLY the verified claims
into a short Overview shown above them, where **each Overview sentence links back to the verified claim(s) it
restates** (per-sentence trace; citations inherited from verified claims, never LLM-invented).

**Architecture:** A new `OverviewGenerator` (Gemini, egress-gated at the inc-58 seam) runs inside
`summarize_scope` after verification; its per-sentence `claim_indices` are validated ⊆ the verified set and mapped
to the verified sentences' ordinals, stored as a new `summaries.overview_json` column, returned on the summary
response, and rendered above the claims in `20_synthesis.jsx` with click-to-scroll-and-flash per-sentence trace.

**Tech Stack:** Python (SQLAlchemy Core, Alembic), Gemini (`google-genai`), React JSX (esbuild), pytest.

## Global Constraints

- **Part B of the inc-123/124 design** (`.claude/docs/specs/2026-06-25-synthesis-overview-design.md` §3). Part A
  (front-matter filter, inc 123) is shipped.
- **Egress (invariant #3):** the Overview pass sends library-derived text (verified claims) → it rides the
  **library egress gate** via `EgressGatedOverviewGenerator`. Egress off → summary generation already raised
  upstream, so the Overview pass is never reached. A generator error is caught → overview `None` (never fails the
  synthesis). **No autonomous real-Gemini call** — the real-output eyeball is the user's to trigger.
- **Traceability, not "unverified blob":** framing is *"Overview — synthesized from the verified claims below"*;
  every Overview sentence carries `claim_ordinals` pointing at the verified claims (which hold quote/page/
  confidence). Citations are **inherited from verified claims, never LLM-invented**; out-of-range refs are dropped.
- **Principles gate (#9): aligned** — traceable-to-evidence, restates only verified claims, secondary/above the
  evidence, egress-gated, omitted when 0 verified. **Audit gate (#5):** open
  `.claude/security-audits/2026-06-25_synthesis-overview.md` (reuses the Gemini provider + egress gate; no new
  external service). **Rule #10:** extend `route_55_synthesis_verification.md`.
- **600-line cap (rule #1):** new generator code in its own modules; `pipeline.py` (~345 after inc 123) and
  `summaries.py` (~356) stay under 600 — re-measure before committing.
- **Build after frontend edits:** `python tools/build_frontend.py`. **Read `.claude/DESIGN.md` before CSS.**
- This is **increment 124**. Commit per task; push at session end on the user's OK.

---

### Task 1: `summaries.overview_json` column (schema + migration)

**Files:**
- Modify: `app/backend/persistence/schema.py` (add the column to the `summaries` Table)
- Create: `alembic/versions/0015_summary_overview.py`
- Test: `tests/test_summary_overview.py` (new)

**Interfaces:**
- Produces: a nullable `summaries.overview_json` JSON column (fresh DBs via `metadata.create_all`; existing DBs
  via migration 0015).

- [ ] **Step 1: Write the failing test** (`tests/test_summary_overview.py`):

```python
from __future__ import annotations

import sqlalchemy as sa

from app.backend.persistence.database import make_engine


def test_summaries_has_overview_json_column(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)  # create_all + alembic upgrade head
    cols = {c["name"] for c in sa.inspect(engine).get_columns("summaries")}
    engine.dispose()
    assert "overview_json" in cols
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_summary_overview.py -q`
Expected: FAIL — `overview_json` not in the column set.

- [ ] **Step 3: Add the column to `schema.py`.** In the `summaries = Table(...)` block (line ~334), after the
  `content` column add:

```python
    Column("overview_json", JSON),  # inc 124: per-sentence traceable Overview [{text, claim_ordinals:[int]}]
```

  (`JSON` is already imported — it's used by `scope_ref_json`.)

- [ ] **Step 4: Create the migration** `alembic/versions/0015_summary_overview.py`:

```python
"""Synthesis Overview (inc 124): a ``summaries.overview_json`` column holding the per-sentence evidence-traceable
Overview — [{text, claim_ordinals:[int]}], narrativizing the verified claims.

Additive + idempotent (like 0002-0014): a fresh DB already has the column from 0001's ``metadata.create_all``, so
the add is guarded and skipped there; an existing DB gets it here.

Revision ID: 0015_summary_overview
Revises: 0014_watched_folders
Create Date: 2026-06-25
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0015_summary_overview"
down_revision = "0014_watched_folders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("summaries")}
    if "overview_json" not in columns:
        op.add_column("summaries", sa.Column("overview_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    # No-op by design (the schema lives in 0001's metadata; downgrades aren't a supported workflow).
    return
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_summary_overview.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/backend/persistence/schema.py alembic/versions/0015_summary_overview.py tests/test_summary_overview.py
git commit -m "feat(synthesis): summaries.overview_json column + migration 0015 (inc 124 t1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: the OverviewGenerator (Protocol + Fake + Gemini) + egress wrapper

**Files:**
- Create: `app/backend/summarization/overview.py` (Protocol + `OverviewSentence` + `FakeOverviewGenerator`)
- Create: `integrations/gemini/overview.py` (`GeminiOverviewGenerator`)
- Modify: `app/backend/llm/egress.py` (`EgressGatedOverviewGenerator`)
- Test: `tests/test_summary_overview.py` (add generator + egress tests)

**Interfaces:**
- Produces:
  - `OverviewSentence = dataclass(text: str, claim_indices: list[int])`
  - `OverviewGenerator` Protocol: `generate(*, verified_claims: list[str], scope_ref: dict[str, object]) -> list[OverviewSentence]`
  - `FakeOverviewGenerator(sentences: list[OverviewSentence], name="fake-overview-generator")`
  - `GeminiOverviewGenerator(config: GeminiConfig, name="gemini-overview-generator")` + `OVERVIEW_PROMPT_VERSION`
  - `EgressGatedOverviewGenerator(inner, data_egress_enabled)` — raises `DataEgressDisabledError` when off.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_summary_overview.py`:

```python
from app.backend.llm.egress import DataEgressDisabledError, EgressGatedOverviewGenerator
from app.backend.summarization.overview import FakeOverviewGenerator, OverviewSentence
from integrations.gemini.overview import GeminiOverviewGenerator, _parse_overview_response
from integrations.gemini.generator import GeminiConfig


def test_fake_overview_generator_returns_sentences() -> None:
    gen = FakeOverviewGenerator(sentences=[OverviewSentence(text="In sum, X.", claim_indices=[0, 1])])
    out = gen.generate(verified_claims=["claim a", "claim b"], scope_ref={})
    assert out == [OverviewSentence(text="In sum, X.", claim_indices=[0, 1])]


def test_egress_gate_blocks_overview_when_disabled() -> None:
    gated = EgressGatedOverviewGenerator(inner=FakeOverviewGenerator(sentences=[]), data_egress_enabled=False)
    try:
        gated.generate(verified_claims=["a"], scope_ref={})
        raised = False
    except DataEgressDisabledError:
        raised = True
    assert raised


def test_egress_gate_delegates_when_enabled() -> None:
    inner = FakeOverviewGenerator(sentences=[OverviewSentence(text="Y.", claim_indices=[0])])
    gated = EgressGatedOverviewGenerator(inner=inner, data_egress_enabled=True)
    assert gated.generate(verified_claims=["a"], scope_ref={}) == inner.sentences


def test_parse_overview_response_drops_malformed_items() -> None:
    raw = '[{"text":"A.","claim_indices":[0,1]},{"text":"","claim_indices":[0]},{"claim_indices":[2]},'\
          '{"text":"B.","claim_indices":"nope"},{"text":"C.","claim_indices":[1,"x",2]}]'
    out = _parse_overview_response(raw)
    # kept: "A." (valid) and "C." (non-int refs dropped, leaving [1,2]); dropped: empty text, missing text,
    # non-list claim_indices.
    assert [s.text for s in out] == ["A.", "C."]
    assert out[1].claim_indices == [1, 2]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_summary_overview.py -q`
Expected: FAIL — modules/classes not defined.

- [ ] **Step 3: Implement `app/backend/summarization/overview.py`:**

```python
"""Overview generation interfaces (inc 124).

A second pass that narrativizes the ALREADY-VERIFIED claims of a synthesis into a short Overview, where each
Overview sentence carries the indices of the verified claims it restates (per-sentence evidence trace). The
Overview is traceable-to-evidence, not authoritative: it works only from the verified claims and adds no new
facts; its citations are inherited from those claims (never LLM-invented).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OverviewSentence:
    text: str
    claim_indices: list[int]  # indices into the ordered ``verified_claims`` passed to generate()


class OverviewGenerator(Protocol):
    name: str

    def generate(
        self, *, verified_claims: list[str], scope_ref: dict[str, object]
    ) -> list[OverviewSentence]:
        """Return Overview sentences, each tagged with the verified-claim indices it restates."""


@dataclass(frozen=True)
class FakeOverviewGenerator:
    sentences: list[OverviewSentence]
    name: str = "fake-overview-generator"

    def generate(
        self, *, verified_claims: list[str], scope_ref: dict[str, object]
    ) -> list[OverviewSentence]:
        return list(self.sentences)
```

- [ ] **Step 4: Implement `integrations/gemini/overview.py`** (mirrors `research_summary.py`):

```python
"""Gemini-backed Overview generation (inc 124), egress-gated.

Narrativizes the verified claims of a synthesis into a short Overview, returning per-sentence claim references
(an evidence trace). Sends library-derived text (the verified claims), so — like summary/research-summary
generation — it is gated at the inc-58 seam and only runs with explicit data-egress consent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.backend.llm.usage import log_usage
from app.backend.summarization.overview import OverviewSentence
from integrations.gemini.generator import DataEgressDisabledError, GeminiConfig

# Part of nothing cached yet, but versioned for a future cache key (cf. SUMMARY_PROMPT_VERSION).
OVERVIEW_PROMPT_VERSION = "overview-v1"
MAX_CLAIMS = 40  # cap how many verified claims we send
MAX_CLAIM_CHARS = 400  # truncate each claim
MAX_OVERVIEW_SENTENCES = 6  # defensively cap returned sentences (untrusted output)
MAX_SENTENCE_CHARS = 400


@dataclass(frozen=True)
class GeminiOverviewGenerator:
    config: GeminiConfig
    name: str = "gemini-overview-generator"

    def generate(self, *, verified_claims: list[str], scope_ref: dict[str, object]) -> list[OverviewSentence]:
        if not self.config.data_egress_enabled:
            raise DataEgressDisabledError("Gemini overview generation requires explicit data-egress consent.")
        from google import genai

        client = genai.Client(api_key=self.config.resolved_api_key())
        response = client.models.generate_content(
            model=self.config.model, contents=_prompt(verified_claims)
        )
        log_usage("overview", self.config.model, response)
        return _parse_overview_response(str(response.text or "[]"))


def _prompt(verified_claims: list[str]) -> str:
    items = [
        {"index": i, "claim": str(c).strip()[:MAX_CLAIM_CHARS]}
        for i, c in enumerate(verified_claims[:MAX_CLAIMS])
        if str(c).strip()
    ]
    return (
        "You are given NUMBERED claims that have ALREADY been verified against source papers. Write a brief "
        "overview (2-4 sentences) synthesizing them for a reader. Return JSON ONLY: an array of objects "
        '{"text": <sentence>, "claim_indices": [<the index numbers of the claims that sentence restates>]}. '
        "Use ONLY information in the listed claims; introduce NO new facts, numbers, names, or citations. Every "
        "sentence must restate one or more of the numbered claims and list their indices.\n"
        f"Claims (JSON): {json.dumps(items, ensure_ascii=True)}"
    )


def _parse_overview_response(text: str) -> list[OverviewSentence]:
    payload = json.loads(_strip_code_fence(text))
    out: list[OverviewSentence] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        sentence = str(item.get("text") or "").strip()[:MAX_SENTENCE_CHARS]
        refs = item.get("claim_indices")
        if not sentence or not isinstance(refs, list):
            continue
        indices = [int(r) for r in refs if isinstance(r, bool) is False and isinstance(r, int)]
        out.append(OverviewSentence(text=sentence, claim_indices=indices))
    return out[:MAX_OVERVIEW_SENTENCES]


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped
```

  Note: `isinstance(r, bool) is False and isinstance(r, int)` excludes JSON `true`/`false` (which are `int`
  subclasses in Python) from claim indices.

- [ ] **Step 5: Add `EgressGatedOverviewGenerator` to `app/backend/llm/egress.py`** — under `TYPE_CHECKING` add
  `from app.backend.summarization.overview import OverviewGenerator, OverviewSentence`, and add the wrapper after
  `EgressGatedResearchSummaryGenerator`:

```python
@dataclass(frozen=True)
class EgressGatedOverviewGenerator:
    """Egress gate around an ``OverviewGenerator`` (inc 124). It narrativizes the verified claims (library-derived
    text), so it rides the library egress gate."""

    inner: "OverviewGenerator"
    data_egress_enabled: bool

    @property
    def name(self) -> str:
        return self.inner.name

    def generate(self, *, verified_claims: list[str], scope_ref: dict[str, object]) -> list["OverviewSentence"]:
        if not self.data_egress_enabled:
            raise DataEgressDisabledError("Gemini overview generation requires explicit data-egress consent.")
        return self.inner.generate(verified_claims=verified_claims, scope_ref=scope_ref)
```

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_summary_overview.py -q`
Expected: PASS (column test + 4 generator/egress/parse tests).

- [ ] **Step 7: Commit**

```bash
git add app/backend/summarization/overview.py integrations/gemini/overview.py app/backend/llm/egress.py tests/test_summary_overview.py
git commit -m "feat(synthesis): OverviewGenerator + Gemini impl + egress gate (inc 124 t2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: wire the Overview pass into `summarize_scope`

**Files:**
- Modify: `app/backend/summarization/pipeline.py`
- Test: `tests/test_summary_overview.py` (add a pipeline storage test)

**Interfaces:**
- Consumes: `OverviewGenerator` (Task 2); the `summaries` row's new `overview_json` (Task 1).
- Produces: `summarize_scope(..., overview_generator: OverviewGenerator | None = None)` storing
  `summaries.overview_json = [{"text": str, "claim_ordinals": [int]}]` (the verified sentences' ordinals).

- [ ] **Step 1: Write the failing test** — append to `tests/test_summary_overview.py`:

```python
from sqlalchemy import select as _select

from app.backend.embeddings.models import EmbeddingModel  # noqa: F401  (types only in comments)
from app.backend.persistence.database import make_engine as _make_engine
from app.backend.persistence.schema import summaries as _summaries
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence
from app.backend.summarization.pipeline import SummaryScope, summarize_scope
from tests.api_helpers import ApiFakeEmbeddingModel, ConstantSupportScorer, InMemoryVectorStore
from tests.test_summarize_selected import _seed_two_papers_two_chunks  # reuse the multi-paper fixture
from app.backend.summarization.generators import FakeSummaryGenerator


def _overview_for(db_url: str, *, overview_gen) -> list | None:
    seed = _seed_two_papers_two_chunks(db_url)
    sgen = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Cortex is discussed.",
                citations=[CandidateCitation(chunk_id=seed["a1"], quote="Paper A chunk 1 discusses cortex.")],
            )
        ]
    )
    engine = _make_engine(db_url)
    with engine.begin() as conn:
        result = summarize_scope(
            conn,
            scope=SummaryScope(scope_type="papers", paper_ids=[seed["pa"], seed["pb"]]),
            generator=sgen,
            model=ApiFakeEmbeddingModel(),
            vector_store=InMemoryVectorStore(),
            support_scorer=ConstantSupportScorer(),
            top_k=4,
            overview_generator=overview_gen,
        )
        row = conn.execute(
            _select(_summaries.c.overview_json).where(_summaries.c.id == result.summary_id)
        ).scalar_one()
    engine.dispose()
    return row


def test_overview_stored_with_mapped_ordinals(temp_db_url: str) -> None:
    gen = FakeOverviewGenerator(sentences=[OverviewSentence(text="In sum, cortex matters.", claim_indices=[0])])
    overview = _overview_for(temp_db_url, overview_gen=gen)
    assert overview == [{"text": "In sum, cortex matters.", "claim_ordinals": [0]}]


def test_overview_drops_out_of_range_claim_indices(temp_db_url: str) -> None:
    # index 5 doesn't exist (only 1 verified claim, ordinal 0) → dropped; a sentence left with no valid refs is
    # dropped entirely.
    gen = FakeOverviewGenerator(
        sentences=[
            OverviewSentence(text="Valid.", claim_indices=[0, 5]),
            OverviewSentence(text="All bad refs.", claim_indices=[9]),
        ]
    )
    overview = _overview_for(temp_db_url, overview_gen=gen)
    assert overview == [{"text": "Valid.", "claim_ordinals": [0]}]


def test_no_overview_generator_leaves_overview_null(temp_db_url: str) -> None:
    assert _overview_for(temp_db_url, overview_gen=None) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_summary_overview.py -k overview -q`
Expected: FAIL — `summarize_scope` has no `overview_generator` parameter.

- [ ] **Step 3: Implement the pass in `pipeline.py`.** Add the import:

```python
from app.backend.summarization.overview import OverviewGenerator
```

  Add `overview_generator` to the `summarize_scope` signature (after `support_scorer`):

```python
    support_scorer: SupportScorer | None = None,
    overview_generator: OverviewGenerator | None = None,
) -> SummaryPersistenceResult:
```

  After the `sentence_results` loop completes and before the `return`, insert:

```python
    _maybe_store_overview(
        conn,
        summary_id=summary_id,
        sentence_results=sentence_results,
        scope=scope,
        overview_generator=overview_generator,
    )
```

  Add the helper near `_insert_summary` (use `sqlalchemy.update`, already importable):

```python
def _maybe_store_overview(
    conn: Connection,
    *,
    summary_id: int,
    sentence_results: list[SummarySentencePersistenceResult],
    scope: SummaryScope,
    overview_generator: OverviewGenerator | None,
) -> None:
    """Second pass: narrativize ONLY the verified claims into a per-sentence traceable Overview. Each Overview
    sentence's claim_indices (into the ordered verified claims) are validated and mapped to those claims'
    ordinals, then stored on summaries.overview_json. 0 verified claims → no overview; any error → no overview
    (never fails the synthesis)."""
    if overview_generator is None:
        return
    verified = [s for s in sentence_results if not s.flagged]
    if not verified:
        return
    claims = [s.text for s in verified]
    try:
        produced = overview_generator.generate(verified_claims=claims, scope_ref=scope.to_ref())
    except Exception:
        return  # egress-off or any generator failure → leave overview NULL; the verified claims stand alone
    items: list[dict[str, object]] = []
    for sentence in produced:
        ordinals = sorted({verified[i].ordinal for i in sentence.claim_indices if 0 <= i < len(verified)})
        if sentence.text.strip() and ordinals:
            items.append({"text": sentence.text.strip(), "claim_ordinals": ordinals})
    if items:
        conn.execute(update(summaries).where(summaries.c.id == summary_id).values(overview_json=items))
```

  Add `update` to the sqlalchemy import at the top: `from sqlalchemy import Connection, insert, select, update`.

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_summary_overview.py -q`
Expected: PASS (all column/generator/pipeline tests).

- [ ] **Step 5: Re-measure `pipeline.py`** (rule #1).

Run: `wc -l app/backend/summarization/pipeline.py`
Expected: < 600 (≈ 370). If ≥ 600, STOP and report.

- [ ] **Step 6: Commit**

```bash
git add app/backend/summarization/pipeline.py tests/test_summary_overview.py
git commit -m "feat(synthesis): wire the Overview pass into summarize_scope (inc 124 t3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: response field + router/create_app injection

**Files:**
- Modify: `app/backend/api/routers/summaries.py` (response model + `_persisted_summary_response` + `_overview_generator` + pass into `summarize_scope`)
- Modify: `app/backend/api/app.py` (`overview_generator` param + state)
- Modify: `tests/api_helpers.py` (`_summarization_app` accepts `overview_generator`)
- Test: `tests/test_summary_overview.py` (end-to-end via TestClient)

**Interfaces:**
- Consumes: `summarize_scope(..., overview_generator=...)` (Task 3); `summaries.overview_json` (Task 1).
- Produces: `SummarizeJobResponse.overview: list[OverviewItemResponse] | None`, `OverviewItemResponse = {text:
  str, claim_ordinals: list[int]}`; `create_app(overview_generator=None)`; `_summarization_app(...,
  overview_generator=None)`.

- [ ] **Step 1: Write the failing end-to-end test** — append to `tests/test_summary_overview.py`:

```python
from fastapi.testclient import TestClient
from tests.api_helpers import _summarization_app


def test_summary_response_includes_traceable_overview(temp_db_url: str) -> None:
    seed = _seed_two_papers_two_chunks(temp_db_url)
    sgen = FakeSummaryGenerator(
        sentences=[
            CandidateSummarySentence(
                text="Cortex is discussed.",
                citations=[CandidateCitation(chunk_id=seed["a1"], quote="Paper A chunk 1 discusses cortex.")],
            )
        ]
    )
    ogen = FakeOverviewGenerator(sentences=[OverviewSentence(text="In sum, cortex.", claim_indices=[0])])
    client = TestClient(_summarization_app(temp_db_url, generator=sgen, overview_generator=ogen))

    started = client.post(
        "/summarize", json={"scope_type": "papers", "paper_ids": [seed["pa"], seed["pb"]], "top_k": 4}
    )
    result = client.get(f"/summarize/{started.json()['job_id']}").json()

    assert started.status_code == 202
    assert result["status"] == "done"
    assert result["overview"] == [{"text": "In sum, cortex.", "claim_ordinals": [0]}]
    # the trace target exists: a verified sentence at ordinal 0
    assert any(s["ordinal"] == 0 and not s["flagged"] for s in result["sentences"])
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_summary_overview.py::test_summary_response_includes_traceable_overview -q`
Expected: FAIL — `_summarization_app` has no `overview_generator` kwarg / no `overview` in the response.

- [ ] **Step 3: `summaries.py` — add the response model** (after `SummarySentenceResponse`):

```python
class OverviewItemResponse(BaseModel):
    text: str
    claim_ordinals: list[int]  # ordinals of the verified sentences this Overview sentence restates
```

  Add `overview` to `SummarizeJobResponse`:

```python
    sentences: list[SummarySentenceResponse] | None = None
    overview: list[OverviewItemResponse] | None = None
```

  In `_persisted_summary_response`, read it from the summary row and pass it through:

```python
    overview_raw = summary["overview_json"] if "overview_json" in summary else None
    overview = (
        [OverviewItemResponse(text=str(i["text"]), claim_ordinals=[int(o) for o in i["claim_ordinals"]])
         for i in overview_raw if isinstance(i, dict) and i.get("text") and isinstance(i.get("claim_ordinals"), list)]
        if isinstance(overview_raw, list) else None
    )
    return SummarizeJobResponse(
        job_id=job_id,
        status="done",
        summary_id=summary_id,
        summary_status=summary["status"],
        sentences=[_summary_sentence_response(conn, sentence) for sentence in sentence_rows],
        overview=overview,
    )
```

  Add the `_overview_generator` factory (mirrors `_summary_generator`), after `_summary_generator`:

```python
def _overview_generator(api: FastAPI):
    from app.backend.llm.egress import EgressGatedOverviewGenerator
    from integrations.gemini.overview import GeminiOverviewGenerator

    inner = api.state.overview_generator
    if inner is None:
        config = GeminiConfig.from_environment()
        if not (config.data_egress_enabled and config.resolved_api_key()):
            return None  # no overview without egress + a key; the verified claims stand alone
        inner = GeminiOverviewGenerator(config=config)
    return EgressGatedOverviewGenerator(
        inner=inner, data_egress_enabled=GeminiConfig.from_environment().data_egress_enabled
    )
```

  In `_run_summarize_job`, pass it into `summarize_scope`:

```python
            result = summarize_scope(
                conn,
                scope=_summary_scope_from_request(request),
                generator=generator,
                model=model,
                vector_store=store,
                top_k=request.top_k,
                verifier_config=config,
                support_scorer=support_scorer,
                overview_generator=_overview_generator(api),
            )
```

- [ ] **Step 4: `app.py` — add the injection seam.** Add the param to `create_app` (after
  `research_summary_generator`, line ~71):

```python
    overview_generator: OverviewGenerator | None = None,
```

  Add the import near the other summarization imports (top of app.py) — `from
  app.backend.summarization.overview import OverviewGenerator` (under TYPE_CHECKING if the file uses that
  pattern; otherwise a plain import is fine). Add the state line (after `research_summary_generator`, line ~114):

```python
    api.state.overview_generator = overview_generator
```

- [ ] **Step 5: `tests/api_helpers.py` — thread the fake.** Update `_summarization_app`:

```python
def _summarization_app(temp_db_url: str, *, generator: FakeSummaryGenerator | None = None, overview_generator=None):
    if generator is None:
        generator = FakeSummaryGenerator(sentences=[])
    return create_app(
        db_url=temp_db_url,
        summary_generator=generator,
        overview_generator=overview_generator,
        embedding_model=ApiFakeEmbeddingModel(),
        vector_store=InMemoryVectorStore(),
        support_scorer=ConstantSupportScorer(),
    )
```

- [ ] **Step 6: Run the test + the existing summary tests**

Run: `python -m pytest tests/test_summary_overview.py tests/test_summarize_selected.py tests/test_summaries.py -q`
Expected: PASS (the new e2e test + all existing — the `overview` field defaults to `None`/absent when no
overview generator is injected, so existing tests are unaffected).

- [ ] **Step 7: Re-measure `summaries.py`** (rule #1): `wc -l app/backend/api/routers/summaries.py` → < 600.

- [ ] **Step 8: Commit**

```bash
git add app/backend/api/routers/summaries.py app/backend/api/app.py tests/api_helpers.py tests/test_summary_overview.py
git commit -m "feat(synthesis): expose traceable Overview on the summary response + inject generator (inc 124 t4)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: frontend — render the Overview with per-sentence trace links

**Files:**
- Modify: `app/frontend/js/20_synthesis.jsx`
- Modify: `app/frontend/styles.css` (read DESIGN.md first)
- Regenerate: `callosum-app.html`
- Test: headed Playwright with a seeded overview (no egress)

**Interfaces:**
- Consumes: the summary response's `overview` (`[{text, claim_ordinals}]`) and `sentences` (each with `ordinal`,
  `sentence_id`).

- [ ] **Step 1: Read `.claude/DESIGN.md`** (rule #8) — pick existing tokens/recipes for the Overview block
  (muted panel + eyebrow label) and a flash highlight; no new raw hex.

- [ ] **Step 2: Add an Overview component + per-sentence trace.** In `20_synthesis.jsx`, add a helper to flash a
  claim by ordinal and an `OverviewBlock`, then render it above `GroupedSummarySentences`.

  Add the flash helper (module scope, near the top of the file):

```jsx
// inc 124: scroll to + briefly flash the verified claim(s) an Overview sentence traces to (by ordinal).
function flashClaims(ordinals) {
  (ordinals || []).forEach((ord, idx) => {
    const el = document.getElementById("summary-claim-" + ord);
    if (!el) return;
    if (idx === 0) el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("claim-flash");
    setTimeout(() => el.classList.remove("claim-flash"), 1400);
  });
}

function OverviewBlock({ overview }) {
  if (!overview || overview.length === 0) return null;
  return (
    <section className="synth-overview">
      <p className="eyebrow">Overview — synthesized from the verified claims below</p>
      {overview.map((item, i) => (
        <button key={i} className="overview-line" title="Show the verified claim(s) this restates"
          onClick={() => flashClaims(item.claim_ordinals)}>
          {item.text}
          <span className="overview-trace">
            {(item.claim_ordinals || []).map(o => "[" + (o + 1) + "]").join(" ")}
          </span>
        </button>
      ))}
    </section>
  );
}
```

  In `SynthesisPane`'s `state.status === "done"` block, render the Overview **above** the grouped sentences
  (only when there are sentences). Replace the line that renders `GroupedSummarySentences`:

```jsx
          {sentences.length > 0 && <OverviewBlock overview={state.result.overview} />}
          {sentences.length > 0 && <GroupedSummarySentences sentences={sentences} onOpenCitation={onOpenCitation} onSaveHighlight={onSaveHighlight} />}
```

  Give each rendered claim an anchor id keyed on its ordinal — in `SummarySentence`, add `id` to the wrapper:

```jsx
    <div id={"summary-claim-" + sentence.ordinal} className={"summary-sentence " + (flagged ? "flagged" : "verified")}>
```

- [ ] **Step 3: Add CSS** (`styles.css`, tokens only — confirm names against DESIGN.md):

```css
.synth-overview { margin: 10px 0 14px; padding: 10px 12px; background: var(--panel-2); border: 1px solid var(--line); border-radius: var(--radius-sm); }
.overview-line { display: block; width: 100%; text-align: left; background: none; border: none; padding: 4px 0; color: var(--ink); font-size: 13px; line-height: 1.5; cursor: pointer; }
.overview-line:hover { color: var(--accent); }
.overview-trace { margin-left: 6px; font-family: var(--mono); font-size: 10.5px; color: var(--ink-3); }
.summary-sentence.claim-flash { box-shadow: 0 0 0 2px var(--accent); border-radius: var(--radius-sm); transition: box-shadow .2s; }
```

  (If any token name above isn't in DESIGN.md, substitute the correct existing token — do NOT introduce a new
  raw hex.)

- [ ] **Step 4: Rebuild + assembly test.**

Run: `python tools/build_frontend.py && python -m pytest tests/test_frontend_assembly.py -q`
Expected: build OK; 5 assembly tests pass.

- [ ] **Step 5: Headed Playwright verification (no egress) via a seeded overview.** Write
  `.local/visual/drive_inc124_overview.py`: seed a DB (reuse `_seed_two_papers_two_chunks`-style + insert a
  `summaries` row with `overview_json=[{"text":"In sum, cortex.","claim_ordinals":[0]}]`, a verified
  `summary_sentences` row at ordinal 0, and its citation rows), start uvicorn on a free port against that DB,
  open the synthesis history, load the seeded summary, and assert: the `.synth-overview` block renders above the
  claims with the "synthesized from the verified claims below" label; clicking `.overview-line` adds
  `.claim-flash` to `#summary-claim-0`; 0 console/page errors; 0 genai requests. (Backed by the Task-4 e2e test,
  this is the visual confirmation.) Screenshot to `.local/visual/inc124/`.

  Run: `python .local/visual/drive_inc124_overview.py` → Expected: `PASS`.

- [ ] **Step 6: Commit**

```bash
git add app/frontend/js/20_synthesis.jsx app/frontend/styles.css callosum-app.html
git commit -m "feat(synthesis): render the evidence-traceable Overview with per-sentence claim links (inc 124 t5)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: audit + Principles + QA route + docs + final verification

**Files:**
- Create: `.claude/security-audits/2026-06-25_synthesis-overview.md`
- Modify: `.claude/qa-routes/route_55_synthesis_verification.md`
- Modify: `app/backend/help/help_content.md` (synthesis section)
- Create: `.claude/docs/increment-notes/INCREMENT-124-NOTES.md`
- Modify: `.claude/changes.md`, `RECOVERY-LOG.md`, `.claude/CLAUDE.md`

- [ ] **Step 1: Security audit** — write `.claude/security-audits/2026-06-25_synthesis-overview.md`: threat review
  (input = verified claims [library-derived] → rides the egress gate; no new external service; untrusted model
  output is parsed defensively, claim refs validated ⊆ verified set, sentence/claim counts + chars capped;
  egress-off → no overview, never a 503; no file/path/SQL surface — bound-param `update`). Run the negative-path
  checks (egress-off → overview NULL [the Task-3 test]; malformed/over-range refs dropped [Task-2/3 tests]).
  End with **Security Audit: PASS**.

- [ ] **Step 2: Principles note** — append a short alignment note to the audit (or the increment notes): aligned
  (traceable-to-evidence, restates only verified claims, citations inherited, secondary/above evidence,
  egress-gated, omitted when 0 verified); the declined easy path (authoritative prose eclipsing the evidence).

- [ ] **Step 3: QA route** — extend `.claude/qa-routes/route_55_synthesis_verification.md`: add the `overview`
  surface to its coverage + steps asserting (a) the Overview renders above the verified claims with the
  "synthesized from the verified claims below" framing; (b) each Overview line traces to ≥1 verified claim
  (click → the claim flashes); (c) with egress unset, no overview is produced and the verified claims stand
  alone; (d) signal-not-verdict: the Overview never presents a claim the verified set doesn't support.

- [ ] **Step 4: Regenerate surface map + check.**

Run: `python tools/qa/build_surface_map.py extract && python tools/qa/build_surface_map.py check`
Expected: exit 0 (the `/summarize*` API surface is unchanged — same endpoints; the `overview` field is part of
the existing response; FE additions are covered by route_55).

- [ ] **Step 5: Help corpus** — in `app/backend/help/help_content.md`, in the synthesis section, add a short
  paragraph: a synthesis now shows an **Overview** above the verified claims — a plain-language synthesis of the
  verified claims, where each Overview line links to the claim(s) it restates; it only appears with data-egress
  enabled and only restates verified claims. Move the `HELP-DOCS-SYNCED` marker forward to inc 124.

- [ ] **Step 6: Increment notes** — `.claude/docs/increment-notes/INCREMENT-124-NOTES.md` (Implemented / Key
  technical detail [second pass over verified claims only; per-sentence claim_indices validated ⊆ verified set →
  mapped to ordinals → overview_json; egress-gated; 0-verified→none; frontend flash-by-ordinal] / Manual
  verification [the Task-5 headed script + the note that real-prose quality needs egress] / Pytest count).

- [ ] **Step 7: `changes.md`** (top entry, move `HELP-DOCS-SYNCED` here), **`RECOVERY-LOG.md`** (one line, real
  timestamp + commit hashes), **`CLAUDE.md`** (bump "Increment 124" + footer block; demote inc 123 to "Earlier";
  note the My-Pubs-style egress posture + the per-sentence trace; mention the migration head is now 0015).

- [ ] **Step 8: Final verification.**

Run: `ruff check . && ruff format --check . && python -m pytest -q`
Expected: ruff clean; pytest PASS (record the count). If `ruff format` reformats new files, apply it and include
in the commit.

- [ ] **Step 9: Commit**

```bash
git add .claude/security-audits/2026-06-25_synthesis-overview.md .claude/qa-routes/route_55_synthesis_verification.md \
  app/backend/help/help_content.md .claude/docs/increment-notes/INCREMENT-124-NOTES.md .claude/changes.md \
  RECOVERY-LOG.md .claude/CLAUDE.md
git commit -m "docs(synthesis): inc 124 audit/QA/help/notes/changes/RECOVERY-LOG/CLAUDE (Part B)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage** (design §3): OverviewGenerator+Gemini+egress → Task 2; second pass narrativizing verified
claims, per-sentence claim_indices validated+mapped → Task 3; `summaries.overview_json` migration → Task 1;
response field + injection → Task 4; frontend render above claims + per-sentence trace flash + "synthesized from
the verified claims below" framing → Task 5; Principles/audit/rule-#10/help → Task 6; egress-gated + 0-verified→
none + inherited-not-invented citations → Tasks 3/4 + tests. ✔

**Placeholder scan:** all new modules shown in full; diffs show exact insertion points + code; the only run-time
values are the pytest count + RECOVERY-LOG timestamp/hashes (resolved at execution). The CSS token names carry an
explicit "substitute the correct DESIGN.md token if a name differs" guard. ✔

**Type/name consistency:** `OverviewSentence{text, claim_indices}` (Task 2) consumed in Task 3's mapping;
`OverviewGenerator.generate(*, verified_claims, scope_ref)` consistent across Fake/Gemini/EgressGated/pipeline;
`summaries.overview_json` shape `[{text, claim_ordinals}]` consistent across Task 3 storage, Task 4 response
(`OverviewItemResponse{text, claim_ordinals}`), and Task 5 frontend (`item.text`, `item.claim_ordinals`); the
frontend anchor `#summary-claim-<ordinal>` matches `flashClaims`. ✔
