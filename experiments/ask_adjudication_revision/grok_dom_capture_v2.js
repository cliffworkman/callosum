/* Mechanical DOM boundary only. Does not parse or assess scientific content. */
function inspectGrokDomV2(root) {
  function rendered(el) {
    if (!el.getClientRects().length) return false;
    for (let p = el; p; p = p.parentElement) {
      const style = getComputedStyle(p);
      if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse' || style.opacity === '0') return false;
    }
    return true;
  }
  const servicePattern = /rate limit|too many requests|reached.{0,40}limit|limit.{0,40}(reached|reset)|try again later|service unavailable/i;
  const outsideMessages = Array.from(root.querySelectorAll('*')).filter(el =>
    el.children.length === 0 &&
    !el.closest('script, style, template, noscript, [hidden], [aria-hidden="true"]') &&
    rendered(el) &&
    !el.closest('[data-testid="user-message"], [data-testid="assistant-message"], .message-bubble, nav, aside')
  );
  if (outsideMessages.some(el => servicePattern.test(el.textContent || ''))) {
    return { status: 'SERVICE_NON_RESPONSE', text: null };
  }
  const stop = Array.from(root.querySelectorAll('button')).some(el =>
    /^stop(?: generating| response| streaming)?$/i.test((el.getAttribute('aria-label') || el.textContent || '').trim())
  );
  if (stop) return { status: 'PENDING', text: null };
  const assistants = root.querySelectorAll('[data-testid="assistant-message"]');
  if (assistants.length !== 1) return { status: assistants.length ? 'AMBIGUOUS' : 'PENDING', text: null };
  const bodies = assistants[0].querySelectorAll('.response-content-markdown');
  if (bodies.length !== 1) return { status: bodies.length ? 'AMBIGUOUS' : 'PENDING', text: null };
  const text = bodies[0].innerText;
  if (!text || !text.trim()) return { status: 'PENDING', text: null };
  const copy = Array.from(root.querySelectorAll('button')).some(el =>
    /^copy(?: response| message| text)?$/i.test((el.getAttribute('aria-label') || el.textContent || '').trim())
  );
  if (!copy) return { status: 'PENDING', text: null };
  return { status: 'ASSISTANT_FINAL', text };
}

if (typeof module !== 'undefined') module.exports = { inspectGrokDomV2 };
