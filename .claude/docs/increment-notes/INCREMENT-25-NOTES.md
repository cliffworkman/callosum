# Increment 25 Notes

## Implemented

- Added a Synthesis tab to the existing right pane in `callosum-app.html`.
- Preserved the existing paper detail pane as a sibling Detail tab.
- Added a query-scoped synthesis workflow:
  - `POST /summarize` with `{ "scope_type": "query", "query": str, "top_k": 8 }`
  - Polls `GET /summarize/{job_id}` until `done` or `error`
  - Shows a non-frozen `Generating and verifying` state while polling
  - Shows backend error details directly when a job fails
- Rendered completed summaries sentence-by-sentence, with visible `verified` vs `flagged` badges.
- Rendered click-open provenance cards for each citation, including paper title, page, quote, citation status, and the three confidence components.

## API Field Mapping

The frontend uses the accepted Increment 24 field names directly:

- Start request: `scope_type`, `query`, `top_k`
- Job status: `job_id`, `status`, `detail`, `summary_id`, `summary_status`, `sentences`
- Sentence fields: `sentence_id`, `ordinal`, `text`, `flagged`, `citations`
- Citation fields: `mapping_id`, `evidence_quote_id`, `chunk_id`, `paper_id`, `paper_title`, `page_start`, `page_end`, `quote`, `retrieval_confidence`, `quote_confidence`, `support_confidence`, `status`, `coordinate_precision`, `bbox_json`

## Coordinate Honesty

- `coordinate_precision === "exact"` renders as `exact quote coordinates`.
- `coordinate_precision === "region"` renders as `region-level · precise highlight pending` and includes a warning that it must not be treated as an exact quote highlight.
- `coordinate_precision == null` renders as `no coordinate claim`.
- Citation status is shown separately from coordinate precision, so a non-verified citation cannot be mistaken for a verified exact source.

## Loading And Error Handling

- The Synthesize button is disabled when the query is empty or a job is running.
- Polling runs every ~1.2 seconds while a job is pending/running.
- `status: "error"` displays the backend `detail`, including egress/API-key failures.
- A completed summary with zero sentences renders `No groundable summary produced`.
- All-flagged summaries are rendered with flagged badges; flagged content is not hidden.

## Static Verification

I launched the app through FastAPI using the existing local validation database:

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8768
```

Then opened:

```text
http://127.0.0.1:8768/
```

Playwright result: page title `Callosum`, existing library panes loaded, Synthesis/Detail right-pane tabs present, and `0` console errors. The only console warning was the existing Babel standalone development warning.

## Manual Verification Script

Real Gemini/NLI path:

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
$env:CALLOSUM_ALLOW_DATA_EGRESS = "true"
$env:GOOGLE_API_KEY = "<your key>"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

1. Open `http://127.0.0.1:8080/`.
2. Confirm the library list and axes load.
3. In the Synthesis tab, enter a query such as `What does this library say about facial anomalies and social judgments?`.
4. Click `Synthesize`.
5. Confirm the UI shows `Generating and verifying` while polling.
6. When done, confirm verified sentences have green `verified` badges and flagged sentences have amber `flagged` badges.
7. Open citation cards and confirm each shows paper title, page, quote, retrieval/quote/support scores, citation status, and exact/region/null coordinate precision.
8. Confirm region-level citations explicitly say precise highlight is pending and are not presented as exact quote highlights.

Egress-disabled path:

```powershell
Remove-Item Env:CALLOSUM_ALLOW_DATA_EGRESS -ErrorAction SilentlyContinue
Remove-Item Env:GOOGLE_API_KEY -ErrorAction SilentlyContinue
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```

Run a query and confirm the Synthesis tab displays the backend error message instead of spinning forever.

Fake generator path for frontend development, with no Gemini call and no model download:

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
@'
from dataclasses import dataclass
import os

import uvicorn
from sqlalchemy import select

from app.backend.api.app import create_app
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import chunks
from app.backend.summarization.generators import CandidateCitation, CandidateSummarySentence, FakeSummaryGenerator

@dataclass(frozen=True)
class DemoEmbeddingModel:
    name: str = "demo-constant"
    version: str = "v1"
    dimension: int = 3
    normalization: str = DEFAULT_NORMALIZATION
    def encode_texts(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

@dataclass(frozen=True)
class ConstantSupportScorer:
    def score(self, *, sentence, passage):
        return 1.0

engine = make_engine(os.environ["CALLOSUM_DB_URL"])
with engine.connect() as conn:
    row = conn.execute(select(chunks.c.id, chunks.c.text).order_by(chunks.c.id).limit(1)).mappings().one()

quote = row["text"].split(".")[0].strip() + "."
generator = FakeSummaryGenerator([
    CandidateSummarySentence(
        text="This demo sentence is grounded in the first available chunk.",
        citations=[CandidateCitation(chunk_id=int(row["id"]), quote=quote)],
    )
])

app = create_app(
    summary_generator=generator,
    embedding_model=DemoEmbeddingModel(),
    vector_store=InMemoryVectorStore(),
    support_scorer=ConstantSupportScorer(),
)
uvicorn.run(app, host="127.0.0.1", port=8080)
'@ | python -
```

Then open `http://127.0.0.1:8080/`, run any synthesis query, and confirm the fake verified result renders with a provenance card. To test flagged rendering, change `quote = ...` to a fabricated quote that is not present in the selected chunk and rerun the same script.

## Deferred

- PDF rendering and bbox overlay highlighting.
- Paper/cluster-scoped controls in the frontend.
- Persisted summary read-back UI.
- Any backend or response-model changes.
