const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { SELECTORS, classifyGrokState, collectGrokState, boundedRead } = require('./grok_capture_v3.cjs');

let passed = 0;
function check(name, input, expected) {
  assert.equal(classifyGrokState(input).status, expected, name);
  passed++;
}
const complete = { assistants: 1, users: 1, bodies: 1, text: 'FABRICATED RECEIPT', copy: true };
check('complete', complete, 'ASSISTANT_FINAL');
check('empty page', {}, 'NO_ASSISTANT_FINAL');
check('user only', { users: 1 }, 'USER_MESSAGE_ONLY');
check('empty assistant', { assistants: 1 }, 'PENDING');
check('empty body', { ...complete, text: '' }, 'PENDING');
check('whitespace body', { ...complete, text: ' ' }, 'PENDING');
check('streaming', { ...complete, stop: true }, 'PENDING');
check('missing final control', { ...complete, copy: false }, 'PENDING');
check('service', { ...complete, service: true }, 'SERVICE_NON_RESPONSE');
check('control timeout', { controlTimeout: true }, 'BROWSER_CONTROL_TIMEOUT');
check('bounded failure', { boundExceeded: true }, 'BOUNDARY_UNAVAILABLE');
check('ambiguous assistant', { ...complete, assistants: 2 }, 'AMBIGUOUS');
check('ambiguous body', { ...complete, bodies: 2 }, 'AMBIGUOUS');
assert.equal(classifyGrokState(complete).text, complete.text);

let operations = 0;
const touch = () => { if (++operations > 5000) throw Error('synthetic CDP deadline budget'); };
const decoration = () => ({ children: [], closest: () => null, getClientRects: () => { touch(); return [{}]; }, parentElement: null, textContent: 'FABRICATED DECORATION' });
const unrelated = Array.from({ length: 10000 }, decoration);
const copy = { getAttribute: () => 'Copy', closest: () => null };
const assistant = { querySelectorAll: selector => { assert.equal(selector, SELECTORS.body); return [{ innerText: 'FABRICATED RECEIPT' }]; } };
let selectors = [];
const root = { querySelectorAll(selector) {
  selectors.push(selector);
  if (selector === '*') return unrelated;
  if (selector === SELECTORS.service) return [];
  if (selector === SELECTORS.buttons) return [copy];
  if (selector === SELECTORS.assistants) return [assistant];
  if (selector === SELECTORS.users) return [{}];
  throw Error('unexpected broad selector');
} };
const oldContext = { module: { exports: {} }, getComputedStyle: () => { touch(); return {}; } };
vm.runInNewContext(fs.readFileSync(require.resolve('./grok_dom_capture_v2.js'), 'utf8'), oldContext);
assert.throws(() => oldContext.module.exports.inspectGrokDomV2(root), /synthetic CDP deadline budget/);
const oldOperations = operations;
operations = 0; selectors = [];
const state = collectGrokState(root, () => { touch(); return true; });
assert.equal(classifyGrokState(state).status, 'ASSISTANT_FINAL');
assert(!selectors.includes('*'));
assert(operations <= 1);
passed += 3;

(async () => {
  check('hung transport', await boundedRead(() => new Promise(() => {}), 10), 'BROWSER_CONTROL_TIMEOUT');
  check('rejected transport', await boundedRead(() => { throw Error('CDP timed out'); }), 'BROWSER_CONTROL_TIMEOUT');
  check('unknown transport error', await boundedRead(() => { throw Error('unavailable boundary'); }), 'BOUNDARY_UNAVAILABLE');
  check('working transport', await boundedRead(() => complete), 'ASSISTANT_FINAL');
  process.stdout.write(JSON.stringify({ passed, failures: 0, unrelatedSyntheticNodes: unrelated.length, oldWalkOperationsBeforeInjectedTimeout: oldOperations, boundedPathVisibilityOperations: operations, selectorCount: selectors.length, modelCalls: 0, limitation: 'Models an operation-budget timeout; does not establish that all observed browser timeouts have this cause. Browser fixture qualification still required before study access.' }) + '\n');
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
