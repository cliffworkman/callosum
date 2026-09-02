"""inc 259 — the assisted-extraction funnel's local, deterministic pieces: page-tagged text, proposable-field
selection, the anchor-state derivation (via a real fitz PDF so locate_quote runs), and the untrusted-response parser.
Hermetic — no DB, no network."""

from __future__ import annotations

from types import SimpleNamespace

import fitz  # PyMuPDF — build a tiny real PDF so locate_quote can anchor

from app.backend import workbench_assist as wa
from integrations.gemini.extraction_assistant import parse_proposals


class _FakeConnection:
    def __init__(self):
        self.savepoint_rolled_back = None

    def begin_nested(self):
        owner = self

        class _Savepoint:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                owner.savepoint_rolled_back = exc_type is not None
                return False

        return _Savepoint()


def _pdf(tmp_path, text: str) -> str:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    path = tmp_path / "study.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def test_anchor_exact_when_value_literal_in_located_quote(tmp_path):
    pdf = _pdf(tmp_path, "The correlation was r = 0.42 across the full sample.")
    res = wa.anchor_proposal(pdf, "0.42", "The correlation was r = 0.42 across the full sample", claimed_page=9)
    assert res["anchor_state"] == "exact"
    assert res["bbox_json"] and res["reason"] is None
    assert res["page"] is not None  # the LOCATED page, not the model's claimed 9


def test_anchor_region_when_value_not_in_quote(tmp_path):
    pdf = _pdf(tmp_path, "The correlation was r = 0.42 across the full sample.")
    res = wa.anchor_proposal(pdf, "999", "The correlation was r = 0.42 across the full sample", claimed_page=9)
    assert res["anchor_state"] == "region"
    assert res["bbox_json"] is None and res["reason"] == "value_not_in_quote"


def test_anchor_unanchored_when_quote_absent(tmp_path):
    pdf = _pdf(tmp_path, "The correlation was r = 0.42 across the full sample.")
    res = wa.anchor_proposal(pdf, "0.42", "this sentence does not occur anywhere in the pdf zzz", claimed_page=9)
    assert res["anchor_state"] == "unanchored"
    assert res["bbox_json"] is None and res["reason"] == "quote_not_found"
    assert res["page"] == 9  # the model's claimed page is kept (rendered with a "?")


def test_proposable_fields_only_empty_structured():
    template = [
        {"key": "r", "label": "r", "type": "number", "role": "r"},
        {"key": "n", "label": "N", "type": "number", "role": "n"},
        {"key": "measure", "label": "Measure", "type": "choice", "role": "measure", "options": ["or", "rr"]},
        {"key": "notes", "label": "Notes", "type": "text", "role": None},
    ]
    cells = {"r": {"value": "0.5"}, "notes": {"value": ""}}  # r filled; n/measure empty; notes is text
    keys = [f["key"] for f in wa.proposable_fields(template, cells)]
    assert keys == ["n", "measure"]  # skip filled `r`, skip text `notes`


def test_page_tagged_text_caps_and_flags_truncation():
    chunks = [{"page_start": i, "page_end": i, "text": "x" * 100} for i in range(1, 40)]
    text, truncated = wa.page_tagged_text(chunks, cap=500)
    assert truncated is True and len(text) <= 500
    assert text.startswith("[p.1] ")


def test_page_tagged_text_truncates_rather_than_drops_a_single_oversized_chunk():
    """A single chunk whose own page-tagged text alone exceeds `cap` must still be truncated to fit, not
    dropped entirely -- the prior behavior broke before appending anything, silently returning "" for a paper
    that does have real (if dense) extracted text."""
    chunks = [{"page_start": 1, "page_end": 1, "text": "x" * 1000}]
    text, truncated = wa.page_tagged_text(chunks, cap=200)
    assert truncated is True
    assert text != ""
    assert len(text) <= 200
    assert text.startswith("[p.1] ")

    # a later, normal-sized chunk after the oversized one is still correctly dropped, not appended past cap
    chunks_two = [{"page_start": 1, "page_end": 1, "text": "x" * 1000}, {"page_start": 2, "page_end": 2, "text": "y"}]
    text_two, truncated_two = wa.page_tagged_text(chunks_two, cap=200)
    assert truncated_two is True
    assert "y" not in text_two


def test_relevant_text_ranks_only_this_papers_chunks_from_field_labels(monkeypatch):
    chunks = [{"id": i, "page_start": i, "page_end": i, "text": f"chunk {i}"} for i in range(1, 16)]
    captured = {}

    def fake_embed(conn, *, model, vector_store, chunk_ids):
        captured["embedded"] = chunk_ids

    def fake_search(conn, **kwargs):
        captured["search"] = kwargs
        return [SimpleNamespace(chunk_id=14), SimpleNamespace(chunk_id=9), SimpleNamespace(chunk_id=3)]

    monkeypatch.setattr(wa, "embed_chunks", fake_embed)
    monkeypatch.setattr(wa, "search_similar", fake_search)
    conn = _FakeConnection()
    fields = [
        {"key": "r", "label": "Correlation r", "type": "number"},
        {"key": "n", "label": "Sample size", "type": "number"},
    ]
    text, narrowed = wa.relevant_page_tagged_text(
        conn, chunks, fields=fields, model=object(), vector_store=object(), top_k=3
    )

    assert captured["embedded"] == list(range(1, 16))
    assert captured["search"]["query"] == "Extraction field: Correlation r\nExtraction field: Sample size"
    assert captured["search"]["candidate_target_ids"] == set(range(1, 16))
    assert captured["search"]["target_types"] == ("chunk",)
    assert text == "[p.14] chunk 14\n[p.9] chunk 9\n[p.3] chunk 3\n"
    assert narrowed is True
    assert conn.savepoint_rolled_back is False


def test_relevant_text_falls_back_to_bounded_document_order(monkeypatch):
    chunks = [{"id": i, "page_start": i, "page_end": i, "text": "x" * 30} for i in range(1, 16)]

    def unavailable(*args, **kwargs):
        raise RuntimeError("local embedding unavailable")

    monkeypatch.setattr(wa, "embed_chunks", unavailable)
    conn = _FakeConnection()
    text, truncated = wa.relevant_page_tagged_text(
        conn,
        chunks,
        fields=[{"label": "Correlation r"}],
        model=object(),
        vector_store=object(),
        top_k=3,
        cap=80,
    )

    assert text.startswith("[p.1] ")
    assert "[p.3]" not in text
    assert truncated is True
    assert conn.savepoint_rolled_back is True


def test_parse_proposals_defensive():
    allowed = {"r", "n"}
    # strict JSON
    good = '{"r": {"value": "0.42", "quote": "r = .42", "page": 3}, "bogus": {"value": "x"}}'
    parsed = parse_proposals(good, allowed_keys=allowed)
    assert parsed == [{"field_key": "r", "value": "0.42", "quote": "r = .42", "page": 3}]
    # markdown code fence + surrounding junk is tolerated
    fenced = 'Sure!\n```json\n{"n": {"value": 60, "quote": "N = 60", "page": 2}}\n```\n'
    assert parse_proposals(fenced, allowed_keys=allowed) == [
        {"field_key": "n", "value": "60", "quote": "N = 60", "page": 2}
    ]
    # junk → zero proposals, never a crash
    assert parse_proposals("not json at all", allowed_keys=allowed) == []
    assert parse_proposals("", allowed_keys=allowed) == []


def test_parse_proposals_caps_lengths():
    allowed = {"r"}
    big = '{"r": {"value": "' + "9" * 900 + '", "quote": "' + "q" * 5000 + '", "page": "7"}}'
    parsed = parse_proposals(big, allowed_keys=allowed)
    assert len(parsed[0]["value"]) == 500 and len(parsed[0]["quote"]) == 4000 and parsed[0]["page"] == 7


def test_anchor_region_when_found_but_no_rects(monkeypatch):
    """found=True but rectangles=() (PDF text layer has the quote but no word bboxes) → region with the KNOWN page."""
    from app.backend.pdf_processing.quote_matching import QuoteMatch

    def fake_locate(pdf_path, quote):
        return QuoteMatch(found=True, quote=quote, page_start=5, page_end=5, rectangles=())

    monkeypatch.setattr(wa, "locate_quote", fake_locate)
    res = wa.anchor_proposal("fake.pdf", "0.42", "r = 0.42", claimed_page=9)
    assert res["anchor_state"] == "region"
    assert res["page"] == 5  # the LOCATED page, not the model's claimed 9
    assert res["bbox_json"] is None
    assert res["reason"] == "no_rects"


def test_assemble_proposals_filters_and_shapes(monkeypatch):
    """assemble_proposals filters non-allowed keys and returns the expected storable dict shape."""

    def fake_anchor(pdf_path, value, quote, claimed_page):
        return {"anchor_state": "unanchored", "page": claimed_page, "bbox_json": None, "reason": "quote_not_found"}

    monkeypatch.setattr(wa, "anchor_proposal", fake_anchor)
    raw = [
        {"field_key": "r", "value": "0.42", "quote": "r = 0.42", "page": 3},
        {"field_key": "secret", "value": "x", "quote": None, "page": None},  # not in allowed_keys → filtered
    ]
    result = wa.assemble_proposals("fake.pdf", raw, allowed_keys={"r", "n"})
    assert len(result) == 1  # "secret" was filtered out
    assert result[0]["field_key"] == "r"
    assert {"field_key", "value", "quote", "anchor_state", "page", "bbox_json", "reason"} <= set(result[0].keys())


def test_extraction_prompt_defense_in_depth_caps_text_for_managed_local():
    """workbench_assist.py already pre-bounds its own `text` (MAX_TEXT_CHARS/MAX_TEXT_CHARS_MANAGED_LOCAL) before
    it reaches this layer -- this is a defense-in-depth cap for any future caller that forgets to."""
    from integrations.gemini.extraction_assistant import MAX_PAPER_TEXT_CHARS_MANAGED_LOCAL, _prompt

    long_text = "x" * 20_000
    fields = [{"key": "r", "label": "Correlation", "type": "number", "options": None}]

    cloud_prompt = _prompt(text=long_text, fields=fields, provider="gemini")
    managed_prompt = _prompt(text=long_text, fields=fields, provider="managed_local")

    assert long_text in cloud_prompt
    assert long_text not in managed_prompt
    assert long_text[:MAX_PAPER_TEXT_CHARS_MANAGED_LOCAL] in managed_prompt
