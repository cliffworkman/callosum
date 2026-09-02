from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.help.assistant import HelpAnswer, HelpReference, HelpTurn
from app.backend.help.corpus import load_help_corpus, parse_help_sections

# ── corpus parsing + safe rendering (inline samples; independent of the shipped file) ────────────────

SAMPLE = """
<!-- section: alpha -->
## Alpha Title
First paragraph with **bold**, *italic*, and `code`.
A second line of the same paragraph.

- item one with a [link](https://example.com)
- item two

### A subhead
Body with unsafe <script>alert(1)</script>, a [bad](javascript:boom) link, and an [anchor](#alpha).

<!-- section: beta -->
## Beta Title
Just one paragraph.
"""


def test_parse_splits_on_markers_with_stable_ids_and_titles() -> None:
    sections = parse_help_sections(SAMPLE)
    assert [s.id for s in sections] == ["alpha", "beta"]
    assert [s.title for s in sections] == ["Alpha Title", "Beta Title"]


def test_render_html_escapes_and_allowlists() -> None:
    alpha = parse_help_sections(SAMPLE)[0].html
    assert "<strong>bold</strong>" in alpha and "<em>italic</em>" in alpha and "<code>code</code>" in alpha
    assert "<ul><li>" in alpha and "<h3>A subhead</h3>" in alpha
    # adjacent non-blank lines join into one paragraph
    assert (
        "<p>First paragraph with <strong>bold</strong>, <em>italic</em>, and <code>code</code>. A second line of the same paragraph.</p>"
        in alpha
    )
    # untrusted markup is escaped, never emitted raw
    assert "<script>" not in alpha and "&lt;script&gt;" in alpha


def test_render_html_link_scheme_allowlist() -> None:
    alpha = parse_help_sections(SAMPLE)[0].html
    assert '<a href="https://example.com" target="_blank" rel="noopener noreferrer">link</a>' in alpha
    assert '<a href="#alpha">anchor</a>' in alpha  # in-page anchor: no target
    assert "javascript:" not in alpha  # unsafe scheme dropped...
    assert "a bad link" in alpha  # ...keeping only the visible label as plain text


def test_duplicate_section_id_raises() -> None:
    with pytest.raises(ValueError):
        parse_help_sections("<!-- section: a -->\n## X\nb\n<!-- section: a -->\n## Y\nc")


def test_render_text_strips_markdown() -> None:
    text = parse_help_sections(SAMPLE)[0].text
    assert "**" not in text and "`" not in text
    assert "bold" in text and "italic" in text and "code" in text
    assert "- item one with a link" in text and "A subhead" in text


# ── shipped corpus + GET endpoint ────────────────────────────────────────────────────────────────

GUARANTEED_IDS = {
    "getting-started",
    "axes-overview",
    "scoring-axes-and-tiers",
    "synthesis-overview",
    "verifying-synthesis-citations",
    "privacy-and-data-egress",
}


def test_shipped_corpus_loads_with_unique_ids() -> None:
    sections = load_help_corpus()
    ids = [s.id for s in sections]
    assert len(ids) >= 10  # extensive
    assert len(ids) == len(set(ids))  # unique
    assert all(s.title and s.html for s in sections)
    assert GUARANTEED_IDS.issubset(set(ids))  # the ids the help assistant + tests rely on


def test_help_corpus_endpoint_returns_sections(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.get("/help/corpus")
    assert r.status_code == 200
    sections = r.json()["sections"]
    assert len(sections) >= 10
    assert all(set(s) == {"id", "title", "html"} and s["id"] and s["title"] and s["html"] for s in sections)
    assert GUARANTEED_IDS.issubset({s["id"] for s in sections})


# ── AI help assistant (inc 60) — its own gate, independent of the library egress gate ────────────────


@dataclass(frozen=True)
class FakeHelpAssistant:
    """A help assistant that does NOT self-gate — used to prove the seam gate is authoritative."""

    canned: HelpAnswer

    def answer(self, *, message: str, history: list) -> HelpAnswer:
        return self.canned


def _help_app(temp_db_url: str, *, assistant=None):
    return create_app(db_url=temp_db_url, help_assistant=assistant)


def test_help_ask_returns_answer_and_references(temp_db_url: str) -> None:
    fake = FakeHelpAssistant(
        HelpAnswer(
            answer="Open the Axes panel and click +.",
            references=[HelpReference("creating-and-editing-axes", "how to create")],
        )
    )
    client = TestClient(_help_app(temp_db_url, assistant=fake))
    r = client.post("/help/ask", json={"message": "how do I make an axis?", "history": []})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Open the Axes panel and click +."
    assert body["references"] == [{"section_id": "creating-and-editing-axes", "reason": "how to create"}]


def test_help_ask_works_when_library_egress_off(temp_db_url: str, monkeypatch) -> None:
    """Gate independence: the help assistant runs with the LIBRARY egress flag off (help flag stays on)."""
    monkeypatch.delenv("CALLOSUM_ALLOW_DATA_EGRESS", raising=False)
    fake = FakeHelpAssistant(HelpAnswer(answer="ok", references=[]))
    client = TestClient(_help_app(temp_db_url, assistant=fake))
    r = client.post("/help/ask", json={"message": "hi", "history": []})
    assert r.status_code == 200 and r.json()["answer"] == "ok"


def test_help_ask_blocked_when_help_disabled(temp_db_url: str, monkeypatch) -> None:
    """Hole closed: an injected assistant that does NOT self-gate is blocked at the seam (503) when the
    help toggle is off — even though the library egress flag stays on."""
    monkeypatch.delenv("CALLOSUM_HELP_ASSISTANT_ENABLED", raising=False)
    fake = FakeHelpAssistant(HelpAnswer(answer="should not be returned", references=[]))
    client = TestClient(_help_app(temp_db_url, assistant=fake))
    r = client.post("/help/ask", json={"message": "hi", "history": []})
    assert r.status_code == 503
    assert "Settings" in r.json()["detail"]
    assert "GOOGLE_API_KEY" not in r.json()["detail"]  # not provider-specific -- any active provider may apply


def test_prompt_bounds_history_tighter_for_managed_local_than_cloud() -> None:
    """History had no managed_local-aware cap at all: 20 turns x 4,000 chars is up to 80,000 chars alone, which
    combined with the (already-bounded) corpus measured 98,783 chars total real worst-case input -- against the
    managed Local AI preview's ~10,240-token budget."""
    from integrations.gemini.help_assistant import _prompt

    history = [HelpTurn(role="user", content="x" * 4000) for _ in range(20)]

    cloud_prompt = _prompt(message="q", history=history, config=None)
    managed_prompt = _prompt(message="q", history=history, config=type("C", (), {"provider": "managed_local"})())

    assert len(managed_prompt) < len(cloud_prompt)


def test_help_ask_drops_unknown_section_ids(temp_db_url: str) -> None:
    fake = FakeHelpAssistant(
        HelpAnswer(
            answer="x",
            references=[
                HelpReference("getting-started", "real"),
                HelpReference("totally-made-up-section", "hallucinated"),
            ],
        )
    )
    client = TestClient(_help_app(temp_db_url, assistant=fake))
    r = client.post("/help/ask", json={"message": "hi", "history": []})
    assert [ref["section_id"] for ref in r.json()["references"]] == ["getting-started"]


def test_help_ask_rejects_empty_message(temp_db_url: str) -> None:
    fake = FakeHelpAssistant(HelpAnswer(answer="x", references=[]))
    client = TestClient(_help_app(temp_db_url, assistant=fake))
    assert client.post("/help/ask", json={"message": "", "history": []}).status_code == 422
    assert client.post("/help/ask", json={"message": "   ", "history": []}).status_code == 422


def test_help_assistant_parse_failure_degrades() -> None:
    from integrations.gemini.help_assistant import _parse_answer

    degraded = _parse_answer("this is not JSON at all")
    assert degraded.answer == "this is not JSON at all" and degraded.references == []
    shaped = _parse_answer('```json\n{"answer":"hi","references":[{"section_id":"a","reason":"r"}]}\n```')
    assert shaped.answer == "hi" and [r.section_id for r in shaped.references] == ["a"]


def test_gemini_help_assistant_self_checks_when_disabled() -> None:
    from app.backend.llm.egress import HelpAssistantDisabledError
    from integrations.gemini import GeminiConfig, GeminiHelpAssistant

    assistant = GeminiHelpAssistant(config=GeminiConfig(help_assistant_enabled=False))
    with pytest.raises(HelpAssistantDisabledError):
        assistant.answer(message="hi", history=[])
