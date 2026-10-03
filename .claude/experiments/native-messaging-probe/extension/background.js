// EXPERIMENTAL HARNESS (browser-capture #61) — not production code.
// Reports each probe outcome to a local collector so failure modes are observable from the shell.
const HOST = "com.callosum.connector.probe";
const COLLECTOR = "http://127.0.0.1:8777/probe";

function report(result) {
  try { fetch(COLLECTOR + "?r=" + encodeURIComponent(JSON.stringify(result))); } catch (e) { /* ignore */ }
}

function probe(reason) {
  const started = Date.now();
  try {
    chrome.runtime.sendNativeMessage(HOST, { id: "handshake-1", protocol_version: 1, reason }, (response) => {
      const err = chrome.runtime.lastError;
      report(err
        ? { ok: false, error: String(err.message), elapsed_ms: Date.now() - started, reason }
        : { ok: true, response, elapsed_ms: Date.now() - started, reason });
    });
  } catch (e) {
    report({ ok: false, threw: String(e), reason });
  }
}
probe("worker-eval");
