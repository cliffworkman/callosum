# Security audit — GROBID section-scoping integration (backlog #30 Stage 2)

**Date:** 2026-08-15
**Status:** complete — PASS

## Scope

The whole 12-task GROBID/section-scoping plan's security-relevant surface, reviewed together at the plan's
close (Task 12), covering:

- `integrations/grobid/client.py` — a thin `httpx` client posting a PDF to a user-configured GROBID server
  (`POST /api/processFulltextDocument`), returning the raw TEI-XML response body.
- `integrations/grobid/tei_parse.py` — parses that TEI-XML with stdlib `xml.etree.ElementTree`, including a
  hand-built DOCTYPE/XXE/entity-expansion defense (no `defusedxml` dependency).
- `integrations/grobid/section_classify.py` — pure string classification, reuses the existing
  `pdf_processing/sections.py` taxonomy. No new attack surface.
- `app/backend/grobid_pipeline.py` — orchestrates client → parser → coordinate-overlap mapping →
  `paper_sections`/`chunks.grobid_section_id` writes. Parameterized SQLAlchemy Core throughout (rule #3).
- `app/backend/api/routers/grobid.py` — 7 endpoints: `GET /grobid/status`, `POST /grobid/settings`,
  `POST /grobid/test-connection`, `POST /grobid/papers/{paper_id}/parse` (+ its `GET .../{job_id}` poll),
  `POST /grobid/library/parse` (+ its `GET .../{job_id}` poll).
- `app/backend/app_settings.py::set_grobid_url`/`stored_grobid_url` — a plain, non-secret local preference
  (mirrors `local_base_url` exactly).
- `app/frontend/js/35e_maintenance.jsx` (`GrobidSettings`) + `app/frontend/js/25a_detail_actions.jsx`
  (`GrobidParseRow`) — the Settings URL field/test/bulk-parse UI and the per-paper parse action.
- `alembic/versions/0074_paper_sections.py` — additive schema only (new table + nullable FK column).

## Principles-gate note (rule #9)

This feature produces no new claim/signal/judgment surface of its own — `paper_sections`/
`chunks.grobid_section_id` feed Suggest-Citation's existing candidate-reordering (Task 1-3/10), never a
score or verdict. The one genuinely new inspectability question is provenance-accuracy: does
`candidate_section_family` ever claim a GROBID-derived match that coordinate overlap didn't actually produce?
**Verified NO** by the live smoke test below (`candidate_section_family` returns exactly `(None, "none")` for
every chunk `grobid_section_id` leaves `NULL`, and `(family, "grobid")` only for chunks a real bbox overlap
actually mapped) — the strict-either/or provenance rule Task 10 designed and this audit independently
re-confirmed against real GROBID output, not just Task 10's faked-client unit tests.

## Threat review

### 1. Egress gate — the loopback/non-loopback split (Core invariant #3)

**Structural, not just tested.** `_egress_refused()` (`grobid.py:126-131`) calls the same
`llm.providers.requires_egress()` invariant-#3 primitive every custom AI provider endpoint uses, via a
duck-typed `_GrobidEgressProbe(provider="grobid", base_url=<configured GROBID url>)`. `requires_egress` asks
"is `base_url` non-loopback," so:

- A loopback GROBID URL (`http://127.0.0.1:*`, `http://localhost:*`, `http://[::1]:*`) needs **no consent** —
  correct, since the request never leaves the machine.
- A non-loopback URL is refused with **403** unless `CALLOSUM_ALLOW_DATA_EGRESS`/the Settings egress toggle is
  on — **verified this fires BEFORE the paper-existence check** (`test_parse_paper_non_loopback_url_requires_
  egress_consent`, `tests/test_grobid_endpoints.py:32-47`, posts against paper id `1` in a fresh empty DB and
  still gets 403, not 404 — the ordering the brief specifically asked to confirm holds).
- Both `parse_paper` and `parse_library` call `_egress_refused` before any other work (`grobid.py:158`,
  `grobid.py:229`) — code-inspected directly, not inferred.

**A real duck-typing footnote worth recording** (already caught by Task 9's own review, re-confirmed here):
`requires_egress`/`_wire_of` default an empty/`None` `provider` to `"gemini"` (always-egress). The
`_GrobidEgressProbe` dataclass hard-codes `provider: str = "grobid"` specifically to avoid this footgun — a
falsy provider here would silently egress-gate a loopback GROBID URL too (annoying, fail-safe direction) or,
worse if the default flipped, fail to gate a real remote one. Confirmed by direct read of `_wire_of` in
`app/backend/llm/providers.py` that `"grobid"` is treated as an unrecognized-but-non-empty provider, which
`requires_egress` only inspects for `base_url` loopback-ness, not the provider name itself — so this is correct
as built.

### 2. DOCTYPE/XXE/entity-expansion defense — verified on every code path, not just the happy path

`parse_tei()` (`tei_parse.py:98`) is the **only** public entry point into this module that reaches
`ET.fromstring()`, and it unconditionally calls `_decode_and_reject_doctype(tei_xml)` first
(`tei_parse.py:103`) — there is no second, unguarded call site. Traced every caller:

- `grobid_pipeline.py::parse_paper_structure` — the only production caller, passes GROBID's raw response
  bytes straight to `parse_tei` with no alternate path.
- Tests (`tests/test_grobid_tei_parse.py`) call `parse_tei` directly, exercising the guard, not bypassing it.

The guard itself (`tei_parse.py:53-69`) does three things **in this order**, all against the same already-
decoded `str` (never re-handing ElementTree raw bytes it could re-interpret under a different encoding):
1. Strict UTF-8 decode — rejects any BOM'd UTF-16/UTF-32 payload (their lead bytes are never valid UTF-8).
2. Reject any embedded `\x00` — closes the **bare, no-BOM** UTF-16/UTF-32 bypass a code review caught during
   Task 5 (interleaved NUL bytes survive UTF-8 "decoding" as literal NUL codepoints, and CPython's `pyexpat`
   was empirically confirmed to still parse + expand entities through them).
3. Reject any `<!DOCTYPE` substring (case-insensitive) in the decoded text — the only vector for both XXE and
   billion-laughs entity expansion; rejecting it outright is a complete, auditable defense with no new
   dependency (`defusedxml` was considered and declined as an unneeded second dependency for this narrow use).

**Re-verified independently in this audit**, not taken on the implementer's word: reran both bypass shapes
from `tests/test_grobid_tei_parse.py` (a raw ASCII-substring-check-evading UTF-16 DOCTYPE payload, and the
deeper no-BOM variant) directly against the current code — both raise `GrobidParseError` before `ET.fromstring`
is ever called. `xml.etree.ElementTree`'s own default behavior (blocks *external* entity fetches, no built-in
defense against *internal* entity expansion) is the correctly-identified residual gap this guard exists to
close, and it closes the entire class (no DOCTYPE reaches the parser at all, not just the two demonstrated
bypass shapes) rather than patching the two known variants.

### 3. `/grobid/test-connection` has no egress gate — disclosed, reviewed, judged intentional

Per the brief's own flag: `POST /grobid/test-connection` (`grobid.py:93-108`) sends **zero** library content —
a bare `GET {url}/api/isalive`, no PDF, no request body, no query parameters derived from library data. It is
gated only by network reachability, never by the egress-consent toggle, even against a non-loopback URL.

**Verdict: this is a defensible, correctly-scoped reading of invariant #3, not an oversight.** Invariant #3's
actual concern is "library **text** leaving the machine without consent." A liveness ping carries no text —
functionally identical to a plain uptime check any browser could perform by loading the URL directly. It does
diverge from `/settings/test-key`'s own gated precedent (that endpoint's docstring explicitly draws the
parallel), but that divergence is *correct*, not merely consistent-by-accident: `/settings/test-key` gates
because testing an LLM key requires sending an actual (small) prompt to the provider — real content, even if
trivial — whereas `/grobid/test-connection` sends nothing derived from the user's data at all. The only thing
disclosed to a non-loopback host by this endpoint is the fact that *some* callosum instance exists at the
caller's IP — a much smaller disclosure than even a single character of library text, and arguably no smaller
than what a plain DNS/TCP connection attempt already reveals to that host's network operator regardless of
gating. **No change recommended.**

**Operational guardrail added by the final-review fix wave (2026-08-16), recorded here for discoverability:**
`/grobid/*` must **never** be added to the cloudflared tunnel ingress allowlist that fronts the single-user
remote-access add-on (CLAUDE.md's Security baseline section — today that allowlist forwards only `/papers`,
`/papers/export`, and `/citations/*`). The `/grobid/test-connection` design above is correctly reasoned for the
threat model it was scoped against (a local caller who already trusts the machine), but that reasoning does
NOT extend to Remote access: with the tunnel enabled, an unauthenticated-content, no-egress-gated `GET`-any-host
endpoint would become a blind LAN-scanning primitive for any caller holding the remote-access bearer token — it
would let that caller probe arbitrary internal hosts/ports reachable from the callosum machine and read back
liveness/reachability, something `/papers`, `/papers/export`, and `/citations/*` cannot do. This is a control to
maintain going forward (the allowlist is a manual, out-of-repo cloudflared config, not something this codebase
can enforce structurally), not a code defect in the current PASS verdict.

### 4. Response size caps — a real gap, judged low-severity and accepted rather than silently left unmentioned

**Finding:** neither `client.py::parse_fulltext` nor `tei_parse.py::parse_tei` bounds the size of the TEI-XML
response GROBID returns before buffering it fully into memory (`resp.content` in `client.py:44`) and decoding
it whole (`tei_xml.decode("utf-8")` in `tei_parse.py:60`). A GROBID server that returned an arbitrarily large
response body (misconfigured, compromised, or simply pathological on a huge/adversarial PDF) could exhaust
memory on the callosum process. This is the same class of gap CLAUDE.md's rule #4 names explicitly
("**External APIs**... set httpx timeouts, fail closed... resource exhaustion... is the local-app threat
model").

**Severity assessment — accepted, not fixed in this task:**
- **The threat actor who could exploit this is the user's own, self-run Docker container** (or, in the
  non-loopback case, a remote GROBID server the *user themselves* explicitly typed into Settings and consented
  to send PDFs to via the egress toggle). There is no cross-user boundary here at all — this is not a shared
  service; a single-user local tool being asked to trust a server *it* points at is a fundamentally different
  risk than an unauthenticated public endpoint accepting arbitrary input.
- **A misbehaving/malicious GROBID response is bounded by what the user's own network/Docker setup can
  produce** — this is not attacker-controlled input arriving over the open internet the way OpenAlex/Crossref/
  a scraped PDF is; it is a response from an endpoint the user configured and (for the non-loopback case)
  explicitly consented to send data to.
- `httpx.Client(timeout=60.0)` (the default in `client.py:22`) already bounds how long a hung/slow-drip
  response can tie up the request — a slowloris-style unbounded-duration attack is already closed even though
  unbounded-*size* is not.
- Every other external-API integration in this codebase that accepts a response body of unknown size (Crossref,
  OpenAlex, Retraction Watch/TOP Factor/AJOL mirror downloads) has the same posture — none of them impose an
  explicit byte cap on the inbound response either (confirmed by grep across `integrations/`), so adding one
  here alone would be inconsistent with the codebase's actual existing standard rather than closing a
  GROBID-specific gap.

**Disposition:** flagged here as a genuine, real, unaddressed gap per the audit's job — not fixed in this task,
because (a) it matches this codebase's existing accepted posture for every comparable external-response path,
(b) the threat model is user-self-inflicted, not a remote attacker, and (c) a real GROBID response for even a
very long article tops out in the low hundreds of KB (the committed fixture, `sample_fulltext.tei.xml`,
directly measured via `wc -c` at **183,878 bytes (~180KB) for a full 17-page article**), so the practical
exposure is theoretical rather than observed. **Recorded as a disclosed, accepted risk** — a natural, low-cost
future addition (e.g. an `httpx` streaming read with a hard byte cap, mirroring a size cap if one is ever added
to the metadata-mirror downloads) rather than a blocking finding.

### 5. URL validation on the configured GROBID host

`GrobidSettingsRequest.url` (`grobid.py:66`) accepts any string up to 500 chars with **no scheme/format
validation** — mirrors `set_local_base_url`'s identical precedent in `app_settings.py` exactly (also no
validation). This is intentional-by-precedent, not a new gap: the value is set by the same single local user
who runs the machine, through the Settings UI they themselves control; there is no cross-user trust boundary
for a URL validator to protect. `httpx` itself will fail closed on genuinely malformed input (unsupported
scheme, unparseable host) with an `httpx.HTTPError` that `GrobidError` wraps — never an unhandled crash
(verified: `client.py:36-38` catches `httpx.HTTPError` broadly). **No change recommended** — matches the
existing `local_base_url` standard this codebase already ships.

### 6. SQL injection / input validation at the boundary (rule #3/#4)

- `grobid_pipeline.py` uses only parameterized SQLAlchemy Core (`.insert().values(...)`, `.update().where(...)`,
  `select(...)`) — no string-built SQL anywhere in the new module. Confirmed by direct read.
- GROBID's TEI-XML response is untrusted external-API output (rule #4) and is validated at the boundary: the
  DOCTYPE/NUL/UTF-8 guard (item 2 above) before any parsing, and `_parse_coords` (`tei_parse.py:80-95`) treats
  malformed `@coords` attributes as **skip, not crash** (`try/except ValueError: continue`) — a hostile or
  buggy GROBID response with garbage coordinate strings degrades to fewer mapped sections, never an exception
  propagating past the pipeline's own `GrobidParseError` boundary.
- `_bboxes_overlap`/`_chunk_overlaps_span` (`grobid_pipeline.py:20-37`) only ever read numeric fields with
  `.get(..., default)` + `float()` coercion — a malformed `bbox_json` chunk row degrades to `0`, never raises.

### 7. Resource caps on the parse operations themselves

- Per-paper parse: bounded to exactly one PDF, one GROBID call, one paper's chunks — no unbounded loop.
- Bulk (library-wide) parse: `ThreadPoolExecutor(max_workers=GROBID_PARSE_WORKERS=4)` — the same inc-418
  bounded-concurrency precedent `library_enrich.py`/`citation_counts.py` already use, not dozens of concurrent
  requests hammering the user's own GROBID container. One paper's failure is caught and skipped
  (`grobid.py:288`), never aborting the whole batch or leaking a stack trace to the job's `detail` field beyond
  `f"{type(exc).__name__}: {exc}"` (no raw traceback surfaced to the client).

### 8. Data exposure / secret handling

No secret is involved anywhere in this feature — `grobid_url` is explicitly documented as non-secret
(`app_settings.py:300-302`, mirrors `local_base_url`) and is returned in full by `GET /grobid/status` (correct:
there is nothing to protect, unlike a BYOK API key). No credential, token, or key is read, stored, or
transmitted by any GROBID code path.

## Negative-path checks (executed, not assumed)

From `tests/test_grobid_endpoints.py` (5 passed) + `tests/test_grobid_client.py`/`test_grobid_tei_parse.py`/
`test_grobid_pipeline.py` (all passing, see increment notes for the full count):
- Unconfigured GROBID URL → `POST /grobid/papers/{id}/parse` → **409**, no network call attempted.
- Non-loopback URL + egress unset → **403**, confirmed to win over a 404 for a nonexistent paper id.
- Loopback URL → not blocked by the egress gate (verified via a patched `parse_paper_structure`, isolating the
  gate check from GROBID reachability).
- Malformed/DOCTYPE-bearing/non-UTF-8/NUL-embedded TEI payloads → `GrobidParseError`, never `ET.fromstring`
  reached (re-verified live in this audit, see item 2).
- Non-200 GROBID HTTP response → `GrobidError` with the response body truncated to 500 chars in the message
  (`client.py:43`) — bounded, no unbounded error-body leak into logs/UI.

**Additionally, live-verified end-to-end in this audit** (not simulated): a real callosum backend against a
fresh migrated temp DB, a real 17-page open-access PDF (PLOS ONE, CC BY 4.0, the same source as the Task 5
fixture) imported via `POST /library/scan`, GROBID configured to the real, currently-running local
`http://localhost:8070` container, and `POST /grobid/papers/1/parse` run to completion. See
`.claude/docs/increment-notes/INCREMENT-479-NOTES.md`'s Manual verification script for the full transcript.
Result: 28 real sections extracted with correct verbatim titles, 48 of 229 real PyMuPDF chunks correctly
coordinate-mapped (spot-checked several — a chunk about "cognitively unimpaired participants" mapped to
"Methods," a chunk about "higher RSFC" mapped to "Results," matching their real content), the pre-existing
`chunks.section` heuristic column independently populated and **untouched** by the GROBID pipeline (confirmed
by direct DB query), and `candidate_section_family` correctly reporting `"grobid"` provenance only for mapped
chunks and `"none"`/`"heuristic"` honestly for the rest — the exact strict-either/or contract Task 10 designed,
now confirmed against real GROBID output rather than only a faked test client. **This closes Task 8's disclosed
deferred verification gap with a genuine, positive result — no bug found in Tasks 5-10's logic.**

## Result

One real, disclosed, low-severity gap (response size caps — item 4) is accepted rather than fixed, for reasons
recorded above; it matches this codebase's existing standard for every comparable external-response path and
carries a self-inflicted (not cross-user) threat model. `/grobid/test-connection`'s no-egress-gate design
(item 3) is reviewed and judged a correct, narrower-than-`/settings/test-key` reading of invariant #3's actual
target, not an inconsistency. Every other reviewed surface (egress-gate ordering, XXE/DOCTYPE defense
completeness, SQL parameterization, malformed-input handling, resource bounding, secret handling) is verified
correct by direct code inspection plus a real, live end-to-end GROBID run against real data — not asserted on
the implementers' word alone.

**Security Audit: PASS**
(one disclosed, accepted low-severity risk: no explicit response-size cap on the GROBID TEI-XML response — see
item 4 for the full reasoning; recommended as a future low-cost addition, not a blocker)
