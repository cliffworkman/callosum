"""POST /citations/classify-stance (inc 461, backlog #33/#34 P2 #20): pairwise stance classification for the
LibreOffice "Insert evidence…" command's claim-check. Split from test_citations_suggest.py -- a new sibling
router, not a change to /citations/suggest itself. Uses fakes (never loads the real NLI model, same discipline
as test_citations_suggest.py's FakeStanceScorer) so this suite stays fast and hermetic.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.summarization.verification import Stance


@dataclass
class _FakeStanceScorer:
    label: str = "support"
    confidence: float = 0.91

    def classify_stance(self, *, sentence: str, passage: str) -> Stance:
        return Stance(
            label=self.label, confidence=self.confidence, probs={"support": 0.91, "contrast": 0.04, "mention": 0.05}
        )


class _UnavailableStanceScorer:
    def classify_stance(self, *, sentence: str, passage: str) -> None:
        return None


def _app(db_url: str, *, stance_scorer=None):
    return create_app(db_url=db_url, stance_scorer=stance_scorer)


def test_classify_stance_returns_real_stance(temp_db_url: str) -> None:
    client = TestClient(_app(temp_db_url, stance_scorer=_FakeStanceScorer("contrast", 0.77)))
    resp = client.post(
        "/citations/classify-stance",
        json={
            "sentence": "Faces with facial anomalies are perceived less favorably.",
            "passage": "We found no effect of facial anomaly on perceived trustworthiness.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["label"] == "contrast" and body["confidence"] == 0.77
    assert body["probs"] == {"support": 0.91, "contrast": 0.04, "mention": 0.05}


def test_classify_stance_returns_null_when_scorer_unavailable(temp_db_url: str) -> None:
    """The model being unavailable/inference failing must never surface as a 500 or a guessed verdict -- the
    endpoint mirrors classify_stance's own None contract exactly."""
    client = TestClient(_app(temp_db_url, stance_scorer=_UnavailableStanceScorer()))
    resp = client.post("/citations/classify-stance", json={"sentence": "A claim.", "passage": "A passage."})
    assert resp.status_code == 200
    assert resp.json() is None


def test_classify_stance_rejects_empty_sentence_or_passage(temp_db_url: str) -> None:
    client = TestClient(_app(temp_db_url, stance_scorer=_FakeStanceScorer()))
    assert client.post("/citations/classify-stance", json={"sentence": "", "passage": "x"}).status_code == 422
    assert client.post("/citations/classify-stance", json={"sentence": "x", "passage": ""}).status_code == 422
    assert client.post("/citations/classify-stance", json={"sentence": "x"}).status_code == 422  # passage missing


def test_classify_stance_rejects_oversize_text(temp_db_url: str) -> None:
    from app.backend.citations.suggest import MAX_TEXT_LEN

    client = TestClient(_app(temp_db_url, stance_scorer=_FakeStanceScorer()))
    too_long = "x" * (MAX_TEXT_LEN + 1)
    resp = client.post("/citations/classify-stance", json={"sentence": too_long, "passage": "ok"})
    assert resp.status_code == 422


def test_classify_stance_uses_cached_scorer_not_reloaded_per_call(temp_db_url: str) -> None:
    """Confirms the endpoint reuses `_suggest_stance_scorer`'s app.state caching (the whole point of importing
    it rather than calling default_stance_scorer() fresh) -- two calls hit the SAME injected instance."""
    calls = []

    @dataclass
    class _CountingScorer:
        def classify_stance(self, *, sentence: str, passage: str) -> Stance:
            calls.append((sentence, passage))
            return Stance(label="mention", confidence=0.5, probs={"support": 0.2, "contrast": 0.2, "mention": 0.6})

    client = TestClient(_app(temp_db_url, stance_scorer=_CountingScorer()))
    client.post("/citations/classify-stance", json={"sentence": "a", "passage": "b"})
    client.post("/citations/classify-stance", json={"sentence": "c", "passage": "d"})
    assert calls == [("a", "b"), ("c", "d")]  # both calls reached the one injected instance, not a fresh one each time
