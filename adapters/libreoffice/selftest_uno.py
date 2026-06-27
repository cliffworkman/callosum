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
