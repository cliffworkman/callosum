# Browser capture architecture — research and design (issue #61)

**Date:** 2026-09-15
**Status:** research/design increment. No product code ships here.
**Issue:** #61 (browser extension). Related: #25 (identity resolution), #62/#63/#64/#65 (Tauri
boundary audits), #70 (packaged-vs-dev runtime boundary), #72 (attachment lifecycle).
**Branch:** `browser-capture-research`

---

## 0. Governing principle

> **The installed desktop application is the canonical Callosum runtime. Development servers are
> test harnesses for that runtime, not alternate product targets. Browser integration must
> therefore be designed against packaged Tauri behavior first. Any development-specific
> accommodation must remain outside release behavior and should emulate the packaged contract
> wherever practical.**

This is the evaluation lens for transport, discovery, security, tests, and sequencing throughout
this document — not merely a closing smoke check. Issue **#70** is the named precedent for the
failure mode it guards against: a packaged feature telling the user to run `npm install` at the
project root, i.e. an installed feature depending on repository-root development state.

**Canonical acceptance path.** Dev-server demonstrations are diagnostic evidence only:

```
installed browser extension
  -> installed Callosum desktop application
  -> canonical packaged backend instance
  -> canonical import / identity / attachment / indexing path
  -> visible result in installed Callosum
```

Three correctness levels are tracked separately for every feature in this track:
**hermetic/unit**, **browser-extension**, and **packaged-desktop**. Only the third closes a phase.

### Target capability

> If a researcher is already looking at a scholarly paper or record in their browser, they should
> normally be able to click once and have Callosum receive the correct canonical scholarly record
> plus any full text the user has already legitimately accessed in that browser context.

Not literal Zotero Connector parity.

---

## 1. Current-state Callosum architecture relevant to browser capture

All references are `file:line` in this repo at `1aa3973a`.

### 1.1 Ingestion entry points

There is **no generic "add this paper" endpoint**. Items enter the Library through feature-owned
paths:

| Path | Route | Service |
|---|---|---|
| Folder scan / watched folders | `POST /library/scan`, `/library/watched/rescan` | `pdf_processing/library_scan.py:55` |
| Citation files (RIS/BibTeX/CSL-JSON) | `POST /library/import` | `metadata/citation_import.py:367` |
| Zotero native library | `POST /library/zotero/import` | `importers/zotero.py` |
| Portable bundle | `POST /library/bundle/import` | `metadata/library_bundle.py` |
| **Discovery save** | `POST /discovery/save` | `discovery/search.py:59 save_item` |
| Agent reference (DOI only) | `POST /agent/references` | `api/routers/agent.py:113` |
| Gaps / citing / my-publications | `POST /gaps/add`, `/my-publications/citing/import` | `clustering/my_publications.py:438` |
| OA acquisition (attach to existing) | `POST /papers/{id}/acquire-oa` | `acquisition/fetch.py` |

**`POST /discovery/save` is the closest existing analogue to browser capture.** Its `SaveRequest`
(`api/routers/discovery.py:59`) already accepts title, doi, pmid, abstract, authors, journal, year,
url; it dedupes via `find_existing_paper_by_identity` and fires a background
`enrich_paper_metadata_multi`. This is the reuse seam, not a template to copy into a parallel path.

### 1.2 Metadata resolution

Three entry points, not one (`metadata/enrichment.py`):

- `enrich_paper_metadata_from_crossref:84` — **wholesale overwrite** from Crossref by DOI, guarded
  by `_can_update_from_crossref:283`.
- `enrich_paper_metadata_from_identifier:143` — wholesale overwrite via OpenAlex from PMID/arXiv.
- `enrich_paper_metadata_multi:409` — **gap-fill only**, never overwrites a populated key
  (`gap_merge:354`). Cascade: Crossref → OpenAlex → EuropePMC → PubMed
  (`metadata/enrich_sources.py:235`).

**The gap-fill posture is the correct model for capture**: the browser is a noisy source and must
not clobber better data.

Identifier support: DOI is a first-class column; **PMID and arXiv live only in `csl_json`**;
OpenAlex/Semantic Scholar/Zotero ids have UNIQUE columns; ISBN/ISSN are stored but never used for
resolution; **PMCID is unsupported**. `paper_external_identifiers`
(`persistence/schema.py:78`) exists but is effectively dormant — written only by the routeless
Mendeley importer and tests. It is the natural home for captured identifiers.

### 1.3 Attachments, validation, indexing

- `attachments` (`persistence/schema.py:90`): `storage_mode ∈ {managed, linked, url}`,
  `availability ∈ {available, missing, unresolved}`, `checksum`, `role`, OA labels.
- **The only streamed-bytes endpoint in the whole API** is
  `api/routers/transparency.py:245` — `Content-Length` precheck → 413, running byte cap → 413,
  `%PDF-` magic → 422, `fitz.open` with `page_count >= 1` → 422, gated by
  `require_local_file_access`. **This is the template for any capture upload.**
- `acquisition/fetch.py:47 download_oa_pdf` is the equivalent for fetched bytes, and takes an
  `OaLocation`, **never a bare URL** — a structural guarantee worth preserving in capture.
- `pdf_processing/ingest.py:142 attach_pdf_to_paper` is the shared core and **validates nothing**.
- FTS5 is transactional and self-cleaning (`alembic/versions/0026_chunks_fts.py`). Vector
  embedding is **per-caller and inconsistently applied** — the OA and registration paths never call
  `embed_chunks`.

### 1.4 Security posture

- `api/app.py:331-337` — CORS `allow_origin_regex=^https?://(localhost|127\.0\.0\.1)(:\d+)?$`,
  `allow_credentials=False`, **`allow_methods=["GET"]`**.
- `api/local_only.py:35-42` — GET-only CORS *is* the CSRF defense; reinforced on 2 of ~90 routers by
  a non-safelisted header. **Now pinned by `tests/test_cors_boundary.py` (added in this
  increment, 17 tests passing).**
- `api/access_control.py` — Remote Access bearer gate, **default-OFF**, whole-API when on. Its
  docstring already **formally rejects loopback origin as a trust signal**, because cloudflared
  forwards to localhost.
- **No `TrustedHostMiddleware`.** Inbound Host validation exists only inside `local_only._require_local`.
  DNS-rebinding gap on every other router.
- No global request-size limit; no rate limiting at all on the default loopback path.

---

## 2. Current Zotero Connector / translator architecture

### 2.1 The standalone contract (this is the decisive finding)

`zotero/translate`'s README documents that a consumer outside Zotero must implement exactly three
interfaces — `Zotero.Translators`, `Zotero.HTTP`, `Zotero.Translate.ItemSaver` — and initialise
`Zotero.Schema` and `Zotero.Date`. A working reference lives in `translate/example/`.

The driver is small:

```js
const translate = new Zotero.Translate.Web();
translate.setDocument(doc);
const translators = await translate.getTranslators();   // detection
translate.setHandler("select", (t, items, cb) => cb(chosen));  // multiple-item pages
translate.setHandler("error", ...);
const items = await translate.translate();              // → item JSON
```

`Zotero.Translate.ItemSaver` is a bare stub in `translate/src/translation/translate.js:32`; the
example implementation is **four lines** that simply collect `jsonItems`. **Translators terminate
cleanly at the ItemSaver boundary and require no Zotero persistence.**

### 2.2 Detection, multiple items, attachments

- **Detection** is two-stage: a `target` regex on the translator's JSON header filters candidates
  by URL before any code runs; then `detectWeb(doc, url)` runs and returns an item type,
  `"multiple"`, or falsy.
- **Multiple-item pages**: the translator calls `Zotero.selectItems(items)`; `translate.js:481`
  routes this to the `"select"` handler as a `{key: title}` map, and the consumer calls back with a
  subset. This maps exactly onto "never silently pick one candidate".
- **Attachments**: items carry `attachments[] = {url, title, mimeType, snapshot}` — **URL
  references, not bytes.** The consumer decides whether to fetch them. This distinction is
  load-bearing for §8.
- `translatorType` is a bitfield (1 import, 2 export, 4 web, 8 search); `browserSupport` is a
  letter set; `priority` orders candidates.

### 2.3 Runtime assumptions that are genuinely Zotero-specific

| Assumption | Reality for a consumer |
|---|---|
| `Zotero.Repo` fetches translator metadata/code from zotero.org | Must be replaced by a local bundle. The README says so explicitly: *"Please bundle translators and Zotero schema with the translation architecture. Do not load them from a remote server."* |
| `SandboxManager.eval()` uses raw `eval` | Replaceable; the README lists `SandboxManager` as a customisation point. This is the MV3 crux (§10). |
| `Zotero.HTTP` is XHR-shaped, with a cookie sandbox | Must be supplied; determines whether requests carry the user's session (§7). |
| Some translators' `detectWeb` returns `"server"` | Signals "defer to translation-server". A standalone consumer must decide; simplest correct answer is to treat it as unsupported. |
| `Zotero.Schema` / `Zotero.Date` init from schema + dateFormats | Data files, bundled. |
| ~30-file load order incl. `zotero/utilities` and RDF | Real vendoring surface, not a single dependency. |

### 2.4 The headless alternative, and why it is rejected

`zotero/translation-server` (Node, actively maintained) bundles the same shims and would avoid the
MV3 problem entirely. It is rejected on **product**, not technical, grounds:

- Its `/web` endpoint **fetches the URL itself** (`src/webEndpoint.js` → `session.handleURL()`),
  making Callosum's backend the requester rather than the user's browser.
- Its README documents that it ships **a spoofed Chrome `User-Agent` "to maximize compatibility"**.

Callosum's OA lane deliberately does the opposite — `acquisition/fetch.py:216-226` sends an
honest identifying UA with the comment *"identifying politely, not paywall circumvention"*.
Adopting translation-server would import exactly the posture that `APPROACH-AVOIDANCE.md` Part II
names as a standalone hard boundary, and it is the mirror image of the 403-on-automated-fetch
problem that motivated #61 in the first place.

---

## 3. Feasibility assessment of translator reuse

Answering the eight questions posed.

**1. Can Callosum run the corpus without embedding Zotero?**
**Yes, for the runtime.** Evidenced by an upstream-maintained standalone example and by
translation-server, which is that same runtime in a non-browser host. Not yet proven *in MV3* —
see §15 O1.

**2. What runtime interfaces/shims are required?**
`Zotero.Translators` (over a local bundle), `Zotero.HTTP`, `Zotero.Translate.ItemSaver`, plus a
`Zotero.Repo` replacement and — for MV3 — a `SandboxManager`. Schema and dateFormats are bundled
data. The ItemSaver is trivial; `Zotero.HTTP` and the bundle loader are the real work.

**3. Which assumptions are genuinely Zotero-specific?** See §2.3. The load-bearing ones are the
remote repo, the `eval` sandbox, and the cookie-sandboxed HTTP.

**4. Can translator output map cleanly into a Callosum DTO?**
Yes. Translator output is CSL-adjacent item JSON; Callosum already stores `csl_json` and already
projects CSL into columns (`metadata/citation_import.py:343 csl_record_to_paper_fields`). The
adapter is a field mapping plus attachment-candidate extraction. See §6.

**5. Can accessible attachments reach Callosum without granting the backend reusable browser
credentials?**
Yes, and this is the architecturally important answer. The extension fetches attachment bytes **in
the browser context, on the user's explicit action**, and transfers *bytes*. Callosum never
receives a cookie, a session, or a URL-to-fetch-later. This is the difference between an import aid
and a credentialed downloader, and it must be structural: the capture API accepts bytes or nothing.

**6. Licensing/distribution obligations?** See §11 — and the answer is more interesting than
expected.

**7. Should a thin generic extractor ship first?** **Yes.** See §4/§5.

**8. What would make translator reuse a bad choice?** See §4 Strategy C risks and §15.

---

## 4. Strategy comparison

### Strategy A — Callosum-specific publisher/database extractors
**Rejected.** Recreates, by hand, 748 files that a community already maintains against sites that
change without notice. Maintenance burden scales with coverage and never amortises. No path to
long-term viability for a single-maintainer project.

### Strategy B — Generic scholarly metadata only
DOI detection; Highwire `citation_*` meta tags; JSON-LD / schema.org; embedded metadata; common
identifiers; direct-PDF detection; recovery through Callosum's existing resolution.

**Stronger than it sounds**, for a specific structural reason: publishers emit Highwire
`citation_*` tags *in order to be indexed by Google Scholar*, so the incentive to keep them present
and correct is external to Zotero and unusually durable. Combined with Callosum's existing
Crossref → OpenAlex → EuropePMC → PubMed cascade, the extension only needs to produce a **good
identifier**, not a complete record.

**Where it predictably fails:** search and result pages; database list views (PubMed, Google
Scholar); aggregators and discovery layers; library catalogues; sites with no embedded metadata;
pages where the DOI on screen is a *reference*, not the current work. These are precisely the cases
Strategy C covers.

**Verdict: the right P0.** Small, hermetically testable, no eval, no broad permissions, and it
exercises every seam (DTO, transport, identity, attachment, result states) that C will later reuse.

### Strategy C — Zotero translator runtime and corpus
Technically feasible (§3). Costs and risks:

- **Runtime vendoring**: ~30 files across four upstream repos, two of which report no license
  metadata.
- **Update treadmill**: translators change constantly (`lastUpdated` fields span 2023–2026). Zotero
  solves this with a live repo; the README forbids that for consumers. So Callosum must re-vendor
  on a cadence and re-verify — a standing maintenance commitment, not a one-off.
- **Permission surface**: Zotero's MV3 connector needs `host_permissions: http://*/*, https://*/*`
  plus `cookies`, `webRequest`, `declarativeNetRequest`, `webNavigation`. Justifiable when
  translators genuinely need cross-origin session-bearing fetches, but it is a real posture change
  for a local-first, privacy-forward product and should be requested per-phase, with reasons.
- **Licensing**: not the clean "it's all AGPL" story it appears to be (§11).
- **Inherited compatibility**: high. Where a translator works in Zotero it will generally work
  here, because the corpus, not our code, encodes the site knowledge.

**Verdict: adopt, but behind a proven seam and with a curated subset** (§11), not blanket bundling.

### Recommendation

**B first, C behind the same DTO and transport, A never.** The DTO boundary (§6) means C is an
additional *producer* of `CaptureEnvelope`, not a re-architecture. If C proves unworkable in MV3 or
licensing review blocks corpus bundling, B still stands on its own and nothing is stranded.

---

## 5. Recommended architecture

```
browser context
  -> observation / translation        (generic extractor now; translators later)
  -> CaptureEnvelope (Callosum-owned)
  -> connector discovery + capture API
  -> canonical identity resolution
  -> dedupe / metadata reconciliation
  -> attachment handling
  -> indexing
```

The extension **observes, translates, transports, and shows status**. Callosum remains
authoritative for canonical identity, dedupe, metadata conflict, attachment ownership, OA
acquisition, indexing, Library semantics, provenance, and later relationships. **No second
reference-manager data model exists in the extension**; it holds a DTO in flight and nothing at rest
beyond its pairing credential and last-known connector state.

---

## 6. The capture DTO — `CaptureEnvelope` v1

Callosum-owned and versioned. Zotero item JSON is *adapted into* it; it is never Zotero's schema.

```jsonc
{
  "envelope_version": 1,
  "capture": {
    "source_url": "https://…",            // the tab URL, always present
    "captured_at": "2026-09-15T10:04:31Z",
    "producer": {                          // how this envelope was made
      "kind": "generic" | "zotero-translator" | "direct-pdf",
      "id": "highwire-meta" | "<translatorID>" | null,
      "label": "Embedded metadata" | "PubMed",
      "version": "…"                      // extractor or vendored-corpus revision
    },
    "user_action": "toolbar-click"        // never absent; no background capture
  },
  "candidates": [                          // >1 ⇒ ambiguous; Callosum must not auto-pick
    {
      "item_type": "journalArticle",
      "title": "…",
      "creators": [{"family": "…", "given": "…", "role": "author"}],
      "container_title": "…",
      "publisher": "…",
      "issued": {"year": 2024, "month": 3, "day": null, "raw": "2024-03"},
      "volume": "…", "issue": "…", "pages": "…",
      "language": "en",
      "abstract": "…",
      "identifiers": {                     // normalised; absent ≠ empty string
        "doi": "10.1234/abc",
        "pmid": "12345678",
        "pmcid": "PMC123456",
        "arxiv": "2401.01234",
        "isbn": "…", "issn": "…"
      },
      "field_provenance": {                // per-field, so reconciliation can be honest
        "title": "citation_title",
        "doi": "json-ld"
      },
      "attachments": [
        {
          "role": "article-fulltext" | "supplement" | "preprint",
          "mime_type": "application/pdf",
          "origin": "browser-bytes" | "url-reference",
          "url": "https://…",             // present for both; NOT permission to fetch
          "byte_ref": "<transfer handle>", // present only when origin == browser-bytes
          "declared_size": 1234567,
          "title": "Full text PDF"
        }
      ]
    }
  ]
}
```

Design notes:

- **`origin` is the safety-critical field.** `url-reference` is metadata, not an attachment.
  Callosum may pass such a URL to its *own ordinary* OA machinery, which will independently decide
  whether it is legitimately fetchable — but it is never treated as captured full text. A URL is
  never equivalent to an accessible PDF.
- **`candidates` is a list at the top level**, so ambiguity is representable by construction rather
  than signalled by a side channel.
- **`field_provenance`** lets Callosum answer "how was this record obtained" at field granularity,
  which `imported_source` alone cannot.
- **Front-end agnostic.** Clipboard capture, share-sheet, highlighted-reference capture, and
  camera/OCR (issue #25) can all produce a `CaptureEnvelope` with a different `producer.kind` and
  converge on the same resolution path.

---

## 7. Extension ↔ local-app security boundary

### 7.1 Threat model

| Threat | Mitigation |
|---|---|
| Hostile webpage JS reaching the capture API | Native messaging has **no** network surface. If the HTTP capture API is used for bytes, it requires a pairing token the page cannot obtain, plus a non-safelisted header and Host validation. |
| DNS rebinding | Host-header allowlist on the capture router — closing the gap that exists today outside `local_only`. |
| CSRF | Token + non-safelisted header + preserved GET-only CORS (now pinned by tests). |
| Binding to the wrong local process | Discovery returns an **instance role**; only the canonical UI role serves capture (§7.3). |
| Extension compromise | Capture is bounded: it can create/update Library records and attach PDFs. It cannot read arbitrary files, enumerate folders, or reach `/library/scan`. Token is per-install and revocable from Settings. |
| Arbitrary local-file submission | The capture API accepts **bytes**, never a filesystem path. |
| Oversized / malformed payloads | `Content-Length` precheck, running byte cap, `%PDF-` magic, `fitz` open — the `transparency.py:245` pattern. |
| Replay | Per-capture nonce; idempotency keyed on content checksum + source URL. |
| Rate abuse | A limiter on the capture router active **even when Remote Access is off** (today there is none on the loopback path). |

### 7.2 Why not the existing Remote Access machinery

Mechanically reusing it would be wrong, as #61 suspected. Enabling Remote Access to authenticate
the extension would **simultaneously expose the whole API through the cloudflared tunnel**; it is a
single global static token with a **global-bucket** limiter and no per-client identity. Its threat
model is "this request may have come from the internet". The extension's is "this request came from
a specific local program the user paired". Different problems; a shared token conflates them.

### 7.3 Discovery is a product feature

The shipped extension **never probes ports.** This is not stylistic: the packaged app can run a
**Word HTTPS companion on fixed port 8443 launched with `CALLOSUM_DISABLE_REMOTE_ACCESS=1`**
(`src-tauri/src/backend.rs:318,344`) — i.e. the one instance with the auth gate force-disabled. Port
probing can find it. That disqualifies probing on security grounds, independently of taste.

**Recommended: a native-messaging connector host owned by the desktop shell.**

- The extension calls `connectNative("org.callosum.connector")`. The browser launches the host from
  the manifest path the **installer** registered (Windows: an `HKCU\Software\Google\Chrome\
  NativeMessagingHosts\…` value, matching the existing NSIS `currentUser` install and the
  `installerHooks` already configured; macOS/Linux: a JSON file in a well-known directory).
- **Fails closed by construction**: not installed → no host → a clean "Callosum is not installed"
  state, with no network surface at all for a webpage to reach.
- The host **owns resolution**: it reads the canonical backend location from the state Tauri
  already maintains and decides which instance is canonical. The extension never sees a port and
  **cannot** be bound to the Word-HTTPS or tunnel-target children.
- It reports app state — *running* / *starting* (the ≤120s cold window) / *closed* — so result
  states are honest rather than inferred from a connection failure.
- **Release-aware identity is enforced by the platform**: `allowed_origins` is an explicit
  extension-ID list and **cannot contain wildcards**. The production installer writes production
  IDs; a dev build writes a dev manifest with the dev ID. A blanket allowance for arbitrary
  unpacked extensions is not expressible.
- **Auth is separate from discovery**: discovery yields location + role; the per-install pairing
  token for the capture API is issued over the native channel.
- **Bytes go over loopback HTTP, not the native channel.** Native messaging caps host→extension at
  **1 MB** and extension→host at **64 MiB**, under Callosum's 80 MiB `MAX_OA_PDF_BYTES`. So the
  native channel carries discovery/pairing/control; PDF bytes go to the capture API with the issued
  token. A `/capture/hello` role confirmation survives as a *post-discovery* check, not a search.

**Documented alternative — fixed loopback rendezvous port owned by Tauri.** Simpler, browser-
agnostic, no installer work. But it is still a port that can collide; it **reintroduces** the
hostile-webpage and DNS-rebinding surface native messaging removes; and it needs its own Host and
origin defenses. Scored against the requirements:

| Requirement | Native messaging | Rendezvous port |
|---|---|---|
| Works in a normal packaged install | ✅ (installer registers) | ✅ |
| Positively identifies canonical UI instance | ✅ host decides | ⚠️ needs its own role protocol |
| Cannot bind to sibling children | ✅ structurally | ⚠️ by convention |
| No reliance on port secrecy | ✅ no port | ✅ |
| Discovery separate from capture auth | ✅ | ✅ |
| Fails closed | ✅ absent host | ⚠️ absent listener is ambiguous |
| Hostile-webpage surface | ✅ none | ❌ reintroduced |
| Cross-browser cost | ❌ per-browser/per-OS manifests | ✅ uniform |
| Installer work | ❌ required | ✅ none |

Native messaging wins on every security axis and loses on packaging cost. Given the governing
principle, packaging cost is the right cost to pay — **conditional on O2 (§15)**.

### 7.4 Permissions

Phase 1: `activeTab` + the connector host only. `activeTab` grants host access to the current tab
**on explicit user gesture**, which is exactly the product boundary. Broad `host_permissions` are
acceptable from Phase 2 where translators genuinely require cross-origin session-bearing fetches —
requested then, with reasons, not pre-emptively.

### 7.5 Dev adapts to the product contract

`tools/run_dev.py` gains a **dev-only** mode registering a dev manifest and running the same
connector host against the dev backend, so a checkout *satisfies* the production contract rather
than being a second acceptance target. Dev and packaged share discovery, pairing, capture API, role
identification, auth, DTO, and result semantics. **One architecture, not two.**

**Anti-leak rule.** No source-tree path, fixed dev port, npm/project-root dependency, manually
started server, unpacked-extension ID, developer certificate, checkout-only environment variable,
or `run_dev.py`-only behavior may appear in any user-facing path. An installed user must never need
to know these exist. (This is #70's lesson generalised.)

---

## 8. Attachment handling semantics

| Situation | Behaviour |
|---|---|
| Browser already displays a PDF | Capture bytes from that context; validate; attach. |
| Article page exposes an accessible PDF URL | Fetch **in the browser context** on the user's action; transfer bytes. If the fetch fails or is not entitled, report "no PDF captured" — never retry from the backend with different credentials. |
| Translator discovers an attachment URL | Same as above. A translator-supplied URL is a *candidate*, not an entitlement. |
| Metadata-only article page | Metadata-only import; optionally offer the Wanted list (inc 76). |
| Callosum has metadata but no PDF | Attach through the existing path; this is #61's motivating case. Result: "Already in Callosum — PDF added". |
| Callosum already has the same PDF | Checksum match → no-op; report "already present". Reuse `library_scan.py`'s `existing_by_checksum` logic rather than inventing a second byte-identity rule. |
| Callosum has a *different* attachment for the same work | **Never overwrite.** Add as an additional attachment with an explicit role, or route to review. Attachment lifecycle belongs to #72. |

**Two hazards that must be fixed, not worked around:**

- `ingest.py:142 attach_pdf_to_paper` defaults `role="primary"` and validates nothing, so a second
  attach silently produces two rows claiming primary. Capture must validate like the OA lane and
  must not blindly claim primary.
- Annotations with `attachment_id IS NULL` render over **any** PDF the paper owns
  (`annotations_repo.py:61-98`). Attaching captured bytes to an existing record can therefore
  display unrelated highlights over the new file. This lands squarely on the "Already in Callosum —
  PDF added" flow and must be resolved before that flow ships.

---

## 9. Identity and deduplication

### 9.1 Current state

Two unrelated mechanisms that do not talk to each other:

| | `find_existing_paper_by_identity` (`repository.py:161`) | `find_duplicate_groups` (`clustering/duplicate_detection.py:39`) |
|---|---|---|
| When | Inline, on every import | Explicit user-triggered scan |
| Matching | Exact only | Exact + fuzzy (embeddings) |
| Outcome | **Silently auto-picks the first hit** | Flags groups; never auto-merges |
| Ambiguity | None — no candidates, no confidence | Reason + confidence |

**Issue #25's core requirement — "expose uncertainty / candidate matches rather than silently
choosing" — exists on no write path today.** That is the missing shared primitive, and browser
capture is the front end that makes its absence visible: a page with a title but no DOI is exactly
the ambiguous case.

### 9.2 Defects a capture path would inherit (all verified)

1. `find_existing_paper_by_identity` **does not filter `deleted_at`** — capture would dedupe onto a
   trashed paper. **Blocking; fix first.**
2. `_normalize_doi` is `.strip().lower()` only — **no `https://doi.org/` prefix stripping**; callers
   strip ad hoc (`routers/agent.py:115`). A browser DOI is almost always prefixed.
   **Blocking; fix first.**
3. Its `title_year_author` arm is raw SQL equality on the stored title — case-, punctuation-, and
   whitespace-sensitive. Much weaker than the scan's `normalize_text(strip_punctuation(...))`.
4. No DOI-add path calls `embed_papers`, so captured papers are invisible to semantic search.
5. `imported_source` is load-bearing: a `browser-capture` value is protected from Crossref clobber
   by `_can_update_from_crossref:283`, but `enrich_paper_metadata_multi` would **downgrade it to
   `crossref`** (`enrichment.py:464-470`). Decide deliberately.
6. `papers.doi` is deliberately **not unique** (migration `0040`), so same-DOI duplicates can exist
   and `.limit(1)` picks arbitrarily among them.

### 9.3 Target flow

```
CaptureEnvelope.candidates
  -> normalise identifiers (DOI prefix-stripped, PMID/arXiv extracted)
  -> resolve_candidate_identity()        ← the #25 primitive
       returns: MATCH(paper_id, reason, confidence)
              | NO_MATCH
              | AMBIGUOUS([candidates])   ← never auto-picked
  -> MATCH      → gap-fill reconcile, attach if bytes present
     NO_MATCH   → create via save_item, background enrich, embed
     AMBIGUOUS  → explicit Callosum review state; extension says "needs review"
```

**Principle: different capture front ends produce candidate scholarly identity; Callosum resolves
canonical identity once.** No browser-specific dedupe rules. The primitive belongs in
`persistence/` or `metadata/`, is shared with #25's other front ends, and returns candidates with
reasons rather than a silent winner.

---

## 10. Chromium / Firefox / Tauri and platform implications

### 10.1 MV3 and dynamic code

Translator execution needs `eval`. MV3's `extension_pages` CSP forbids it, and the service worker
cannot create iframes. **Zotero's own MV3 manifest solves this** with
`"sandbox": {"pages": ["offscreen/offscreenSandbox.html"]}` plus the `offscreen` permission —
a sandboxed page hosted inside an offscreen document, where the relaxed sandbox CSP still permits
`unsafe-eval`. That is the proven Chromium path, and the one to follow.

**Firefox does not have this escape hatch.** Firefox MV3 does not support the `sandbox` manifest
key, and permits only `'self'` and `'wasm-unsafe-eval'` for `script-src`. The Chromium approach
does not port. Firefox translator execution is therefore an **open question** (§15 O3), not a
scheduling detail — which is why Firefox sits in Phase 4 and why Strategy B matters: generic
extraction needs no `eval` and works on both engines today.

### 10.2 Packaged Tauri is the target

Verified in `app/desktop-shell/src-tauri/src/`:

1. **Dynamic port.** `pick_free_port()`, remembered in `<app_data_dir>/last-port.txt`
   (`backend.rs:132`), with a fresh random port on retry attempts 1–2 (`MAX_SPAWN_ATTEMPTS = 3`,
   `backend.rs:182`). Dev uses fixed 8888/8080. **An extension built against dev ports passes every
   dev test and fails on install.**
2. **Three uvicorn children of the same `app:app` can run**, none present in a dev checkout: the UI
   backend; the Word HTTPS companion on **fixed 8443 with the auth gate force-disabled**; and the
   tunnel target (`CALLOSUM_TUNNEL_TARGET=1`, `quick_tunnel.rs:215`). See §7.3.
3. **Cold start up to 120s** (`HEALTH_TIMEOUT`, `backend.rs:19`) — uvicorn does not bind until
   `app.py`'s eager ML imports finish. *Closed* and *starting* are distinct user-visible states.
4. **No way to launch Callosum when closed** — no deep links, no custom scheme, no file
   associations; `single-instance` receives argv and **discards it** (`lib.rs:290-297`). P0 keeps an
   honest "Open Callosum and try again"; the `_argv` hook is the clean future insertion point.
5. **Paths differ**: port file in Tauri's `app_data_dir`; secrets in keychain or
   `~/.callosum/app-settings.json`.
6. **Per-OS packaging**: NSIS `currentUser` (Windows), `.app` with `NSAppTransportSecurity` loopback
   exceptions (macOS), `.deb` (Linux). Native-messaging manifests are per-browser *and* per-OS.

This is the concrete content behind #62's open "future browser-extension handoff" and
"deep links / file associations / single-instance delivery" items, and #65's smoke matrix.

### 10.3 Places where packaged behavior is still subordinate to dev conventions

Reported as required, whether or not fixing them is in scope here:

- `mcp_server/client.py:16` hardcodes `DEFAULT_BASE_URL = "http://127.0.0.1:8080"` — a dev port
  baked into a shipped client, which cannot be right for a packaged app with a dynamic port.
- The Word HTTPS companion ships with `CALLOSUM_DISABLE_REMOTE_ACCESS=1` on a **fixed** port —
  a permanently auth-disabled listener whose only protection is that nothing advertises it.
- `capabilities/default.json` grants Tauri IPC to **any** `http://127.0.0.1:*/*` origin, so any
  loopback content loaded in those windows inherits `core:default` plus every custom command.
- `tauri.conf.json` sets `"csp": null`, and the FastAPI shell sends no CSP header either.
- There is **no packaged smoke coverage** for any shell crossing (#65 is still open).
- #70 is the same class of defect in a different feature.

---

## 11. Licensing and provenance inventory

Measured, not assumed: `.claude/` scan of a shallow clone at 2026-09-15 (748 translator files,
20 `translate/src` files). **The corpus is not uniformly AGPL.**

### `zotero/translators` — **no repository-level LICENSE file**

| License (per-file header) | Files |
|---|---|
| AGPL-3.0-or-later | 596 |
| **No license header at all** | **104** |
| **GPL-3.0-or-later (non-Affero)** | **29** |
| AGPL-3.0-only | 19 |

**312 distinct copyright holders.** Verified samples: `Douban.js` is
"Copyright (C) 2009-2010 TAO Cheng … GNU General Public License … version 3 or later" — **GPL, not
Affero**. `AIP.js`, `Amazon.js`, `BIBSYS.js` go straight from the JSON header into code with **no
license block**, and there is no repo LICENSE to supply a default.

Among the translators Callosum would actually want, most are AGPL-3.0-or-later (PubMed, arXiv.org,
Google Scholar, Crossref REST, DOI, Embedded Metadata, Europe PMC, JSTOR, Wiley, Springer Link,
SAGE Journals, PLoS, IEEE Xplore, OSF Preprints, Semantic Scholar, OpenAlex, HighWire 2.0…). But:

- **`ScienceDirect.js` (Elsevier) has no license header.**
- Legacy `HighWire.js` has no license header.
- `Nature Publishing Group.js` is AGPL-3.0-**only** (no "or later").
- `SAGE Knowledge.js` is GPL non-Affero.

### `zotero/translate` — `COPYING` = AGPL-3.0

| License | Files |
|---|---|
| AGPL-3.0-or-later | 12 |
| **W3C licence** | **3** (`rdf/rdfparser.js`, `rdf/term.js`, `rdf/uri.js`) |
| **No header** | **5** (`rdf/identity.js`, `rdf/init.js`, `rdf/n3parser.js`, `rdf/serialize.js`, `tlds.js`) |

`zotero/utilities` and `zotero/zotero-schema` report NOASSERTION / none at repo level.

### Engineering conclusions (not legal conclusions)

- Callosum is AGPL-3.0, so the dominant direction is compatible, and AGPL-3.0-only is fine against
  an AGPL-3.0 work.
- **This is the strongest argument for a curated subset over blanket bundling.** Vendoring ~30
  vetted scholarly translators with known headers is a tractable provenance story; vendoring 748
  files of which 133 are non-AGPL or unlabelled is not.
- **Items requiring formal review before any distribution:** the 104 header-less translators
  (including ScienceDirect) and the 5 header-less `translate` files; the 29 GPL-non-Affero
  translators; the W3C-licensed `rdf/` subtree; and the repo-level license status of `utilities`
  and `zotero-schema`. `THIRD-PARTY-NOTICES.md` would need a corresponding section.

---

## 12. Deterministic test strategy

**Hermetic by default.** Saved HTML fixtures under `tests/fixtures/capture/`, never live publisher
pages in CI. Any site-specific live check is a separately-invoked smoke script, never part of the
deterministic suite.

| Fixture class | Asserts |
|---|---|
| Crossref/DOI-bearing generic article page | DOI extracted; canonical record resolved |
| PubMed record page | PMID extracted; resolution prefers PMID |
| Google Scholar result list | Recognised as multiple-result; **no auto-pick** |
| arXiv abstract page | arXiv id; preprint item type |
| Major publisher article page | Highwire tags; PDF URL detected as `url-reference` |
| Direct PDF | Detected; bytes path, not metadata path |
| Metadata-only page | Metadata-only result state |
| Multiple-result page | `candidates.length > 1` → review state |
| Unsupported generic webpage | Clean "unsupported", not a junk record |
| Already-imported item | "Already in Callosum"; no duplicate |
| Malformed metadata | Rejected at the boundary; no partial record |
| Missing DOI | Falls back to title/author/year; ambiguity surfaced |
| Ambiguous identity | `AMBIGUOUS` → review; never silently resolved |
| Inaccessible attachment | Metadata-only; **no backend retry** |
| Callosum unavailable | *Closed* vs *starting* distinguished |

Plus: **boundary tests** (`tests/test_cors_boundary.py`, added here, 17 passing); byte-cap and
`%PDF-` negative paths modelled on `transparency.py:245`; a translator-adapter test asserting
Zotero item JSON → `CaptureEnvelope` for each representative translator class; and a
**packaged-desktop smoke check** that is required before any phase closes.

---

## 13. Phased implementation plan

**Phase 1 — packaged-first generic capture vertical slice.**
Define the canonical connector-discovery mechanism; define per-install pairing/auth; expose the
bounded capture API **only on the canonical eligible backend role**; minimal Chromium extension
(`activeTab` + explicit click); generic metadata / DOI / direct-PDF capture; `CaptureEnvelope`
handoff; canonical identity/dedupe/import/indexing including the missing `embed_papers` call;
visible result states including *closed* vs *starting*; hermetic fixture tests; **packaged Windows
end-to-end smoke test**. Prerequisite fixes: §9.2 defects 1 and 2. Dev consumes the same contract
via the dev adapter. **Not complete until it works against an installed desktop build.**

**Phase 2 — translator feasibility.** Promote the spike (§14); prove a representative subset behind
the Callosum adapter. No large-scale bundling until runtime, security, and licensing are settled.

**Phase 3 — translator-backed single-item capture.** Curated bundle + update cadence; contextual
icon; safe attachment transfer; provenance. Re-validate packaged — the offscreen/sandbox runtime is
new surface Phase 1 did not cover.

**Phase 4 — breadth.** Multiple-result pages; Firefox (needs its own `eval` answer *and* its own
connector-host registration); optional Axis/Project actions; macOS/Linux packaged verification.

**Audit gate.** The build trips `CLAUDE.md:1835-1842` items 1 (new endpoint), 3 (file ingestion),
4 (new auth logic), 5 (3+ files), and 6 if a connector host is added — requiring
`.claude/security-audits/YYYY-MM-DD_browser-capture.md` before it is called done.

---

## 14. Empirical checks — status

| Check | Status | Result |
|---|---|---|
| License inventory | **DONE** | §11. Corpus is not uniformly AGPL; 133/748 non-AGPL or unlabelled. |
| CORS boundary regression tests | **DONE** | `tests/test_cors_boundary.py`, 17 passed. |
| Callosum source tracing | **DONE** | §1, §9.2 — all claims carry `file:line`. |
| Zotero runtime contract | **DONE** (documentary + source) | §2. |
| **Chrome MV3 sandbox+offscreen translator spike** | **NOT RUN** | Requires an interactive browser load. Must show: a sandboxed page in an offscreen document loading the vendored runtime, and ≥1 translator producing correct item JSON from a saved fixture. |
| **Native-messaging round-trip probe** | **NOT RUN** | Must show: installer-style manifest registration under `HKCU`, `connectNative` launching the host, and a measured round trip. §7.3 is conditional on this. |
| **Packaged-Tauri observation** | **NOT RUN** | Must record by observation: bound port, `last-port.txt`, cold-start latency to a 200 `/health`, and whether 8443 / tunnel-target children are listening. |

The three not-run checks are the Phase-1 entry criteria. They are deliberately not simulated.

---

## 15. Open questions requiring empirical resolution

- **O1 — Does the Zotero runtime actually execute under Chrome MV3's sandbox+offscreen?** Zotero's
  own manifest says the mechanism is right; it does not prove *our* vendored subset loads and runs.
  Blocks Phase 2.
- **O2 — Is native messaging viable at acceptable packaging cost on Windows/macOS/Linux?** §7.3's
  recommendation is conditional. If it is not, the rendezvous-port alternative must be re-scored
  and its hostile-webpage surface defended explicitly.
- **O3 — How can translators run on Firefox MV3** without `sandbox` or `unsafe-eval`? Options
  include `wasm-unsafe-eval`, a Firefox MV2 build, or accepting generic-only capture on Firefox.
  Unresolved.
- **O4 — What is the real-world Highwire/JSON-LD coverage rate** across the journals this user
  actually reads? Strategy B's value rests on it. Measurable against a sample of the existing
  Library's venues.
- **O5 — Does the translator corpus's update cadence fit a vendored model?** How often would
  re-vendoring be required for the curated subset to stay correct?
- **O6 — Which `imported_source` policy is right for capture** given that
  `enrich_paper_metadata_multi` would downgrade `browser-capture` to `crossref`?
- **O7 — What is the licensing status of the 104 header-less translators**, including
  ScienceDirect? Formal review needed before distribution.
- **O8 — Should the connector host be able to launch Callosum** when it is closed, and is the
  discarded `_argv` hook the right mechanism?

---

## 16. Anti-goals

No autonomous publisher crawling. No turning browser cookies or session state into a generalised
downloader. No paywall circumvention in any form. No silent acquisition of inaccessible PDFs. No
background capture without an explicit user action. No exporting authenticated browser state to
Callosum for later arbitrary retrieval. No cloud fallback when Callosum is closed. No telemetry. No
institutional proxy rewriting. No arbitrary webpage snapshots. No RIS/BibTeX browser interception.
No second reference-manager data model inside the extension. No browser-specific canonical identity
logic. No silent selection among ambiguous paper identities. **No dev ports, dev paths, or dev
fallbacks in any shipped code path.** And "works in browser dev mode" is never evidence that
packaged Tauri integration works.

---

## Appendix A — proposed revised text for issue #61

*(Drafted here; applied to the issue body in this increment.)* See the issue itself.
