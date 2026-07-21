"""Headless round-trip self-test for the LibreOffice citation adapter (inc 108).

Drives a REAL (headless) LibreOffice Writer through the full live-field loop against a running callosum server,
asserting the position-aware render, the bibliography, restyle, and flatten. This is the proof the adapter works
end-to-end — and the regression harness for future changes.

Run it with **LibreOffice's bundled Python** (it has the `uno` bridge), pointed at a callosum server that already
holds the two papers whose ids you pass:

    soffice --headless --norestore --accept="socket,host=localhost,port=2002;urp;"
    "C:\\Program Files\\LibreOffice\\program\\python.exe" selftest_uno.py http://127.0.0.1:8080 <id1> <id2> 2002

(`.local/lo_roundtrip/run_roundtrip.py` automates this — seed a temp callosum, start the server + a headless
soffice, run this, tear down.)

Prints "SELFTEST OK" and exits 0 on success; prints the failed assertion and exits 1 otherwise.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callosum_cite as cc  # noqa: E402  (after sys.path injection)
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


def load_doc(ctx, url):
    """Load an existing document from a URL (vs. new_writer's blank-factory create) — used by the Phase-0
    save/reopen spike to get a genuinely fresh doc object backed by the saved file, not the original in-memory one."""
    from com.sun.star.beans import PropertyValue

    smgr = ctx.ServiceManager
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    hidden = PropertyValue()
    hidden.Name, hidden.Value = "Hidden", True
    return desktop.loadComponentFromURL(url, "_blank", 0, (hidden,))


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


def spike_mark_size_and_reopen(ctx, base, p1, p2, n=25):
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
    AAA/BBB round-trip test above already sidesteps it) so this spike measures what it set out to measure."""
    import tempfile

    log(f"spike 1/4: mark-size/scale — inserting {n} citations")
    doc = new_writer(ctx)
    text = doc.getText()

    def find_range(needle):
        sd = doc.createSearchDescriptor()
        sd.SearchString = needle
        return doc.findFirst(sd)

    anchors = "\n".join(f"Anchor{i} XXX{i}" for i in range(n))
    text.createTextCursorByRange(text.getStart()).setString(f"Stress test paragraph.\n{anchors}\n")
    for i in range(n):
        pid = p1 if i % 2 == 0 else p2
        rng = find_range(f"XXX{i}")
        check(rng is not None, f"anchor XXX{i} not found before citation insert")
        cc.insert_citation(doc, pid, base, cursor=text.createTextCursorByRange(rng))
    before = sorted(nm for nm in doc.getReferenceMarks().getElementNames() if cc.decode_mark_name(nm))
    lengths = [len(nm) for nm in before]
    log(f"spike 1/4: inserted {len(before)} marks; name length min={min(lengths)} max={max(lengths)} chars")
    check(len(before) == n, f"expected {n} marks, found {len(before)}")

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
        check(len(after) == n, f"after save/reopen: expected {n} marks, found {len(after)}")
        items_before = {nm: cc.decode_mark_name(nm)["items"] for nm in before}
        items_after = {nm: cc.decode_mark_name(nm)["items"] for nm in after}
        check(items_before == items_after, "mark payload changed after a save/reopen round-trip")
        log(
            f"spike 1/4: OK — {n} marks (max name length {max(lengths)} chars) round-trip losslessly through save/reopen"
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


def main():
    base, p1, p2, port = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    id1, id2 = f"callosum-{p1}", f"callosum-{p2}"
    log(f"connecting to soffice :{port}")
    ctx = connect(port)
    log("connected; cleaning + opening Writer")
    close_open_docs(ctx)
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
        sugg = cc.fetch_suggestions(base, "attention mechanism transformer architecture")
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
        log("dispatcher OK")

        # 6) P0 phase-0 spike (backlog #33/#34): empirically de-risk open questions for the rework's later
        # phases, before committing further engineering on top of assumed answers. Findings are LOGGED, not all
        # hard-asserted — some outcomes (e.g. copy/paste behavior) are genuinely open questions, not predictions.
        spike_mark_size_and_reopen(ctx, base, p1, p2)
        spike_undo_manager(ctx)
        spike_copy_paste_duplicate_name(ctx, base, p1)
        spike_bounded_bibliography(ctx)

        # 7) P0 phase 2 (backlog #33/#34): transactional refresh — a real fault-injection proof, not assumed.
        spike_transactional_refresh_rollback(ctx, base, p1, p2)

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
