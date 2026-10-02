import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import { fetchActiveDocument, handleCapture } from "./background.js";

const URL = "https://journals.plos.org/plosmedicine/article/file?id=10.1371/journal.pmed.0020124&type=printable";
const pdf = await readFile(new globalThis.URL("../../../tests/fixtures/capture/ioannidis-pmed.0020124.pdf", import.meta.url));

test("original publisher PDF is recognized without a .pdf suffix, including octet-stream", async () => {
  for (const type of ["application/pdf", "application/octet-stream", "text/html", ""]) {
    const result = await fetchActiveDocument(URL, { fetchImpl: async () => new Response(pdf, { headers: { "Content-Type": type } }) });
    assert.equal(result.kind, "pdf");
    assert.deepEqual(Buffer.from(result.buffer), pdf);
  }
});

test("HTML remains generic, while invalid PDF and ambiguous responses cannot create metadata", async () => {
  for (const [url, type, body, kind] of [
    [URL, "text/html; charset=utf-8", "<html>A scholarly page</html>", "html"],
    [URL, "application/pdf", "<html>Sign in</html>", "unavailable"],
    ["https://example.org/a.pdf", "text/html", "<html>Sign in</html>", "unavailable"],
    [URL, "application/octet-stream", "unknown bytes", "unavailable"],
    [URL, "application/pdf", "%PDF", "unavailable"],
  ]) {
    assert.equal((await fetchActiveDocument(url, { fetchImpl: async () => new Response(body, { headers: { "Content-Type": type } }) })).kind, kind);
  }
});

test("declared and streamed oversize PDFs are refused; split magic is recognized", async () => {
  const fake = (chunks, headers = {}) => new Response(new ReadableStream({
    start(controller) { for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk)); controller.close(); },
  }), { headers });
  assert.equal((await fetchActiveDocument(URL, { maxBytes: 8, fetchImpl: async () => fake(["%PDF-012345"]) })).kind, "unavailable");
  assert.equal((await fetchActiveDocument(URL, { maxBytes: 8, fetchImpl: async () => fake(["%PDF-"], { "Content-Length": "9" }) })).kind, "unavailable");
  const result = await fetchActiveDocument(URL, { maxBytes: 8, fetchImpl: async () => fake(["%P", "DF", "-", "123"]) });
  assert.equal(result.kind, "pdf");
  assert.equal(new TextDecoder().decode(result.buffer), "%PDF-123");
});

test("timeout, inaccessible document and non-web schemes fail closed", async () => {
  const hanging = (_url, { signal }) => new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(new Error("aborted"))));
  assert.equal((await fetchActiveDocument(URL, { fetchImpl: hanging, timeoutMs: 10 })).kind, "unavailable");
  assert.equal((await fetchActiveDocument(URL, { fetchImpl: async () => { throw new Error("No access"); } })).kind, "unavailable");
  let calls = 0;
  for (const url of ["file:///paper.pdf", "chrome://extensions", "https://user:pass@example.org/paper.pdf"]) {
    assert.equal((await fetchActiveDocument(url, { fetchImpl: async () => { calls++; } })).kind, "unavailable");
  }
  assert.equal(calls, 0);
});

test("a stalled PDF body is aborted; HTML classification cancels the unused body", async () => {
  let aborted = false;
  const stalled = async (_url, { signal }) => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode("%PDF-"));
      signal.addEventListener("abort", () => { aborted = true; controller.error(new Error("aborted")); });
    },
  }));
  assert.equal((await fetchActiveDocument(URL, { fetchImpl: stalled, timeoutMs: 10 })).kind, "unavailable");
  assert.equal(aborted, true);
  let cancelled = false;
  const html = async () => new Response(new ReadableStream({
    start(controller) { controller.enqueue(new TextEncoder().encode("<html>")); },
    cancel() { cancelled = true; },
  }), { headers: { "Content-Type": "text/html" } });
  assert.equal((await fetchActiveDocument(URL, { fetchImpl: html })).kind, "html");
  assert.equal(cancelled, true);
});

test("real click handler sends publisher PDF bytes and never sends the viewer title as generic metadata", async () => {
  const saved = { chrome: globalThis.chrome, fetch: globalThis.fetch };
  const posts = [], badges = [];
  globalThis.chrome = {
    action: { setBadgeText: ({ text }) => badges.push(text), setBadgeBackgroundColor() {}, setTitle() {} },
    runtime: { sendNativeMessage(_name, _request, cb) { cb({ runtime_state: "available", backend_base_url: "http://127.0.0.1:43210", session_token: "test-only" }); } },
    scripting: { executeScript() { throw new Error("PDF must never use DOM metadata extraction"); } },
  };
  globalThis.fetch = async (url, init) => {
    if (url === URL) return new Response(pdf, { headers: { "Content-Type": "application/pdf" } });
    posts.push({ url, init });
    return Response.json(url.endsWith("/pdf")
      ? { status: "direct_pdf_queued_for_review", pdf_reason: "provisional_capture" }
      : { status: "direct_pdf_identity_unresolved", pdf_accepted: true, pdf_reason: "provisional_capture", capture_id: "a".repeat(32) });
  };
  try {
    await handleCapture({ id: 7, url: URL, title: "PLME0208_696-701.indd" });
    assert.equal(posts.length, 2);
    const envelope = JSON.parse(posts[0].init.body);
    assert.equal(envelope.producer_kind, "direct-pdf");
    assert.equal(envelope.pdf_bytes_from_active_tab, true);
    assert.notEqual(envelope.title, "PLME0208_696-701.indd");
    assert.deepEqual(Buffer.from(posts[1].init.body), pdf);
    assert.equal(badges.at(-1), "OK");
    posts.length = 0;
    globalThis.fetch = async () => { throw new Error("PDF inaccessible"); };
    await handleCapture({ id: 7, url: URL, title: "PLME0208_696-701.indd" });
    assert.equal(posts.length, 0);
    assert.notEqual(badges.at(-1), "OK");
    // A publisher can serve an HTML challenge on re-fetch while Chrome still
    // displays its PDF viewer. Failed DOM inspection must not admit its title.
    globalThis.fetch = async (url, init) => {
      if (url === URL) return new Response("<html>Challenge</html>", { headers: { "Content-Type": "text/html" } });
      posts.push({ url, init });
      return Response.json({ status: "added" });
    };
    await handleCapture({ id: 7, url: URL, title: "PLME0208_696-701.indd" });
    assert.equal(posts.length, 0);
    assert.notEqual(badges.at(-1), "OK");
  } finally {
    globalThis.chrome = saved.chrome;
    globalThis.fetch = saved.fetch;
  }
});
