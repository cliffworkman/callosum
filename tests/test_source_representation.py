"""Regression coverage for source-representation completeness and durable identity (inc 579, H1b.1).

H1b's fidelity was validated exhaustively by two independent audits, and its central representation
is not in question here. What *is* in question is the state machine around it. An independent audit
lowered the component cap, wrote one page and zero components, and found that partial graph
classified as **current** -- because its checksum and derivation version matched, which was all H1b
checked. An ordinary backfill would then have skipped it forever.

So the load-bearing cases in this file are again NEGATIVE:

* a truncated graph must NOT be current,
* an incomplete graph must NOT be current,
* a failed derivation must NOT be current,
* a status row that outlived its graph must NOT be current,
* a forced rebuild must NOT change any logical locator, even though every surrogate id changes,
* and none of it may become visible to retrieval.

The cap-truncation case is the one the audit actually discovered; it is reproduced exactly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest
from sqlalchemy import delete, func, select

from app.backend.pdf_processing.extraction import extract_pdf
from app.backend.pdf_processing.source_components import (
    GEOMETRY_INVALID,
    GEOMETRY_PAGE_TOLERANCE_PT,
    GEOMETRY_UNKNOWN,
    GEOMETRY_VALID,
    build_page,
    classify_geometry,
)
from app.backend.persistence import source_representation_repo
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_paper
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.persistence.schema_source_components import (
    source_components,
    source_pages,
    source_representations,
)
from app.backend.persistence.source_components_repo import (
    STATE_COMPLETE,
    STATE_FAILED,
    STATE_INCOMPLETE,
    STATE_TRUNCATED,
    SourceLocator,
    attachments_with_current_source,
    is_source_current,
    locator_for_component,
    record_source_failure,
    replace_attachment_source,
    resolve_locator,
    source_representation_for,
    source_representation_report,
)

SEED_PDF = Path("tests/fixtures/seed.pdf")

# --- literal page-dict builders (no PDF, no database), mirroring tests/test_source_components.py ---


def _span(text: str, bbox, *, font="Times", size=10.0, flags=0) -> dict:
    return {"text": text, "bbox": bbox, "font": font, "size": size, "flags": flags}


def _line(spans: list[dict], bbox) -> dict:
    return {"spans": spans, "bbox": bbox, "dir": (1.0, 0.0), "wmode": 0}


def _text_block(number: int, bbox, lines: list[dict]) -> dict:
    return {"type": 0, "number": number, "bbox": bbox, "lines": lines}


def _image_block(number: int, bbox) -> dict:
    return {"type": 1, "number": number, "bbox": bbox, "width": 100, "height": 50, "ext": "png"}


def _prose_block(number: int, y: float, text: str = "Participants completed the task in one session.") -> dict:
    return _text_block(
        number,
        (72.0, y, 400.0, y + 12.0),
        [_line([_span(text, (72.0, y, 400.0, y + 12.0))], (72.0, y, 400.0, y + 12.0))],
    )


def _page(number: int, blocks: list[dict], *, width: float = 612.0, height: float = 792.0):
    return build_page(
        {"width": width, "height": height, "blocks": blocks},
        page_number=number,
        width=width,
        height=height,
    )


def _pages(count: int = 2, blocks_per_page: int = 3):
    return [_page(n + 1, [_prose_block(i, 100.0 + 20.0 * i) for i in range(blocks_per_page)]) for n in range(count)]


def _seed(db_url: str, *, checksum: str = "live-sha", deleted: bool = False):
    engine = make_engine(db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="H1b.1 fixture", csl_json={"title": "H1b.1 fixture"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            original_path="/tmp/x.pdf",
            resolved_path="/tmp/x.pdf",
            checksum=checksum,
            file_size=100,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="article-fulltext",
        )
        if deleted:
            conn.execute(papers.update().where(papers.c.id == paper_id).values(deleted_at=func.current_timestamp()))
    return engine, paper_id, attachment_id


def _store(engine, attachment_id: int, pages, *, checksum: str = "live-sha", derivation: str | None = None):
    with engine.begin() as conn:
        return replace_attachment_source(
            conn,
            attachment_id=attachment_id,
            pages=pages,
            coordinate_system="pdf-points-top-left",
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            source_checksum=checksum,
            **({"derivation_version": derivation} if derivation else {}),
        )


def _logical_tree(engine, attachment_id: int) -> str:
    """A canonical digest of the LOGICAL tree only -- no surrogate ids anywhere in it.

    This is what must be identical across a forced rebuild, an interrupted-then-repaired run, and an
    uninterrupted control. Comparing rows including their ids would compare storage, not content.
    """
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                source_pages.c.page_number,
                source_components.c.component_path,
                source_components.c.kind,
                source_components.c.native_order,
                source_components.c.sorted_order,
                source_components.c.child_order,
                source_components.c.x0,
                source_components.c.y0,
                source_components.c.x1,
                source_components.c.y1,
                source_components.c.text,
                source_components.c.font,
                source_components.c.font_size,
                source_components.c.flags,
                source_components.c.geometry_state,
            )
            .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
            .where(source_pages.c.attachment_id == attachment_id)
            .order_by(source_pages.c.page_number, source_components.c.component_path)
        ).all()
    return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()


# --- 1-2: a full write becomes complete, and complete is current ---


def test_a_full_write_becomes_complete(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    receipt = _store(engine, attachment_id, _pages(count=3))
    assert receipt.state == STATE_COMPLETE
    assert receipt.state_reason is None
    assert (receipt.expected_pages, receipt.written_pages, receipt.skipped_pages) == (3, 3, 0)
    assert receipt.written_components > 0

    with engine.begin() as conn:
        stored = source_representation_for(conn, attachment_id)
    assert stored["state"] == STATE_COMPLETE
    assert stored["written_components"] == receipt.written_components


def test_a_complete_representation_is_current(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, _pages())
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == {attachment_id}
        assert is_source_current(conn, attachment_id) is True


# --- 3-4: the cap-truncation class the independent audit found (MANDATORY) ---


def test_a_cap_truncated_representation_is_not_current(temp_db_url: str, monkeypatch) -> None:
    """The exact defect the audit discovered.

    With the cap lowered, H1b wrote one page and zero components, and because that page carried a
    matching checksum and derivation version the graph was classified CURRENT -- so an ordinary
    backfill would have skipped the partial representation forever.
    """
    monkeypatch.setattr(source_representation_repo, "MAX_COMPONENTS_PER_ATTACHMENT", 10, raising=False)
    import app.backend.persistence.source_components_repo as repo

    monkeypatch.setattr(repo, "MAX_COMPONENTS_PER_ATTACHMENT", 10)

    engine, _, attachment_id = _seed(temp_db_url)
    receipt = _store(engine, attachment_id, _pages(count=2, blocks_per_page=5))

    assert receipt.state == STATE_TRUNCATED
    assert receipt.state_reason == "component_cap"
    assert receipt.written_pages < receipt.expected_pages
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == set(), "a truncated graph must never be current"
        # The page whose components were dropped is rolled back with them, so no orphan page row
        # claims coverage it does not have.
        assert conn.execute(select(func.count()).select_from(source_pages)).scalar_one() == receipt.written_pages


def test_a_cap_hit_on_the_last_page_is_still_truncated(temp_db_url: str, monkeypatch) -> None:
    """The subtle half: if the cap trips on the LAST page, the page arithmetic alone still reads as
    complete. The truncation flag has to decide independently."""
    import app.backend.persistence.source_components_repo as repo

    # Page 1 fits under the cap; page 2 pushes past it, so written_pages would equal expected_pages
    # if the flag were not authoritative.
    pages = [_page(1, [_prose_block(0, 100.0)]), _page(2, [_prose_block(0, 100.0)])]
    monkeypatch.setattr(repo, "MAX_COMPONENTS_PER_ATTACHMENT", 3)
    engine, _, attachment_id = _seed(temp_db_url)
    receipt = _store(engine, attachment_id, pages)
    assert receipt.state == STATE_TRUNCATED
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == set()


def test_a_truncated_representation_is_reprocessed_by_an_ordinary_rerun(temp_db_url: str, monkeypatch) -> None:
    import app.backend.persistence.source_components_repo as repo

    engine, _, attachment_id = _seed(temp_db_url)
    monkeypatch.setattr(repo, "MAX_COMPONENTS_PER_ATTACHMENT", 10)
    assert _store(engine, attachment_id, _pages(count=2, blocks_per_page=5)).state == STATE_TRUNCATED

    monkeypatch.undo()
    control = _store(engine, attachment_id, _pages(count=2, blocks_per_page=5))
    assert control.state == STATE_COMPLETE
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == {attachment_id}


# --- 5: an unrepresentable page fails closed rather than counting as complete ---


def test_a_page_that_cannot_be_represented_is_incomplete_not_complete(temp_db_url: str) -> None:
    """A degenerate page is deterministic, so a rerun will keep producing it and the backfill will
    keep retrying. That is the honest cost. Calling the graph complete because everything
    *representable* happened to be written would make `current` mean something weaker than
    `complete`, which is the exact invariant H1b.1 exists to establish."""
    engine, _, attachment_id = _seed(temp_db_url)
    pages = [_page(1, [_prose_block(0, 100.0)]), _page(2, [_prose_block(0, 100.0)], width=0.0, height=0.0)]
    receipt = _store(engine, attachment_id, pages)

    assert receipt.state == STATE_INCOMPLETE
    assert receipt.state_reason == "degenerate_pages"
    assert (receipt.expected_pages, receipt.written_pages, receipt.skipped_pages) == (2, 1, 1)
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == set()


def test_an_empty_page_list_cannot_mint_a_complete_representation(temp_db_url: str) -> None:
    """ "Complete representation of nothing" is a contradiction, not a success."""
    engine, _, attachment_id = _seed(temp_db_url)
    receipt = _store(engine, attachment_id, [])
    assert receipt.state == STATE_INCOMPLETE
    assert receipt.state_reason == "no_pages"
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == set()


# --- 6-7: failure state, and a failed attempt over a surviving valid representation ---


def test_a_failed_representation_is_not_current_and_is_reprocessed(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    with engine.begin() as conn:
        assert (
            record_source_failure(
                conn,
                attachment_id=attachment_id,
                source_checksum="live-sha",
                extraction_tool="pymupdf",
                extraction_version="1.27.2",
                reason="persistence_error:RuntimeError",
            )
            is True
        )
    with engine.begin() as conn:
        assert source_representation_for(conn, attachment_id)["state"] == STATE_FAILED
        assert attachments_with_current_source(conn) == set()

    assert _store(engine, attachment_id, _pages()).state == STATE_COMPLETE
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == {attachment_id}


def test_a_failed_attempt_never_corrupts_a_surviving_valid_representation(temp_db_url: str) -> None:
    """The state of the persisted representation and the outcome of the latest attempt are two
    different facts. A rebuild that fails and rolls back leaves the previous complete graph intact;
    marking that row failed would destroy a good representation because a later attempt went wrong.
    """
    engine, _, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, _pages())
    before = _logical_tree(engine, attachment_id)

    with engine.begin() as conn:
        recorded = record_source_failure(
            conn,
            attachment_id=attachment_id,
            source_checksum="live-sha",
            extraction_tool="pymupdf",
            extraction_version="1.27.2",
            reason="persistence_error:RuntimeError",
        )
    assert recorded is False, "a still-current representation must be left alone"
    with engine.begin() as conn:
        assert source_representation_for(conn, attachment_id)["state"] == STATE_COMPLETE
        assert attachments_with_current_source(conn) == {attachment_id}
    assert _logical_tree(engine, attachment_id) == before


# --- 8-10: interruption, and convergence with an uninterrupted control ---


def test_an_interrupted_write_is_never_current(temp_db_url: str, monkeypatch) -> None:
    """Interruption at any point leaves either the previous committed representation or nothing --
    never a complete marker over a half-written graph, because the marker is written last."""
    import app.backend.persistence.source_components_repo as repo

    engine, _, attachment_id = _seed(temp_db_url)
    original = repo._flatten
    calls = {"n": 0}

    def explode(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] >= 2:  # fail mid-write, after page 1 was already persisted
            raise RuntimeError("interrupted")
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "_flatten", explode)
    with pytest.raises(RuntimeError):
        _store(engine, attachment_id, _pages(count=3))

    with engine.begin() as conn:
        assert source_representation_for(conn, attachment_id) is None
        assert attachments_with_current_source(conn) == set()
        assert conn.execute(select(func.count()).select_from(source_pages)).scalar_one() == 0


def test_an_interrupted_run_converges_to_the_uninterrupted_canonical_result(temp_db_url: str, monkeypatch) -> None:
    import app.backend.persistence.source_components_repo as repo

    control_engine, _, control_id = _seed(temp_db_url)
    _store(control_engine, control_id, _pages(count=3))
    control = _logical_tree(control_engine, control_id)

    engine, _, attachment_id = _seed(temp_db_url)
    original = repo._flatten
    calls = {"n": 0}

    def explode(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("interrupted")
        return original(*args, **kwargs)

    monkeypatch.setattr(repo, "_flatten", explode)
    with pytest.raises(RuntimeError):
        _store(engine, attachment_id, _pages(count=3))
    monkeypatch.undo()

    assert _store(engine, attachment_id, _pages(count=3)).state == STATE_COMPLETE
    assert _logical_tree(engine, attachment_id) == control


def test_a_status_row_that_outlived_its_graph_is_not_current(temp_db_url: str) -> None:
    """Identity plus a complete marker is still not enough: the rows actually present must match the
    counts the record claims. Checked for pages AND components -- an intact page envelope with
    missing component rows is not a complete graph."""
    engine, _, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, _pages())

    with engine.begin() as conn:
        conn.execute(delete(source_components))
        # every page row survives, so only the component cross-check can catch this
        assert conn.execute(select(func.count()).select_from(source_pages)).scalar_one() > 0
        assert attachments_with_current_source(conn) == set()

    with engine.begin() as conn:
        conn.execute(delete(source_pages))
        assert attachments_with_current_source(conn) == set()


def test_a_page_count_mismatch_prevents_current(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, _pages(count=3))
    with engine.begin() as conn:
        conn.execute(
            source_representations.update()
            .where(source_representations.c.attachment_id == attachment_id)
            .values(expected_pages=4)
        )
        assert attachments_with_current_source(conn) == set()


# --- 11-12: staleness still holds under the new contract ---


def test_a_stale_checksum_prevents_current(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url, checksum="live-sha")
    _store(engine, attachment_id, _pages(), checksum="live-sha")
    with engine.begin() as conn:
        conn.execute(attachments.update().where(attachments.c.id == attachment_id).values(checksum="replaced-sha"))
        assert attachments_with_current_source(conn) == set()


def test_a_stale_derivation_version_prevents_current(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, _pages())
    with engine.begin() as conn:
        assert attachments_with_current_source(conn, "source-components-v99") == set()


# --- 13-15: the stable logical locator ---


def test_a_forced_rebuild_changes_every_surrogate_id_but_no_logical_locator(temp_db_url: str) -> None:
    """The measured property that makes durable provenance possible at all."""
    engine, _, attachment_id = _seed(temp_db_url)
    # A co-resident attachment, because that is the real condition: `_flatten` allocates ids from
    # max(id)+1, so in a database holding only ONE attachment a rebuild reuses the very same ids and
    # the property under test is untestable. The audit observed id movement across a 114-attachment
    # corpus; this reproduces that, minimally.
    _, _, neighbour_id = _seed(temp_db_url)
    _store(engine, attachment_id, _pages(count=2))
    _store(engine, neighbour_id, _pages(count=2))

    def snapshot():
        with engine.begin() as conn:
            return conn.execute(
                select(source_components.c.id, source_pages.c.page_number, source_components.c.component_path)
                .select_from(
                    source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id)
                )
                .where(source_pages.c.attachment_id == attachment_id)
                .order_by(source_pages.c.page_number, source_components.c.component_path)
            ).all()

    before = snapshot()
    _store(engine, attachment_id, _pages(count=2))  # forced destructive replacement
    after = snapshot()

    assert [row[0] for row in before] != [row[0] for row in after], "surrogate ids are expected to move"
    assert [(row[1], row[2]) for row in before] == [(row[1], row[2]) for row in after]


def test_a_rebuild_can_silently_reuse_a_previous_surrogate_id(temp_db_url: str) -> None:
    """Surrogate ids are worse than unstable: they can be *reused*.

    ``_flatten`` allocates from ``max(id) + 1``, so when the attachment being rebuilt holds the top
    of the id space its old ids are handed straight back to different content. A stale reference to
    component 7 then resolves successfully, to the wrong thing, with no error anywhere. That is the
    failure mode a durable locator has to prevent, and it is why provenance may never name a
    component by its row id.
    """
    engine, _, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, [_page(1, [_prose_block(0, 100.0, "First version of the sentence.")])])
    with engine.begin() as conn:
        before = conn.execute(
            select(source_components.c.id, source_components.c.text)
            .where(source_components.c.kind == "span")
            .order_by(source_components.c.id)
        ).all()

    _store(engine, attachment_id, [_page(1, [_prose_block(0, 100.0, "Second, entirely different sentence.")])])
    with engine.begin() as conn:
        after = conn.execute(
            select(source_components.c.id, source_components.c.text)
            .where(source_components.c.kind == "span")
            .order_by(source_components.c.id)
        ).all()

    assert [row[0] for row in before] == [row[0] for row in after], "the ids came back"
    assert [row[1] for row in before] != [row[1] for row in after], "...naming different content"


def test_the_logical_locator_is_unambiguous_across_a_representative_hierarchy(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    page = _page(
        1,
        [
            _image_block(9, (10.0, 10.0, 60.0, 60.0)),
            _text_block(
                0,
                (72.0, 100.0, 400.0, 140.0),
                [
                    _line(
                        [_span("Alpha ", (72.0, 100.0, 120.0, 112.0)), _span("beta", (120.0, 100.0, 160.0, 112.0))],
                        (72.0, 100.0, 160.0, 112.0),
                    ),
                    _line([_span("Gamma", (72.0, 116.0, 130.0, 128.0))], (72.0, 116.0, 130.0, 128.0)),
                ],
            ),
            _prose_block(3, 200.0),
        ],
    )
    receipt = _store(engine, attachment_id, [page])

    with engine.begin() as conn:
        paths = [
            row[0]
            for row in conn.execute(
                select(source_components.c.component_path).select_from(
                    source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id)
                )
            )
        ]
    assert len(paths) == receipt.written_components
    assert len(set(paths)) == len(paths), "a locator path must be unique within its page"
    assert None not in paths
    assert {"b0", "b1", "b1/l0", "b1/l0/s0", "b1/l0/s1", "b1/l1", "b1/l1/s0", "b2"} <= set(paths)


def test_a_locator_resolves_after_rebuild_and_fails_closed_when_identity_moves(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url, checksum="live-sha")
    _, _, neighbour_id = _seed(temp_db_url, checksum="other-sha")  # see the co-resident note above
    _store(engine, attachment_id, _pages(count=2), checksum="live-sha")
    _store(engine, neighbour_id, _pages(count=2), checksum="other-sha")

    with engine.begin() as conn:
        component_id = conn.execute(
            select(source_components.c.id)
            .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
            .where(source_pages.c.attachment_id == attachment_id, source_components.c.component_path == "b1/l0/s0")
            .limit(1)
        ).scalar_one()
        locator = locator_for_component(conn, component_id)
        original = resolve_locator(conn, attachment_id, locator)
    assert locator is not None and original is not None
    assert SourceLocator.parse(locator.as_key()) == locator

    _store(engine, attachment_id, _pages(count=2), checksum="live-sha")  # every surrogate id moves
    with engine.begin() as conn:
        rebuilt = resolve_locator(conn, attachment_id, locator)
    assert rebuilt is not None
    assert rebuilt["id"] != original["id"], "the surrogate id moved..."
    assert (rebuilt["text"], rebuilt["x0"], rebuilt["kind"]) == (original["text"], original["x0"], original["kind"])

    # ...and every identity constituent must invalidate the locator when it moves.
    for field, value in (
        ("source_checksum", "other-sha"),
        ("extraction_version", "9.9.9"),
        ("extraction_tool", "other-tool"),
        ("derivation_version", "source-components-v99"),
        ("page_number", 99),
        ("component_path", "b99/l0/s0"),
    ):
        with engine.begin() as conn:
            assert resolve_locator(conn, attachment_id, locator.__class__(**{**locator.__dict__, field: value})) is None

    with engine.begin() as conn:
        conn.execute(attachments.update().where(attachments.c.id == attachment_id).values(checksum="replaced-sha"))
        assert resolve_locator(conn, attachment_id, locator) is None, "a replaced file makes the locator stale"


def test_the_same_file_attached_twice_shares_one_durable_identity(temp_db_url: str) -> None:
    """The locator identifies CONTENT within a document identity, not a storage row.

    Found in corpus validation: 3,342 of 1,089,546 components shared a durable key, and every one
    was the same PDF attached twice to the same paper. That is the locator working correctly -- two
    byte-identical documents *are* the same document -- and the property that actually matters holds
    exactly: **no durable key ever names different content** (measured 0 across the corpus). It does
    mean the key is not by itself a globally unique row address, so provenance carries the
    attachment id alongside it, which `resolve_locator` already requires.
    """
    engine, paper_id, first_id = _seed(temp_db_url, checksum="same-sha")
    with engine.begin() as conn:
        second_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            original_path="/tmp/x.pdf",
            resolved_path="/tmp/x.pdf",
            checksum="same-sha",
            file_size=100,
            content_type="application/pdf",
            import_source="test",
            attachment_type="pdf",
            role="article-fulltext",
        )
    _store(engine, first_id, _pages(count=2), checksum="same-sha")
    _store(engine, second_id, _pages(count=2), checksum="same-sha")

    assert _logical_tree(engine, first_id) == _logical_tree(engine, second_id)
    with engine.begin() as conn:
        assert attachments_with_current_source(conn) == {first_id, second_id}
        component_id = conn.execute(
            select(source_components.c.id)
            .select_from(source_components.join(source_pages, source_pages.c.id == source_components.c.source_page_id))
            .where(source_pages.c.attachment_id == first_id, source_components.c.component_path == "b1/l0/s0")
            .limit(1)
        ).scalar_one()
        locator = locator_for_component(conn, component_id)
        # The same locator resolves under either attachment, to identical content -- never to
        # different content, which is the only outcome that would be a defect.
        first = resolve_locator(conn, first_id, locator)
        second = resolve_locator(conn, second_id, locator)
    assert first is not None and second is not None
    assert first["id"] != second["id"], "different storage rows"
    assert (first["text"], first["x0"], first["kind"]) == (second["text"], second["x0"], second["kind"])


# --- 16-19: geometry validity, preserved raw ---


def test_an_inverted_bbox_is_preserved_raw_and_marked_unusable(temp_db_url: str) -> None:
    """363 of these exist in the real corpus. Fidelity is not validity: the coordinates stay exactly
    as the extractor reported them, and a separate judgment says they cannot be intersected."""
    engine, _, attachment_id = _seed(temp_db_url)
    inverted = (300.0, 700.0, 200.0, 600.0)
    _store(engine, attachment_id, [_page(1, [_image_block(0, inverted), _prose_block(1, 100.0)])])

    with engine.begin() as conn:
        row = conn.execute(select(source_components).where(source_components.c.kind == "image")).mappings().one()
    assert (row["x0"], row["y0"], row["x1"], row["y1"]) == inverted, "raw coordinates are never rewritten"
    assert row["geometry_state"] == GEOMETRY_INVALID


def test_an_out_of_page_bbox_is_preserved_raw_and_marked_unusable(temp_db_url: str) -> None:
    engine, _, attachment_id = _seed(temp_db_url)
    outside = (10.0, 10.0, 900.0, 60.0)  # x1 far beyond a 612pt-wide page
    _store(engine, attachment_id, [_page(1, [_image_block(0, outside), _prose_block(1, 100.0)])])

    with engine.begin() as conn:
        row = conn.execute(select(source_components).where(source_components.c.kind == "image")).mappings().one()
    assert (row["x0"], row["y0"], row["x1"], row["y1"]) == outside
    assert row["geometry_state"] == GEOMETRY_INVALID


def test_ordinary_geometry_stays_valid_and_the_tolerance_is_frozen() -> None:
    assert GEOMETRY_PAGE_TOLERANCE_PT == 2.0, "frozen before corpus validation; never tuned to a desired count"
    assert classify_geometry((72.0, 100.0, 400.0, 112.0), page_width=612.0, page_height=792.0) == (GEOMETRY_VALID, None)
    # Just inside the frozen tolerance: a CropBox/MediaBox difference is not a malformed observation.
    assert classify_geometry((-1.5, 0.0, 612.0, 792.0), page_width=612.0, page_height=792.0) == (GEOMETRY_VALID, None)
    assert classify_geometry((-2.5, 0.0, 612.0, 792.0), page_width=612.0, page_height=792.0) == (
        GEOMETRY_INVALID,
        "out_of_page",
    )
    assert classify_geometry(None, page_width=612.0, page_height=792.0) == (GEOMETRY_UNKNOWN, "missing")
    assert classify_geometry((5.0, 5.0, 4.0, 9.0), page_width=612.0, page_height=792.0) == (
        GEOMETRY_INVALID,
        "inverted",
    )


def test_geometry_validity_does_not_alter_chunk_or_extraction_behaviour(temp_db_url: str) -> None:
    """The judgment is recorded beside the observation; it changes nothing upstream of it."""
    from app.backend.pdf_processing.extraction import make_chunk_drafts

    extraction = extract_pdf(SEED_PDF)
    before = [
        (d.text, d.page_start, d.bbox_json) for d in make_chunk_drafts(extraction, source_attachment_checksum="x")
    ]

    engine, paper_id, attachment_id = _seed(temp_db_url)
    _store(engine, attachment_id, list(extraction.source_pages))

    after = [(d.text, d.page_start, d.bbox_json) for d in make_chunk_drafts(extraction, source_attachment_checksum="x")]
    assert before == after


# --- 20-23: the non-load-bearing and coverage invariants ---


def test_persisted_chunk_text_is_untouched_by_a_source_representation_write(temp_db_url: str) -> None:
    from app.backend.pdf_processing.ingest import attach_pdf_to_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Invariant fixture", csl_json={"title": "Invariant fixture"})
        result = attach_pdf_to_paper(conn, paper_id, str(SEED_PDF.resolve()))

    def chunk_digest():
        with engine.begin() as conn:
            rows = conn.execute(
                select(chunks.c.id, chunks.c.text, chunks.c.page_start, chunks.c.bbox_json).order_by(chunks.c.id)
            ).all()
        return hashlib.sha256(repr(rows).encode("utf-8")).hexdigest()

    before = chunk_digest()
    with engine.begin() as conn:
        assert is_source_current(conn, result["attachment_id"]) is True
    _store(engine, result["attachment_id"], list(extract_pdf(SEED_PDF).source_pages), checksum=result["checksum"])
    assert chunk_digest() == before


_RETRIEVAL_MODULES = (
    "app/backend/summarization/pipeline.py",
    "app/backend/summarization/verification.py",
    "app/backend/embeddings/pipeline.py",
    "app/backend/embeddings/retrieval.py",
    "app/backend/embeddings/vector_store.py",
    "app/backend/citations/suggest.py",
    "app/backend/citations/section_scope.py",
    "app/backend/persistence/fulltext_repo.py",
    "app/backend/llm/providers.py",
)

# H1b.1's own vocabulary joins the H1b guard: the moment retrieval consults completeness state, a
# stable locator or a geometry judgment, this substrate has become load-bearing.
_H1B1_NAMES = (
    "source_representations",
    "source_representation_repo",
    "component_path",
    "geometry_state",
    "SourceLocator",
)


@pytest.mark.parametrize("module_path", _RETRIEVAL_MODULES)
def test_retrieval_and_generation_never_read_the_representation_substrate(module_path: str) -> None:
    source = Path(module_path).read_text(encoding="utf-8")
    for name in _H1B1_NAMES:
        assert name not in source, f"{module_path} must not reference the H1b.1 substrate ({name})"


def test_a_soft_deleted_attachment_stays_outside_live_currentness_accounting(temp_db_url: str) -> None:
    engine, _, trashed_id = _seed(temp_db_url, deleted=True)
    _store(engine, trashed_id, _pages())
    engine_live, _, live_id = _seed(temp_db_url)
    _store(engine_live, live_id, _pages())

    with engine.begin() as conn:
        report = source_representation_report(conn)
        # A trashed paper's representation is still *current* in the technical sense -- it is simply
        # outside the live universe the report counts, which is what "by design" means here.
        assert trashed_id in attachments_with_current_source(conn)
    assert report["live"] == 1
    assert report["current"] == 1
    assert report[STATE_COMPLETE] == 1
    assert report["absent"] == 0


def test_extraction_observes_every_page_of_the_document(temp_db_url: str) -> None:
    """`expected_pages` is what extraction produced, which proves persistence completeness relative
    to deterministic extractor output. This is the separate guarantee that the extractor itself
    dropped no page -- held here rather than by a second PDF open on the ingest critical path."""
    extraction = extract_pdf(SEED_PDF)
    with fitz.open(SEED_PDF) as document:
        assert len(extraction.source_pages) == document.page_count
        assert len(extraction.pages) == document.page_count
    assert [page.page_number for page in extraction.source_pages] == list(range(1, len(extraction.source_pages) + 1))


def test_the_backfill_reports_every_non_current_state(temp_db_url: str, monkeypatch) -> None:
    """`--summary`'s accounting is what a developer reads to decide whether a library is covered."""
    import app.backend.persistence.source_components_repo as repo

    engine, _, complete_id = _seed(temp_db_url)
    _store(engine, complete_id, _pages())

    _, _, truncated_id = _seed(temp_db_url)
    monkeypatch.setattr(repo, "MAX_COMPONENTS_PER_ATTACHMENT", 10)
    _store(engine, truncated_id, _pages(count=2, blocks_per_page=5))
    monkeypatch.undo()

    _, _, absent_id = _seed(temp_db_url)

    with engine.begin() as conn:
        report = source_representation_report(conn)
    assert report["live"] == 3
    assert report["current"] == 1
    assert report[STATE_COMPLETE] == 1
    assert report[STATE_TRUNCATED] == 1
    assert report["absent"] == 1
    assert absent_id not in attachments_with_current_source_ids(engine)


def attachments_with_current_source_ids(engine) -> set[int]:
    with engine.begin() as conn:
        return attachments_with_current_source(conn)
