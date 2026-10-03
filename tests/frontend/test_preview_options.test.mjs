import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../../app/desktop-shell/preview-extension/options.js", import.meta.url), "utf8");
function options() {
  let click, respond, request;
  const status = {}, button = { addEventListener(_, fn) { click = fn; } };
  const runtime = {
    getManifest: () => ({ version: "0.1.1" }),
    sendNativeMessage(host, body, callback) { request = { host, body }; respond = callback; },
  };
  vm.runInNewContext(source, { document: { getElementById: id => id === "verify" ? button : status }, chrome: { runtime }, crypto: { randomUUID: () => "test-request" } });
  return { button, status, runtime, click: () => click(), reply: value => respond(value), request: () => request };
}

test("verification performs only the normal-host handshake, never capture or file setup", () => {
  const h = options(); h.click();
  assert.equal(h.button.disabled, true);
  assert.equal(h.request().host, "org.callosum.connector");
  assert.equal(h.request().body.operation, "verify_preview");
  assert.equal(h.request().body.extension_version, "0.1.1");
  h.reply({ runtime_state: "available" });
  assert.match(h.status.textContent, /Connection verified/);
  assert.equal(h.button.disabled, false);
});

test("missing host, disabled preview and expired challenge never report verified", () => {
  for (const [state, text] of [["preview_disabled", /Enable early access/], ["verification_not_requested", /60 seconds/], ["version_incompatible", /Reload/], ["pairing_unavailable", /pairing/]]) {
    const h = options(); h.click(); h.reply({ runtime_state: state });
    assert.match(h.status.textContent, text);
    assert.doesNotMatch(h.status.textContent, /^Connection verified/);
  }
  const h = options(); h.click(); h.runtime.lastError = { message: "host absent" }; h.reply();
  assert.match(h.status.textContent, /unavailable.*identity/);
});
