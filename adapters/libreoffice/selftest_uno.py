"""Headless round-trip self-test for the LibreOffice citation adapter (inc 108).

Drives a REAL (headless) LibreOffice Writer through the full live-field loop against a running callosum server,
asserting the position-aware render, the bibliography, restyle, and flatten. This is the proof the adapter works
end-to-end — and the regression harness for future changes.

Run it with **LibreOffice's bundled Python** (it has the `uno` bridge), pointed at a callosum server that already
holds the two papers whose ids you pass:

    soffice --headless --norestore --accept="socket,host=localhost,port=2002;urp;"
    "C:\\Program Files\\LibreOffice\\program\\python.exe" selftest_uno.py http://127.0.0.1:8080 <id1> <id2> 2002

(`adapters/libreoffice/run_roundtrip.py` automates this — seed a temp callosum, start the server + a headless
soffice, run this, tear down. Also runs in CI, path-scoped and non-blocking — see
`.github/workflows/libreoffice-adapter.yml`.)

Prints "SELFTEST OK" and exits 0 on success; prints the failed assertion and exits 1 otherwise.
"""

import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callosum_cite as cc  # noqa: E402  (after sys.path injection)
import evidence_insert  # noqa: E402
import uno  # noqa: E402


def connect(port, attempts=30):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    url = f"uno:socket,host=localhost,port={port};urp;StarOffice.ComponentContext"
    last = None
    for _ in range(attempts):
        try:
            return resolver.resolve(url)
        except Exception as exc:  # soffice not ready yet
            last = exc
            time.sleep(1)
    raise RuntimeError(f"could not connect to soffice on {port}: {last}")


def close_open_docs(ctx):
    """Close any documents left open (e.g. by a previously killed run) so the instance starts clean."""
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    enum = desktop.getComponents().createEnumeration()
    while enum.hasMoreElements():
        comp = enum.nextElement()
        try:
            comp.close(False)
        except Exception:
            pass


def new_writer(ctx):
    from com.sun.star.beans import PropertyValue

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = PropertyValue()
    hidden.Name, hidden.Value = "Hidden", True
    return desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, (hidden,))


def load_doc(ctx, url, hidden=True):
    """Load an existing document from a URL (vs. new_writer's blank-factory create) — used by the Phase-0
    save/reopen spike to get a genuinely fresh doc object backed by the saved file, not the original in-memory one."""
    from com.sun.star.beans import PropertyValue

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden_arg = PropertyValue()
    hidden_arg.Name, hidden_arg.Value = "Hidden", hidden
    return desktop.loadComponentFromURL(url, "_blank", 0, (hidden_arg,))


def dispatch_uno(ctx, frame, url):
    helper = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.DispatchHelper", ctx)
    helper.executeDispatch(frame, url, "", 0, ())


def rendered_by_paper(doc):
    out = {}
    for f in cc.scan_citations_in_order(doc):
        out[f["items"][0].get("id")] = f["_mark"].getAnchor().getString()
    return out


def order_of_papers(doc):
    return [f["items"][0].get("id") for f in cc.scan_citations_in_order(doc)]


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def log(msg):
    print(f"[selftest] {msg}", flush=True)


def wait_until(predicate, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return bool(predicate())


def spike_mark_size_and_reopen(ctx, base, p1, p2, n=25, evidence_n=3):
    """P0 phase-0 spike #1: insert N citations (redundant full-CSL-record embedding is the roadmap's own
    architectural concern) in one document, save to a real .odt, load it back as a FRESH doc object, and confirm
    every mark still decodes losslessly. Reports actual name-length numbers rather than assuming a scale is fine.

    IMPORTANT: citations are placed at N pre-existing anchors laid down BEFORE any refresh has run — never at
    "document end" repeatedly. An earlier version of this spike inserted at `text.getEnd()` on each iteration and
    accidentally reproduced the verified bibliography data-loss bug live: `insert_citation`'s own auto-refresh
    appends the bibliography at doc-end on its first run, so a *second* "insert at the end" call lands its new
    citation inside the bibliography's future-deletion zone — the very next refresh's
    `cursor.gotoEnd(True); cursor.setString("")` then silently destroyed every citation after the first. Only 1
    of 25 marks survived. This is exactly the hazard `_write_bibliography` was already known to have, now
    reproduced through a completely ordinary "cite, cite again" sequence, not a contrived edge case — a real
    finding for Phase 7, not a test bug. The anchor-based approach below avoids it (matching how the existing
    AAA/BBB round-trip test above already sidesteps it) so this spike measures what it set out to measure.

    inc 460 (roadmap #17): also inserts `evidence_n` GROUPED, evidence-bearing citations (2 items each, every
    item carrying a full-length `EVIDENCE_SNIPPET_MAX` snippet — the worst case for mark-name size, and exactly
    the shape `suggest_and_insert`'s multi-select path produces via `insert_citation_items`), proving both that
    the evidence-audit locator doesn't blow up mark-name size unreasonably and that a grouped multi-item citation
    with evidence round-trips losslessly through save/reopen, same as the plain single-item citations above."""
    import tempfile

    log(f"spike 1/4: mark-size/scale — inserting {n} citations + {evidence_n} grouped evidence-bearing citations")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    anchors = "\n".join(f"Anchor{i} XXX{i}" for i in range(n))
    evidence_anchors = "\n".join(f"EvAnchor{i} YYY{i}" for i in range(evidence_n))
    text.createTextCursorByRange(text.getStart()).setString(f"Stress test paragraph.\n{anchors}\n{evidence_anchors}\n")
    for i in range(n):
        pid = p1 if i % 2 == 0 else p2
        rng = find_range(f"XXX{i}")
        check(rng is not None, f"anchor XXX{i} not found before citation insert")
        cc.insert_citation(doc, pid, base, cursor=text.createTextCursorByRange(rng))

    long_snippet = "x" * cc.EVIDENCE_SNIPPET_MAX
    for i in range(evidence_n):
        rng = find_range(f"YYY{i}")
        check(rng is not None, f"anchor YYY{i} not found before evidence citation insert")
        items = [
            {
                "paper_id": p1,
                "locator": "12",
                "label": "page",
                "evidence_chunk_id": 100 + i,
                "evidence_page_start": 12,
                "evidence_page_end": 12,
                "evidence_snippet": long_snippet,
            },
            {
                "paper_id": p2,
                "locator": "30-32",
                "label": "page",
                "evidence_chunk_id": 200 + i,
                "evidence_page_start": 30,
                "evidence_page_end": 32,
                "evidence_snippet": long_snippet,
            },
        ]
        cc.insert_citation_items(doc, items, base, cursor=text.createTextCursorByRange(rng))

    total = n + evidence_n
    before = sorted(nm for nm in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm))
    lengths = [len(nm) for nm in before]
    log(f"spike 1/4: inserted {len(before)} marks; name length min={min(lengths)} max={max(lengths)} chars")
    check(len(before) == total, f"expected {total} marks, found {len(before)}")

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    try:
        save_url = uno.systemPathToFileUrl(save_path)
        from com.sun.star.beans import PropertyValue

        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeToURL(save_url, (filt,))
        reopened = load_doc(ctx, save_url)
        after = sorted(nm for nm in reopened.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm))
        check(len(after) == total, f"after save/reopen: expected {total} marks, found {len(after)}")
        items_before = {nm: cc.decode_mark_name(nm)["items"] for nm in before}
        items_after = {nm: cc.decode_mark_name(nm)["items"] for nm in after}
        check(items_before == items_after, "mark payload changed after a save/reopen round-trip")
        # inc 460: confirm the evidence-bearing items specifically survived the round-trip with their
        # evidence_* fields intact (not just "some payload equal to some other payload").
        evidence_items_after = [
            it for nm in after for it in cc.decode_mark_name(nm)["items"] if it.get("evidence_snippet")
        ]
        check(
            len(evidence_items_after) == evidence_n * 2,
            f"expected {evidence_n * 2} evidence-bearing items after reopen, found {len(evidence_items_after)}",
        )
        check(
            all(it["evidence_snippet"] == long_snippet for it in evidence_items_after),
            "an evidence snippet changed after save/reopen",
        )
        log(
            f"spike 1/4: OK — {total} marks (max name length {max(lengths)} chars, including {evidence_n} "
            "grouped evidence-bearing citations) round-trip losslessly through save/reopen"
        )
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass


def spike_undo_manager(ctx):
    """P0 phase-0 spike #2: XUndoManager has ZERO prior usage anywhere in this codebase — confirm
    enterUndoContext/leaveUndoContext/undo() actually groups + reverts a multi-step mutation in one call, since
    Phase 2 (transactional refresh) and Phase 8 (safe flatten) both depend on this behaving as documented."""
    log("spike 2/4: XUndoManager enter/leave/undo")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Before mutation.\n")
    original = text.getString()
    undo_mgr = doc.getUndoManager()
    undo_mgr.enterUndoContext("spike test")
    text.createTextCursorByRange(text.getEnd()).setString("Extra text added by the mutation.\n")
    undo_mgr.leaveUndoContext()
    mutated = text.getString()
    check(mutated != original, "the grouped mutation didn't actually change the document")
    undo_mgr.undo()
    restored = text.getString()
    check(restored == original, f"undo() did not restore the pre-mutation state: {restored!r} != {original!r}")
    log("spike 2/4: OK — enterUndoContext/leaveUndoContext/undo() reverts a grouped mutation in one call")


def spike_copy_paste_duplicate_name(ctx, base, p1):
    """P0 phase-0 spike #3: copy/paste a CALLOSUM_CITATION-named ReferenceMark within the same document and
    observe what Writer actually does to the name. This is a genuine open question, not a prediction — the
    outcome is LOGGED as a finding (for Phase 9's diagnostics design), never asserted to be a specific answer."""
    log("spike 3/4: copy/paste duplicate-name behavior")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Copy paste test.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(text.getEnd()))
    before = [nm for nm in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm)]
    check(len(before) == 1, f"expected exactly one mark before the copy/paste spike, found {len(before)}")
    mark = doc.getReferenceMarks().getByName(before[0])
    try:
        controller = doc.getCurrentController()
        controller.select(mark.getAnchor())
        frame = controller.getFrame()
        dispatch_uno(ctx, frame, ".uno:Copy")
        text.insertString(text.createTextCursorByRange(text.getEnd()), "\n", False)
        controller.select(text.createTextCursorByRange(text.getEnd()))
        dispatch_uno(ctx, frame, ".uno:Paste")
        after = [nm for nm in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm)]
        log(f"spike 3/4: before={before!r} after={after!r}")
        if len(after) == 1:
            log("spike 3/4 FINDING: paste did NOT duplicate the mark (Writer refused/dropped the name collision)")
        elif len(after) == 2 and after[0] == after[1]:
            log("spike 3/4 FINDING: paste DUPLICATED the exact mark name — a real collision risk for Phase 9")
        elif len(after) == 2:
            log("spike 3/4 FINDING: paste created a SECOND mark with a DIFFERENT auto-renamed name")
        else:
            log(f"spike 3/4 FINDING: unexpected mark count after copy/paste: {len(after)}")
    except Exception as exc:
        log(f"spike 3/4 FINDING: copy/paste dispatch raised {exc!r} — needs manual GUI investigation for Phase 9")


def spike_bounded_bibliography(ctx):
    """P0 phase-0 spike #4: prototype a bounded managed range for the future bibliography rewrite (Phase 7) —
    a TextSection wrapping the whole heading+entries block, rebuilt via ITS OWN anchor range rather than
    "bookmark-start to document-end". Proves (or disproves) that a rebuild-in-place preserves user text placed
    after the block — the exact fix the verified data-loss hazard needs."""
    log("spike 4/4: TextSection-bounded bibliography rebuild")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Body text before the bibliography.\n")
    try:
        section_cursor = text.createTextCursorByRange(text.getEnd())
        section = doc.createInstance("com.sun.star.text.TextSection")
        section.Name = "CALLOSUM_BIBLIOGRAPHY_SECTION_SPIKE"
        text.insertTextContent(section_cursor, section, False)
        section_range_text = section.getAnchor().getText()
        inner = section_range_text.createTextCursorByRange(section.getAnchor().getEnd())
        section_range_text.insertString(inner, "References\nEntry one\nEntry two\n", False)
        text.insertString(
            text.createTextCursorByRange(text.getEnd()), "User text placed after the bibliography.\n", False
        )

        sections = doc.getTextSections()
        check(sections.hasByName(section.Name), "TextSection not found by name after insert")
        sec = sections.getByName(section.Name)
        sec_cursor = text.createTextCursorByRange(sec.getAnchor())
        sec_cursor.setString("References\nRebuilt entry.\n")  # simulate a refresh rebuilding the block in place

        after_text = text.getString()
        check(
            "User text placed after the bibliography." in after_text,
            "TextSection rebuild destroyed text OUTSIDE the section — the bounded-range approach failed!",
        )
        check("Rebuilt entry." in after_text, "TextSection rebuild did not apply")
        log("spike 4/4: OK — TextSection rebuild-in-place preserved trailing user text. RECOMMENDED for Phase 7.")
    except Exception as exc:
        log(f"spike 4/4 FINDING: TextSection approach failed with {exc!r} — evaluate the Bookmark fallback for Phase 7")


def spike_transactional_refresh_rollback(ctx, base, p1, p2):
    """P0 phase 2: refresh()'s write-back loop is now wrapped in an UndoManager-grouped transaction
    (`_transactional_apply`) — a failure partway through must roll the WHOLE document back to its exact
    pre-refresh state, not leave some marks updated and others not. Injects a REAL failure (a module-level patch
    of `_replace_mark_text` that raises on its 2nd call) against a real UNO doc with 3 already-rendered
    citations, mid-restyle, and confirms every mark's text is back to its pre-refresh state afterward — the
    roadmap's own "verify expected marks still exist" step, proven against real UNO, not assumed."""
    log("spike (phase 2): transactional refresh rollback on a mid-loop failure")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    text.createTextCursorByRange(text.getStart()).setString("A XXX0. B XXX1. C XXX2.\n")
    for i, pid in enumerate((p1, p2, p1)):
        rng = find_range(f"XXX{i}")
        check(rng is not None, f"anchor XXX{i} not found")
        cc.insert_citation(doc, pid, base, cursor=text.createTextCursorByRange(rng))
    cc.set_style(doc, "ieee", "en-US", base)  # a known-good, successfully-rendered baseline to roll back to

    def snapshot():
        return {
            nm: doc.getReferenceMarks().getByName(nm).getAnchor().getString()
            for nm in doc.getReferenceMarks().getElementNames()
            if cc.decode_mark_name(nm)
        }

    before = snapshot()
    check(len(before) == 3, f"expected 3 marks before the fault injection, found {len(before)}")

    original = cc._replace_mark_text
    calls = {"n": 0}

    def flaky(doc_, mark, new_text):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("injected failure for the phase-2 rollback spike")
        return original(doc_, mark, new_text)

    cc._replace_mark_text = flaky
    try:
        raised = None
        try:
            cc.set_style(doc, "apa", "en-US", base)  # a real, different render — restyle mid-loop, then fail
        except Exception as exc:
            raised = exc
        check(raised is not None, "expected the injected failure to propagate out of set_style/refresh")
        log(f"spike (phase 2): injected failure propagated as expected: {raised!r}")
    finally:
        cc._replace_mark_text = original

    after = snapshot()
    log(f"spike (phase 2): before={before} after={after}")
    check(after == before, f"rollback did not restore the pre-refresh state: {after} != {before}")
    log("spike (phase 2): OK — a mid-loop failure rolled back to the exact pre-refresh state (no mixed document)")


def spike_refresh_progress_cancellation(ctx, base, p1, p2):
    """P1 item #13: native status progress, cooperative cancellation rollback, and stale-response rejection."""
    log("spike (P1 #13): native refresh progress + cancellation")
    cc._DISPATCH_CTX = ctx
    doc = new_writer(ctx)
    text = doc.getText()
    count = 12
    text.createTextCursorByRange(text.getStart()).setString(" ".join(f"XXX{i}" for i in range(count)) + "\n")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    cc.set_cite_auto(doc, False)
    cc.set_bib_auto(doc, False)
    for index in range(count):
        cc.insert_citation(
            doc,
            p1 if index % 2 == 0 else p2,
            base,
            cursor=text.createTextCursorByRange(find_range(f"XXX{index}")),
        )
    cc.set_cite_auto(doc, True)
    cc.set_bib_auto(doc, True)
    cc._set_pref(doc, "ieee", "en-US")
    cc.refresh(doc, base)

    native = cc._new_refresh_progress(doc, cc.PROGRESS_MIN_WORK)
    check(native.indicator is not None and native.started, "Writer did not provide a native status indicator")
    check(native.listener is not None, "Writer did not register the temporary Escape-key listener")

    class EscapeEvent:
        KeyCode = 1281  # com.sun.star.awt.Key.ESCAPE

    check(native.listener.keyPressed(EscapeEvent()), "the Escape listener did not consume Escape")
    cancelled = False
    try:
        native.update(1, "Callosum: cancellation probe")
    except cc.RefreshCancelled:
        cancelled = True
    finally:
        native.close()
    check(cancelled, "the Escape listener did not cooperatively cancel progress")

    def snapshot():
        return {
            nm: doc.getReferenceMarks().getByName(nm).getAnchor().getString()
            for nm in doc.getReferenceMarks().getElementNames()
            if cc.decode_mark_name(nm)
        }

    cc._set_pref(doc, "apa", "en-US")
    cc.set_dirty_state(doc, citations=True, bibliography=True)
    before = snapshot()
    original_progress_factory = cc._new_refresh_progress

    class CancelDuringWrite:
        def __init__(self):
            self.closed = False

        def update(self, _value, label):
            if "updated citation 3 of" in label:
                raise cc.RefreshCancelled("injected cancellation")

        def close(self):
            self.closed = True

    injected = CancelDuringWrite()
    cc._new_refresh_progress = lambda _doc, _total: injected
    try:
        raised = None
        try:
            cc.refresh(doc, base)
        except Exception as exc:
            raised = exc
        check(isinstance(raised, cc.RefreshCancelled), f"expected RefreshCancelled, got {raised!r}")
    finally:
        cc._new_refresh_progress = original_progress_factory
    check(injected.closed, "refresh did not close its progress controller after cancellation")
    check(snapshot() == before, "cancellation did not roll every partial citation write back")
    check(cc.dirty_state(doc) == (True, True), "cancelled refresh incorrectly cleared pending state")

    original_render = cc.render_document
    manual_text = "MANUAL CITATION EDIT"

    def render_while_document_changes(base_, request):
        response = original_render(base_, request)
        first = cc.scan_citations_in_order(doc)[0]["_mark"]
        cc._replace_mark_text(doc, first, manual_text)
        return response

    cc.render_document = render_while_document_changes
    try:
        raised = None
        try:
            cc.refresh(doc, base)
        except Exception as exc:
            raised = exc
        check(
            isinstance(raised, RuntimeError) and "changed while Callosum was formatting" in str(raised),
            f"stale render response was not rejected: {raised!r}",
        )
    finally:
        cc.render_document = original_render
    check(
        cc.scan_citations_in_order(doc)[0]["_mark"].getAnchor().getString() == manual_text,
        "stale render response overwrote the concurrent Writer citation edit",
    )
    log("spike (P1 #13): OK — native progress, full cancellation rollback, stale response rejected")


def spike_incremental_rendering(ctx, base, p1, p2):
    """P1 item #13: full-document citeproc context produces only the Writer mutations whose output changed."""
    log("spike (P1 #13): incremental citation/bibliography write-back")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("First XXX0. Second XXX1. Third XXX2.\n")
    cc._set_pref(doc, "ieee", "en-US")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    for index, paper_id in enumerate((p1, p2, p1)):
        cc.insert_citation(doc, paper_id, base, cursor=text.createTextCursorByRange(find_range(f"XXX{index}")))
    fields = cc.scan_citations_in_order(doc)
    check(len(fields) == 3, f"incremental fixture expected 3 fields, found {len(fields)}")
    check(
        cc.bibliography_render_is_current(
            doc,
            cc.render_document(
                base,
                cc.build_render_request(fields, "ieee", "en-US"),
            )["bibliography_text"].splitlines(),
        ),
        "incremental fixture bibliography was not current",
    )

    original_replace = cc._replace_mark_text
    original_write_bibliography = cc._write_bibliography
    calls = {"citations": 0, "bibliography": 0}

    def tracked_replace(doc_, mark, rendered):
        calls["citations"] += 1
        return original_replace(doc_, mark, rendered)

    def tracked_bibliography(
        doc_,
        entries,
        entry_ids=None,
        entry_links=None,
        entry_categories=None,
        external_links=False,
        cursor=None,
    ):
        calls["bibliography"] += 1
        return original_write_bibliography(
            doc_,
            entries,
            entry_ids=entry_ids,
            entry_links=entry_links,
            entry_categories=entry_categories,
            external_links=external_links,
            cursor=cursor,
        )

    cc._replace_mark_text = tracked_replace
    cc._write_bibliography = tracked_bibliography
    try:
        cc.refresh(doc, base)
        check(calls == {"citations": 0, "bibliography": 0}, f"identical refresh mutated Writer: {calls}")

        first = cc.scan_citations_in_order(doc)[0]["_mark"]
        original_replace(doc, first, "STALE CITATION")
        calls.update(citations=0, bibliography=0)
        cc.refresh(doc, base)
        check(calls == {"citations": 1, "bibliography": 0}, f"one stale citation produced wrong delta: {calls}")

        original_write_bibliography(doc, ["STALE BIBLIOGRAPHY"])
        calls.update(citations=0, bibliography=0)
        cc.refresh_bibliography(doc, base)
        check(
            calls == {"citations": 0, "bibliography": 1},
            f"one stale bibliography produced wrong delta: {calls}",
        )
    finally:
        cc._replace_mark_text = original_replace
        cc._write_bibliography = original_write_bibliography
    log("spike (P1 #13): OK — identical=0 writes; stale citation=1; stale bibliography=1")


def spike_note_style_footnotes(ctx, base, p1, p2):
    """P1 item #10: note styles create/manage real Writer footnotes and endnotes with native note indexes."""
    log("spike (P1 #10): note-style citations in real Writer footnotes and endnotes")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("First XXX0. Second XXX1. Third XXX2.\n")
    cc._set_pref(doc, "chicago-notes-bibliography", "en-US")

    def insertion_cursor(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        found = doc.findFirst(sd)
        cursor = text.createTextCursorByRange(found)
        cursor.setString("")
        cursor.collapseToStart()
        return cursor

    for index, paper_id in enumerate((p1, p2, p1)):
        cc.insert_citation(doc, paper_id, base, cursor=insertion_cursor(f"XXX{index}"))

    fields = cc.scan_citations_in_order(doc)
    check(doc.getFootnotes().getCount() == 3, "note style did not create three Writer footnotes")
    check(len(fields) == 3, f"note-style fixture expected 3 citation fields, found {len(fields)}")
    check([field["placement"] for field in fields] == ["footnote"] * 3, "note marks were not classified as footnotes")
    check([field["noteIndex"] for field in fields] == [1, 2, 3], "Writer footnote indexes did not reach scan order")
    request = cc.build_render_request(fields, "chicago-notes-bibliography", "en-US")
    check([cluster["noteIndex"] for cluster in request["citations"]] == [1, 2, 3], "note indexes left request shape")
    first_text = fields[0]["_mark"].getAnchor().getString()
    repeated_text = fields[2]["_mark"].getAnchor().getString()
    check(first_text and repeated_text and first_text != repeated_text, "subsequent Chicago note was not shortened")
    check(first_text not in text.getString(), "rendered note citation leaked into the main document text")

    view = doc.getCurrentController().getViewCursor()
    view.gotoRange(fields[1]["_mark"].getAnchor().getStart(), False)
    selected = cc.mark_at_cursor(doc)
    check(
        selected is not None and selected["citationID"] == fields[1]["citationID"], "cursor lookup failed in footnote"
    )

    old_pref = cc._get_pref(doc)
    try:
        cc.set_style(doc, "apa", "en-US", base)
    except ValueError as exc:
        check("Automatic conversion" in str(exc), f"wrong note-to-inline style error: {exc}")
    else:
        raise AssertionError("note-to-inline style switch was silently accepted")
    check(cc._get_pref(doc) == old_pref, "rejected note-to-inline switch changed document preferences")

    cc.delete_citation(doc, fields[1])
    cc.refresh(doc, base)
    remaining = cc.scan_citations_in_order(doc)
    check(doc.getFootnotes().getCount() == 2, "deleting an otherwise-empty note citation left an empty footnote")
    check([field["noteIndex"] for field in remaining] == [1, 2], "remaining footnotes did not renumber after delete")

    static_note_text = [field["_mark"].getAnchor().getString() for field in remaining]
    check(cc.flatten(doc) == 2, "flatten did not unlink both remaining note citations")
    check(doc.getReferenceMarks().getCount() == 0, "flatten left live ReferenceMarks in note bodies")
    check(
        [doc.getFootnotes().getByIndex(index).getString() for index in range(2)] == static_note_text,
        "flatten did not preserve static rendered note text",
    )

    end_doc = new_writer(ctx)
    end_text = end_doc.getText()
    end_text.createTextCursorByRange(end_text.getStart()).setString("End one END0. End two END1. End three END2.\n")
    cc._set_pref(end_doc, "chicago-notes-bibliography", "en-US")
    check(cc.note_placement(end_doc) == "footnote", "fresh document did not default note placement to footnotes")
    cc.set_note_placement(end_doc, "endnote")
    check(cc.note_placement(end_doc) == "endnote", "endnote placement did not persist in the document")

    def endnote_cursor(needle):
        sd = end_doc.createSearchDescriptor()
        sd.SearchString = needle
        found = end_doc.findFirst(sd)
        cursor = end_text.createTextCursorByRange(found)
        cursor.setString("")
        cursor.collapseToStart()
        return cursor

    for index, paper_id in enumerate((p1, p2, p1)):
        cc.insert_citation(end_doc, paper_id, base, cursor=endnote_cursor(f"END{index}"))

    end_fields = cc.scan_citations_in_order(end_doc)
    check(end_doc.getFootnotes().getCount() == 0, "endnote placement unexpectedly created a footnote")
    check(end_doc.getEndnotes().getCount() == 3, "endnote placement did not create three Writer endnotes")
    check([field["placement"] for field in end_fields] == ["endnote"] * 3, "endnote marks were misclassified")
    check([field["noteIndex"] for field in end_fields] == [1, 2, 3], "Writer endnote indexes did not reach scan order")
    check(
        end_fields[0]["_mark"].getAnchor().getString() != end_fields[2]["_mark"].getAnchor().getString(),
        "repeated Chicago endnote was not shortened",
    )

    old_placement = cc.note_placement(end_doc)
    try:
        cc.set_note_placement(end_doc, "footnote")
    except ValueError as exc:
        check("Convert citation placement" in str(exc), f"wrong endnote-to-footnote placement error: {exc}")
    else:
        raise AssertionError("endnote-to-footnote placement change was silently accepted")
    check(cc.note_placement(end_doc) == old_placement, "rejected placement change mutated the document preference")

    end_view = end_doc.getCurrentController().getViewCursor()
    end_view.gotoRange(end_fields[1]["_mark"].getAnchor().getStart(), False)
    selected_endnote = cc.mark_at_cursor(end_doc)
    check(
        selected_endnote is not None and selected_endnote["citationID"] == end_fields[1]["citationID"],
        "cursor lookup failed in endnote",
    )
    endnote_static_text = [field["_mark"].getAnchor().getString() for field in end_fields]
    check(cc.flatten(end_doc) == 3, "flatten did not unlink all endnote citations")
    check(
        [end_doc.getEndnotes().getByIndex(index).getString() for index in range(3)] == endnote_static_text,
        "flatten did not preserve static rendered endnote text",
    )
    log(
        "spike (P1 #10): OK — real footnotes/endnotes, note indexes, shortened repeats, "
        "safe placement/style/delete/flatten"
    )


def spike_note_style_positions(ctx, base, p1, p2):
    """P1 item #10: exact citeproc ibid, near-note, and far-subsequent state from native Writer indexes."""
    log("spike (P1 #10): exact ibid/near-note/subsequent positions through an imported note style")
    position_csl = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="note" version="1.0">
  <info>
    <title>Callosum Writer Note Position Test</title>
    <id>https://example.test/styles/callosum-writer-note-position-test</id>
    <link href="https://example.test/styles/callosum-writer-note-position-test" rel="self"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
    <category citation-format="note"/>
  </info>
  <citation near-note-distance="2">
    <layout delimiter="; ">
      <choose>
        <if position="ibid-with-locator">
          <text value="IBID-WITH-LOCATOR"/>
          <text variable="locator" prefix=":"/>
        </if>
        <else-if position="ibid"><text value="IBID"/></else-if>
        <else-if position="subsequent">
          <choose>
            <if position="near-note"><text value="NEAR"/></if>
            <else><text value="SUBSEQUENT"/></else>
          </choose>
        </else-if>
        <else>
          <text value="FIRST"/>
          <text variable="title" prefix=":"/>
        </else>
      </choose>
    </layout>
  </citation>
  <bibliography><layout><text variable="title"/></layout></bibliography>
</style>"""
    installed = cc._post_json(
        f"{base}/citations/styles/install",
        {"filename": "callosum-writer-note-position-test.csl", "csl": position_csl, "replace": True},
    )["install"]
    style_id = installed["style"]["id"]
    doc = new_writer(ctx)
    text = doc.getText()
    text.setString("First N1. Ibid N2. New locator N3. Other N4. Near N5. User U6. User U7. Far N8.\n")
    cc._set_pref(doc, style_id, "en-US")

    def insertion_cursor(needle):
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = needle
        found = doc.findFirst(descriptor)
        check(found is not None, f"missing note-position fixture marker {needle}")
        cursor = text.createTextCursorByRange(found)
        cursor.setString("")
        cursor.collapseToStart()
        return cursor

    cc.insert_citation_items(
        doc,
        [{"paper_id": p1, "locator": "10", "label": "page"}],
        base,
        insertion_cursor("N1"),
    )
    cc.insert_citation_items(
        doc,
        [{"paper_id": p1, "locator": "10", "label": "page"}],
        base,
        insertion_cursor("N2"),
    )
    cc.insert_citation_items(
        doc,
        [{"paper_id": p1, "locator": "11", "label": "page"}],
        base,
        insertion_cursor("N3"),
    )
    cc.insert_citation(doc, p2, base, cursor=insertion_cursor("N4"))
    cc.insert_citation(doc, p1, base, cursor=insertion_cursor("N5"))
    for marker, body in (("U6", "ordinary user note one"), ("U7", "ordinary user note two")):
        note = doc.createInstance("com.sun.star.text.Footnote")
        text.insertTextContent(insertion_cursor(marker), note, False)
        note.setString(body)
    cc.insert_citation(doc, p1, base, cursor=insertion_cursor("N8"))

    fields = cc.scan_citations_in_order(doc)
    check([field["noteIndex"] for field in fields] == [1, 2, 3, 4, 5, 8], "ordinary notes did not create index gaps")
    rendered = [field["_mark"].getAnchor().getString() for field in fields]
    check(rendered[0].startswith("FIRST:"), f"first note position was {rendered[0]!r}")
    check(rendered[1] == "IBID", f"same-locator ibid position was {rendered[1]!r}")
    check(rendered[2] == "IBID-WITH-LOCATOR:11", f"changed-locator ibid position was {rendered[2]!r}")
    check(rendered[3].startswith("FIRST:"), f"intervening source first position was {rendered[3]!r}")
    check(rendered[4] == "NEAR", f"near-note position was {rendered[4]!r}")
    check(rendered[5] == "SUBSEQUENT", f"far subsequent-note position was {rendered[5]!r}")
    check(
        [doc.getFootnotes().getByIndex(index).getString() for index in (5, 6)]
        == ["ordinary user note one", "ordinary user note two"],
        "position-aware refresh changed ordinary Writer footnotes",
    )
    log("spike (P1 #10): OK — exact ibid/locator/near/far branches and native note-index gaps")


def spike_multiple_citations_in_prose_notes(ctx, base, p1, p2):
    """P1 item #10: add/manage independent live clusters at a caret inside prose-bearing native notes."""
    log("spike (P1 #10): multiple independent live clusters mixed with user prose in one note")
    for placement, getter in (("footnote", "getFootnotes"), ("endnote", "getEndnotes")):
        doc = new_writer(ctx)
        text = doc.getText()
        text.setString(f"One shared {placement} NOTE.\n")
        cc._set_pref(doc, "chicago-notes-bibliography", "en-US")
        cc.set_note_placement(doc, placement)

        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = "NOTE"
        found = doc.findFirst(descriptor)
        cursor = text.createTextCursorByRange(found)
        cursor.setString("")
        cursor.collapseToStart()
        cc.insert_citation(doc, p1, base, cursor=cursor)

        notes = getattr(doc, getter)()
        check(notes.getCount() == 1, f"initial {placement} citation did not create one native note")
        note = notes.getByIndex(0)
        note.insertString(note.getEnd(), " supports the first point; compare ", False)
        view = doc.getCurrentController().getViewCursor()
        view.gotoRange(note.getEnd(), False)
        cc.insert_citation(doc, p2, base)
        note.insertString(note.getEnd(), " for a contrasting account.", False)

        fields = cc.scan_citations_in_order(doc)
        check(len(fields) == 2, f"{placement} did not retain two independent live clusters")
        check([field["placement"] for field in fields] == [placement, placement], f"wrong {placement} contexts")
        check([field["noteIndex"] for field in fields] == [1, 1], f"{placement} clusters did not share note index 1")
        check(
            fields[0]["citationID"] != fields[1]["citationID"],
            f"{placement} clusters unexpectedly shared one citation identity",
        )
        shared_text = note.getString()
        check(
            "supports the first point; compare" in shared_text and "for a contrasting account." in shared_text,
            f"{placement} prose was not retained around the two citations",
        )
        cc.refresh(doc, base)
        check(note.getString() == shared_text, f"idempotent refresh rewrote current {placement} prose or citations")

        before_conversion = cc._conversion_snapshot(doc)
        try:
            cc.convert_citation_placement(doc, "apa", "en-US", placement, base)
        except ValueError as exc:
            check("exactly one live citation cluster" in str(exc), f"wrong grouped-note refusal: {exc}")
        else:
            raise AssertionError(f"conversion silently moved a prose-bearing multi-cluster {placement}")
        check(
            cc._conversion_snapshot(doc) == before_conversion,
            f"refused {placement} conversion changed the document",
        )

        first = cc.scan_citations_in_order(doc)[0]
        cc.delete_citation(doc, first)
        cc.refresh(doc, base)
        remaining = cc.scan_citations_in_order(doc)
        check(len(remaining) == 1 and notes.getCount() == 1, f"deleting one cluster removed the shared {placement}")
        check(
            "supports the first point; compare" in note.getString(), f"deleting one cluster removed {placement} prose"
        )

        cc.delete_citation(doc, remaining[0])
        cc.refresh(doc, base)
        check(not cc.scan_citations_in_order(doc), f"last live cluster survived deletion from {placement}")
        check(notes.getCount() == 1, f"deleting the last cluster removed a prose-bearing {placement}")
        check(
            "supports the first point; compare" in note.getString()
            and "for a contrasting account." in note.getString(),
            f"deleting the last cluster removed prose from {placement}",
        )
    log("spike (P1 #10): OK — shared footnote/endnote authoring, refresh, refusal, and deletion")


def spike_note_placement_conversion(ctx, base, p1, p2):
    """P1 #10 conversion: native relocation, custom property Undo/Redo, rollback, refusal, and copy isolation."""
    import tempfile

    log("spike (P1 #10): explicit inline/footnote/endnote conversion")

    def inline_fixture():
        fixture = new_writer(ctx)
        body = fixture.getText()
        body.createTextCursorByRange(body.getStart()).setString("First CV0. Second CV1. Third CV2.\n")
        cc._set_pref(fixture, "apa", "en-US")
        for index, paper_id in enumerate((p1, p2, p1)):
            sd = fixture.createSearchDescriptor()
            sd.SearchString = f"CV{index}"
            found = fixture.findFirst(sd)
            cursor = body.createTextCursorByRange(found)
            cursor.setString("")
            cursor.collapseToStart()
            cc.insert_citation(fixture, paper_id, base, cursor=cursor)
        return fixture

    doc = inline_fixture()
    before = cc._conversion_snapshot(doc)
    original_names = [field["_mark"].Name for field in cc.scan_citations_in_order(doc)]
    result = cc.convert_citation_placement(doc, "chicago-notes-bibliography", "en-US", "footnote", base)
    converted = cc.scan_citations_in_order(doc)
    check(result["source_placement"] == "inline" and result["target_placement"] == "footnote", f"bad result: {result}")
    check(doc.getFootnotes().getCount() == 3, "inline-to-footnote conversion did not create three footnotes")
    check([field["placement"] for field in converted] == ["footnote"] * 3, "converted fields are not footnotes")
    check([field["_mark"].Name for field in converted] == original_names, "conversion changed citation identities")
    check(cc._get_pref(doc) == ("chicago-notes-bibliography", "en-US"), "conversion did not persist target style")

    undo = doc.getUndoManager()
    check(undo.getCurrentUndoActionTitle() == "Convert Callosum citation placement", "conversion is not one undo step")
    undo.undo()
    after_undo = cc._conversion_snapshot(doc)
    check(
        after_undo == before,
        "Writer Undo did not restore inline fields and metadata exactly: "
        + cc._conversion_snapshot_differences(before, after_undo),
    )
    undo.redo()
    redone = cc.scan_citations_in_order(doc)
    check([field["placement"] for field in redone] == ["footnote"] * 3, "Writer Redo did not restore footnotes")
    check(cc._get_pref(doc)[0] == "chicago-notes-bibliography", "Writer Redo did not restore target style")

    cc.convert_citation_placement(doc, "chicago-notes-bibliography", "en-US", "endnote", base)
    endnotes = cc.scan_citations_in_order(doc)
    check(doc.getFootnotes().getCount() == 0 and doc.getEndnotes().getCount() == 3, "footnote-to-endnote failed")
    check([field["placement"] for field in endnotes] == ["endnote"] * 3, "converted notes are not endnotes")
    check([field["_mark"].Name for field in endnotes] == original_names, "footnote-to-endnote changed identities")

    cc.convert_citation_placement(doc, "apa", "en-US", "endnote", base)
    inline_again = cc.scan_citations_in_order(doc)
    check(doc.getEndnotes().getCount() == 0, "endnote-to-inline left native endnotes behind")
    check([field["placement"] for field in inline_again] == ["inline"] * 3, "endnote-to-inline failed")
    check([field["_mark"].Name for field in inline_again] == original_names, "endnote-to-inline changed identities")
    check(cc._get_pref(doc) == ("apa", "en-US"), "endnote-to-inline did not persist APA")

    prose_doc = new_writer(ctx)
    prose_text = prose_doc.getText()
    prose_text.setString("One PROSE.\n")
    cc._set_pref(prose_doc, "chicago-notes-bibliography", "en-US")
    sd = prose_doc.createSearchDescriptor()
    sd.SearchString = "PROSE"
    prose_cursor = prose_text.createTextCursorByRange(prose_doc.findFirst(sd))
    prose_cursor.setString("")
    cc.insert_citation(prose_doc, p1, base, cursor=prose_cursor)
    prose_note = prose_doc.getFootnotes().getByIndex(0)
    prose_note.insertString(prose_note.getEnd(), " user-authored explanation", False)
    prose_before = cc._conversion_snapshot(prose_doc)
    try:
        cc.convert_citation_placement(prose_doc, "apa", "en-US", "footnote", base)
    except ValueError as exc:
        check("user prose" in str(exc), f"wrong prose refusal: {exc}")
    else:
        raise AssertionError("conversion silently moved a note containing user prose")
    check(cc._conversion_snapshot(prose_doc) == prose_before, "prose refusal mutated the document")

    rollback_doc = inline_fixture()
    rollback_before = cc._conversion_snapshot(rollback_doc)
    original_relocate = cc._relocate_mark
    calls = {"n": 0}

    def fail_second(doc_, name, rendered, target):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("injected conversion failure")
        return original_relocate(doc_, name, rendered, target)

    cc._relocate_mark = fail_second
    try:
        try:
            cc.convert_citation_placement(
                rollback_doc,
                "chicago-notes-bibliography",
                "en-US",
                "footnote",
                base,
            )
        except RuntimeError as exc:
            check("injected conversion failure" in str(exc), f"wrong injected error: {exc}")
        else:
            raise AssertionError("injected conversion failure did not propagate")
    finally:
        cc._relocate_mark = original_relocate
    check(cc._conversion_snapshot(rollback_doc) == rollback_before, "conversion rollback did not restore exactly")

    fd, source_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    source_url = uno.systemPathToFileUrl(source_path)
    copy_path = os.path.join(os.path.dirname(source_path), "callosum-converted-copy.odt")
    try:
        from com.sun.star.beans import PropertyValue

        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeAsURL(source_url, (filt,))
        copy_before = cc._conversion_snapshot(doc)
        copy_result, copy_url = cc.save_converted_copy(
            doc,
            os.path.basename(copy_path),
            "chicago-notes-bibliography",
            "en-US",
            "footnote",
            base,
        )
        check(copy_result["count"] == 3 and copy_url == uno.systemPathToFileUrl(copy_path), "bad copy result")
        check(cc._conversion_snapshot(doc) == copy_before, "converted-copy flow changed the open document")
        reopened = load_doc(ctx, copy_url)
        copied_fields = cc.scan_citations_in_order(reopened)
        check([field["placement"] for field in copied_fields] == ["footnote"] * 3, "saved copy is not converted")
        check(cc._get_pref(reopened)[0] == "chicago-notes-bibliography", "saved copy lost target style")
        reopened.close(False)
    finally:
        for path in (copy_path, source_path):
            try:
                os.remove(path)
            except OSError:
                pass
    log(
        "spike (P1 #10): OK — inline/footnote/endnote conversion, one-step Undo/Redo, "
        "verified rollback/prose refusal, isolated copy"
    )


def spike_tracked_change_placement_conversion(ctx, base, p1, p2):
    """P1 item #10: preserve unrelated Writer redlines and refuse redlines inside managed citation content."""
    log("spike (P1 #10): tracked-change-aware citation placement conversion")

    def tracked_fixture():
        fixture = new_writer(ctx)
        body = fixture.getText()
        body.setString("First TC0. Second TC1. Closing prose.\n")
        cc._set_pref(fixture, "apa", "en-US")
        for index, paper_id in enumerate((p1, p2)):
            descriptor = fixture.createSearchDescriptor()
            descriptor.SearchString = f"TC{index}"
            found = fixture.findFirst(descriptor)
            cursor = body.createTextCursorByRange(found)
            cursor.setString("")
            cursor.collapseToStart()
            cc.insert_citation(fixture, paper_id, base, cursor=cursor)

        ordinary_note = fixture.createInstance("com.sun.star.text.Footnote")
        body.insertTextContent(body.createTextCursorByRange(body.getEnd()), ordinary_note, False)
        ordinary_note.setString("Ordinary note.")

        fixture.RecordChanges = True
        descriptor = fixture.createSearchDescriptor()
        descriptor.SearchString = "First"
        insert_at = body.createTextCursorByRange(fixture.findFirst(descriptor).getEnd())
        body.insertString(insert_at, " carefully", False)
        descriptor.SearchString = "Closing"
        body.createTextCursorByRange(fixture.findFirst(descriptor)).setString("")
        ordinary_note.insertString(ordinary_note.getEnd(), " Tracked note edit.", False)
        return fixture, ordinary_note

    doc, ordinary_note = tracked_fixture()
    before = cc._conversion_snapshot(doc)
    before_redlines = cc._tracked_changes_signature(doc)
    check(len(before_redlines) == 3, f"expected three unrelated tracked changes, got {before_redlines}")
    result = cc.convert_citation_placement(doc, "chicago-notes-bibliography", "en-US", "footnote", base)
    fields = cc.scan_citations_in_order(doc)
    check([field["placement"] for field in fields] == ["footnote", "footnote"], "tracked conversion did not finish")
    check(result["tracked_changes_preserved"] == 3, f"wrong preserved redline count: {result}")
    check(doc.RecordChanges is True, "conversion did not restore Track Changes recording")
    check(cc._tracked_changes_signature(doc) == before_redlines, "conversion changed unrelated tracked changes")
    check("Tracked note edit." in ordinary_note.getString(), "conversion changed an unrelated tracked note")

    undo = doc.getUndoManager()
    undo.undo()
    check(doc.RecordChanges is True, "Writer Undo changed the Track Changes recording state")
    check(cc._conversion_snapshot(doc) == before, "Writer Undo did not restore tracked conversion exactly")
    undo.redo()
    check(doc.RecordChanges is True, "Writer Redo changed the Track Changes recording state")
    check(cc._tracked_changes_signature(doc) == before_redlines, "Writer Redo changed unrelated tracked changes")

    conflict = new_writer(ctx)
    conflict_text = conflict.getText()
    conflict_text.setString("Conflict TRACKED-CITE.\n")
    cc._set_pref(conflict, "apa", "en-US")
    descriptor = conflict.createSearchDescriptor()
    descriptor.SearchString = "TRACKED-CITE"
    cursor = conflict_text.createTextCursorByRange(conflict.findFirst(descriptor))
    cursor.setString("")
    cursor.collapseToStart()
    cc.insert_citation(conflict, p1, base, cursor=cursor)
    conflict.RecordChanges = True
    mark = cc.scan_citations_in_order(conflict)[0]["_mark"]
    inside = conflict_text.createTextCursorByRange(mark.getAnchor().getStart())
    inside.goRight(1, False)
    conflict_text.insertString(inside, "X", False)
    conflict_before = cc._conversion_snapshot(conflict)
    try:
        cc.convert_citation_placement(conflict, "chicago-notes-bibliography", "en-US", "footnote", base)
    except ValueError as exc:
        check("overlap a live citation" in str(exc), f"wrong tracked-citation refusal: {exc}")
    else:
        raise AssertionError("conversion silently moved a citation containing a tracked change")
    check(conflict.RecordChanges is True, "refused conversion changed Track Changes recording")
    check(cc._conversion_snapshot(conflict) == conflict_before, "tracked-citation refusal mutated the document")
    log("spike (P1 #10): OK — unrelated redlines preserved; managed overlap refused before mutation")


def spike_mark_at_cursor(ctx, base, p1, p2):
    """P0 phase 4: `mark_at_cursor` is the first "which ONE existing citation is the user pointing at" lookup —
    every prior action either inserted new or operated over all marks. Confirms, against real UNO, that moving
    the VIEW cursor inside citation #2 of 3 correctly resolves to citation #2 (not #1 or #3), and that a cursor
    positioned in plain body text (on no citation at all) correctly resolves to None."""
    log("spike (phase 4): mark_at_cursor resolves the citation under the view cursor")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    text.createTextCursorByRange(text.getStart()).setString("Body start. A XXX0. B XXX1. C XXX2. Body end.\n")
    rnds = []
    for i, pid in enumerate((p1, p2, p1)):
        rng = find_range(f"XXX{i}")
        check(rng is not None, f"anchor XXX{i} not found")
        rnds.append(cc.insert_citation(doc, pid, base, cursor=text.createTextCursorByRange(rng)))

    controller = doc.getCurrentController()
    view_cursor = controller.getViewCursor()

    # Move the view cursor INTO citation #2's own rendered range (its anchor's own text, not just near it).
    marks = doc.getReferenceMarks()
    second_mark = next(
        m
        for m in [marks.getByName(n) for n in marks.getElementNames()]
        if cc.decode_mark_name(m.Name) and cc.decode_mark_name(m.Name)["rnd"] == rnds[1]
    )
    view_cursor.gotoRange(second_mark.getAnchor().getStart(), False)
    found = cc.mark_at_cursor(doc)
    check(found is not None, "mark_at_cursor found nothing with the cursor inside citation #2")
    check(
        found["citationID"] == rnds[1],
        f"mark_at_cursor resolved citationID {found['citationID']!r}, expected {rnds[1]!r} (citation #2)",
    )
    log(f"spike (phase 4): cursor inside citation #2 correctly resolved to citationID={found['citationID']!r}")

    # Move the view cursor to plain body text (the very start of the document) — no citation there.
    view_cursor.gotoRange(text.getStart(), False)
    none_found = cc.mark_at_cursor(doc)
    check(none_found is None, f"mark_at_cursor should have found nothing in plain body text, got {none_found!r}")
    log("spike (phase 4): OK — cursor in plain body text correctly resolved to None")


def spike_delete_citation(ctx, base, p1, p2):
    """P0 phase 6: `delete_citation` must remove BOTH the mark and its rendered text (unlike `flatten`, which
    keeps the text) — confirmed against real UNO rather than assumed, since `flatten`'s own comment and
    `_replace_mark_text`'s describe `removeTextContent`'s effect on wrapped text inconsistently; `delete_citation`
    is written to be correct either way, and this proves it. Surrounding body text must survive untouched."""
    log("spike (phase 6): delete_citation removes both the mark and its rendered text")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    text.createTextCursorByRange(text.getStart()).setString("Before XXX0 middle XXX1 after.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("XXX0")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("XXX1")))
    before = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(before) == 2, f"expected 2 marks before delete, found {len(before)}")

    target = next(f for f in cc.scan_citations_in_order(doc) if f["items"][0].get("id") == f"callosum-{p1}")
    rendered_p1 = target["_mark"].getAnchor().getString()
    controller = doc.getCurrentController()
    view_cursor = controller.getViewCursor()
    view_cursor.gotoRange(target["_mark"].getAnchor().getStart(), False)
    cc.delete_citation_interactive(doc, base)

    after = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(after) == 1, f"expected 1 mark after delete, found {len(after)}")
    remaining = cc.scan_citations_in_order(doc)[0]
    check(
        remaining["items"][0].get("id") == f"callosum-{p2}",
        f"the wrong citation survived the delete: {remaining['items'][0].get('id')!r}",
    )
    body = text.getString()
    check(rendered_p1 not in body, f"deleted citation's rendered text {rendered_p1!r} still present in the body")
    check("Before" in body and "middle" in body and "after" in body, "surrounding body text was destroyed")
    log("spike (phase 6): OK — delete_citation removed both the mark and its text; body text intact")


def spike_merge_and_split_citations(ctx, base, p1, p2):
    """P0 phase 6: merge_with_next combines two adjacent single-item citations into one grouped citation;
    split_citation reverses it back into that many single-item citations. Confirmed against real UNO —
    both the item sets AND the resulting mark counts, not just that no exception was raised."""
    log("spike (phase 6): merge_with_next + split_citation round-trip")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    text.createTextCursorByRange(text.getStart()).setString("See XXX0 and XXX1 for details.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("XXX0")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("XXX1")))
    check(
        len([n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]) == 2,
        "expected 2 marks before merge",
    )

    controller = doc.getCurrentController()
    view_cursor = controller.getViewCursor()
    first_field = cc.scan_citations_in_order(doc)[0]
    view_cursor.gotoRange(first_field["_mark"].getAnchor().getStart(), False)
    cc.merge_with_next_interactive(doc, base)

    after_merge = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(after_merge) == 1, f"expected 1 grouped mark after merge, found {len(after_merge)}")
    merged = cc.scan_citations_in_order(doc)[0]
    check(len(merged["items"]) == 2, f"expected 2 items in the merged citation, found {len(merged['items'])}")
    merged_ids = {it.get("id") for it in merged["items"]}
    check(merged_ids == {f"callosum-{p1}", f"callosum-{p2}"}, f"merged citation has wrong items: {merged_ids}")
    log(f"spike (phase 6): merge OK — one grouped citation with items {merged_ids}")

    view_cursor.gotoRange(merged["_mark"].getAnchor().getStart(), False)
    cc.split_citation_interactive(doc, base)
    after_split = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(after_split) == 2, f"expected 2 marks after split, found {len(after_split)}")
    split_fields = cc.scan_citations_in_order(doc)
    check(all(len(f["items"]) == 1 for f in split_fields), "split citations should each have exactly 1 item")
    split_ids = {f["items"][0].get("id") for f in split_fields}
    check(split_ids == {f"callosum-{p1}", f"callosum-{p2}"}, f"split citations have wrong items: {split_ids}")
    log(f"spike (phase 6): split OK — {len(split_fields)} single-item citations with ids {split_ids}")


def spike_open_in_callosum(ctx, base, p1, p2):
    """Per-source navigation: a grouped citation can open the specifically chosen Callosum paper."""
    log("spike (P1 #11): grouped open_in_callosum resolves the chosen paper id + URL")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("A citation here.\n")
    cc.insert_citation_items(
        doc,
        [{"paper_id": p1}, {"paper_id": p2}],
        base,
        cursor=text.createTextCursorByRange(text.getEnd()),
    )
    marks = doc.getReferenceMarks()
    mark = next(marks.getByName(n) for n in marks.getElementNames() if cc.decode_mark_name(n))
    controller = doc.getCurrentController()
    view_cursor = controller.getViewCursor()
    view_cursor.gotoRange(mark.getAnchor().getStart(), False)

    captured = {}
    original_open = cc.webbrowser.open
    original_choose = cc._choose_citation_source
    cc.webbrowser.open = lambda url: captured.update(url=url)
    cc._choose_citation_source = lambda choices, **_kwargs: next(
        choice for choice in choices if choice["paper_id"] == str(p2)
    )
    try:
        cc.open_in_callosum(doc, base)
    finally:
        cc.webbrowser.open = original_open
        cc._choose_citation_source = original_choose
    check("url" in captured, "open_in_callosum did not call webbrowser.open")
    check(captured["url"] == f"{base}/?open_paper={p2}", f"unexpected URL: {captured['url']!r}")
    log(f"spike (P1 #11): OK — opened selected grouped source {captured['url']!r}")


def spike_bounded_bibliography_preserves_trailing_text(ctx, base, p1):
    """P0 phase 7: the verified data-loss bug, reproduced live and then confirmed FIXED. The old design deleted
    from the bibliography bookmark to the literal document end on every refresh; the new bookmark-PAIR design
    must never touch anything past its own end bookmark."""
    log("spike (phase 7): bounded bibliography preserves text placed after it")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Body text.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(text.getEnd()))
    # A bibliography now exists (from insert_citation's own refresh). Type NEW user text after it -- the
    # historically dangerous sequence.
    text.insertString(text.createTextCursorByRange(text.getEnd()), "User's own trailing paragraph.\n", False)
    cc.refresh(doc, base)  # the second refresh is what used to destroy the trailing text
    body = text.getString()
    check("User's own trailing paragraph." in body, "trailing user text was destroyed by a bibliography rebuild!")
    check(cc.BIB_HEADING in body, "bibliography heading missing")
    log("spike (phase 7): OK — trailing user text survived a bibliography rebuild")


def spike_insert_bibliography_here(ctx, base, p1):
    """P0 phase 7: "Insert bibliography here" moves the bibliography to the cursor position, removing it from
    its old location — confirmed the new location precedes the surrounding text and nothing else was destroyed."""
    log("spike (phase 7): insert bibliography here (move)")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    text.createTextCursorByRange(text.getStart()).setString("Intro. MOVE_HERE more text.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(text.getEnd()))
    check(cc.BIB_HEADING in text.getString(), "bibliography not created by the initial refresh")

    marker = find_range("MOVE_HERE")
    check(marker is not None, "MOVE_HERE anchor not found")
    controller = doc.getCurrentController()
    view_cursor = controller.getViewCursor()
    view_cursor.gotoRange(marker.getStart(), False)
    cc.insert_bibliography_here_interactive(doc, base)

    body = text.getString()
    check(cc.BIB_HEADING in body, "bibliography missing after the move")
    check("more text." in body, "surrounding text was destroyed by the move")
    check(
        body.index(cc.BIB_HEADING) < body.index("more text."),
        "bibliography did not actually move to the cursor position",
    )
    log("spike (phase 7): OK — bibliography moved to the cursor position, surrounding text intact")


def spike_toggle_bib_auto(ctx, base, p1, p2):
    """P0 phase 7: turning off automatic bibliography rebuilding freezes the bibliography block while citations
    still update on refresh — confirmed the bibliography heading count never grows past 1 while off, and that
    citation marks DO still accumulate (proving refresh itself keeps running, only the bib write is skipped).

    `toggle_bib_auto_interactive` always shows a confirmation message box (unlike most other interactive
    actions, which only message-box on a failure/edge case) — the real `.oxt` dispatcher sets `cc._DISPATCH_CTX`
    before calling it (`callosum_addon.py`); this spike calls it directly, so it must set the same thing itself.

    Also proves the state-blind-toggle UX follow-up (backlog #33/#34, inc 446): `diagnose_document`'s
    "preferences" key tracks bib_auto through both toggles, and the message names the ON/OFF transition, not
    just the destination.
    """
    log("spike (phase 7): toggle bibliography auto-rebuild")
    cc._DISPATCH_CTX = ctx
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    text.createTextCursorByRange(text.getStart()).setString("A XXX0 and B XXX1.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("XXX0")))
    check(cc.bib_auto_enabled(doc), "bibliography auto-rebuild should default to enabled")
    check(text.getString().count(cc.BIB_HEADING) == 1, "expected exactly 1 bibliography heading after the first cite")
    check(
        cc.diagnose_document(doc, base)["preferences"]["bib_auto"] is True,
        "diagnostics should report bib_auto=True before any toggle",
    )

    captured = []
    original_msgbox = cc._msgbox
    cc._msgbox = lambda message, title="callosum": captured.append(message)
    try:
        cc.toggle_bib_auto_interactive(doc, base)
    finally:
        cc._msgbox = original_msgbox
    check(not cc.bib_auto_enabled(doc), "toggle did not disable bib auto")
    check(
        captured and captured[0].startswith("Automatic bibliography rebuilding: ON → OFF."),
        f"unexpected toggle-off message: {captured}",
    )
    check(
        cc.diagnose_document(doc, base)["preferences"]["bib_auto"] is False,
        "diagnostics did not reflect bib_auto=False right after toggling off",
    )

    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("XXX1")))
    body = text.getString()
    check(
        body.count(cc.BIB_HEADING) == 1,
        f"expected the bibliography heading count to stay at 1 while auto-rebuild is off, found {body.count(cc.BIB_HEADING)}",
    )
    marks = cc.scan_citations_in_order(doc)
    check(len(marks) == 2, f"expected 2 citation marks (citations still update), found {len(marks)}")

    captured.clear()
    cc._msgbox = lambda message, title="callosum": captured.append(message)
    try:
        cc.toggle_bib_auto_interactive(doc, base)
    finally:
        cc._msgbox = original_msgbox
    check(cc.bib_auto_enabled(doc), "toggle did not re-enable bib auto")
    check(
        captured and captured[0].startswith("Automatic bibliography rebuilding: OFF → ON."),
        f"unexpected toggle-on message: {captured}",
    )
    check(
        cc.diagnose_document(doc, base)["preferences"]["bib_auto"] is True,
        "diagnostics did not reflect bib_auto=True right after re-enabling",
    )
    cc.refresh(doc, base)
    check(cc.BIB_HEADING in text.getString(), "bibliography missing after re-enabling + a refresh")
    log(
        "spike (phase 7): OK — bibliography stayed frozen while auto-rebuild was off; citations kept updating; "
        "diagnostics + message wording reflected each transition"
    )


def spike_prepare_submission_copy(ctx, base, p1):
    """P0 phase 8: `prepare_submission_copy` must NEVER leave the live, open document flattened — it saves a
    separate copy, then undoes the flatten in place. Confirms the SAVED copy has zero live citation marks (the
    rendered text present as plain static text) while the OPEN document still has its live mark AND identical
    visible text afterward."""
    log("spike (phase 8): prepare_submission_copy never mutates the live document")
    import uuid

    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Intro sentence.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(text.getEnd()))
    live_before = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(live_before) == 1, f"expected 1 live mark before prepare_submission_copy, found {len(live_before)}")
    body_before = text.getString()

    filename = f"callosum_selftest_submission_copy_{uuid.uuid4().hex[:8]}.odt"
    count, save_url = cc.prepare_submission_copy(doc, filename)
    check(count == 1, f"expected 1 citation flattened, found {count}")

    live_after = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(
        len(live_after) == 1,
        f"the OPEN document lost its live mark(s) — it should be untouched, found {len(live_after)}",
    )
    body_after = text.getString()
    check(body_after == body_before, "the OPEN document's text changed — it should be byte-identical to before")

    saved_doc = load_doc(ctx, save_url)
    saved_marks = [n for n in saved_doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(saved_marks) == 0, f"the SAVED copy should have zero live marks (flattened), found {len(saved_marks)}")
    saved_body = saved_doc.getText().getString()
    check(saved_body == body_before, "the SAVED copy's visible text should match the original")
    log(f"spike (phase 8): OK — saved copy at {save_url!r} is flattened; the open document is untouched")

    try:
        os.remove(uno.fileUrlToSystemPath(save_url))
    except Exception:
        pass


def spike_live_search_listener(ctx, base):
    """Phase 5a spike (the citation composer, backlog #33/#34): this codebase has never implemented a UNO event
    listener from Python except the .oxt dispatcher itself (`XJobExecutor` in `callosum_addon.py`) — a live
    text-changed listener driving Zotero-style search-as-you-type is new territory. Empirically confirms whether
    a PROGRAMMATIC `setText()` call fires `XTextListener.textChanged` at all (UNO's own docs are silent on this
    for various AWT controls) and whether a synchronous local search-and-refresh from inside that callback works
    without a reentrancy problem. Never calls `dialog.execute()` (which blocks on real user interaction), so
    this is spikeable headless — but real per-keystroke firing/timing from an actual human typing is NOT provable
    this way and needs a manual check in real Writer before the composer design commits to this listener type."""
    import time as _time

    import unohelper
    from com.sun.star.awt import XTextListener

    log("spike (phase 5a): live-search text-listener mechanism")

    class _TextChangeListener(unohelper.Base, XTextListener):
        def __init__(self, callback):
            self._callback = callback

        def textChanged(self, event):
            self._callback()

        def disposing(self, event):
            pass

    smgr = ctx.ServiceManager
    dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dm.Width, dm.Height, dm.Title = 300, 150, "spike"
    edit = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
    edit.PositionX, edit.PositionY, edit.Width, edit.Height, edit.Text = 6, 6, 288, 14, ""
    dm.insertByName("edit", edit)
    lst = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
    lst.PositionX, lst.PositionY, lst.Width, lst.Height = 6, 24, 288, 100
    dm.insertByName("list", lst)
    dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dm)
    toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, None)

    edit_ctrl = dialog.getControl("edit")
    list_ctrl = dialog.getControl("list")
    events = {"n": 0}

    def on_change():
        events["n"] += 1
        query = edit_ctrl.getModel().Text
        hits = cc.search_library(base, query) if query.strip() else []
        list_ctrl.getModel().StringItemList = tuple(cc.build_search_rows(hits))

    edit_ctrl.addTextListener(_TextChangeListener(on_change))
    check(events["n"] == 0, "no textChanged events should have fired before any text change")

    t0 = _time.time()
    edit_ctrl.setText("attention")
    elapsed_ms = (_time.time() - t0) * 1000
    fired = events["n"] > 0
    row_count = len(list_ctrl.getModel().StringItemList)
    log(
        f"spike (phase 5a): setText() {'fired' if fired else 'did NOT fire'} textChanged "
        f"({events['n']} event(s)); listbox has {row_count} row(s); search+refresh took {elapsed_ms:.0f}ms"
    )

    if fired:
        check(row_count >= 1, "expected search results in the listbox after setText('attention')")
        log(
            "spike (phase 5a): FINDING -- programmatic setText() DOES fire XTextListener; a synchronous "
            "search-and-refresh from inside the callback works with no observed reentrancy problem. This only "
            "proves the wiring mechanism -- real per-keystroke debounce timing still needs manual verification "
            "in actual Writer, since headless can't synthesize real key events."
        )
    else:
        log(
            "spike (phase 5a): FINDING -- programmatic setText() does NOT fire XTextListener here. Real keyboard "
            "input may still fire it (untested -- headless can't synthesize keys), or XKeyListener may be the "
            "more reliable mechanism. Needs manual GUI verification before committing the composer to this "
            "listener type."
        )

    dialog.dispose()


def spike_insert_citation_items(ctx, base, p1, p2):
    """Phase 5a/5b (backlog #33/#34): `insert_citation_items` generalizes `insert_citation` to accept multiple
    papers (each optionally carrying a per-occurrence override) in ONE mark (the composer's insert path) —
    confirms exactly one mark is created (not two), its item list has both papers in the given order, the
    rendered text reflects both sources, and that the original single-item `insert_citation` (now a thin
    wrapper) still behaves identically to before (a regression check on every existing caller: suggest,
    add-by-search's old path, insert-by-id)."""
    log("spike (phase 5a): insert_citation_items — a single mark with multiple items")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("See the following.\n")
    cc.set_style(doc, "apa", "en-US", base)
    rnd = cc.insert_citation_items(
        doc, [{"paper_id": p1}, {"paper_id": p2}], base, cursor=text.createTextCursorByRange(text.getEnd())
    )

    marks = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
    check(len(marks) == 1, f"expected exactly 1 mark for a grouped insert, found {len(marks)}")
    field = cc.scan_citations_in_order(doc)[0]
    check(field["citationID"] == rnd, f"the mark's citationID {field['citationID']!r} != returned rnd {rnd!r}")
    ids = [it.get("id") for it in field["items"]]
    check(
        ids == [f"callosum-{p1}", f"callosum-{p2}"],
        f"expected items [callosum-{p1}, callosum-{p2}] in order, got {ids}",
    )
    rendered = field["_mark"].getAnchor().getString()
    check(rendered.startswith("(") and rendered.endswith(")"), f"expected an APA '(...)' render, got {rendered!r}")
    check(";" in rendered or "," in rendered, f"expected a grouped multi-source APA render, got {rendered!r}")
    log(f"spike (phase 5a): OK — one mark, 2 items in order, rendered as {rendered!r}")

    log("spike (phase 5a): insert_citation (single-item wrapper) is an unaffected regression check")
    doc2 = new_writer(ctx)
    text2 = doc2.getText()
    text2.createTextCursorByRange(text2.getStart()).setString("Solo cite.\n")
    cc.insert_citation(doc2, p1, base, cursor=text2.createTextCursorByRange(text2.getEnd()))
    solo = cc.scan_citations_in_order(doc2)
    check(len(solo) == 1 and len(solo[0]["items"]) == 1, f"expected 1 mark with 1 item, got {solo}")
    check(solo[0]["items"][0].get("id") == f"callosum-{p1}", "single-item insert_citation regressed")
    log("spike (phase 5a): OK — insert_citation (single-item) still behaves identically")


def spike_per_item_citation_overrides(ctx, base, p1):
    """Phase 5b (backlog #33/#34): the composer's "Options…" per-item fields (locator/label/prefix/suffix/
    suppress-author/author-only) actually reach the render through `insert_citation_items` — confirmed against
    real citeproc-js output, not assumed. Reuses the Phase-3 findings already verified in `tests/test_citations.py`
    (prefix/suffix wrap INSIDE the parenthetical; author-only is a bare name, no year/parens) as the expected
    shape, now proven through this adapter's own insert path rather than only the backend's own test suite."""
    log("spike (phase 5b): per-item locator/prefix/suffix/suppress-author reach the real render")

    def fresh_doc_with(overrides: dict) -> str:
        doc = new_writer(ctx)
        text = doc.getText()
        text.createTextCursorByRange(text.getStart()).setString("Body.\n")
        cc.set_style(doc, "apa", "en-US", base)
        cc.insert_citation_items(
            doc, [{"paper_id": p1, **overrides}], base, cursor=text.createTextCursorByRange(text.getEnd())
        )
        return cc.scan_citations_in_order(doc)[0]["_mark"].getAnchor().getString()

    locator_rendered = fresh_doc_with({"label": "page", "locator": "12"})
    check("12" in locator_rendered, f"expected the locator '12' to appear in the render, got {locator_rendered!r}")
    log(f"spike (phase 5b): OK — locator reached the render: {locator_rendered!r}")

    prefix_rendered = fresh_doc_with({"prefix": "see "})
    check("see " in prefix_rendered, f"expected the prefix 'see ' to appear in the render, got {prefix_rendered!r}")
    log(f"spike (phase 5b): OK — prefix reached the render: {prefix_rendered!r}")

    suffix_rendered = fresh_doc_with({"suffix": " (emphasis added)"})
    check(
        "emphasis added" in suffix_rendered,
        f"expected the suffix to appear in the render, got {suffix_rendered!r}",
    )
    log(f"spike (phase 5b): OK — suffix reached the render: {suffix_rendered!r}")

    suppressed_rendered = fresh_doc_with({"suppress-author": True})
    check(
        "Vaswani" not in suppressed_rendered,
        f"expected the author to be suppressed, got {suppressed_rendered!r}",
    )
    log(f"spike (phase 5b): OK — suppress-author reached the render: {suppressed_rendered!r}")

    author_only_rendered = fresh_doc_with({"author-only": True})
    check(
        "Vaswani" in author_only_rendered and "2017" not in author_only_rendered,
        f"expected a bare author name with no year, got {author_only_rendered!r}",
    )
    log(f"spike (phase 5b): OK — author-only reached the render: {author_only_rendered!r}")


def spike_edit_citation(ctx, base, p1, p2):
    """Phase 5c (backlog #33/#34): `edit_citation_items` replaces an EXISTING citation's items in place — same
    rnd/mark identity, new item set — confirmed against real UNO by calling it directly, bypassing the composer
    dialog (which blocks on real user interaction, the same limitation every dialog-driven action in this file
    has). Covers both growing a citation (add an item + set a locator) and shrinking one (remove an item)."""
    log("spike (phase 5c): edit_citation_items preserves citation identity while changing its items")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("A single citation here.\n")
    cc.set_style(doc, "apa", "en-US", base)
    original_rnd = cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(text.getEnd()))

    field = cc.scan_citations_in_order(doc)[0]
    check(field["citationID"] == original_rnd, "sanity: citationID should match the insert's own rnd")
    cc.edit_citation_items(doc, field, [{"paper_id": p1, "label": "page", "locator": "9"}, {"paper_id": p2}], base)

    after = cc.scan_citations_in_order(doc)
    check(len(after) == 1, f"expected still exactly 1 mark after editing, found {len(after)}")
    check(after[0]["citationID"] == original_rnd, "editing a citation must not change its rnd/identity")
    ids = [it.get("id") for it in after[0]["items"]]
    check(ids == [f"callosum-{p1}", f"callosum-{p2}"], f"expected items in the given order, got {ids}")
    check(after[0]["items"][0].get("locator") == "9", "the locator set during edit did not persist")
    rendered = after[0]["_mark"].getAnchor().getString()
    check("9" in rendered, f"expected the locator to reach the render, got {rendered!r}")
    log(f"spike (phase 5c): OK — same rnd ({original_rnd!r}), 2 items now, locator reached render: {rendered!r}")

    log("spike (phase 5c): edit_citation_items can also REMOVE an item, still same identity")
    cc.edit_citation_items(doc, cc.scan_citations_in_order(doc)[0], [{"paper_id": p2}], base)
    reduced = cc.scan_citations_in_order(doc)
    check(len(reduced) == 1, f"expected still exactly 1 mark, found {len(reduced)}")
    check(reduced[0]["citationID"] == original_rnd, "removing an item during edit must not change identity")
    check(
        len(reduced[0]["items"]) == 1 and reduced[0]["items"][0].get("id") == f"callosum-{p2}",
        f"expected only {p2} remaining, got {reduced[0]['items']}",
    )
    log("spike (phase 5c): OK — editing down to 1 item kept the same citation identity")


def spike_beyond_library_checkbox_listener(ctx, base):
    """Backlog #30 (Track C SP2/Stage-3): the Suggest dialog's opt-in "Also search beyond my library" checkbox
    logic (its `itemStateChanged` callback) correctly triggers a live re-fetch that merges in beyond-library
    rows. `cc._post_json` is monkeypatched to a deterministic FAKE `/citations/suggest` response rather than
    hitting real external APIs (Crossref/PubMed/OpenAlex) — this offline-by-design harness must never depend on
    live third-party network availability. Mirrors `spike_live_search_listener`'s established pattern (a
    minimal standalone dialog, never calling `.execute()`, which would block on real user interaction).

    FINDING (see inline comment below): unlike Phase 5a's `edit_ctrl.setText()` reliably firing `textChanged`,
    a programmatic `checkbox.setState()` does NOT fire `XItemListener.itemStateChanged` in this LibreOffice
    version — standard UNO/AWT behavior (it fires on a real user click, not a scripted mutation), not a bug.
    There is no headless way to synthesize a real click, so this spike invokes the listener's own callback
    directly (proving the callback LOGIC), rather than proving the click-to-callback wiring itself — which
    remains a manual-verification-only question, same as every other dialog interaction in this file. This
    applies retroactively to the already-shipped Phase 5b/5c Options dialog's suppress-author/author-only mutex
    checkboxes too, which rely on the identical mechanism and were never spike-tested for exactly this reason."""
    log("spike (backlog #30): beyond-library checkbox triggers a live re-fetch + merge")

    calls = {"n": 0, "last_include_beyond": None}
    original_post = cc._post_json

    def fake_post(url, body, timeout=20):
        calls["n"] += 1
        calls["last_include_beyond"] = body.get("include_beyond_library")
        beyond = (
            [{"title": "Beyond-library paper", "authors": ["Someone"], "year": 2021, "reason": "matches"}]
            if body.get("include_beyond_library")
            else []
        )
        return {
            "suggestions": [{"paper_id": 1, "title": "In-library paper", "match_score": 0.9}],
            "beyond_library_suggestions": beyond,
        }

    cc._post_json = fake_post
    try:
        smgr = ctx.ServiceManager
        dm = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
        dm.Width, dm.Height, dm.Title = 300, 150, "spike"
        beyond_model = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        beyond_model.PositionX, beyond_model.PositionY, beyond_model.Width, beyond_model.Height = 6, 6, 280, 14
        beyond_model.Label, beyond_model.State = "beyond", 0
        dm.insertByName("beyond", beyond_model)
        lst = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
        lst.PositionX, lst.PositionY, lst.Width, lst.Height = 6, 24, 280, 100
        dm.insertByName("list", lst)
        dialog = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
        dialog.setModel(dm)
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        dialog.createPeer(toolkit, None)

        beyond_ctrl = dialog.getControl("beyond")
        list_ctrl = dialog.getControl("list")
        state = {"rows": []}

        def refresh(include_beyond):
            result = cc.fetch_suggestions(base, "a draft sentence", include_beyond_library=include_beyond)
            parallel = [("library", s) for s in result["suggestions"]]
            parallel += [("beyond", b) for b in result["beyond_library_suggestions"]]
            rows = cc.build_suggest_rows(result["suggestions"]) + cc.build_beyond_suggest_rows(
                result["beyond_library_suggestions"]
            )
            state["rows"] = parallel
            list_ctrl.getModel().StringItemList = tuple(rows)

        refresh(False)
        check(calls["n"] == 1, f"expected exactly 1 fetch before any toggle, got {calls['n']}")
        check(len(state["rows"]) == 1, f"expected 1 in-library row before toggle, got {len(state['rows'])}")

        import unohelper
        from com.sun.star.awt import XItemListener

        class _Listener(unohelper.Base, XItemListener):
            def itemStateChanged(self, event):
                refresh(beyond_ctrl.getState() == 1)

            def disposing(self, event):
                pass

        listener = _Listener()
        beyond_ctrl.addItemListener(listener)
        beyond_ctrl.setState(1)
        # FINDING: unlike Phase 5a's edit_ctrl.setText() reliably firing textChanged, a programmatic setState()
        # here does NOT fire itemStateChanged (confirmed: calls["n"] stays 1 after the line above alone). This
        # matches standard UNO/AWT behavior -- itemStateChanged fires on a REAL user click, not a scripted state
        # mutation -- and there is no headless way to synthesize a real click. So this spike verifies the actual
        # callback LOGIC directly (does the closure merge rows correctly when it runs), invoking it exactly as
        # the toolkit would on a real click, rather than the event-dispatch wiring itself -- whether a real
        # click in real Writer fires it (which standard UNO/AWT behavior says it will) remains a manual-
        # verification-only question, like every other dialog interaction in this file. This also applies
        # retroactively to the Phase 5b/5c Options dialog's suppress-author/author-only mutex checkboxes,
        # which rely on the identical mechanism and were never spike-tested for exactly this reason.
        listener.itemStateChanged(None)
        check(calls["n"] == 2, f"expected the simulated click to trigger a second fetch, got {calls['n']}")
        check(calls["last_include_beyond"] is True, "expected include_beyond_library=True on the toggled fetch")
        check(len(state["rows"]) == 2, f"expected 2 rows (1 library + 1 beyond) after toggle, got {len(state['rows'])}")
        check(
            state["rows"][0][0] == "library" and state["rows"][1][0] == "beyond",
            f"expected [library, beyond] row kinds, got {[k for k, _ in state['rows']]}",
        )
        log(f"spike (backlog #30): OK — checkbox toggle fired {calls['n']} fetches, merged rows correctly")
        dialog.dispose()
    finally:
        cc._post_json = original_post


def spike_save_beyond_library_item_and_cite(ctx, base):
    """Backlog #30: `save_beyond_library_item` + `insert_citation` end-to-end against the REAL local callosum
    server (`/discovery/save` — no internet needed for a bare metadata-only save) — confirms a beyond-library
    candidate can be added to the library and immediately cited in one flow, via the exact same write path the
    web app's own "Add to library" button already uses (`/discovery/save`)."""
    log("spike (backlog #30): save_beyond_library_item + insert_citation end-to-end")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("A fresh discovery.\n")

    fake_item = {
        "title": "Graph Attention Networks",
        "doi": None,  # no DOI -- save_item must still succeed on a title-only save
        "abstract": "We present graph attention networks (GATs)...",
        "authors": ["Velickovic"],
        "journal": "ICLR",
        "year": 2018,
        "url": None,
    }
    paper_id = cc.save_beyond_library_item(base, fake_item)
    check(isinstance(paper_id, int) and paper_id > 0, f"expected a real new paper_id, got {paper_id!r}")

    rnd = cc.insert_citation(doc, paper_id, base, cursor=text.createTextCursorByRange(text.getEnd()))
    field = cc.scan_citations_in_order(doc)[0]
    check(field["citationID"] == rnd, "sanity: citationID should match insert_citation's own rnd")
    check(field["items"][0].get("id") == f"callosum-{paper_id}", "the newly-saved paper's id should be cited")
    rendered = field["_mark"].getAnchor().getString()
    check("Velickovic" in rendered, f"expected the newly-saved author to appear in the render, got {rendered!r}")
    log(f"spike (backlog #30): OK — beyond-library item saved as paper {paper_id}, cited, rendered as {rendered!r}")


def spike_document_diagnostics(ctx, base, p1, p2):
    """P0 phase 9 (the last of the smaller phases, backlog #33/#34): `diagnose_document` is read-only, so this
    spike constructs each unhealthy state directly rather than waiting for it to occur naturally — a truly
    malformed mark, a schema version this adapter has never shipped, and a bibliography bookmark pair damaged
    down to one side can't happen through this adapter's own normal use at all; they exist to prove the
    diagnostic notices corruption from OUTSIDE its own control (a hand-edited document, a future adapter
    version, manual bookmark deletion via Writer's own UI) — exactly the scenario this command exists for."""
    import base64
    import json

    log("spike (phase 9): a normal, healthy document reports no findings")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("A clean citation.\n")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(text.getEnd()))
    report = cc.diagnose_document(doc, base)
    check(
        not any([report["malformed"], report["unsupported_version"], report["duplicate_ids"], report["orphaned"]]),
        f"a clean document reported findings: {report}",
    )
    check(report["bibliography"] == "ok", f"clean doc bibliography state was {report['bibliography']!r}")
    check(
        report["preferences"] == {"bib_auto": True, "bibliography_links": False, "bibliography_external_links": False},
        f"a fresh document's preferences should all be at their defaults, got {report['preferences']}",
    )
    log("spike (phase 9): OK — a normal, healthy document reports no findings")

    log(
        "spike (phase 9): document_diagnostics_interactive reports both issues and current settings (backlog #33/#34, inc 446)"
    )
    cc._DISPATCH_CTX = ctx
    captured = []
    original_msgbox = cc._msgbox
    cc._msgbox = lambda message, title="callosum": captured.append((message, title))
    try:
        cc.document_diagnostics_interactive(doc, base)
    finally:
        cc._msgbox = original_msgbox
    message, title = captured[0]
    check(title == "callosum — document diagnostics", f"unexpected diagnostics dialog title: {title!r}")
    check("No issues found." in message, f"clean-document diagnostics message missing the issues line: {message!r}")
    check(
        "Current settings" in message
        and "Automatic bibliography rebuilding: ON" in message
        and "Citation-to-bibliography links: OFF" in message
        and "Bibliography title/DOI links: OFF" in message,
        f"diagnostics message did not report all three current preference states: {message!r}",
    )
    log("spike (phase 9): OK — document_diagnostics_interactive reports both issues and current settings")

    log("spike (phase 9): malformed / unsupported-version / duplicate-id / orphaned marks are all detected")
    doc2 = new_writer(ctx)
    text2 = doc2.getText()
    text2.createTextCursorByRange(text2.getStart()).setString("Body text.\n")

    def plant(name: str) -> None:
        c = text2.createTextCursorByRange(text2.getEnd())
        c.setString(cc.PLACEHOLDER)
        mark = doc2.createInstance("com.sun.star.text.ReferenceMark")
        mark.Name = name
        text2.insertTextContent(c, mark, True)

    bad_name = "CALLOSUM_CITATION !!!notbase64!!! zzz"
    plant(bad_name)

    future_blob = base64.b64encode(json.dumps({"v": 99, "items": [{"id": "callosum-1"}]}).encode()).decode()
    plant(f"CALLOSUM_CITATION {future_blob} futurernd")

    # Two marks sharing the same rnd ("dup1") but different payloads — a real ReferenceMark NAME is unique (the
    # base64 blob differs), but nothing enforces the embedded rnd's uniqueness beyond `_new_rnd`'s own counter,
    # so a hand-crafted or corrupted document could still collide.
    for pid in (p1, p2):
        blob = base64.b64encode(json.dumps({"items": [{"id": f"callosum-{pid}"}]}).encode()).decode()
        plant(f"CALLOSUM_CITATION {blob} dup1")

    orphan_blob = base64.b64encode(json.dumps({"items": [{"id": "callosum-999999"}]}).encode()).decode()
    plant(f"CALLOSUM_CITATION {orphan_blob} orphan1")

    report2 = cc.diagnose_document(doc2, base)
    check(report2["malformed"] == [bad_name], f"expected malformed=[{bad_name!r}], got {report2['malformed']}")
    check(
        report2["unsupported_version"] == ["futurernd"],
        f"expected unsupported_version=['futurernd'], got {report2['unsupported_version']}",
    )
    check(report2["duplicate_ids"] == ["dup1"], f"expected duplicate_ids=['dup1'], got {report2['duplicate_ids']}")
    check(report2["orphaned"] == ["999999"], f"expected orphaned=['999999'], got {report2['orphaned']}")
    log(f"spike (phase 9): OK — detected malformed/unsupported/duplicate/orphaned: {report2}")

    log("spike (phase 9): a damaged bibliography (missing end bookmark) is detected")
    doc3 = new_writer(ctx)
    text3 = doc3.getText()
    text3.createTextCursorByRange(text3.getStart()).setString("Body.\n")
    cc.insert_citation(doc3, p1, base, cursor=text3.createTextCursorByRange(text3.getEnd()))
    check(
        doc3.getBookmarks().hasByName(cc.BIB_BOOKMARK) and doc3.getBookmarks().hasByName(cc.BIB_BOOKMARK_END),
        "expected a healthy bookmark pair after the first refresh",
    )
    text3.removeTextContent(doc3.getBookmarks().getByName(cc.BIB_BOOKMARK_END))  # simulate manual/foreign damage
    report3 = cc.diagnose_document(doc3, base)
    check(report3["bibliography"] == "damaged", f"expected 'damaged', got {report3['bibliography']!r}")
    log("spike (phase 9): OK — a start-without-end bibliography is reported as damaged")

    log("spike (phase 9): citations with no bibliography built yet are reported as not_built")
    doc4 = new_writer(ctx)
    cc.set_bib_auto(doc4, False)  # disable BEFORE the first-ever refresh, so no bookmark pair gets created at all
    text4 = doc4.getText()
    text4.createTextCursorByRange(text4.getStart()).setString("Body.\n")
    cc.insert_citation(doc4, p1, base, cursor=text4.createTextCursorByRange(text4.getEnd()))
    check(not doc4.getBookmarks().hasByName(cc.BIB_BOOKMARK), "a bibliography bookmark should not exist yet")
    report4 = cc.diagnose_document(doc4, base)
    check(report4["bibliography"] == "not_built", f"expected 'not_built', got {report4['bibliography']!r}")
    log("spike (phase 9): OK — citations without a bibliography yet are reported as not_built")


def spike_list_document_citations(ctx, base, p1, p2):
    """P1 item #12 (backlog #33/#34): `list_document_citations` is read-only, so this spike proves it against a
    real document — real ReferenceMarks, real document-order comparison, real `fetch_csl` + retraction calls —
    the parts a CPython-side fake (tests/test_libreoffice_adapter.py) can't fully exercise."""
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Claim one AAA. Claim two BBB. Claim three CCC.\n")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("AAA")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("BBB")))
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("CCC")))  # p1 cited again

    entries = cc.list_document_citations(doc, base)
    check(len(entries) == 2, f"expected 2 unique cited works, got {len(entries)}: {entries}")
    check(entries[0]["paper_id"] == p1, f"expected paper {p1} first (document order), got {entries[0]}")
    check(entries[0]["count"] == 2, f"expected paper {p1} cited twice, got count={entries[0]['count']}")
    check(entries[1]["paper_id"] == p2, f"expected paper {p2} second, got {entries[1]}")
    check("Vaswani" in entries[0]["row"], f"expected Vaswani in row, got {entries[0]['row']!r}")
    check(not entries[0]["orphaned"] and not entries[1]["orphaned"], "neither cited paper should be orphaned")
    check(entries[0]["retraction_label"] is None, f"a fresh seeded paper shouldn't be flagged retracted: {entries[0]}")
    check(entries[0]["mark"] is not None, "first entry's mark handle should be the actual ReferenceMark")
    log(f"spike (P1 #12): OK — list_document_citations = {[(e['paper_id'], e['count']) for e in entries]}")


def spike_citation_integrity_preflight(ctx, base, p1, p2):
    """P2 item #19 (backlog #33/#34, inc 459): `citation_integrity_preflight` is read-only (never mutates), so
    this spike proves the REAL round trip -- real ReferenceMarks, a real HTTP call to the new
    `POST /methods/retraction/check-selected` endpoint, and the real server-side persistence side-effect --
    against the seeded p1/p2 papers (both carry deliberately synthetic `10.5555/callosum.*` DOIs, so this
    spike does NOT assert on what Crossref/OpenAlex actually say about them; that determinism-dependent logic
    already has full pytest coverage via injected fake checkers in tests/test_retraction.py. This spike proves
    the WIRING: the adapter reaches the real endpoint, the real endpoint runs + persists a real check, and the
    merged report + rendered dialog carry both the mechanics section and the retraction section."""
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Claim one AAA. Claim two BBB.\n")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("AAA")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("BBB")))

    report = cc.citation_integrity_preflight(doc, base)
    check(report["bibliography"] == "ok", f"expected a healthy bibliography in the merged report: {report}")
    check(
        report["retraction_check_error"] is None,
        f"the real retraction re-check call should not have errored: {report['retraction_check_error']}",
    )
    checked_ids = {str(item["paper_id"]) for item in report["retraction_checked"]}
    check(checked_ids == {p1, p2}, f"expected both cited papers checked, got {checked_ids}")
    log(
        f"spike (P2 #19): OK — citation_integrity_preflight checked {sorted(checked_ids)}: {report['retraction_checked']}"
    )

    # the real endpoint persists -- GET /papers/{id}/retraction now shows "checked" rather than "unchecked",
    # proving the on-demand preflight benefits the already-audited read-only cached endpoint too, for free.
    import json as _json
    import urllib.request as _urlreq

    with _urlreq.urlopen(f"{base}/papers/{p1}/retraction", timeout=10) as r:
        status_after = _json.loads(r.read().decode("utf-8"))
    check(status_after["checked"] is True, f"expected the fresh check to persist as checked=True: {status_after}")
    log(f"spike (P2 #19): OK — the on-demand check persisted server-side: {status_after}")

    log("spike (P2 #19): citation_integrity_preflight_interactive renders a combined mechanics + retraction dialog")
    captured = []
    original_msgbox = cc._msgbox
    cc._msgbox = lambda message, title="callosum": captured.append((message, title))
    try:
        cc.citation_integrity_preflight_interactive(doc, base)
    finally:
        cc._msgbox = original_msgbox
    message, title = captured[0]
    check(title == "callosum — citation integrity preflight", f"unexpected preflight dialog title: {title!r}")
    check(
        "Retraction re-check" in message or "clean" in message,
        f"preflight message missing a retraction re-check summary line: {message!r}",
    )
    log("spike (P2 #19): OK — citation_integrity_preflight_interactive rendered a combined dialog")


def spike_insert_evidence(ctx, base, p1, p2):
    """P2 item #20 (backlog #33/#34, inc 461): `evidence_insert.insert_evidence` is the first place this
    adapter inserts free-form body text AND a citation mark together as one action. This spike proves the real
    two-step UNO sequence (`text.insertString` then `insert_citation_items` reusing the SAME cursor) actually
    lands body-then-mark in a real document, that each format produces the right body text (or none, for
    "quote only"), and that the new `evidence_annotation_id` field round-trips losslessly through a real
    save/reopen — the `evidence_insert.py` analog of `spike_mark_size_and_reopen`'s `evidence_chunk_id` proof.

    The three real dialogs (`_paper_search_dialog`/`_annotation_list_dialog`/`_annotation_configure_dialog`)
    are only ever exercised interactively — like `composer.py`'s own dialogs, `dialog.execute()` blocks for
    real human input, so there's no way to spike them headlessly. This calls `insert_evidence` directly with
    hand-built annotation dicts instead — the same "skip the dialog, prove the mutation" split
    `spike_citation_integrity_preflight` already established for `citation_integrity_preflight_interactive`.
    """
    import tempfile

    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString(
        "Intro paragraph.\nMARK-QUOTE-CITE\nMARK-QUOTE-ONLY\nMARK-CARD\n"
    )

    def find(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    def place_view(needle):
        found = find(needle)
        check(found is not None, f"anchor {needle} not found")
        cursor = text.createTextCursorByRange(found)
        cursor.collapseToStart()
        doc.getCurrentController().getViewCursor().gotoRange(cursor, False)

    quote_annotation = {
        "id": 501,
        "page": 7,
        "anchor_text": "The effect was null across all conditions.",
        "note": None,
    }
    card_annotation = {
        "id": 502,
        "page": 9,
        "anchor_text": "Participants reported high engagement.",
        "note": "Worth contrasting with our own null result.",
    }

    place_view("MARK-QUOTE-CITE")
    rnd1 = evidence_insert.insert_evidence(doc, base, p1, quote_annotation, evidence_insert.FORMAT_QUOTE_CITE, "7")
    check(rnd1 is not None, "quote_cite format should insert a citation mark")

    marks_before = doc.getReferenceMarks().getCount()
    place_view("MARK-QUOTE-ONLY")
    rnd2 = evidence_insert.insert_evidence(doc, base, p1, quote_annotation, evidence_insert.FORMAT_QUOTE_ONLY, None)
    check(rnd2 is None, "quote_only format must not return a mark rnd")
    check(doc.getReferenceMarks().getCount() == marks_before, "quote_only format must not insert a citation mark")

    place_view("MARK-CARD")
    rnd3 = evidence_insert.insert_evidence(doc, base, p2, card_annotation, evidence_insert.FORMAT_CARD, None)
    check(rnd3 is not None, "card format should insert a citation mark")

    full_text = text.getString()
    check("The effect was null across all conditions." in full_text, "quote body text not found in document")
    check("Worth contrasting with our own null result" in full_text, "card format's note text not found in document")

    names = [nm for nm in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm)]
    check(len(names) == 2, f"expected exactly 2 citation marks (quote_only inserts none), found {len(names)}")
    decoded_by_rnd = {cc.decode_mark_name(nm)["rnd"]: cc.decode_mark_name(nm) for nm in names}

    item1 = decoded_by_rnd[rnd1]["items"][0]
    check(item1["evidence_annotation_id"] == 501, f"quote_cite mark missing evidence_annotation_id=501: {item1}")
    check(
        item1["evidence_page_start"] == 7 and item1["evidence_page_end"] == 7,
        f"quote_cite mark page fields wrong: {item1}",
    )
    check(item1["locator"] == "7", f"quote_cite mark locator wrong: {item1}")

    item3 = decoded_by_rnd[rnd3]["items"][0]
    check(item3["evidence_annotation_id"] == 502, f"card mark missing evidence_annotation_id=502: {item3}")
    check(item3["evidence_page_start"] == 9, f"card mark page field wrong: {item3}")

    log(
        f"spike (P2 #20): OK — two-step body+citation insertion produced {len(names)} marks with correct "
        "evidence_annotation_id; quote_only inserted zero marks"
    )

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    try:
        save_url = uno.systemPathToFileUrl(save_path)
        from com.sun.star.beans import PropertyValue

        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeToURL(save_url, (filt,))
        reopened = load_doc(ctx, save_url)
        after_names = [nm for nm in reopened.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm)]
        check(len(after_names) == 2, f"after save/reopen: expected 2 marks, found {len(after_names)}")
        after_by_rnd = {cc.decode_mark_name(nm)["rnd"]: cc.decode_mark_name(nm)["items"][0] for nm in after_names}
        check(
            after_by_rnd[rnd1]["evidence_annotation_id"] == 501,
            "evidence_annotation_id changed after save/reopen (quote_cite mark)",
        )
        check(
            after_by_rnd[rnd3]["evidence_annotation_id"] == 502,
            "evidence_annotation_id changed after save/reopen (card mark)",
        )
        reopened_text = reopened.getText().getString()
        check("Worth contrasting with our own null result" in reopened_text, "card body text lost after save/reopen")
        log(
            "spike (P2 #20): OK — evidence_annotation_id + inserted body text round-trip losslessly through save/reopen"
        )
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass


def spike_insert_staged_statement(ctx, base):
    """P2 item #21 (backlog #33/#34, inc 462): `insert_staged_statement` is the first place this adapter reads a
    MULTI-KIND pending store (unlike CRediT's own single-slot `/credit/pending`) and reuses the existing
    `_choice_box` picker (no new dialog construction) to choose among several staged statements. This spike
    proves the real HTTP round trip — a real `POST /statements/pending` call for two distinct kinds, then a real
    insert into a real document, picking one specific kind via a monkeypatched `_choice_box` (the dialog itself
    is interactive-only, like every other choice/input box in this file — see `composer.py`'s own docstring for
    why). Also confirms the "nothing staged" path is an honest message, not a crash or a stray insertion."""
    import json as _json
    import urllib.request as _urlreq

    def post_json(path, body):
        data = _json.dumps(body).encode("utf-8")
        req = _urlreq.Request(f"{base}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
        with _urlreq.urlopen(req, timeout=10) as r:  # noqa: S310 -- fixed local base, mirrors selftest's own helpers
            return _json.loads(r.read().decode("utf-8"))

    def get_json(path):
        with _urlreq.urlopen(f"{base}{path}", timeout=10) as r:  # noqa: S310
            return _json.loads(r.read().decode("utf-8"))

    log("spike (P2 #21): staging two open-science statements via the real endpoint")
    post_json("/statements/pending", {"kind": "funding", "text": "This work was supported by a real grant."})
    post_json("/statements/pending", {"kind": "ethics", "text": "This study was approved by a real IRB."})
    staged = get_json("/statements/pending")
    check(staged.get("funding") == "This work was supported by a real grant.", f"funding not staged: {staged}")
    check(staged.get("ethics") == "This study was approved by a real IRB.", f"ethics not staged: {staged}")
    log(f"spike (P2 #21): OK — staged {sorted(staged.keys())} via the real endpoint")

    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Intro paragraph.\n")
    end_cursor = text.createTextCursorByRange(text.getEnd())
    doc.getCurrentController().getViewCursor().gotoRange(end_cursor, False)

    original_choice_box = cc._choice_box
    cc._choice_box = lambda doc_, title, prompt, options, current_value: "ethics"
    try:
        cc.insert_staged_statement(doc, base)
    finally:
        cc._choice_box = original_choice_box

    body = text.getString()
    check("This study was approved by a real IRB." in body, "chosen (ethics) statement text not found in document")
    check(
        "This work was supported by a real grant." not in body,
        "the NON-chosen (funding) statement should not have been inserted",
    )
    log("spike (P2 #21): OK — insert_staged_statement inserted exactly the chosen kind's text at the cursor")

    post_json("/statements/pending", {"kind": "funding", "text": ""})
    post_json("/statements/pending", {"kind": "ethics", "text": ""})
    check(get_json("/statements/pending") == {}, "expected both kinds un-staged after clearing")
    captured = []
    original_msgbox = cc._msgbox
    cc._msgbox = lambda message, title="callosum": captured.append(message)
    try:
        cc.insert_staged_statement(doc, base)
    finally:
        cc._msgbox = original_msgbox
    check(len(captured) == 1, f"expected exactly one message when nothing is staged, got {captured}")
    log("spike (P2 #21): OK — no staged statements shows an honest message, no insertion")


def spike_citation_coverage_audit(ctx, base, p1, p2):
    """P2 item #18 (backlog #33/#34, inc 463): proves both halves of `citation_coverage_audit` against real
    documents — the real `POST /methods/citation-equity/check-selected` round trip, AND the genuinely novel,
    no-existing-precedent piece: the local paragraph/citation-anchor structural scan, including the
    `compareRegionStarts`/`compareRegionEnds` polarity `order_by_comparator`'s own docstring documents (>0 iff
    a precedes b — gotten backwards once already during this increment's own implementation, caught only by
    cross-checking already-shipped code, not assumed here either) and the note-style citation fallback via a
    footnote's own `getAnchor()` (the exact pattern `_insert_note_mark` itself already relies on).

    TWO separate documents, not one: this spike's first draft mixed an inline citation and a note-style
    citation in the SAME document and hit a real, pre-existing, deliberate refusal —
    `citation_placement_error` ("This note style is configured to use Writer footnotes, but the existing live
    citations are in footnote, inline... Automatic conversion... is not available yet") — a genuine app
    invariant this spike's setup violated, not a bug in the code under test. Inline and note-style citation
    anchors are proven separately instead."""
    # -- inline citations: the primary path, and the real backend endpoint call ---------------------------
    doc = new_writer(ctx)
    text = doc.getText()

    def _para(s: str) -> None:
        cursor = text.createTextCursorByRange(text.getEnd())
        text.insertString(cursor, s, False)
        text.insertControlCharacter(cursor, cc._PARAGRAH_BREAK(), False)

    substantive = " ".join(["word"] * 15)
    short = " ".join(["word"] * 5)
    _para("Intro paragraph.")
    _para(substantive)  # uncited #1
    _para(substantive)  # uncited #2
    _para(substantive)  # uncited #3 -- a run of 3, should flag
    _para(substantive + " CITE-HERE")  # gets an inline citation (p1)
    _para(short)  # too short to count -- breaks the run regardless
    _para(substantive)  # uncited
    _para(substantive)  # uncited -- only 2 in a row, must NOT flag
    _para("CITE-HERE-2 end.")  # gets a second inline citation (p2) -- both anchors placed BEFORE either
    # insert runs, so the second insert's own auto-refresh (which appends a bibliography at doc-end) can never
    # land the second citation inside the bibliography's future-deletion zone (the spike_mark_size_and_reopen
    # hazard this file already documents elsewhere).

    def find(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find("CITE-HERE")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find("CITE-HERE-2")))

    stretches = cc._uncited_paragraph_stretches(doc)
    check(len(stretches) == 1, f"expected exactly 1 flagged stretch, got {stretches}")
    check(stretches[0]["paragraph_count"] == 3, f"expected a 3-paragraph stretch, got {stretches[0]}")
    log(f"spike (P2 #18): OK — inline uncited-stretch scan found exactly the expected 3-paragraph run: {stretches}")

    report = cc.citation_coverage_audit(doc, base)
    check(report["equity_check_error"] is None, f"equity check errored: {report['equity_check_error']}")
    check(report["references_total"] == 2, f"expected 2 distinct cited papers, got {report['references_total']}")
    check(len(report["signals"]) > 0, f"expected concentration signals, got none: {report}")
    log(
        f"spike (P2 #18): OK — citation_coverage_audit's real backend call returned {len(report['signals'])} "
        f"signals for {report['references_resolved']}/{report['references_total']} resolved papers"
    )

    log("spike (P2 #18): citation_coverage_audit_interactive renders a combined report")
    captured = []
    original_msgbox = cc._msgbox
    cc._msgbox = lambda message, title="callosum": captured.append((message, title))
    try:
        cc.citation_coverage_audit_interactive(doc, base)
    finally:
        cc._msgbox = original_msgbox
    check(len(captured) == 1, f"expected exactly one combined report message, got {captured}")
    message, title = captured[0]
    check(title == "callosum — citation coverage audit", f"unexpected report title: {title!r}")
    check("paragraphs" in message, f"report missing the uncited-stretch section: {message!r}")
    log("spike (P2 #18): OK — citation_coverage_audit_interactive rendered a combined dialog")

    # -- note-style citations: a SEPARATE document (mixed inline+note placement in one doc is refused by
    # design, confirmed live above) -- proves a footnote-anchored citation correctly marks its main-text
    # paragraph as "cited" via the footnote's own getAnchor(), not the mark's anchor inside the note itself. --
    note_doc = new_writer(ctx)
    note_text = note_doc.getText()

    def _note_para(s: str) -> None:
        cursor = note_text.createTextCursorByRange(note_text.getEnd())
        note_text.insertString(cursor, s, False)
        note_text.insertControlCharacter(cursor, cc._PARAGRAH_BREAK(), False)

    _note_para("Intro.")
    _note_para(substantive)  # uncited #1
    _note_para(substantive)  # uncited #2
    _note_para(substantive)  # uncited #3 -- a run of 3 BEFORE the footnote-cited paragraph
    _note_para(substantive + " FOOTNOTE-HERE")  # gets a note-style citation

    def note_find(needle):
        sd = note_doc.createSearchDescriptor()
        sd.SearchString = needle
        return note_doc.findFirst(sd)

    cc._set_pref(note_doc, "chicago-notes-bibliography", "en-US")
    cc.insert_citation(note_doc, p1, base, cursor=note_text.createTextCursorByRange(note_find("FOOTNOTE-HERE")))

    note_stretches = cc._uncited_paragraph_stretches(note_doc)
    check(len(note_stretches) == 1, f"expected exactly 1 flagged stretch before the footnote, got {note_stretches}")
    check(
        all("FOOTNOTE-HERE" not in s.get("preview", "") for s in note_stretches),
        f"the footnote-cited paragraph was misread as uncited: {note_stretches}",
    )
    log(
        "spike (P2 #18): OK — a note-style citation correctly counts as 'cited' for its main-text paragraph "
        f"(not flagged into the preceding run): {note_stretches}"
    )


def _zotero_mark_name(suffix: str, item_data: dict, uris: list | None = None) -> str:
    payload = {"citationItems": [{"itemData": item_data, "uris": uris or []}]}
    return f"ZOTERO_ITEM CSL_CITATION {json.dumps(payload)} RND{suffix}"


def _insert_zotero_mark(doc, text, service: str, name: str, rendered_text: str, *, content_updatable=True) -> None:
    cursor = text.createTextCursorByRange(text.getEnd())
    cursor.setString(rendered_text)
    content = doc.createInstance(service)
    content.Name = name
    text.insertTextContent(cursor, content, content_updatable)
    text.insertControlCharacter(text.createTextCursorByRange(text.getEnd()), cc._PARAGRAH_BREAK(), False)


def _run_zotero_conversion(doc, base):
    """Runs `convert_zotero_citations_interactive` with the confirm dialog auto-accepted, returns the captured
    summary text. Shared by both halves of `spike_zotero_citation_conversion`."""
    captured = []
    original_msgbox, original_confirm = cc._msgbox, cc._confirm_box
    cc._msgbox = lambda message, title="callosum": captured.append((message, title))
    cc._confirm_box = lambda *a, **k: True
    try:
        cc.convert_zotero_citations_interactive(doc, base)
    finally:
        cc._msgbox, cc._confirm_box = original_msgbox, original_confirm
    check(len(captured) == 1, f"expected exactly one summary report, got {captured}")
    summary, title = captured[0]
    check(title == "callosum — convert Zotero citations", f"unexpected report title: {title!r}")
    return summary


def spike_zotero_citation_conversion(ctx, base, p1, p2):
    """P2 item #22 (backlog #33/#34, inc 464 — the final item in this track): proves
    `convert_zotero_citations_interactive` against REAL Writer documents carrying hand-built Zotero-shaped
    ReferenceMarks and a Zotero-shaped bibliography TextSection. No live Zotero install is available, so the
    marks are constructed directly from the VERIFIED naming/payload scheme
    (zotero-libreoffice-integration's Document.java/ReferenceMark.java — `ZOTERO_` + `ITEM CSL_CITATION ` +
    citation.json + ` RND` + random), never simulated through this adapter's own `encode_mark_name`.

    TWO separate documents, not one -- deliberately, after this spike's first draft caught a real gap: the
    shared `p1`/`p2` fixture papers (`run_roundtrip.py::seed_db`) are created with `csl_json=` only, never an
    explicit `doi=`/`year=`/`first_author_family_name=`, so their DB COLUMNS (what `find_existing_paper_by_
    identity` actually matches against) are NULL even though their `csl_json` blob happens to carry a DOI. This
    spike proves the real "match an existing paper" path with a fixture-independent, self-contained pair of
    documents instead: doc A cites a brand-new work (must auto-add it), doc B independently cites the SAME work
    (must resolve to the paper doc A just created, never a duplicate) -- exercising the exact same
    `find_existing_paper_by_identity` DOI path, just proven end-to-end rather than assumed against a column the
    shared seed fixture never actually populates.
    """
    shared_doi = f"10.9999/zotero-spike-{uuid.uuid4().hex[:8]}"
    shared_item_data = {
        "type": "article-journal",
        "title": "A Brand New Zotero-Cited Work",
        "DOI": shared_doi,
        "author": [{"family": "New", "given": "Author"}],
        "issued": {"date-parts": [[2024]]},
    }

    # -- doc A: the brand-new work, PLUS the malformed-mark/Bookmark-mode/bibliography boundary checks --------
    doc_a = new_writer(ctx)
    text_a = doc_a.getText()
    _insert_zotero_mark(
        doc_a,
        text_a,
        "com.sun.star.text.ReferenceMark",
        _zotero_mark_name("aaaaaaaaaa", shared_item_data),
        "(New Author, 2024)",
    )
    _insert_zotero_mark(
        doc_a,
        text_a,
        "com.sun.star.text.ReferenceMark",
        "ZOTERO_ITEM CSL_CITATION not-json RNDcccccccccc",
        "(broken)",
    )
    _insert_zotero_mark(
        doc_a,
        text_a,
        "com.sun.star.text.Bookmark",
        "ZOTERO_BREF_spike00000_1",
        "(bookmark mode)",
        content_updatable=False,
    )
    cursor = text_a.createTextCursorByRange(text_a.getEnd())
    cursor.setString("References\nNew, A. (2024). A Brand New Zotero-Cited Work.\n")
    section = doc_a.createInstance("com.sun.star.text.TextSection")
    section.Name = "ZOTERO_BIBL {} RNDdddddddddd"
    text_a.insertTextContent(cursor, section, False)

    log("spike (P2 #22): doc A hand-built (1 new citation, 1 malformed mark, 1 Bookmark-mode anchor, 1 bibliography)")
    scan_a = cc.zotero_conversion_scan(doc_a)
    check(
        len(scan_a["inline"]) == 1,
        f"expected 1 convertible inline Zotero citation, got {len(scan_a['inline'])}: {scan_a}",
    )
    check(scan_a["bookmark_count"] == 1, f"expected 1 Bookmark-mode anchor detected, got {scan_a['bookmark_count']}")
    check(scan_a["bibliography_found"] is True, "Zotero bibliography TextSection was not detected")
    check(scan_a["malformed_count"] == 1, f"expected 1 malformed Zotero mark reported, got {scan_a['malformed_count']}")
    log(
        f"spike (P2 #22): OK — doc A scan matches exactly what was built: "
        f"{scan_a['bookmark_count']=} {scan_a['malformed_count']=}"
    )

    summary_a = _run_zotero_conversion(doc_a, base)
    check("Converted 1 of 1" in summary_a, f"doc A summary did not report converting its one citation: {summary_a!r}")
    check(
        "Bookmark-mode" in summary_a,
        f"doc A summary did not disclose the skipped Bookmark-mode citation: {summary_a!r}",
    )
    log(f"spike (P2 #22): OK — doc A conversion summary: {summary_a!r}")

    remaining_zotero_a = [n for n in doc_a.getReferenceMarks().getElementNames() if cc._decode_zotero_mark_name(n)]
    check(
        remaining_zotero_a == [], f"Zotero marks should be fully replaced in doc A, still present: {remaining_zotero_a}"
    )
    check(cc._zotero_bibliography_section(doc_a) is None, "Zotero bibliography TextSection was not removed from doc A")
    check(cc.BIB_HEADING in text_a.getString(), "Callosum-managed bibliography heading missing after the swap in doc A")

    fields_a = cc.scan_citations_in_order(doc_a)
    check(
        len(fields_a) == 1, f"expected exactly 1 real Callosum citation in doc A after conversion, got {len(fields_a)}"
    )
    created_paper_id = cc._paper_id_from_item(fields_a[0]["items"][0])
    check(created_paper_id is not None, f"converted doc A citation carries no resolvable paper id: {fields_a}")
    created_csl = cc.fetch_csl(base, created_paper_id)
    check(
        created_csl.get("DOI") == shared_doi,
        f"auto-added paper {created_paper_id} has DOI {created_csl.get('DOI')!r}, expected {shared_doi!r}",
    )
    log(f"spike (P2 #22): OK — doc A's unmatched citation auto-added new library paper {created_paper_id}")

    # -- doc B: the SAME work cited again, independently -- must resolve to paper {created_paper_id}, no dup ---
    doc_b = new_writer(ctx)
    text_b = doc_b.getText()
    _insert_zotero_mark(
        doc_b,
        text_b,
        "com.sun.star.text.ReferenceMark",
        _zotero_mark_name("eeeeeeeeee", shared_item_data),
        "(New Author, 2024)",
    )
    summary_b = _run_zotero_conversion(doc_b, base)
    check("Converted 1 of 1" in summary_b, f"doc B summary did not report converting its one citation: {summary_b!r}")
    check("0 newly added" in summary_b, f"doc B should have matched, not created, a paper: {summary_b!r}")

    fields_b = cc.scan_citations_in_order(doc_b)
    check(
        len(fields_b) == 1, f"expected exactly 1 real Callosum citation in doc B after conversion, got {len(fields_b)}"
    )
    matched_paper_id = cc._paper_id_from_item(fields_b[0]["items"][0])
    check(
        matched_paper_id == created_paper_id,
        f"doc B's citation of the same DOI should match doc A's paper {created_paper_id}, not create a new one: "
        f"got {matched_paper_id}",
    )
    log(
        f"spike (P2 #22): OK — doc B's independent citation of the same work matched the EXISTING paper {created_paper_id}, no duplicate"
    )


def spike_bibliography_editing(ctx, base, p1, p2):
    """P1 item #11 (backlog #33/#34): exclude a cited work from the bibliography while its in-text citation
    still renders, and include an uncited "further reading" work — both against a real document, real
    `refresh()`, and the real `_get_id_list`/`_set_id_list` user-property persistence (the one part of this
    feature that literally cannot be faked in pytest, since it needs `com.sun.star.beans.PropertyAttribute`)."""
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Claim one AAA.\n")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    def mark_count():
        return len([n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)])

    def bibliography_only():
        # The default style is author-date (APA), so the in-text citation ALSO contains the author surname
        # ("(Vaswani, 2017)") -- isolate the text AFTER the bibliography heading so presence/absence checks
        # below test the bibliography specifically, not "anywhere in the document".
        body = text.getString()
        idx = body.find(cc.BIB_HEADING)
        return body[idx:] if idx >= 0 else ""

    # insert_citation() already calls refresh() internally -- no extra explicit refresh needed right after.
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("AAA")))
    bib = bibliography_only()
    check("Vaswani" in bib, f"expected p1's bibliography entry after the first refresh, bib={bib!r}")
    check("Devlin" not in bib, "p2 shouldn't appear yet -- never cited, never added as uncited")
    marks_before = mark_count()

    log("spike (P1 #11): add p2 as an uncited 'further reading' work")
    cc._set_id_list(doc, cc.PREF_BIB_UNCITED, [p2])
    cc.refresh(doc, base)
    bib = bibliography_only()
    check("Devlin" in bib, f"expected p2's bibliography entry after adding it as uncited, bib={bib!r}")
    check(mark_count() == marks_before, f"p2 must NOT get an in-text citation mark, count={mark_count()}")
    log("spike (P1 #11): OK — uncited work appears in bibliography with no in-text mark")

    log("spike (P1 #11): exclude p1 from the bibliography (still cited in text)")
    cc._set_id_list(doc, cc.PREF_BIB_EXCLUDE, [p1])
    cc.refresh(doc, base)
    bib = bibliography_only()
    check("Vaswani" not in bib, f"p1's bibliography entry should be gone once excluded, bib={bib!r}")
    check("Devlin" in bib, "p2's uncited entry should be unaffected by p1's exclusion")
    check(mark_count() == marks_before, "excluding from the bibliography must not remove the in-text citation mark")
    check("Vaswani" in text.getString(), "p1's in-text citation must still render even though it's excluded")
    entries = cc.list_document_citations(doc, base)
    p1_entry = next(e for e in entries if e["paper_id"] == p1)
    check(p1_entry["excluded"] is True, f"p1 should report excluded=True, got {p1_entry}")
    check(p1_entry["mark"] is not None, "p1 is still cited -- its mark must still be findable")
    log("spike (P1 #11): OK — bibliography exclude persisted + reported, in-text citation untouched")


def spike_custom_bibliography_heading(ctx, base, p1):
    """P1 item #11: a bounded per-document bibliography heading survives refresh/reopen and resets safely."""
    import tempfile

    log("spike (P1 #11): per-document bibliography heading")
    doc = new_writer(ctx)
    text = doc.getText()
    text.setString("Claim HEADING-CITE.\n")
    descriptor = doc.createSearchDescriptor()
    descriptor.SearchString = "HEADING-CITE"
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(doc.findFirst(descriptor)))
    check(cc.BIB_HEADING in text.getString(), "default bibliography heading was not rendered")

    cc.set_bib_auto(doc, False)
    heading = cc.set_bibliography_heading(doc, "Works Cited", base)
    check(heading == "Works Cited", f"wrong normalized heading: {heading!r}")
    check(not cc.bib_auto_enabled(doc), "explicit heading change enabled automatic bibliography rebuilding")
    body = text.getString()
    check("Works Cited\n" in body and f"{cc.BIB_HEADING}\n" not in body, "custom heading did not replace the default")
    entries = cc.render_document(
        base,
        cc.build_render_request(cc.scan_citations_in_order(doc), "apa", "en-US"),
    )["bibliography_text"].splitlines()
    check(cc.bibliography_render_is_current(doc, entries), "custom-heading bibliography was not current")
    cc._write_bibliography(doc, ["MANUALLY EDITED BIBLIOGRAPHY"])
    cc.set_bibliography_heading(doc, "Works Cited", base)
    check(
        cc.bibliography_render_is_current(doc, entries),
        "reapplying the saved heading did not repair a stale managed bibliography",
    )
    check(not cc.bib_auto_enabled(doc), "same-heading repair enabled automatic bibliography rebuilding")

    before_invalid = (text.getString(), cc._effective_user_prop(doc, cc.PREF_BIB_HEADING))
    for invalid in ("x" * (cc.BIB_HEADING_MAX + 1), "Works\nCited"):
        try:
            cc.set_bibliography_heading(doc, invalid, base)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid bibliography heading was accepted: {invalid!r}")
        check(
            (text.getString(), cc._effective_user_prop(doc, cc.PREF_BIB_HEADING)) == before_invalid,
            "invalid bibliography heading mutated Writer or its document preference",
        )

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    try:
        from com.sun.star.beans import PropertyValue

        save_url = uno.systemPathToFileUrl(save_path)
        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeToURL(save_url, (filt,))
        reopened = load_doc(ctx, save_url)
        check(cc.bibliography_heading(reopened) == "Works Cited", "custom heading did not survive save/reopen")
        check("Works Cited\n" in reopened.getText().getString(), "reopened bibliography lost its custom heading")
        check(not cc.bib_auto_enabled(reopened), "save/reopen changed the paused bibliography preference")

        reset = cc.set_bibliography_heading(reopened, "", base)
        reopened_body = reopened.getText().getString()
        check(reset == cc.BIB_HEADING, f"blank heading did not restore the default: {reset!r}")
        check(
            f"{cc.BIB_HEADING}\n" in reopened_body and "Works Cited\n" not in reopened_body,
            "default heading was not restored visibly",
        )
        check(
            cc._effective_user_prop(reopened, cc.PREF_BIB_HEADING) is None,
            "default heading should remove the custom document property",
        )
        reopened.close(False)
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass
    log("spike (P1 #11): OK — custom/default headings refresh and round-trip without changing auto mode")


def spike_categorized_bibliography(ctx, base, p1, p2):
    """P1 item #11: named document-local categories group one bounded bibliography without losing links."""
    import tempfile

    log("spike (P1 #11): categorized bibliography")
    doc = new_writer(ctx)
    text = doc.getText()
    text.setString("First CATEGORY-A. Second CATEGORY-B.\n")

    def insertion(needle):
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = needle
        return text.createTextCursorByRange(doc.findFirst(descriptor))

    cc.insert_citation(doc, p1, base, cursor=insertion("CATEGORY-A"))
    cc.insert_citation(doc, p2, base, cursor=insertion("CATEGORY-B"))
    cc.set_bibliography_external_links(doc, True, base)
    check(
        cc.set_bibliography_categories(doc, [p1, p2, p1], "Methods", base) == {p1: "Methods", p2: "Methods"},
        "batch category assignment did not deduplicate or canonicalize its result",
    )
    cc.set_bibliography_category(doc, p2, "Theory", base)
    body = text.getString()
    methods = body.index("Methods\n")
    vaswani = body.index("Vaswani", methods)
    theory = body.index("Theory\n", vaswani)
    devlin = body.index("Devlin", theory)
    check(methods < vaswani < theory < devlin, f"category grouping/order was not rendered: {body!r}")
    check(
        cc.set_bibliography_category_order(doc, ["Theory", "Methods"], base) == ["Theory", "Methods"],
        "custom category order returned the wrong projection",
    )
    body = text.getString()
    theory = body.index("Theory\n")
    devlin = body.index("Devlin", theory)
    methods = body.index("Methods\n", devlin)
    vaswani = body.index("Vaswani", methods)
    check(theory < devlin < methods < vaswani, f"custom category order was not rendered: {body!r}")

    style, locale = cc._get_pref(doc, base)
    fields = cc.scan_citations_in_order(doc)
    response = cc.render_document(base, cc.build_render_request(fields, style, locale))
    raw_entries = response["bibliography_text"].splitlines()
    raw_ids = response["bibliography_entry_ids"]
    raw_links = cc.normalize_bibliography_links(raw_entries, response.get("bibliography_links"))
    entries, entry_ids, links, categories = cc.categorize_bibliography_entries(
        raw_entries,
        raw_ids,
        raw_links,
        cc.bibliography_categories(doc),
        cc.bibliography_category_order(doc),
    )
    check(categories == ["Theory", "Methods"], f"wrong custom category alignment: {categories}")
    check(cc.bibliography_render_is_current(doc, entries, categories), "categorized bibliography was not current")
    check(
        cc.bibliography_external_links_are_current(doc, entries, links, True, categories),
        "categorized bibliography lost DOI links",
    )
    check(
        {entry["paper_id"]: entry["category"] for entry in cc.list_document_citations(doc, base)}
        == {p1: "Methods", p2: "Theory"},
        "citations panel data did not expose category assignments",
    )

    before_invalid = (body, cc.bibliography_categories(doc))
    try:
        cc.set_bibliography_category(doc, p1, "x" * (cc.BIBLIOGRAPHY_CATEGORY_MAX + 1), base)
    except ValueError:
        pass
    else:
        raise AssertionError("oversized bibliography category was accepted")
    check(
        (text.getString(), cc.bibliography_categories(doc)) == before_invalid,
        "invalid category mutated the document or category map",
    )

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    try:
        from com.sun.star.beans import PropertyValue

        save_url = uno.systemPathToFileUrl(save_path)
        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeToURL(save_url, (filt,))
        reopened = load_doc(ctx, save_url)
        check(
            cc.bibliography_categories(reopened) == {p1: "Methods", p2: "Theory"},
            "category assignments did not survive save/reopen",
        )
        check(
            cc.bibliography_category_order(reopened) == ["Theory", "Methods"],
            "custom category order did not survive save/reopen",
        )
        check("Methods\n" in reopened.getText().getString(), "category headings did not survive save/reopen")
        cc.convert_citation_placement(
            reopened,
            "chicago-notes-bibliography",
            "en-US",
            "footnote",
            base,
        )
        converted_fields = cc.scan_citations_in_order(reopened)
        converted_response = cc.render_document(
            base,
            cc.build_render_request(converted_fields, "chicago-notes-bibliography", "en-US"),
        )
        converted_raw = converted_response["bibliography_text"].splitlines()
        converted = cc.categorize_bibliography_entries(
            converted_raw,
            converted_response["bibliography_entry_ids"],
            cc.normalize_bibliography_links(converted_raw, converted_response.get("bibliography_links")),
            cc.bibliography_categories(reopened),
            cc.bibliography_category_order(reopened),
        )
        converted_entries, _converted_ids, converted_links, converted_categories = converted
        check(
            cc.bibliography_render_is_current(reopened, converted_entries, converted_categories),
            "placement conversion lost categorized bibliography layout",
        )
        check(
            cc.bibliography_external_links_are_current(
                reopened,
                converted_entries,
                converted_links,
                True,
                converted_categories,
            ),
            "placement conversion lost categorized bibliography DOI links",
        )

        check(
            cc.set_bibliography_category_order(reopened, [], base) == [],
            "alphabetical category reset returned the wrong projection",
        )
        reset_body = reopened.getText().getString()
        check(
            reset_body.index("Methods\n") < reset_body.index("Theory\n"),
            "reset did not restore alphabetical category order",
        )
        check(cc.bibliography_category_order(reopened) == [], "reset did not remove custom category order metadata")
        check(
            cc.set_bibliography_categories(reopened, [p1, p2], "Synthesis", base) == {p1: "Synthesis", p2: "Synthesis"},
            "batch category reassignment returned the wrong projection",
        )
        batch_body = reopened.getText().getString()
        check(
            batch_body.count("Synthesis\n") == 1 and f"{cc.BIBLIOGRAPHY_UNCATEGORIZED}\n" not in batch_body,
            "batch category reassignment did not render one shared group",
        )
        cc.set_bibliography_category(reopened, p1, "", base)
        uncategorized_body = reopened.getText().getString()
        check(
            "Synthesis\n" in uncategorized_body and f"{cc.BIBLIOGRAPHY_UNCATEGORIZED}\n" in uncategorized_body,
            "removing one category did not retain the work under Other references",
        )
        check(
            cc.set_bibliography_categories(reopened, [p1, p2], None, base) == {p1: None, p2: None},
            "batch category removal returned the wrong projection",
        )
        plain_body = reopened.getText().getString()
        check(
            "Synthesis\n" not in plain_body and f"{cc.BIBLIOGRAPHY_UNCATEGORIZED}\n" not in plain_body,
            "removing the final assignment did not restore the uncategorized bibliography layout",
        )
        reopened.close(False)
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass
    log("spike (P1 #11): OK — categories batch/reuse, custom-order/reset, link, persist, and clear safely")


def spike_section_bibliographies(ctx, base, p1, p2):
    """P1 item #11: multiple heading-scoped managed bibliographies coexist with the full bibliography."""
    import tempfile

    log("spike (P1 #11): heading-scoped bibliographies alongside the full bibliography")
    doc = new_writer(ctx)
    text = doc.getText()
    for row in (
        "Chapter One",
        "First SECTION-CITE-A.",
        "SECTION-BIB-A",
        "Chapter Two",
        "Second SECTION-CITE-B.",
        "SECTION-BIB-B",
    ):
        cursor = text.createTextCursorByRange(text.getEnd())
        text.insertString(cursor, row, False)
        text.insertControlCharacter(cursor, cc._PARAGRAH_BREAK(), False)

    def find(needle):
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = needle
        return doc.findFirst(descriptor)

    def heading(needle):
        cursor = text.createTextCursorByRange(find(needle))
        cursor.gotoStartOfParagraph(False)
        cursor.gotoEndOfParagraph(True)
        cursor.ParaStyleName = "Heading 1"

    def place_view(needle):
        found = find(needle)
        cursor = text.createTextCursorByRange(found)
        cursor.setString("")
        cursor.collapseToStart()
        doc.getCurrentController().getViewCursor().gotoRange(cursor, False)

    heading("Chapter One")
    heading("Chapter Two")
    cc._set_pref(doc, "apa", "en-US")
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find("SECTION-CITE-A")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find("SECTION-CITE-B")))
    cc.set_bibliography_external_links(doc, True, base)

    place_view("SECTION-BIB-A")
    first_id = cc.insert_section_bibliography(doc, base)
    check(first_id is not None, "first section bibliography was not inserted")
    place_view("SECTION-BIB-B")
    second_id = cc.insert_section_bibliography(doc, base)
    check(second_id is not None and second_id != first_id, "second section bibliography identity was not unique")

    records, damaged = cc.section_bibliography_records(doc)
    check(len(records) == 2 and not damaged, f"wrong section bibliography inventory: {records!r}, {damaged!r}")
    summaries, summary_damage = cc.section_bibliography_summaries(doc)
    check(not summary_damage, f"manager reported unexpected damage: {summary_damage!r}")
    check(
        [(summary["label"], summary["cited_work_count"]) for summary in summaries]
        == [("Chapter One", 1), ("Chapter Two", 1)],
        f"manager rows were not in heading order with accurate counts: {summaries!r}",
    )
    check(
        [summary["row"] for summary in summaries] == ["Chapter One — 1 cited work", "Chapter Two — 1 cited work"],
        f"manager row copy was wrong: {summaries!r}",
    )
    check(cc.go_to_section_bibliography(doc, second_id), "manager could not jump to the second section bibliography")
    second_target = (
        doc.getBookmarks()
        .getByName(next(summary for summary in summaries if summary["id"] == second_id)["start"])
        .getAnchor()
        .getStart()
    )
    check(
        text.compareRegionStarts(doc.getCurrentController().getViewCursor().getStart(), second_target) == 0,
        "manager jump did not land at the second section bibliography",
    )
    by_id = {record["id"]: record for record in records}
    first_text = cc._bookmark_pair_signature(doc, by_id[first_id]["start"], by_id[first_id]["end"])[2]
    second_text = cc._bookmark_pair_signature(doc, by_id[second_id]["start"], by_id[second_id]["end"])[2]
    check("Vaswani" in first_text and "Devlin" not in first_text, f"first section membership was wrong: {first_text!r}")
    check(
        "Devlin" in second_text and "Vaswani" not in second_text,
        f"second section membership was wrong: {second_text!r}",
    )
    check(
        "Vaswani" in cc._managed_bibliography_signature(doc)[2]
        and "Devlin" in cc._managed_bibliography_signature(doc)[2],
        "full bibliography did not remain alongside section bibliographies",
    )
    fields = cc.scan_citations_in_order(doc)
    style, locale = cc._get_pref(doc, base)
    response = cc.render_document(base, cc.build_render_request(fields, style, locale))
    raw_entries = response["bibliography_text"].splitlines()
    raw_ids = response["bibliography_entry_ids"]
    raw_links = cc.normalize_bibliography_links(raw_entries, response.get("bibliography_links"))
    projected_source = cc.categorize_bibliography_entries(
        raw_entries,
        raw_ids,
        raw_links,
        cc.bibliography_categories(doc),
        cc.bibliography_category_order(doc),
    )
    for record in records:
        projected = cc.filter_bibliography_entries(
            *projected_source,
            cc._section_bibliography_item_ids(doc, fields, record),
        )
        section_entries, _section_ids, section_links, section_categories = projected
        check(
            cc.bibliography_external_links_are_current(
                doc,
                section_entries,
                section_links,
                True,
                section_categories,
                start_name=record["start"],
            ),
            "section bibliography lost validated DOI/URL links",
        )

    cc._write_bibliography(
        doc,
        ["STALE SECTION"],
        start_name=by_id[first_id]["start"],
        end_name=by_id[first_id]["end"],
        manage_targets=False,
    )
    cc.refresh_bibliography(doc, base)
    refreshed_first = cc._bookmark_pair_signature(doc, by_id[first_id]["start"], by_id[first_id]["end"])[2]
    check(
        "Vaswani" in refreshed_first and "STALE SECTION" not in refreshed_first,
        "refresh did not repair section bibliography",
    )
    check(
        cc.diagnose_document(doc, base)["section_bibliographies"] == {"count": 2, "damaged": []},
        "diagnostics did not report the two intact section bibliographies",
    )

    before_conversion = cc._conversion_snapshot(doc)
    conversion = cc.convert_citation_placement(
        doc,
        "chicago-notes-bibliography",
        "en-US",
        "footnote",
        base,
    )
    converted = cc._conversion_snapshot(doc)
    check(conversion["section_bibliographies"] == 2, f"conversion reported the wrong section count: {conversion}")
    check(
        [field["placement"] for field in cc.scan_citations_in_order(doc)] == ["footnote", "footnote"],
        "section-bibliography conversion did not create native footnotes",
    )
    converted_records, converted_damaged = cc.section_bibliography_records(doc)
    check(
        len(converted_records) == 2 and not converted_damaged,
        "conversion lost a section bibliography: "
        f"records={converted_records!r}, damaged={converted_damaged!r}, "
        f"bookmarks={doc.getBookmarks().getElementNames()!r}",
    )
    undo = doc.getUndoManager()
    check(
        undo.getCurrentUndoActionTitle() == "Convert Callosum citation placement",
        "multi-range conversion is not one Writer Undo step",
    )
    undo.undo()
    after_undo = cc._conversion_snapshot(doc)
    check(
        after_undo == before_conversion,
        "multi-range Writer Undo did not restore exactly: "
        + cc._conversion_snapshot_differences(before_conversion, after_undo),
    )
    undo.redo()
    after_redo = cc._conversion_snapshot(doc)
    check(
        after_redo == converted,
        "multi-range Writer Redo did not restore exactly: "
        + cc._conversion_snapshot_differences(converted, after_redo),
    )

    failure_before = cc._conversion_snapshot(doc)
    original_rewrite = cc._rewrite_bibliography_in_place
    write_calls = {"count": 0}

    def fail_first_section(*args, **kwargs):
        write_calls["count"] += 1
        if write_calls["count"] == 2:
            raise RuntimeError("injected section conversion failure")
        return original_rewrite(*args, **kwargs)

    cc._rewrite_bibliography_in_place = fail_first_section
    try:
        try:
            cc.convert_citation_placement(doc, "apa", "en-US", "footnote", base)
        except RuntimeError as exc:
            check("injected section conversion failure" in str(exc), f"wrong multi-range rollback error: {exc}")
        else:
            raise AssertionError("injected section conversion failure did not propagate")
    finally:
        cc._rewrite_bibliography_in_place = original_rewrite
    check(
        cc._conversion_snapshot(doc) == failure_before,
        "multi-range conversion rollback did not restore every section exactly",
    )

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    copy_path = os.path.splitext(save_path)[0] + "-converted.odt"
    try:
        from com.sun.star.beans import PropertyValue

        save_url = uno.systemPathToFileUrl(save_path)
        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeAsURL(save_url, (filt,))
        copy_before = cc._conversion_snapshot(doc)
        copy_result, copy_url = cc.save_converted_copy(
            doc,
            os.path.basename(copy_path),
            "apa",
            "en-US",
            "footnote",
            base,
        )
        check(copy_result["section_bibliographies"] == 2, f"converted-copy result lost section count: {copy_result}")
        check(cc._conversion_snapshot(doc) == copy_before, "converted-copy flow changed the open multi-range document")
        converted_copy = load_doc(ctx, copy_url)
        check(
            [field["placement"] for field in cc.scan_citations_in_order(converted_copy)] == ["inline", "inline"],
            "converted section-bibliography copy did not use inline placement",
        )
        check(
            len(cc.section_bibliography_records(converted_copy)[0]) == 2,
            "converted section-bibliography copy lost a local block",
        )
        converted_copy.close(False)

        reopened = load_doc(ctx, save_url)
        reopened_records, reopened_damaged = cc.section_bibliography_records(reopened)
        check(
            len(reopened_records) == 2 and not reopened_damaged, "section bibliography bookmarks did not survive reopen"
        )
        reopened_body = reopened.getText().getString()
        check(reopened_body.count("References\n") == 3, f"reopen lost a full/section bibliography: {reopened_body!r}")
        before_remove_sections = cc._section_bibliography_signatures(reopened)
        before_remove_full = cc._managed_bibliography_signature(reopened)
        before_remove_citations = [
            (field["citationID"], field["_mark"].getAnchor().getString())
            for field in cc.scan_citations_in_order(reopened)
        ]

        def section_links_are_current():
            current_fields = cc.scan_citations_in_order(reopened)
            current_style, current_locale = cc._get_pref(reopened, base)
            current_response = cc.render_document(
                base,
                cc.build_render_request(current_fields, current_style, current_locale),
            )
            current_entries = current_response["bibliography_text"].splitlines()
            current_ids = current_response["bibliography_entry_ids"]
            current_links = cc.normalize_bibliography_links(
                current_entries,
                current_response.get("bibliography_links"),
            )
            current_source = cc.categorize_bibliography_entries(
                current_entries,
                current_ids,
                current_links,
                cc.bibliography_categories(reopened),
                cc.bibliography_category_order(reopened),
            )
            for current_record in cc.section_bibliography_records(reopened)[0]:
                projected = cc.filter_bibliography_entries(
                    *current_source,
                    cc._section_bibliography_item_ids(reopened, current_fields, current_record),
                )
                projected_entries, _projected_ids, projected_links, projected_categories = projected
                if not cc.bibliography_external_links_are_current(
                    reopened,
                    projected_entries,
                    projected_links,
                    True,
                    projected_categories,
                    start_name=current_record["start"],
                ):
                    return False
            return True

        original_delete = cc._delete_section_bibliography_record
        delete_calls = {"count": 0}

        def fail_second_remove(current_doc, record):
            delete_calls["count"] += 1
            if delete_calls["count"] == 2:
                raise RuntimeError("injected remove-all failure")
            return original_delete(current_doc, record)

        cc._delete_section_bibliography_record = fail_second_remove
        try:
            try:
                cc.remove_all_section_bibliographies(reopened, base)
            except RuntimeError as exc:
                check("injected remove-all failure" in str(exc), f"wrong remove-all rollback error: {exc}")
            else:
                raise AssertionError("injected remove-all failure did not propagate")
        finally:
            cc._delete_section_bibliography_record = original_delete
        check(
            cc._section_bibliography_signatures(reopened) == before_remove_sections,
            "remove-all rollback did not restore both section bibliographies exactly",
        )
        check(section_links_are_current(), "remove-all rollback did not restore section bibliography links")

        check(
            cc.remove_section_bibliography_by_id(reopened, first_id, base) == first_id,
            "manager remove-selected targeted the wrong section bibliography",
        )
        check(
            len(cc.section_bibliography_records(reopened)[0]) == 1,
            "manager remove-selected did not leave its peer",
        )
        reopened_undo = reopened.getUndoManager()
        check(
            reopened_undo.getCurrentUndoActionTitle() == "Remove Callosum section bibliography",
            "manager remove-selected was not one Writer Undo step",
        )
        reopened_undo.undo()
        check(
            cc._section_bibliography_signatures(reopened) == before_remove_sections,
            "remove-selected Undo did not restore the removed section exactly",
        )

        removed_ids = cc.remove_all_section_bibliographies(reopened, base)
        check(set(removed_ids) == {first_id, second_id}, f"remove-all returned wrong ids: {removed_ids!r}")
        check(
            cc.section_bibliography_records(reopened) == ([], []),
            "remove-all left section bibliography bookmarks behind",
        )
        check(
            reopened_undo.getCurrentUndoActionTitle() == "Remove all Callosum section bibliographies",
            "remove-all was not one Writer Undo step",
        )
        check(
            cc._managed_bibliography_signature(reopened) == before_remove_full,
            "remove-all changed the full bibliography",
        )
        check(
            [
                (field["citationID"], field["_mark"].getAnchor().getString())
                for field in cc.scan_citations_in_order(reopened)
            ]
            == before_remove_citations,
            "remove-all changed live citations",
        )
        reopened_undo.undo()
        check(
            cc._section_bibliography_signatures(reopened) == before_remove_sections,
            "remove-all Undo did not restore every section exactly",
        )
        check(section_links_are_current(), "remove-all Undo did not restore section bibliography links")
        reopened_undo.redo()
        check(
            cc.section_bibliography_records(reopened) == ([], []),
            "remove-all Redo did not remove every section again",
        )
        reopened.close(False)
    finally:
        for path in (copy_path, save_path):
            try:
                os.remove(path)
            except OSError:
                pass
    log(
        "spike (P1 #11): OK — two section blocks + full bibliography refresh, one-step conversion Undo/Redo, "
        "rollback/copy isolation, manager list/jump, remove-selected/all Undo/Redo, and persist safely"
    )


def spike_bibliography_links(ctx, base, p1, p2):
    """P1 item #11: stable bibliography targets and opt-in single-work citation links survive an ODT round-trip."""
    import tempfile

    log("spike (P1 #11): citation-to-bibliography links")
    doc = new_writer(ctx)
    text = doc.getText()
    text.setString("Single AAA. Single BBB. Group CCC. External LINK.\n")

    def insertion(needle):
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = needle
        return text.createTextCursorByRange(doc.findFirst(descriptor))

    cc.insert_citation(doc, p1, base, cursor=insertion("AAA"))
    cc.insert_citation(doc, p2, base, cursor=insertion("BBB"))
    cc.insert_citation_items(doc, [{"paper_id": p1}, {"paper_id": p2}], base, cursor=insertion("CCC"))
    insertion("LINK").setPropertyValue("HyperLinkURL", "https://example.test/manual")
    check(not cc.bibliography_links_enabled(doc), "bibliography links must default off")
    check(not cc.bibliography_external_links_enabled(doc), "bibliography title/DOI links must default off")

    # UX follow-up (backlog #33/#34, inc 446): prove the interactive toggle wrappers themselves under real
    # headless UNO — previously only the direct setters below (set_bibliography_links/
    # set_bibliography_external_links) were exercised here. One isolated round trip per toggle, then back to
    # defaults before the existing scenario (driven through the direct setters) continues unmodified.
    cc._DISPATCH_CTX = ctx
    captured = []
    original_msgbox = cc._msgbox

    def toggle_and_capture(fn):
        captured.clear()
        cc._msgbox = lambda message, title="callosum": captured.append(message)
        try:
            fn(doc, base)
        finally:
            cc._msgbox = original_msgbox

    toggle_and_capture(cc.toggle_bibliography_links_interactive)
    check(cc.bibliography_links_enabled(doc), "interactive toggle did not enable bibliography links")
    check(
        captured and captured[0].startswith("Citation-to-bibliography links: OFF → ON."),
        f"unexpected bibliography-links toggle-on message: {captured}",
    )
    check(
        cc.diagnose_document(doc, base)["preferences"]["bibliography_links"] is True,
        "diagnostics did not reflect bibliography_links=True after the interactive toggle",
    )

    toggle_and_capture(cc.toggle_bibliography_links_interactive)
    check(not cc.bibliography_links_enabled(doc), "interactive toggle did not disable bibliography links")
    check(
        captured and captured[0].startswith("Citation-to-bibliography links: ON → OFF."),
        f"unexpected bibliography-links toggle-off message: {captured}",
    )
    check(
        cc.diagnose_document(doc, base)["preferences"]["bibliography_links"] is False,
        "diagnostics did not reflect bibliography_links=False after toggling back off",
    )

    toggle_and_capture(cc.toggle_bibliography_external_links_interactive)
    check(cc.bibliography_external_links_enabled(doc), "interactive toggle did not enable bibliography external links")
    check(
        captured and captured[0].startswith("Bibliography title/DOI links: OFF → ON."),
        f"unexpected bibliography-external-links toggle-on message: {captured}",
    )
    check(
        cc.diagnose_document(doc, base)["preferences"]["bibliography_external_links"] is True,
        "diagnostics did not reflect bibliography_external_links=True after the interactive toggle",
    )

    toggle_and_capture(cc.toggle_bibliography_external_links_interactive)
    check(
        not cc.bibliography_external_links_enabled(doc),
        "interactive toggle did not disable bibliography external links",
    )
    check(
        captured and captured[0].startswith("Bibliography title/DOI links: ON → OFF."),
        f"unexpected bibliography-external-links toggle-off message: {captured}",
    )
    check(
        cc.diagnose_document(doc, base)["preferences"]["bibliography_external_links"] is False,
        "diagnostics did not reflect bibliography_external_links=False after toggling back off",
    )

    cc.set_bibliography_links(doc, True, base)
    fields = cc.scan_citations_in_order(doc)
    expected_targets = {
        cc.bibliography_entry_bookmark(f"callosum-{p1}"),
        cc.bibliography_entry_bookmark(f"callosum-{p2}"),
    }
    check(
        expected_targets <= set(doc.getBookmarks().getElementNames()),
        "bibliography entry targets were not created",
    )
    check(
        cc._mark_hyperlink_url(fields[0]["_mark"]) == f"#{cc.bibliography_entry_bookmark(f'callosum-{p1}')}",
        "first single-work citation did not link to its entry",
    )
    check(
        cc._mark_hyperlink_url(fields[1]["_mark"]) == f"#{cc.bibliography_entry_bookmark(f'callosum-{p2}')}",
        "second single-work citation did not link to its entry",
    )
    check(cc._mark_hyperlink_url(fields[2]["_mark"]) == "", "grouped citation must remain unlinked")
    check(
        cc.go_to_bibliography_item(doc, f"callosum-{p2}"),
        "explicit bibliography navigation could not resolve the second grouped source",
    )
    target = doc.getBookmarks().getByName(cc.bibliography_entry_bookmark(f"callosum-{p2}")).getAnchor().getStart()
    check(
        text.compareRegionStarts(doc.getCurrentController().getViewCursor().getStart(), target) == 0,
        "explicit bibliography navigation did not move the view cursor to the selected entry",
    )

    cc.set_bibliography_external_links(doc, True, base)
    style, locale = cc._get_pref(doc, base)
    link_response = cc.render_document(base, cc.build_render_request(fields, style, locale))
    link_entries = link_response["bibliography_text"].splitlines()
    entry_links = cc.normalize_bibliography_links(link_entries, link_response.get("bibliography_links"))
    check(sum(len(links) for links in entry_links) == 2, "expected one rendered DOI link per bibliography entry")
    check(
        cc.bibliography_external_links_are_current(doc, link_entries, entry_links, True),
        "bibliography DOI links were not applied",
    )
    cc.set_bibliography_external_links(doc, False, base)
    check(
        cc.bibliography_external_links_are_current(doc, link_entries, entry_links, False),
        "turning bibliography DOI links off left a managed web link",
    )
    check(
        insertion("LINK").getPropertyValue("HyperLinkURL") == "https://example.test/manual",
        "turning bibliography DOI links off changed an unrelated external hyperlink",
    )
    cc.set_bibliography_external_links(doc, True, base)
    cc.set_style(doc, "nature", "en-US", base)
    nature_fields = cc.scan_citations_in_order(doc)
    nature_response = cc.render_document(base, cc.build_render_request(nature_fields, "nature", "en-US"))
    nature_entries = nature_response["bibliography_text"].splitlines()
    nature_ids = nature_response["bibliography_entry_ids"]
    nature_links = cc.normalize_bibliography_links(
        nature_entries,
        nature_response.get("bibliography_links"),
    )
    titles_by_id = {
        str(item["id"]): str(item["title"])
        for field in nature_fields
        for item in field["items"]
        if item.get("id") and item.get("title")
    }
    check(sum(len(links) for links in nature_links) == 2, "Nature title-link fallback did not cover both entries")
    for entry, ids, links in zip(nature_entries, nature_ids, nature_links, strict=True):
        check(len(ids) == 1 and len(links) == 1, "Nature title-link metadata was not one-to-one")
        start, length, url = links[0]
        check(
            entry[start : start + length].lower() == titles_by_id[ids[0]].lower(),
            "Nature fallback did not select the exact rendered source title",
        )
        check(url.startswith("https://doi.org/10.5555/"), "Nature title fallback did not prefer the source DOI")
    check(
        cc.bibliography_external_links_are_current(doc, nature_entries, nature_links, True),
        "Nature bibliography title links were not applied",
    )
    cc.set_style(doc, "apa", "en-US", base)

    cc._set_id_list(doc, cc.PREF_BIB_EXCLUDE, [p1])
    cc.refresh(doc, base)
    excluded_fields = cc.scan_citations_in_order(doc)
    check(
        cc.bibliography_entry_bookmark(f"callosum-{p1}") not in doc.getBookmarks().getElementNames(),
        "excluded work kept a bibliography target",
    )
    check(cc._mark_hyperlink_url(excluded_fields[0]["_mark"]) == "", "excluded work kept a citation link")
    check(
        cc._mark_hyperlink_url(excluded_fields[1]["_mark"]) == f"#{cc.bibliography_entry_bookmark(f'callosum-{p2}')}",
        "excluding one work disturbed another citation link",
    )
    check(
        not cc.go_to_bibliography_item(doc, f"callosum-{p1}"),
        "explicit bibliography navigation resolved an excluded work",
    )
    cc._set_id_list(doc, cc.PREF_BIB_EXCLUDE, [])
    cc.refresh(doc, base)

    cc.set_bibliography_links(doc, False, base)
    check(
        all(cc._mark_hyperlink_url(field["_mark"]) == "" for field in cc.scan_citations_in_order(doc)),
        "turning links off left a hyperlink on a citation",
    )
    check(
        insertion("LINK").getPropertyValue("HyperLinkURL") == "https://example.test/manual",
        "turning links off changed an unrelated external hyperlink",
    )
    check(
        cc.go_to_bibliography_item(doc, f"callosum-{p2}"),
        "explicit bibliography navigation should not depend on the citation-link preference",
    )
    cc.set_bibliography_links(doc, True, base)

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    try:
        from com.sun.star.beans import PropertyValue

        save_url = uno.systemPathToFileUrl(save_path)
        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeToURL(save_url, (filt,))
        reopened = load_doc(ctx, save_url)
        reopened_fields = cc.scan_citations_in_order(reopened)
        check(cc.bibliography_links_enabled(reopened), "link preference did not survive save/reopen")
        check(cc.bibliography_external_links_enabled(reopened), "DOI/URL link preference did not survive save/reopen")
        check(
            expected_targets <= set(reopened.getBookmarks().getElementNames()),
            "bibliography targets did not survive save/reopen",
        )
        check(
            cc.go_to_bibliography_item(reopened, f"callosum-{p2}"),
            "explicit bibliography navigation did not survive save/reopen",
        )
        reopened_target = (
            reopened.getBookmarks().getByName(cc.bibliography_entry_bookmark(f"callosum-{p2}")).getAnchor().getStart()
        )
        check(
            reopened.getText().compareRegionStarts(
                reopened.getCurrentController().getViewCursor().getStart(),
                reopened_target,
            )
            == 0,
            "reopened explicit navigation did not land on the selected entry",
        )
        reopened_descriptor = reopened.createSearchDescriptor()
        reopened_descriptor.SearchString = "LINK"
        reopened_link = reopened.getText().createTextCursorByRange(reopened.findFirst(reopened_descriptor))
        check(
            reopened_link.getPropertyValue("HyperLinkURL") == "https://example.test/manual",
            "unrelated external hyperlink did not survive save/reopen",
        )
        check(
            cc._mark_hyperlink_url(reopened_fields[0]["_mark"])
            == f"#{cc.bibliography_entry_bookmark(f'callosum-{p1}')}",
            "citation hyperlink did not survive save/reopen",
        )
        check(cc._mark_hyperlink_url(reopened_fields[2]["_mark"]) == "", "grouped citation gained a link on reopen")
        reopened_style, reopened_locale = cc._get_pref(reopened, base)
        reopened_response = cc.render_document(
            base,
            cc.build_render_request(reopened_fields, reopened_style, reopened_locale),
        )
        reopened_entries = reopened_response["bibliography_text"].splitlines()
        reopened_links = cc.normalize_bibliography_links(
            reopened_entries,
            reopened_response.get("bibliography_links"),
        )
        check(
            cc.bibliography_external_links_are_current(reopened, reopened_entries, reopened_links, True),
            "bibliography DOI links did not survive save/reopen",
        )
        cc.convert_citation_placement(
            reopened,
            "chicago-notes-bibliography",
            "en-US",
            "footnote",
            base,
        )
        converted_fields = cc.scan_citations_in_order(reopened)
        check(
            cc._mark_hyperlink_url(converted_fields[0]["_mark"])
            == f"#{cc.bibliography_entry_bookmark(f'callosum-{p1}')}",
            "placement conversion lost the first single-work link",
        )
        check(
            cc._mark_hyperlink_url(converted_fields[1]["_mark"])
            == f"#{cc.bibliography_entry_bookmark(f'callosum-{p2}')}",
            "placement conversion lost the second single-work link",
        )
        check(
            cc._mark_hyperlink_url(converted_fields[2]["_mark"]) == "",
            "placement conversion linked a grouped citation",
        )
        converted_style, converted_locale = cc._get_pref(reopened, base)
        converted_response = cc.render_document(
            base,
            cc.build_render_request(converted_fields, converted_style, converted_locale),
        )
        converted_entries = converted_response["bibliography_text"].splitlines()
        converted_links = cc.normalize_bibliography_links(
            converted_entries,
            converted_response.get("bibliography_links"),
        )
        check(
            cc.bibliography_external_links_are_current(reopened, converted_entries, converted_links, True),
            "placement conversion lost bibliography DOI links",
        )
        reopened.close(False)
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass
    log(
        "spike (P1 #11): OK — citation targets + visible DOI and title-fallback links round-trip; "
        "grouped citation stays plain"
    )


def spike_partial_refresh_controls(ctx, base, p1):
    """P1 item #13: citation-only and bibliography-only refreshes mutate exactly the requested surface.

    This deliberately writes stale visible text into a real ReferenceMark and the real managed bibliography,
    then exercises both public partial-refresh functions. Bibliography-only must work even while automatic
    bibliography rebuilding is paused: it is an explicit user command, not a passive full-refresh side effect.
    """
    log("spike (P1 #13): independent citation-only / bibliography-only refresh")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("Claim XXX.\n")

    sd = doc.createSearchDescriptor()
    sd.SearchString = "XXX"
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(doc.findFirst(sd)))
    field = cc.scan_citations_in_order(doc)[0]
    mark_name = field["_mark"].Name

    cc._replace_mark_text(doc, doc.getReferenceMarks().getByName(mark_name), "STALE CITATION")
    cc._write_bibliography(doc, ["STALE BIBLIOGRAPHY"])
    cc.set_bib_auto(doc, False)
    cc.refresh_bibliography(doc, base)
    check(
        doc.getReferenceMarks().getByName(mark_name).getAnchor().getString() == "STALE CITATION",
        "bibliography-only refresh unexpectedly changed citation text",
    )
    body = text.getString()
    check("STALE BIBLIOGRAPHY" not in body, "bibliography-only refresh did not rebuild the bibliography")
    check(cc.BIB_HEADING in body, "bibliography-only refresh removed the managed bibliography")

    cc._write_bibliography(doc, ["FROZEN BIBLIOGRAPHY"])
    cc.refresh_citations(doc, base)
    check(
        doc.getReferenceMarks().getByName(mark_name).getAnchor().getString() != "STALE CITATION",
        "citation-only refresh did not repair citation text",
    )
    check(
        "FROZEN BIBLIOGRAPHY" in text.getString(),
        "citation-only refresh unexpectedly changed the managed bibliography",
    )
    log("spike (P1 #13): OK — each partial refresh changed only its requested surface")


def spike_selected_citation_refresh(ctx, base, p1, p2):
    """P1 item #13: cursor-scoped refresh renders full context but mutates only one citation mark."""
    log("spike (P1 #13): refresh citation at cursor")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("First XXX0. Second XXX1.\n")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("XXX0")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("XXX1")))
    fields = cc.scan_citations_in_order(doc)
    first_name = fields[0]["_mark"].Name
    second_name = fields[1]["_mark"].Name
    cc._replace_mark_text(doc, doc.getReferenceMarks().getByName(first_name), "STALE FIRST")
    cc._replace_mark_text(doc, doc.getReferenceMarks().getByName(second_name), "STALE SECOND")
    cc.set_dirty_state(doc, citations=True)
    bibliography_before = text.getString().split(cc.BIB_HEADING, 1)[-1]

    view_cursor = doc.getCurrentController().getViewCursor()
    view_cursor.gotoRange(doc.getReferenceMarks().getByName(first_name).getAnchor().getStart(), False)
    cc.refresh_selected_citation(doc, base)

    check(
        doc.getReferenceMarks().getByName(first_name).getAnchor().getString() != "STALE FIRST",
        "cursor-scoped refresh did not update the selected citation",
    )
    check(
        doc.getReferenceMarks().getByName(second_name).getAnchor().getString() == "STALE SECOND",
        "cursor-scoped refresh unexpectedly changed another citation",
    )
    check(
        text.getString().split(cc.BIB_HEADING, 1)[-1] == bibliography_before,
        "cursor-scoped refresh unexpectedly changed the bibliography",
    )
    check(
        cc.dirty_state(doc) == (True, False),
        "cursor-scoped refresh falsely cleared the document-wide citation-pending state",
    )
    log("spike (P1 #13): OK — only the cursor citation changed; global pending state stayed honest")


def spike_current_section_refresh(ctx, base, p1, p2):
    """P1 item #13: outline-defined section refresh includes nested subsections and stops at the next peer."""
    log("spike (P1 #13): refresh current outline section")
    doc = new_writer(ctx)
    text = doc.getText()
    rows = ["Preamble XXX0.", "Section One", "First XXX1.", "Subsection", "Nested XXX2.", "Section Two", "Second XXX3."]
    for row in rows:
        cursor = text.createTextCursorByRange(text.getEnd())
        text.insertString(cursor, row, False)
        text.insertControlCharacter(cursor, cc._PARAGRAH_BREAK(), False)

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    def set_heading(needle, style):
        cursor = text.createTextCursorByRange(find_range(needle))
        cursor.gotoStartOfParagraph(False)
        cursor.gotoEndOfParagraph(True)
        cursor.ParaStyleName = style

    set_heading("Section One", "Heading 1")
    set_heading("Subsection", "Heading 2")
    set_heading("Section Two", "Heading 1")
    for marker, paper_id in (("XXX0", p1), ("XXX1", p1), ("XXX2", p2), ("XXX3", p2)):
        cc.insert_citation(doc, paper_id, base, cursor=text.createTextCursorByRange(find_range(marker)))

    fields = cc.scan_citations_in_order(doc)
    names = [field["_mark"].Name for field in fields]
    stale = ["STALE PREAMBLE", "STALE FIRST", "STALE NESTED", "STALE SECOND"]
    for name, value in zip(names, stale, strict=True):
        cc._replace_mark_text(doc, doc.getReferenceMarks().getByName(name), value)
    cc.set_dirty_state(doc, citations=True)
    bibliography_before = text.getString().split(cc.BIB_HEADING, 1)[-1]

    view_cursor = doc.getCurrentController().getViewCursor()
    view_cursor.gotoRange(doc.getReferenceMarks().getByName(names[1]).getAnchor().getStart(), False)
    cc.refresh_current_section(doc, base)

    rendered = [doc.getReferenceMarks().getByName(name).getAnchor().getString() for name in names]
    check(rendered[0] == stale[0], "current-section refresh unexpectedly changed the preamble citation")
    check(rendered[1] != stale[1], "current-section refresh did not update its direct citation")
    check(rendered[2] != stale[2], "current-section refresh did not include its nested subsection")
    check(rendered[3] == stale[3], "current-section refresh crossed into the next peer section")
    check(
        text.getString().split(cc.BIB_HEADING, 1)[-1] == bibliography_before,
        "current-section refresh unexpectedly changed the bibliography",
    )
    check(
        cc.dirty_state(doc) == (True, False),
        "current-section refresh falsely cleared the document-wide citation-pending state",
    )
    log("spike (P1 #13): OK — heading subtree refreshed; preamble/next peer/bibliography stayed unchanged")


def spike_manual_refresh_mode(ctx, base, p1, p2):
    """P1 item #13: citation formatting and bibliography rebuilding can be paused independently.

    Paused inserts remain real ReferenceMarks with their full payload, but their visible placeholder is left
    alone until an explicit refresh. With both surfaces paused, no automatic document write occurs.
    """
    log("spike (P1 #13): manual refresh mode / pause automatic citation formatting")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("A XXX0, B XXX1, and C XXX2.\n")

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    def bibliography_text():
        bookmarks = doc.getBookmarks()
        start = bookmarks.getByName(cc.BIB_BOOKMARK).getAnchor().getStart()
        end = bookmarks.getByName(cc.BIB_BOOKMARK_END).getAnchor().getEnd()
        cursor = text.createTextCursorByRange(start)
        cursor.gotoRange(end, True)
        return cursor.getString()

    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("XXX0")))
    check(cc.cite_auto_enabled(doc), "citation auto-formatting should default to enabled")
    check(cc.dirty_state(doc) == (False, False), "fully automatic insertion should leave no pending surface")
    check(
        not doc.getCurrentController().hasInfobar(cc.DIRTY_INFOBAR_ID),
        "fully automatic insertion unexpectedly showed the pending-refresh Infobar",
    )
    cc.set_cite_auto(doc, False)
    check(not cc.cite_auto_enabled(doc), "citation auto-formatting preference did not persist as disabled")

    bib_before = bibliography_text()
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("XXX1")))
    fields = cc.scan_citations_in_order(doc)
    paused_mark = fields[1]["_mark"].Name
    check(
        doc.getReferenceMarks().getByName(paused_mark).getAnchor().getString() == cc.PLACEHOLDER,
        "paused citation insertion unexpectedly formatted its visible text",
    )
    check(bibliography_text() != bib_before, "bibliography did not update while only citation formatting was paused")
    check(cc.dirty_state(doc) == (True, False), "citation-only pending state was not persisted")
    check(
        doc.getCurrentController().hasInfobar(cc.DIRTY_INFOBAR_ID),
        "citation-only pending state did not show the Writer Infobar",
    )

    bib_after_insert = bibliography_text()
    cc.refresh_citations(doc, base)
    check(
        doc.getReferenceMarks().getByName(paused_mark).getAnchor().getString() != cc.PLACEHOLDER,
        "explicit citation-only refresh did not format the pending citation",
    )
    check(bibliography_text() == bib_after_insert, "citation-only refresh changed the bibliography")
    check(cc.dirty_state(doc) == (False, False), "citation-only refresh did not clear its dirty flag")
    check(
        not doc.getCurrentController().hasInfobar(cc.DIRTY_INFOBAR_ID),
        "citation-only refresh did not remove the clean Infobar",
    )

    cc.set_bib_auto(doc, False)
    cc._write_bibliography(doc, ["FROZEN BIBLIOGRAPHY"])
    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("XXX2")))
    fields = cc.scan_citations_in_order(doc)
    newest_mark = fields[2]["_mark"].Name
    check(
        doc.getReferenceMarks().getByName(newest_mark).getAnchor().getString() == cc.PLACEHOLDER,
        "both-paused insertion unexpectedly formatted its visible text",
    )
    check("FROZEN BIBLIOGRAPHY" in bibliography_text(), "both-paused insertion unexpectedly rebuilt bibliography")
    check(cc.dirty_state(doc) == (True, True), "both-paused insertion did not persist both dirty flags")
    check(
        doc.getCurrentController().hasInfobar(cc.DIRTY_INFOBAR_ID),
        "both-paused pending state did not show the Writer Infobar",
    )

    cc.refresh_pending(doc, base)
    check(
        all(f["_mark"].getAnchor().getString() != cc.PLACEHOLDER for f in cc.scan_citations_in_order(doc)),
        "Refresh pending left a citation placeholder",
    )
    check("FROZEN BIBLIOGRAPHY" not in bibliography_text(), "Refresh pending did not rebuild bibliography")
    check(cc.dirty_state(doc) == (False, False), "Refresh pending did not clear both dirty flags")
    check(
        not doc.getCurrentController().hasInfobar(cc.DIRTY_INFOBAR_ID),
        "Refresh pending did not remove the clean Infobar",
    )
    log("spike (P1 #13): OK — independent dirty flags drove a persistent Infobar and exact-surface refresh")


def spike_document_lifecycle_observer(ctx, base, p1, p2):
    """P1 item #13: the packaged document-open job restores state immediately and observes native mark moves."""
    import tempfile

    log("spike (P1 #13): document-open state + native Writer citation observation")
    doc = new_writer(ctx)
    text = doc.getText()
    text.createTextCursorByRange(text.getStart()).setString("First XXX0. Second XXX1. Plain PROSE. Move MOVEHERE.\n")

    def find_in(active_doc, needle):
        descriptor = active_doc.createSearchDescriptor()
        descriptor.SearchString = needle
        return active_doc.findFirst(descriptor)

    cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_in(doc, "XXX0")))
    cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_in(doc, "XXX1")))
    cc.set_dirty_state(doc, citations=True, bibliography=False)

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    save_url = uno.systemPathToFileUrl(save_path)
    try:
        from com.sun.star.beans import PropertyValue

        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeAsURL(save_url, (filt,))
        doc.close(False)

        reopened = load_doc(ctx, save_url, hidden=False)
        controller = reopened.getCurrentController()
        check(
            wait_until(lambda: controller.hasInfobar(cc.DIRTY_INFOBAR_ID)),
            "persisted dirty state did not restore its Infobar automatically on document open",
        )
        check(cc.dirty_state(reopened) == (True, False), "reopen changed the persisted citation-only dirty state")

        cc.set_dirty_state(reopened, citations=False, bibliography=False)
        reopened_text = reopened.getText()
        prose = find_in(reopened, "PROSE")
        prose.setString("edited prose")
        time.sleep(0.2)
        check(cc.dirty_state(reopened) == (False, False), "an unrelated prose edit falsely marked citations stale")

        fields = cc.scan_citations_in_order(reopened)
        first = fields[0]["_mark"]
        first_name = first.Name
        rendered = first.getAnchor().getString()
        old_cursor = reopened_text.createTextCursorByRange(first.getAnchor())
        reopened_text.removeTextContent(first)
        old_cursor.setString("")
        target = reopened_text.createTextCursorByRange(find_in(reopened, "MOVEHERE"))
        target.setString(rendered)
        moved = reopened.createInstance("com.sun.star.text.ReferenceMark")
        moved.Name = first_name
        reopened_text.insertTextContent(target, moved, True)

        check(
            wait_until(lambda: cc.dirty_state(reopened) == (True, True)),
            "a native Writer citation move did not mark citation formatting and bibliography stale",
        )
        check(
            controller.hasInfobar(cc.DIRTY_INFOBAR_ID),
            "a native Writer citation move did not show the pending-refresh Infobar",
        )
        check(
            order_of_papers(reopened) == [f"callosum-{p2}", f"callosum-{p1}"],
            "native move fixture did not actually reorder the two live citations",
        )
        reopened.close(False)
    finally:
        try:
            os.remove(save_path)
        except OSError:
            pass
    log("spike (P1 #13): OK — reopen state was immediate; native move detected; prose edit ignored")


def spike_style_manager(ctx, base):
    """P1 item #9: Writer consumes the shared searchable catalog/default/preview contract."""
    log("spike (P1 #9): shared citation style manager contract")
    catalog = cc.style_catalog(base, "psychology")
    check([style["id"] for style in catalog["styles"]] == ["apa"], "Writer style search did not match CSL fields")
    preview = cc.preview_style(base, "apa", "en-US")
    check(preview.get("example_only") is True, "style preview was not marked as example-only")
    check("Rivera & Chen, 2024" in preview["citations"][0], "Writer style preview did not use citeproc output")

    custom_csl = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">
  <info>
    <title>Callosum Native Test Style</title>
    <id>https://example.test/styles/callosum-native-test</id>
    <link href="https://example.test/styles/callosum-native-test" rel="self"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
    <category citation-format="author-date"/>
  </info>
  <citation><layout prefix="[" suffix="]"><text variable="title"/></layout></citation>
  <bibliography><layout><text variable="title"/></layout></bibliography>
</style>"""
    installed = cc._post_json(
        f"{base}/citations/styles/install",
        {"filename": "callosum-native-test.csl", "csl": custom_csl, "replace": True},
    )["install"]
    custom_id = installed["style"]["id"]
    custom_rows = cc.style_catalog(base, "Native Test")["styles"]
    check([style["id"] for style in custom_rows] == [custom_id], "Writer did not discover the installed CSL style")
    custom_preview = cc.preview_style(base, custom_id, "en-US")
    check(
        "An example study of collaborative writing" in custom_preview["citations"][0],
        "installed CSL style did not render through Writer's preview contract",
    )

    cc._put_json(
        f"{base}/citations/styles/preferences",
        {"style": custom_id, "locale": "en-GB", "set_default": True},
    )
    blank = new_writer(ctx)
    try:
        check(cc._get_pref(blank, base) == (custom_id, "en-GB"), "new Writer document did not inherit custom default")
        check(
            cc._effective_user_prop(blank, cc.PREF_STYLE) is None,
            "reading the application default prematurely embedded a document style",
        )
        cc.set_style(blank, custom_id, "en-GB", base)
        check(
            cc._get_pref(blank, base) == (custom_id, "en-GB"),
            "Writer did not embed and apply the installed CSL style",
        )
    finally:
        blank.close(False)
        cc._put_json(
            f"{base}/citations/styles/preferences",
            {"style": "apa", "locale": "en-US", "set_default": True},
        )
    log("spike (P1 #9): OK — bundled/custom search, preview, and new-document default")


def spike_journal_abbreviations(ctx, base, p1, p2):
    """P1 item #15: document-local library/MEDLINE/full journal-title selection through real citeproc + Writer."""
    import tempfile

    log("spike (P1 #15): journal abbreviation modes")
    doc = new_writer(ctx)
    text = doc.getText()
    text.setString("First XXX. Second YYY.\n")
    cc._set_pref(doc, "nature", "en-US")
    for needle, paper_id in (("XXX", p1), ("YYY", p2)):
        descriptor = doc.createSearchDescriptor()
        descriptor.SearchString = needle
        cc.insert_citation(doc, paper_id, base, cursor=text.createTextCursorByRange(doc.findFirst(descriptor)))

    fields = cc.scan_citations_in_order(doc)
    fixtures = (
        {
            "container-title": "Journal of Clinical Investigation",
            "container-title-short": "Library JCI",
            "ISSN": "0021-9738",
        },
        {
            "container-title": "Definitely Unknown Callosum Periodical",
            "container-title-short": None,
            "journalAbbreviation": None,
            "ISSN": None,
        },
    )
    for field, fixture in zip(fields, fixtures, strict=True):
        decoded = cc.decode_mark_name(field["_mark"].Name)
        item = dict(decoded["items"][0])
        for name, value in fixture.items():
            if value is None:
                item.pop(name, None)
            else:
                item[name] = value
        field["_mark"].Name = cc.encode_mark_name({"items": [item], "sort": decoded["sort"]}, decoded["rnd"])

    library_mode, library_summary = cc.set_journal_abbreviation_mode(doc, "library", base)
    library_body = text.getString()
    check(library_mode == "library", "library abbreviation mode did not normalize")
    check("Library JCI" in library_body, f"library abbreviation was not rendered: {library_body!r}")
    check(
        library_summary["library_count"] == 1 and library_summary["unknown_count"] == 1,
        f"library abbreviation coverage was wrong: {library_summary!r}",
    )

    medline_mode, medline_summary = cc.set_journal_abbreviation_mode(doc, "medline", base)
    medline_body = text.getString()
    check(medline_mode == "medline", "MEDLINE abbreviation mode did not normalize")
    check(
        "J Clin Invest" in medline_body and "Library JCI" not in medline_body,
        f"MEDLINE abbreviation did not replace the library short title: {medline_body!r}",
    )
    check(
        medline_summary["medline_count"] == 1
        and medline_summary["unknown_count"] == 1
        and medline_summary["unknown_titles"] == ["Definitely Unknown Callosum Periodical"],
        f"MEDLINE coverage/warning was wrong: {medline_summary!r}",
    )
    embedded = cc.scan_citations_in_order(doc)[0]["items"][0]
    check(
        embedded.get("container-title-short") == "Library JCI",
        "render-time MEDLINE selection rewrote the embedded citation metadata",
    )

    original_refresh = cc.refresh

    def fail_refresh(*_args, **_kwargs):
        raise RuntimeError("injected journal-mode refresh failure")

    cc.refresh = fail_refresh
    try:
        try:
            cc.set_journal_abbreviation_mode(doc, "full", base)
        except RuntimeError as exc:
            check("injected journal-mode" in str(exc), f"wrong preference rollback error: {exc}")
        else:
            raise AssertionError("journal-mode refresh failure did not propagate")
    finally:
        cc.refresh = original_refresh
    check(cc.journal_abbreviation_mode(doc) == "medline", "failed journal-mode refresh did not restore the preference")
    check("J Clin Invest" in text.getString(), "failed journal-mode refresh changed rendered bibliography text")

    fd, save_path = tempfile.mkstemp(suffix=".odt")
    os.close(fd)
    os.remove(save_path)
    save_url = uno.systemPathToFileUrl(save_path)
    reopened = None
    try:
        from com.sun.star.beans import PropertyValue

        filt = PropertyValue()
        filt.Name, filt.Value = "FilterName", "writer8"
        doc.storeAsURL(save_url, (filt,))
        doc.close(True)
        reopened = load_doc(ctx, save_url)
        check(cc.journal_abbreviation_mode(reopened) == "medline", "MEDLINE preference did not survive save/reopen")
        check("J Clin Invest" in reopened.getText().getString(), "MEDLINE-rendered title did not survive save/reopen")
        full_mode, full_summary = cc.set_journal_abbreviation_mode(reopened, "full", base)
        full_body = reopened.getText().getString()
        check(
            full_mode == "full" and full_summary["full_title_count"] == 2,
            f"full-title summary was wrong: {full_summary}",
        )
        check(
            "Journal of Clinical Investigation" in full_body
            and "Definitely Unknown Callosum Periodical" in full_body
            and "J Clin Invest" not in full_body,
            f"full journal titles were not rendered: {full_body!r}",
        )
        reopened.close(False)
        reopened = None
    finally:
        if reopened is not None:
            try:
                reopened.close(False)
            except Exception:
                pass
        if os.path.exists(save_path):
            os.remove(save_path)
    log("spike (P1 #15): OK — library/MEDLINE/full, unknown warning, rollback, immutable fields, and reopen")


def main():
    base, p1, p2, port = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    id1, id2 = f"callosum-{p1}", f"callosum-{p2}"
    log(f"connecting to soffice :{port}")
    ctx = connect(port)
    log("connected; cleaning + opening Writer")
    close_open_docs(ctx)
    spike_style_manager(ctx, base)
    if os.environ.get("CALLOSUM_UNO_SPIKE") == "bibliography-links":
        spike_bibliography_links(ctx, base, p1, p2)
        print("SELFTEST OK", flush=True)
        return 0
    if os.environ.get("CALLOSUM_UNO_SPIKE") == "bibliography-categories":
        spike_categorized_bibliography(ctx, base, p1, p2)
        print("SELFTEST OK", flush=True)
        return 0
    if os.environ.get("CALLOSUM_UNO_SPIKE") == "section-bibliographies":
        spike_section_bibliographies(ctx, base, p1, p2)
        print("SELFTEST OK", flush=True)
        return 0
    if os.environ.get("CALLOSUM_UNO_SPIKE") == "journal-abbreviations":
        spike_journal_abbreviations(ctx, base, p1, p2)
        print("SELFTEST OK", flush=True)
        return 0
    doc = new_writer(ctx)
    log("Writer open")
    try:
        text = doc.getText()

        def find_range(needle):
            sd = doc.createSearchDescriptor()
            sd.SearchString = needle
            return doc.findFirst(sd)

        # Body sentence with two anchor markers; citations replace them (non-adjacent → realistic).
        text.createTextCursorByRange(text.getStart()).setString("Claim one AAA. Claim two BBB.\n")
        log("set_style ieee")
        cc.set_style(doc, "ieee", "en-US", base)
        ieee_style = next(style for style in cc.style_catalog(base)["styles"] if style["id"] == "ieee")
        check(ieee_style["recent_rank"] == 0, "successful Writer style change was not recorded in Recents")
        log("insert p1 @AAA")
        cc.insert_citation(doc, p1, base, cursor=text.createTextCursorByRange(find_range("AAA")))
        log("insert p2 @BBB")
        cc.insert_citation(doc, p2, base, cursor=text.createTextCursorByRange(find_range("BBB")))
        log("both inserted")

        log("scan order")
        order = order_of_papers(doc)
        log(f"order = {order}")
        check(order == [id1, id2], f"doc order {order} != [{id1}, {id2}]")
        rb = rendered_by_paper(doc)
        log(f"ieee rendered = {rb}")
        check(rb.get(id1) == "[1]", f"IEEE in-text for first cite was {rb.get(id1)!r}, expected '[1]'")
        check(rb.get(id2) == "[2]", f"IEEE in-text for second cite was {rb.get(id2)!r}, expected '[2]'")
        body = text.getString()
        check(cc.BIB_HEADING in body, "bibliography heading missing after IEEE render")
        check(body.count("[1]") >= 1 and body.count("[2]") >= 1, "numbered bibliography entries missing")

        # 2) restyle to author-date and re-render.
        log("set_style apa")
        cc.set_style(doc, "apa", "en-US", base)
        log("apa restyled; scanning")
        rb = rendered_by_paper(doc)
        log(f"apa rendered = {rb}")
        check(
            rb.get(id1, "").startswith("(") and rb.get(id1, "").endswith(")"),
            f"APA in-text was {rb.get(id1)!r}, expected an author-date '(...)'",
        )
        check(rb.get(id1) != rb.get(id2), "the two APA citations rendered identically")

        # 3) flatten → marks gone, rendered text stays.
        apa_text = rb.get(id1)
        log("flatten")
        removed = cc.flatten(doc)
        log(f"flattened {removed}")
        check(removed == 2, f"flatten removed {removed} marks, expected 2")
        log("checking marks gone")
        remaining = [n for n in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
        log(f"remaining marks = {remaining}")
        check(remaining == [], "citation marks survived flatten")
        log("reading body")
        body2 = text.getString()
        log(f"apa_text present in body = {apa_text in body2}")
        check(apa_text in body2, "flattened citation text was lost")

        # 4) inc 157: the "Suggest citations" chain — fetch suggestions for a sentence + insert the top one,
        # on a fresh doc (isolated from the AAA/BBB flow above). Proves suggest→insert end-to-end through real
        # LibreOffice + a real server with an embedded library.
        log("suggest: fresh doc")
        doc2 = new_writer(ctx)
        # backlog #30: fetch_suggestions now returns {"suggestions", "beyond_library_suggestions"} (the latter
        # only populated when include_beyond_library=True, which this in-library-only check doesn't request).
        sugg = cc.fetch_suggestions(base, "attention mechanism transformer architecture")["suggestions"]
        log(f"suggestions = {[(s.get('paper_id'), (s.get('stance') or {}).get('label')) for s in sugg]}")
        check(len(sugg) >= 1, "no suggestions returned for the query")
        check(any(int(s["paper_id"]) in (int(p1), int(p2)) for s in sugg), "no seeded paper among suggestions")
        rows = cc.build_suggest_rows(sugg)
        check(len(rows) == len(sugg) and all(r.startswith("[") for r in rows), f"suggest rows malformed: {rows}")
        text2 = doc2.getText()
        text2.createTextCursorByRange(text2.getStart()).setString("We rely on attention mechanisms.\n")
        cc.insert_citation(doc2, sugg[0]["paper_id"], base, cursor=text2.createTextCursorByRange(text2.getEnd()))
        marks2 = [n for n in doc2.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
        check(len(marks2) == 1, f"suggest-insert produced {len(marks2)} marks, expected 1")
        log("suggest-insert OK")

        # 4b) inc 162: the search-to-cite path (Add Citation). Drive the non-dialog parts directly (the input box +
        # pick-list are GUI): search the library, format the rows, insert a hit. ("attention" matches Vaswani.)
        log("search-to-cite")
        hits = cc.search_library(base, "attention")
        log(f"search hits = {[(h.get('id'), h.get('title')) for h in hits]}")
        check(len(hits) >= 1, "library search returned no hits for 'attention'")
        srows = cc.build_search_rows(hits)
        check(len(srows) == len(hits) and " — " in srows[0], f"search rows malformed: {srows}")
        doc3 = new_writer(ctx)
        t3 = doc3.getText()
        t3.createTextCursorByRange(t3.getStart()).setString("Background.\n")
        cc.insert_citation(doc3, hits[0]["id"], base, cursor=t3.createTextCursorByRange(t3.getEnd()))
        m3 = [n for n in doc3.getReferenceMarks().getElementNames() if cc.decode_mark_name(n)]
        check(len(m3) == 1, f"search-insert produced {len(m3)} marks, expected 1")
        log("search-to-cite OK")

        # 5) inc 162: the .oxt menu/toolbar dispatcher resolves. The orchestrator installs callosum.oxt before
        # launching soffice; this confirms the extension registered + that the menu URLs
        # (service:com.callosum.cite.Dispatcher?<action>) will instantiate the component and run an action.
        log("dispatcher: resolving the .oxt service")
        disp = ctx.ServiceManager.createInstanceWithContext("com.callosum.cite.Dispatcher", ctx)
        check(disp is not None, "the .oxt dispatcher service did not resolve — extension not installed/registered?")
        check(hasattr(disp, "trigger"), "the .oxt dispatcher does not expose trigger() (XJobExecutor)")
        lifecycle = ctx.ServiceManager.createInstanceWithContext("com.callosum.cite.DocumentLifecycle", ctx)
        check(lifecycle is not None, "the .oxt document-lifecycle job service did not resolve")
        check(hasattr(lifecycle, "execute"), "the document-lifecycle service does not expose execute() (XJob)")
        log("dispatcher OK")

        # P1 item #13: heading-defined current-section refresh. Kept early because it exercises Writer's live
        # OutlineLevel bridge and should fail fast before the slower legacy scale spikes.
        spike_current_section_refresh(ctx, base, p1, p2)

        # P1 item #13: Jobs.xcu OnLoadFinished lifecycle + structured XModifyListener observation.
        spike_document_lifecycle_observer(ctx, base, p1, p2)

        # 6) P0 phase-0 spike (backlog #33/#34): empirically de-risk open questions for the rework's later
        # phases, before committing further engineering on top of assumed answers. Findings are LOGGED, not all
        # hard-asserted — some outcomes (e.g. copy/paste behavior) are genuinely open questions, not predictions.
        spike_mark_size_and_reopen(ctx, base, p1, p2)
        spike_undo_manager(ctx)
        spike_copy_paste_duplicate_name(ctx, base, p1)
        spike_bounded_bibliography(ctx)

        # 7) P0 phase 2 (backlog #33/#34): transactional refresh — a real fault-injection proof, not assumed.
        spike_transactional_refresh_rollback(ctx, base, p1, p2)

        # P1 item #13: large-refresh status, cooperative Escape cancellation, and stale render protection.
        spike_refresh_progress_cancellation(ctx, base, p1, p2)

        # P1 item #13: full citeproc context with citation/bibliography delta-only Writer mutations.
        spike_incremental_rendering(ctx, base, p1, p2)

        # P1 item #10: note styles create and manage real Writer footnotes with real citeproc note indexes.
        spike_note_style_footnotes(ctx, base, p1, p2)

        # P1 item #10: exact imported-style position branches, including gaps from ordinary Writer notes.
        spike_note_style_positions(ctx, base, p1, p2)

        # P1 item #10: add/manage multiple independent live clusters inside prose-bearing native notes.
        spike_multiple_citations_in_prose_notes(ctx, base, p1, p2)

        # P1 item #10: explicit, rollback-safe placement conversion and separate-copy isolation.
        spike_note_placement_conversion(ctx, base, p1, p2)

        # P1 item #10: preserve unrelated tracked changes and refuse managed-range conflicts.
        spike_tracked_change_placement_conversion(ctx, base, p1, p2)

        # 8) P0 phase 4 (backlog #33/#34): mark_at_cursor — the shared "which existing citation is this" lookup.
        spike_mark_at_cursor(ctx, base, p1, p2)

        # 9) P0 phase 6 (backlog #33/#34): delete / merge / split / open-in-callosum, all riding mark_at_cursor.
        spike_delete_citation(ctx, base, p1, p2)
        spike_merge_and_split_citations(ctx, base, p1, p2)
        spike_open_in_callosum(ctx, base, p1, p2)

        # 10) P0 phase 7 (backlog #33/#34): bounded bibliography, insert-at-cursor/move, auto-rebuild toggle.
        spike_bounded_bibliography_preserves_trailing_text(ctx, base, p1)
        spike_insert_bibliography_here(ctx, base, p1)
        spike_toggle_bib_auto(ctx, base, p1, p2)

        # 11) P0 phase 8 (backlog #33/#34): safe flatten — the live document must never end up mutated.
        spike_prepare_submission_copy(ctx, base, p1)

        # 12) P0 phase 9 (backlog #33/#34, the last of the smaller phases): read-only document diagnostics.
        spike_document_diagnostics(ctx, base, p1, p2)

        # 13) Phase 5a (backlog #33/#34, the composer's live-search mechanism): de-risk before designing further.
        spike_live_search_listener(ctx, base)

        # 14) Phase 5a (backlog #33/#34): the composer's insert-side backend, bypassing the (blocking) dialog.
        spike_insert_citation_items(ctx, base, p1, p2)

        # 15) Phase 5b (backlog #33/#34): per-item locator/prefix/suffix/suppress-author reach the real render.
        spike_per_item_citation_overrides(ctx, base, p1)

        # 16) Phase 5c (backlog #33/#34): Edit Citation's backend -- same identity, new items, bypassing the dialog.
        spike_edit_citation(ctx, base, p1, p2)

        # 17) Backlog #30: the Suggest dialog's beyond-library checkbox mechanism (network layer faked).
        spike_beyond_library_checkbox_listener(ctx, base)

        # 18) Backlog #30: save-then-cite a beyond-library candidate, against the real local server.
        spike_save_beyond_library_item_and_cite(ctx, base)

        # 19) P1 item #12 (backlog #33/#34): the "Citations in this document" panel's read-only data source.
        spike_list_document_citations(ctx, base, p1, p2)

        # 20) P1 item #11 (backlog #33/#34): bibliography editing -- exclude a cited work, include an uncited one.
        spike_bibliography_editing(ctx, base, p1, p2)

        # P1 item #11: custom per-document bibliography heading, including save/reopen and default reset.
        spike_custom_bibliography_heading(ctx, base, p1)

        # P1 item #11: document-local named categories within the single bounded bibliography.
        spike_categorized_bibliography(ctx, base, p1, p2)

        # P1 item #11: multiple heading-scoped bibliographies alongside the full-document bibliography.
        spike_section_bibliographies(ctx, base, p1, p2)

        # P1 item #11: stable bibliography targets + opt-in links for unambiguous single-work citations.
        spike_bibliography_links(ctx, base, p1, p2)

        # P1 item #15: library/MEDLINE/full journal-title selection with honest unknown warnings.
        spike_journal_abbreviations(ctx, base, p1, p2)

        # 21) P1 item #13: explicit partial refreshes for large documents.
        spike_partial_refresh_controls(ctx, base, p1)

        # 22) P1 item #13: cursor-scoped refresh with full-document citeproc context.
        spike_selected_citation_refresh(ctx, base, p1, p2)

        # 23) P1 item #13: independent automatic citation-formatting / bibliography modes.
        spike_manual_refresh_mode(ctx, base, p1, p2)

        # 24) P2 item #19 (backlog #33/#34, inc 459): citation integrity preflight -- the new scoped retraction
        # re-check, proven against the REAL new endpoint through the REAL adapter.
        spike_citation_integrity_preflight(ctx, base, p1, p2)

        # 25) P2 item #20 (backlog #33/#34, inc 461): Citavi-style "Insert evidence" -- the real two-step
        # body-text-then-citation insertion sequence, proven to round-trip through save/reopen.
        spike_insert_evidence(ctx, base, p1, p2)

        # 26) P2 item #21 (backlog #33/#34, inc 462): open-science statement insertion -- the real multi-kind
        # staging round trip + the choice-box picker landing exactly the chosen kind's text.
        spike_insert_staged_statement(ctx, base)

        # 27) P2 item #18 (backlog #33/#34, inc 463): citation coverage audit -- the real citation-equity
        # check-selected round trip + the local uncited-paragraph structural scan (inline and note-style).
        spike_citation_coverage_audit(ctx, base, p1, p2)

        # 28) P2 item #22 (backlog #33/#34, inc 464 -- the final item in this track): Zotero citation conversion
        # -- hand-built real Zotero-shaped marks, the match/auto-add resolve paths, and the disclosed
        # note-style/Bookmark-mode/malformed boundaries, all against a real Writer document.
        spike_zotero_citation_conversion(ctx, base, p1, p2)

        print("SELFTEST OK", flush=True)
        return 0
    finally:
        pass  # intentionally do NOT close the doc — close() can block on a hidden doc; the orchestrator tears down


if __name__ == "__main__":
    import traceback

    try:
        sys.exit(main())
    except Exception as exc:
        print(f"SELFTEST FAILED: {exc}")
        traceback.print_exc()
        sys.exit(1)
