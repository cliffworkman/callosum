import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../../app/frontend/js/03a_capture_updates.jsx", import.meta.url), "utf8");
const tick = () => new Promise(resolve => setImmediate(resolve));

function harness(refresh = async () => true) {
  const requests = [], timers = [], changes = [];
  const context = vm.createContext({
    AbortController,
    JOB_STATUS_FALLBACK_RETRY_MS: 1200,
    window: {
      setTimeout(fn, ms) { const timer = { fn, ms }; timers.push(timer); return timer; },
      clearTimeout(timer) { timer.cancelled = true; },
    },
    api(url, { signal }) { return new Promise(resolve => requests.push({ url, signal, resolve })); },
  });
  vm.runInContext(source, context);
  const stop = context.observeCaptureUpdates(async value => { changes.push(value); return refresh(); });
  return { requests, timers, changes, stop };
}

test("capture wakes an already-open app immediately, including a return before upload completes", async () => {
  const h = harness();
  h.requests[0].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  assert.deepEqual(h.changes, [true]);
  assert.match(h.requests[1].url, /after=a&wait_seconds=20/);
  h.requests[1].resolve({ ok: true, data: { revision: "b" } });
  await tick();
  assert.deepEqual(h.changes, [true, true]);
  assert.equal(h.timers.length, 0, "a successful notification must not add a timer delay");
  assert.match(h.requests[2].url, /after=b&wait_seconds=20/);
  h.stop();
});

test("unchanged timeout renews the held request without repeatedly fetching the queue", async () => {
  const h = harness();
  h.requests[0].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  h.requests[1].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  assert.deepEqual(h.changes, [true]);
  assert.equal(h.requests.length, 3);
  assert.equal(h.timers.length, 0);
  h.stop();
});

test("does not acknowledge a notification whose authoritative fetch failed", async () => {
  let succeeds = false;
  const h = harness(async () => succeeds);
  h.requests[0].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  assert.equal(h.timers.length, 1);
  succeeds = true;
  h.timers[0].fn();
  assert.match(h.requests[1].url, /after=&/);
  h.requests[1].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  assert.match(h.requests[2].url, /after=a&/);
  h.stop();
});

test("change during a slow queue fetch cannot be missed by the next subscription", async () => {
  let finish;
  const h = harness(() => new Promise(resolve => { finish = resolve; }));
  h.requests[0].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  assert.equal(h.requests.length, 1);
  finish(true);
  await tick();
  assert.match(h.requests[1].url, /after=a&/); // Server will immediately return a newer revision.
  h.stop();
});

test("cleanup aborts the held request and ignores a late response", async () => {
  const h = harness();
  h.stop();
  assert.equal(h.requests[0].signal.aborted, true);
  h.requests[0].resolve({ ok: true, data: { revision: "a" } });
  await tick();
  assert.deepEqual(h.changes, []);
  assert.equal(h.requests.length, 1);
});

test("transient failure retries; authorization failure does not loop", async () => {
  const h = harness();
  h.requests[0].resolve({ ok: false, status: 503 });
  await tick();
  assert.equal(h.timers[0].ms, 1200);
  h.timers[0].fn();
  h.requests[1].resolve({ ok: false, status: 401 });
  await tick();
  assert.equal(h.timers.length, 1);
  h.stop();
});
