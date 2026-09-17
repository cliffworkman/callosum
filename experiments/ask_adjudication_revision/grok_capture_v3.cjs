/* Non-production CommonJS mechanical boundary. No interpretation of response content. */
const SELECTORS = Object.freeze({
  service: '[role="alert"], [role="status"]',
  assistants: '[data-testid="assistant-message"]',
  users: '[data-testid="user-message"]',
  body: '.response-content-markdown',
  buttons: 'button[aria-label]',
});

function classifyGrokState(s) {
  const result = status => ({ status, text: null });
  if (s.controlTimeout) return result('BROWSER_CONTROL_TIMEOUT');
  if (s.boundExceeded) return result('BOUNDARY_UNAVAILABLE');
  if (s.service) return result('SERVICE_NON_RESPONSE');
  if (s.stop) return result('PENDING');
  if (s.assistants > 1 || s.bodies > 1) return result('AMBIGUOUS');
  if (!s.assistants) return result(s.users ? 'USER_MESSAGE_ONLY' : 'NO_ASSISTANT_FINAL');
  if (!s.bodies || !s.text || !s.text.trim() || !s.copy) return result('PENDING');
  return { status: 'ASSISTANT_FINAL', text: s.text };
}

// Deliberately no querySelectorAll('*'), page text, scripts, or ancestor-style loop.
// Unknown/unbounded UI stays unresolved. Exceptions never become a missing response.
function collectGrokState(root, visible) {
  const s = { assistants: 0, users: 0, bodies: 0, text: null, service: false, stop: false, copy: false };
  const serviceNodes = root.querySelectorAll(SELECTORS.service);
  const buttons = root.querySelectorAll(SELECTORS.buttons);
  const assistants = root.querySelectorAll(SELECTORS.assistants);
  const users = root.querySelectorAll(SELECTORS.users);
  if (serviceNodes.length > 16 || buttons.length > 128 || assistants.length > 2 || users.length > 2)
    return { ...s, boundExceeded: true };
  s.assistants = assistants.length;
  s.users = users.length;
  for (const el of serviceNodes) {
    if (el.closest('[data-testid="user-message"], [data-testid="assistant-message"], nav, aside, script, style, template, [hidden], [aria-hidden="true"]') || !visible(el)) continue;
    const text = el.innerText || '';
    if (text.length > 2048) return { ...s, boundExceeded: true };
    if (/rate limit|too many requests|reached.{0,40}limit|limit.{0,40}(reached|reset)|try again later|service unavailable/i.test(text)) s.service = true;
  }
  for (const el of buttons) {
    const name = (el.getAttribute('aria-label') || '').trim();
    if (!/^(?:stop(?: generating| response| streaming)?|copy(?: response| message| text)?)$/i.test(name)) continue;
    if (!visible(el)) continue;
    if (/^stop/i.test(name)) s.stop = true;
    if (/^copy/i.test(name)) s.copy = true;
  }
  if (s.assistants === 1) {
    const bodies = assistants[0].querySelectorAll(SELECTORS.body);
    s.bodies = bodies.length;
    if (s.bodies === 1 && !s.stop && !s.service) s.text = bodies[0].innerText;
  }
  return s;
}

async function boundedRead(read, timeoutMs = 5000) {
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(read),
      new Promise(resolve => { timer = setTimeout(() => resolve({ controlTimeout: true }), timeoutMs); }),
    ]);
  } catch (error) {
    if (/timeout|timed out|deadline/i.test(String(error))) return { controlTimeout: true };
    return { boundExceeded: true };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { SELECTORS, classifyGrokState, collectGrokState, boundedRead };
