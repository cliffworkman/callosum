# Browser capture architecture — research and design (issue #61)

**Date:** 2026-09-15
**Status:** research/design increment. No product code ships here.
**Baseline:** all claims verified against **`main` @ `1aa3973a`**.

> **Methodology note.** Initial code tracing ran against `experiment/ask-cli-staged-synthesis`,
> which is 45 commits behind `main`. That produced two stale findings, both corrected here: the
> shared DOI primitive `add_paper_by_doi` and `normalize_doi` (backlog #58) exist on `main` and were
> reported as missing. Every load-bearing claim in this document has since been re-verified against
> `main`; the CORS policy, the `local_only` header gate, `attach_pdf_to_paper`'s `role="primary"`
> default, the null-`attachment_id` annotation visibility, the Word-HTTPS 8443 child, and the
> missing `embed_papers` call all hold unchanged. Anyone extending this work should re-verify
> against the branch they are building on rather than against this document.
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

Twelve independent `create_paper` call sites exist, with **no single shared ingestion service** —
but, importantly, a **shared DOI-add primitive already exists** (§1.5). Items enter the Library
through feature-owned paths:

| Path | Route | Service |
|---|---|---|
| Folder scan / watched folders | `POST /library/scan`, `/library/watched/rescan` | `pdf_processing/library_scan.py:55` |
| Citation files (RIS/BibTeX/CSL-JSON) | `POST /library/import` | `metadata/citation_import.py:367` |
| Zotero native library | `POST /library/zotero/import` | `importers/zotero.py` |
| Portable bundle | `POST /library/bundle/import` | `metadata/library_bundle.py` |
| **Discovery save** | `POST /discovery/save` | `discovery/search.py:59 save_item` |
| **Add with DOI…** | `POST` in `api/routers/acquisition.py:101` | `metadata/doi_add.py:40 add_paper_by_doi` |
| Agent reference (DOI) | `POST /agent/references` | the same `add_paper_by_doi` primitive |
| **Zotero citation resolve** | `POST /citations/zotero/resolve` | `api/routers/zotero_citations.py:48` |
| Gaps / citing / my-publications | `POST /gaps/add`, `/my-publications/citing/import` | `clustering/my_publications.py:438` |
| OA acquisition (attach to existing) | `POST /papers/{id}/acquire-oa` | `acquisition/fetch.py` |

**`POST /discovery/save` is the closest analogue for *noisy field* capture.** Its `SaveRequest`
(`api/routers/discovery.py:59`) already accepts title, doi, pmid, abstract, authors, journal, year,
url; it dedupes via `find_existing_paper_by_identity` and fires a background
`enrich_paper_metadata_multi`. This is a reuse seam, not a template to copy into a parallel path.

**`POST /citations/zotero/resolve` is the closest analogue for *untrusted external client* capture**
(`api/routers/zotero_citations.py:48`). The LibreOffice/Word adapters decode Zotero-authored
document fields locally and post the distinct works; the endpoint resolves-or-creates each against
the full identity tuple. Its docstring is the trust posture a capture endpoint should mirror
verbatim: *"a ReferenceMark/Word Field is untrusted content pulled from an opened document (rule
#4), so this stays defensively bounded like every other adapter-facing endpoint"* — bounded by
`MAX_ZOTERO_DISTINCT_WORKS = 300`, metadata-only, *"a faithful format migration, not a claim about
the literature"*. Its `{paper_id, created}` result shape matches `/discovery/save`'s; that pair is
the de facto ingestion response contract.

### 1.5 The shared DOI primitive already exists (correction)

`metadata/doi_add.py:40 add_paper_by_doi` is **"the shared identity-resolution primitive (backlog
#58)"** — one implementation of "resolve a DOI to a real record and add it, or surface the existing
one", used by *both* the Library "Add with DOI…" endpoint (`acquisition.py:101`) and the MCP agent's
save-reference tool, *"so there is no DOI-specific metadata silo"*.

It already has the properties this document would otherwise have proposed inventing:

- a **machine-readable status enum** — `created` / `existing` / `invalid` / `unresolved`
  (`DoiAddResult`), so an unresolvable DOI creates nothing rather than an invented placeholder;
- **metadata-only and provider-honest**: it never fetches a PDF, so *"a failed download can never
  masquerade as a failed DOI import"* — exactly the separation §8 requires;
- **caller-owned transaction**, so it composes.

`metadata/doi.py:72 normalize_doi` handles bare / `doi:` / `https://doi.org/` / `dx.doi.org` forms
and validates the `10.` registrant prefix, and is documented as *"the ONE place every DOI-add path
normalizes user input"*.

**Capture should extend this primitive, not build a parallel one.** What it lacks for capture is
(a) non-DOI signals and (b) an `AMBIGUOUS` status — see §9.

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
| Metadata-only article page | Metadata-only import; optionally offer the Wanted list (feature inc 76; OA triage + "Open all blocked" hand-off inc 588, shipped 0.5.11 — the surface #61 succeeds). |
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

**Partially closed since this research began.** `add_paper_by_doi` (§1.5) is a real shared primitive
with a machine-readable status, and backlog #58 delivered it. So the #25 gap is now **narrower and
more precisely stateable** than "there is no primitive":

- For a **DOI**, a shared, honest, metadata-only resolve-or-surface path exists.
- For **non-DOI signals** (title/author/year, PMID-only, arXiv-only), there is still no shared
  resolver — those go through `find_existing_paper_by_identity`'s exact-match auto-pick.
- **No path of any kind can return `AMBIGUOUS`.** `DoiAddResult.status` has no such member, and
  `find_existing_paper_by_identity` returns the first hit. Issue #25's requirement to *"expose
  uncertainty / candidate matches rather than silently choosing"* remains unmet.

Browser capture is the front end that makes this visible: a page with a title but no DOI is exactly
the ambiguous case.

### 9.2 Defects a capture path would inherit (all verified)

1. `find_existing_paper_by_identity` **does not filter `deleted_at`** — capture would dedupe onto a
   trashed paper. **Blocking; fix first.**
2. ~~No DOI prefix stripping.~~ **Corrected — already fixed on `main`** by `metadata/doi.py:72
   normalize_doi` (backlog #58). Note the residual trap: `repository._normalize_doi` is a *different,
   weaker* function (`.strip().lower()` only) still used **inside**
   `find_existing_paper_by_identity`. Capture must route DOIs through `normalize_doi`, not hand a
   raw prefixed DOI to the repository function.
3. Its `title_year_author` arm is raw SQL equality on the stored title — case-, punctuation-, and
   whitespace-sensitive. Much weaker than the scan's `normalize_text(strip_punctuation(...))`.
4. No DOI-add path calls `embed_papers`, so captured papers are invisible to semantic search.
5. `imported_source` is load-bearing: a `browser-capture` value is protected from Crossref clobber
   by `_can_update_from_crossref:283`, but `enrich_paper_metadata_multi` would **downgrade it to
   `crossref`** (`enrichment.py:464-470`). Decide deliberately.
6. `papers.doi` is deliberately **not unique** (migration `0040`), so same-DOI duplicates can exist
   and `.limit(1)` picks arbitrarily among them.

### 9.3 Target flow

**Extend `add_paper_by_doi` rather than build alongside it.** Two additive changes:

1. Add an `ambiguous` member to `DoiAddResult.status`, carrying candidates with reason and
   confidence — the one thing #25 asks for that no path provides.
2. Generalise the input from a raw DOI to a candidate identity (DOI, PMID, arXiv, or
   title/author/year), keeping the same honest-status contract.

```
CaptureEnvelope.candidates
  -> normalise identifiers (metadata/doi.py normalize_doi; PMID/arXiv extracted)
  -> add_paper_by_doi(), generalised      ← extends the #58 primitive, shared with #25
       returns: created | existing | invalid | unresolved
              | ambiguous([candidates])   ← NEW; never auto-picked
  -> existing   → gap-fill reconcile, attach if bytes present
     created    → background enrich, then embed (defect 4)
     ambiguous  → explicit Callosum review state; extension says "needs review"
     unresolved → honest "couldn't identify this page"; nothing created
```

**Principle: different capture front ends produce candidate scholarly identity; Callosum resolves
canonical identity once.** No browser-specific dedupe rules, and no second primitive — #58 already
established where this lives.

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
end-to-end smoke test**. Prerequisite fix: §9.2 defect 1 (`deleted_at`) — defect 2 is already fixed
on `main`. Identity work extends `add_paper_by_doi` (§9.3); it does not create a second primitive.
Dev consumes the same contract via the dev adapter. **Not complete until it works against an
installed desktop build.**

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
| Callosum source tracing | **DONE** (re-verified against `main`) | §1, §9.2 — all claims carry `file:line`. Two stale findings corrected; see the methodology note at the top. |
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

---

# Part II — Substrate hardening increment (2026-09-15, second pass)

Implemented on `browser-capture-research`. Everything below is verified against `main` @ `1aa3973a`
and covered by tests; the empirical sections record observations, not inferences.

## 17. Identity no longer resolves onto Trash

`find_existing_paper_by_identity` had no `deleted_at` filter, so **every** import path could resolve
onto a soft-deleted paper and silently suppress the add. The user trashed a paper, re-imported it,
and got nothing back — and the work was then unreachable by either route, because
`wanted_repo.list_open` already skipped trashed papers and `duplicate_detection` already excluded
them. Identity resolution was the odd one out.

**The subtlety that made this more than a one-line filter.** Soft-delete keeps the row, so the UNIQUE
constraints on `openalex_work_id`, `semantic_scholar_paper_id` and the Zotero key still bind against
trashed papers — the same collision `paper_merge` avoids by nulling a husk's identifier columns
(`paper_merge.py:13-17`). Filtering alone converts a silent wrong match into an **uncaught
`IntegrityError` → 500** on the Zotero resolve and import paths. A regression test pins that this is
real, not theoretical (`test_creating_beside_a_trashed_unique_identifier_still_raises`).

**Design.** Lookups are live-only by default, with an explicit `include_trashed=True` opt-in. Creates
that carry a UNIQUE identifier first consult `find_trashed_identifier_holder` and **surface the
trashed paper** — it is the same work, and the user can restore it. That helper is deliberately
narrow: DOI and title/year/author are not consulted, because neither is UNIQUE (`papers.doi`
intentionally so, migration `0040`) and so neither can block a create; widening it would quietly
restore the bug it exists to prevent.

Applied at the four creating paths carrying UNIQUE identifiers (Zotero citation resolve, Zotero
library importer, bundle/share import, my-publications work import). Mendeley opts in for a
different reason — `_paper_for_mendeley_id` resolves the external id without a `deleted_at` filter,
so if only one side stopped seeing trashed rows its conflict guard would abort a whole import over a
conflict that is not real.

Three sites deliberately keep the new live-only default, because resolving to a trashed paper there
would be *wrong*, not merely surprising: curated-axis member resolution, the imported-synthesis
source blob, and the re-verification target.

## 18. Candidate state: absent / active / trashed

The write-side fix is correct, but the read side asks a different question — *"do I already know this
work?"* — and a trashed paper still answers yes. Letting `in_library` flip to `false` would have made
six unmigrated suggestion surfaces render a deliberately-trashed paper as a **fresh discovery**,
inviting an add that creates a live duplicate beside the trashed row. That is worse than the bug.

So candidate state is three-valued via one shared `resolve_library_state` helper, and **`in_library`
is derived** (`state != "absent"`). A trashed paper keeps `in_library=True`, so every unmigrated
consumer renders exactly as before — safe by construction rather than by a promise to migrate later.
Discover reads `library_state` and shows "in Trash", pointing at restore instead of a second copy.

**Known consequence, recorded not fixed:** trashing a duplicate then re-importing now creates a fresh
live row that duplicate detection re-flags, and dismissed pairs are keyed on `(paper_id, paper_id)`
(`duplicate_detection.py:51-53`) so the dismissal does not carry. The `library_state` signal is what
makes this intelligible rather than mysterious.

## 19. Ambiguity — the limitation stated precisely

Do **not** read section 9 as "ambiguity is not collapsed". The accurate statement is the opposite:

- **No current path can represent `AMBIGUOUS`.** `DoiAddResult` has four statuses and none of them is
  ambiguity; `find_existing_paper_by_identity` returns a single optional match.
- Every lookup ends in `.limit(1)` over predicates that are **not unique** — `title_year_author` is
  plain equality on bibliographic fields, and `papers.doi` is deliberately not UNIQUE. So any lookup
  selecting one row from potentially non-unique bibliographic evidence **is** silently collapsing
  ambiguity today.

This remains **an open audit item**, not a solved problem. The seam is defined (section 9.3) and
`add_paper_by_doi` stays narrow and deterministic; the ambiguity boundary is explicit and unbuilt.

## 20. The indexing invariant

**Rule:** if a record is admitted to the active Library and has enough material to participate in an
index, its indexing state must not depend on which front end created it.

**There is no single successful-admission lifecycle seam** — a dozen `create_paper` call sites, no
post-admission hook. So rather than add a fourth "remember to embed" call site:

- **Chunks:** `attach_pdf_to_paper` now takes `vector_store` + `embedding_model` as **required**
  keyword args and embeds, exactly as `reprocess_pdf_attachment` already did. Required, not optional,
  so a new attach path cannot forget — which immediately paid for itself by surfacing
  `tools/validation_harness.py`, a caller that would otherwise have been missed.
- **Papers:** one post-admission invariant (`embeddings/admission.py`) generalizing
  `ensure_candidate_embeddings_committing` — one committed transaction per paper, failure never fatal
  to an otherwise-successful import.

**Ordering matters:** `embed_papers` keys its skip check on the constant `PAPER_TEXT_VERSION`, not on
the paper's text, so an embedding written *before* enrichment would never be refreshed when
enrichment fills in the abstract/venue/year that `paper_embedding_text` joins. Discovery enriches
first, then indexes.

Deliberate deferrals are documented rather than normalized away: lazy backfill in synthesis, faceted
retrieval, verification and axis scoring is principled and stays. It does **not** cover
`search_similar` consumers, which is why the attach-time fix matters.

Enforced by `tests/test_admission_indexing.py`, which parametrizes over every metadata-admission
front end — so a future front end that forgets fails CI rather than shipping unsearchable papers.

## 21. Phase 1 attachment scope — Option B (decided)

**Phase 1 browser capture may NOT attach PDF bytes to a paper that already has a PDF.** Evidence:

- Annotations with `attachment_id IS NULL` are returned for **every** attachment
  (`annotations_repo.py:73-76`, unconditional `or_`), so their geometry paints onto an unrelated PDF.
- They are not legacy-only: `library_bundle.py:373` writes `attachment_id=None` **by design** on every
  bundle/share import, and the annotations endpoint accepts an omitted `attachment_id`. No backfill
  migration has ever existed.
- **There is no detach or delete path** — verified: `grep -rn "delete(attachments)" app/backend/` gives
  zero hits, and there is no attachment DELETE route among the 30 router deletes. A bad attach is
  unrecoverable except by deleting the whole paper.
- `attach_pdf_to_paper` validates nothing, does no checksum dedupe, and defaults `role="primary"`
  with nothing preventing two primaries; `_select_primary_pdf_attachment` then takes `ordered[0]` from
  an **unordered** select, so a new PDF would lose to the pre-existing one with no signal.

This narrows issue #61's motivating case (metadata-only paper + browser-supplied PDF) and is recorded
in the issue. The ordering trap matters: the null-annotation backfill is only cheap while single-PDF
papers dominate. Cross-reference #72.

## 22. Native messaging — PROVEN on Windows

Experimental harness in `.claude/experiments/native-messaging-probe/` ("experimental harness proving
browser-runtime feasibility", **not** the production connector host).

| Check | Result |
|---|---|
| Host stdio framing (4-byte LE length + JSON) | **Works.** Standalone round trip ~360 ms including Python startup |
| Host reads packaged state | **Works.** Returned the real `last-port.txt` port **53459** |
| Registration under `HKCU\...\NativeMessagingHosts` | **Works.** Same per-user model an NSIS currentUser install would use |
| Browser launches the host | **Works** (Edge 153). Host received argv `["chrome-extension://<id>/", "--parent-window=0"]` |
| Caller identity | **Confirmed:** the extension origin arrives as **argv[1]** — the identity signal a real host would gate on |
| `allowed_origins` rejection (wrong id) | **Host never launched** |
| **Stale host path** (manifest registered, binary gone) — the packaged upgrade/uninstall case | **Host never launched**; fails closed |
| Missing manifest (Callosum never installed) | **Host never launched**; fails closed |

**Windows unpacked-extension id derivation confirmed empirically:** sha256 of the path encoded
UTF-16LE, nibbles mapped 0→a … f→p. The observed id matched the UTF-16LE candidate, not UTF-8.

**One genuine obstacle, and it is a dev-harness problem, not a product one:** Chrome 153 refuses
`--load-extension` (disabled for security since Chrome 137), and the documented override flag no
longer re-enables it. The probe therefore ran under **Edge 153**, which still honours it. This does
not affect a production extension installed from a store with a stable id, but the **dev adapter**
needs a plan: a packed CRX with a pinned key, or manual loading via `chrome://extensions` with
Developer Mode. Recorded as an open dev-ergonomics item.

## 23. Packaged-Tauri observation (Windows, by observation)

Installed build **v0.5.15**, matching `tauri.conf.json`.

| Observation | Value |
|---|---|
| `last-port.txt` | `%APPDATA%\com.callosum.desktop\last-port.txt` = **53459** |
| Actually listening | **53459**, PID 51032, **child of callosum-shell.exe** — exact match |
| Backend runtime | app-local CPython (`...\com.callosum.desktop\python-runtimes\...`), `-m uvicorn app.backend.api.app:app` |
| `/health` (packaged) | `app_version: "0.5.15"` |
| `/health` (dev, port 8888) | `app_version: "dev-23caa25d+"`, DB revision 0081 vs packaged 0083 |
| Word HTTPS (8443) | not listening (opt-in, not enabled) |

**The hazard is live, not hypothetical.** A packaged backend (53459) and a dev backend (8888) were
running *simultaneously* on this machine, both serving `app.backend.api.app:app`, against different
databases at different migration revisions. A port-probing extension using the documented dev port
would have reached the dev instance.

**Can a connector host deterministically identify the canonical UI backend from packaged state
alone?** Nearly:

- **Port — yes.** `last-port.txt` matched the live listener exactly, and the probe host read it
  successfully from inside a browser-launched process.
- **Packaged vs dev — yes, already.** `health.py:_dev_git_version` stamps a `dev-` prefix
  "deliberately... so it can never be mistaken for a real packaged release version".
- **Role — no. This is the one gap.** All three packaged children receive the same
  `CALLOSUM_APP_VERSION` (`backend.rs:205`, `:316`, `quick_tunnel.rs:212`) and are distinguished only
  by `CALLOSUM_DISABLE_REMOTE_ACCESS=1` / `CALLOSUM_TUNNEL_TARGET=1`, neither of which is exposed.

**Smallest packaged-shell change:** pass an explicit instance-role env var to each child and surface
it on `/health`, mirroring exactly how `CALLOSUM_APP_VERSION` already flows. Specify now, implement
with the capture endpoint.

Still unobserved: cold-start latency to a usable backend (needs a deliberate restart), and
tunnel-target behaviour. **Windows only — macOS and Linux are untested, not assumed equivalent.**

## 24. Transport recommendation after testing: native messaging, confirmed

The probe settles the question this document left conditional. Native messaging is recommended, now
on evidence rather than on reasoning:

- It **works** end to end on Windows, including the identity signal and every failure mode.
- It **fails closed** in all three negative cases, including the stale-host case a packaged upgrade or
  uninstall would produce — the realistic field failure.
- It carries **no network surface** a hostile webpage can reach.
- The authoritative state (`last-port.txt`) is **filesystem state**: readable by a local process, not
  by an extension. That asymmetry is the architectural argument, and the probe demonstrated a
  browser-launched host reading it.
- `allowed_origins` cannot contain wildcards, so release-aware extension identity is enforced by the
  platform rather than by our discipline.

The fixed loopback rendezvous endpoint stays documented as the alternative, but it loses on every
security axis, and its only advantages (browser-agnostic, no installer work) are now weighed against
a mechanism that has been demonstrated rather than assumed.

Residual risks, honestly held: per-browser and per-OS manifest registration is real installer work;
macOS and Linux are unverified; and the dev-harness loading problem above needs its own answer.

## 25. Where packaged behaviour is still subordinate to dev conventions

Reported as required, whether or not fixing them is in scope:

- `mcp_server/client.py:16` hardcodes `DEFAULT_BASE_URL = "http://127.0.0.1:8080"` — a dev port baked
  into a shipped client, which cannot be right for a packaged app with a dynamic port.
- The Word HTTPS companion ships with `CALLOSUM_DISABLE_REMOTE_ACCESS=1` on a **fixed** port — a
  permanently auth-disabled listener whose only protection is that nothing advertises it.
- `capabilities/default.json` grants Tauri IPC to **any** `http://127.0.0.1:*/*` origin.
- `tauri.conf.json` sets `"csp": null`, and the FastAPI shell sends no CSP header either.
- No packaged smoke coverage exists for any shell crossing (#65 still open).
- **Observed this increment:** the citation-preview, frontend-assembly and demo-snapshot tests fail in
  a worktree without `node_modules` and pass in one that has it — the same class as **#70**, and a
  reminder that "works in my checkout" is an environment claim, not a product claim.

## 26. The nine exit questions, answered

1. **Canonical path for browser metadata into the Library** — the existing admission spine:
   normalize, then `find_existing_paper_by_identity`, then surface-or-`create_paper` with a provenance
   stamp, then the post-admission indexing invariant. `add_paper_by_doi` remains the DOI primitive.
   No fourth resolver was created.
2. **Can that path resolve onto Trash?** No — fixed, with regression tests covering DOI, Zotero key,
   OpenAlex id and title/year/author, plus Trash/restore round-tripping.
3. **How is ambiguous non-DOI identity represented?** It is not. No path can represent `AMBIGUOUS`,
   and `.limit(1)` over non-unique predicates still collapses it silently. Open audit item (section 19).
4. **Is indexing guaranteed independent of front end?** Yes for both chunks and papers, enforced by a
   parametrized test; principled deferrals documented.
5. **May Phase 1 attach bytes to an existing paper?** **No** — Option B, with the null-annotation
   bleed and the absent detach path as the reasons.
6. **Does native messaging work in real Chromium on Windows?** **Yes** — proven, including all three
   failure modes. Verified under Edge 153; Chrome 153 blocks the *dev* loading path only.
7. **Can a connector host identify the canonical backend without probing?** Port yes, dev-vs-packaged
   yes, **role no** — one small shell change specified.
8. **Is native messaging still recommended?** Yes, now on evidence (section 24).
9. **Exact remaining prerequisite before the Phase 1 extension** — the instance-role signal on
   `/health` plus its env var in the shell. Everything else Phase 1 needs is now in place.

---

# Part III — The instance-role contract (2026-09-15, third pass)

The last known prerequisite before Phase 1. Section 23 found that port and version cannot prove a
responding backend is the canonical UI instance; this closes that gap and nothing else.

## 27. The contract

**Environment variable:** `CALLOSUM_INSTANCE_ROLE`, set **explicitly by every launcher at spawn**.

**Vocabulary** (hyphenated, matching `PROCESSING_TIERS`, `ATTACHMENT_STORAGE_MODES`, `DocumentRole`):

| Role | Process | May receive browser capture? |
|---|---|---|
| `ui` | the canonical UI backend | **yes** — the only one |
| `word-https` | Word add-in companion on fixed 8443, Remote Access gate force-disabled | no |
| `tunnel-target` | Quick Tunnel's fail-closed origin | no |
| *(absent)* | a bare `uvicorn`, an older packaged build, a launcher that forgot | **no** — the fail-safe |

**Where it is set**

| Launcher | File | Role |
|---|---|---|
| Packaged UI backend | `src-tauri/src/backend.rs` → `ui_backend_command` | `ui` |
| Packaged Word HTTPS | `src-tauri/src/backend.rs` → `word_https_command` | `word-https` |
| Packaged tunnel target | `src-tauri/src/quick_tunnel.rs` → `tunnel_target_command` | `tunnel-target` |
| Dev supervisor (HTTP child) | `tools/run_dev.py` | `ui` |
| Dev Word HTTPS | `tools/run_https.py` | `word-https` |
| Packaging smoke test | `app/desktop-shell/packaging/smoke_test_backend.py` | `ui` |
| QA harness, e2e smoke, LibreOffice roundtrip | — | *(none, deliberately)* |

Dev launchers declare roles so **development exercises the same product contract**, not a dev-only
shortcut. The three test harnesses are deliberately roleless: they are not connector targets, and the
null default doing its job there is the point rather than an oversight.

**Where it is exposed:** `GET /health` → `instance_role`. That surface was re-evaluated, not assumed:

- `health.py` is already the canonical process-identity module — `reported_app_version()` lives there
  and is reused by `diagnostics.py`, `feedback.py` and `paper_files.py`;
- `/health` is in `access_control._EXEMPT_PATHS`, so a connector can identify an instance **before**
  it holds any credential;
- the packaging smoke test already polls `/health`, and now asserts the role there too — packaged
  coverage against a real bundled runtime, in CI, for free.

No capture endpoint was invented to carry it.

## 28. Two properties that are deliberate, not incidental

**Role is process identity and encodes nothing about the build.** `"ui"` means exactly the same thing
in a dev checkout and a packaged install. Build identity stays a separate axis (`app_version`, with
its deliberate `dev-` prefix). Eligibility is therefore a **policy the consumer composes**:

- a **production** connector host requires `instance_role == "ui"` **and** an approved packaged /
  release identity;
- an explicitly **development** connector host may accept `instance_role == "ui"` **and** a dev
  identity.

The backend reports both facts and enforces neither. Baking "non-dev build" into the meaning of
`"ui"` would have made dev unable to emulate the product contract, or weakened production to let dev
through — so the two axes stay orthogonal.

**Role is never inferred from a behavior flag.** The Word HTTPS child still carries
`CALLOSUM_DISABLE_REMOTE_ACCESS=1` and the tunnel target still carries `CALLOSUM_TUNNEL_TARGET=1`.
Those remain independent controls; a connector refuses those children **by role**, not by inferring
intent from an unrelated env var. A Rust test pins that separation.

**Missing or unrecognized → `null`, never a guess.** A dedicated test asserts `null != "ui"`. An
unrecognized value additionally warns **once per process** (`lru_cache`), because a connector may poll
`/health` frequently and a bad env var must neither flood the log nor brick a user's install.

## 29. Verification

**Rust — `cargo test` in `src-tauri`: 56 passed, 0 failed** (5 new). Command construction was extracted
into `ui_backend_command` / `word_https_command` / `tunnel_target_command` so `Command::get_envs()` can
assert what actually launches — mirroring `word_https_args`, which the file had already extracted for
exactly this reason. The spawn paths call those builders, so test and reality cannot drift.

- `each_backend_child_declares_its_instance_role`
- `instance_roles_are_pairwise_distinct` — siblings stay distinguishable while serving the same app
- `instance_role_is_independent_of_the_remote_access_control`
- `ui_backend_argv_stays_loopback_on_the_picked_port` — guards the extraction
- `tunnel_target_declares_its_instance_role`

Pre-existing `word_https_argv_is_fixed_loopback_tls` and `remote_access_opt_in_is_explicit_true` stay
green.

**Python — 125 passed** across `test_health.py` (26, incl. 8 new), `test_cors_boundary.py`,
`test_access_control.py`, `test_admission_indexing.py`, `test_persistence_core.py`,
`test_mobile_ingress.py`, `test_feedback_relay.py`, `test_diagnostics.py`, `test_run_https.py`.

Note a build-environment prerequisite discovered here: `cargo test` fails outright until
`packaging/stage_source.py` has staged `resources/callosum-src`, because the Tauri build script
resolves that resource path. Worth knowing before anyone runs the Rust tests in a fresh worktree.

## 30. Packaged verification (Windows, by observation)

Built from this branch: `npm install` + `tauri build --no-bundle` (release, 10m42s). The binary was
run **in place** — the installed 0.5.15 was never replaced.

**Isolation was whole-directory, and the real library was never opened.** Procedure
(`.claude/experiments/native-messaging-probe/observe_packaged_role.py`): refuse to run while installed
Callosum is running → rename the real `%APPDATA%\com.callosum.desktop` aside → let the test build
create a **fresh disposable** app-data directory → observe → delete the disposable directory →
restore the real one unchanged. No SQLite snapshot-and-restore, and the script **stops rather than
falling back** if any isolation step fails. This works because the managed Python runtime lives under
**Local** app data while the library lives under **Roaming**, so renaming Roaming isolates the library
and leaves the runtime resolvable.

Verified after each run: `callosum.sqlite` back at 67,383,296 bytes with its original timestamp, and
`last-port.txt` back to `53459`. No leftover parked directories.

| Observation | Result |
|---|---|
| Packaged UI backend reports its role | **`instance_role: "ui"`** ✅ |
| `app_version` alongside it | `"0.5.15"` |
| Port used | `54848` — a fresh random port, neither the installed build's `53459` nor any dev port |
| **Connector host resolves the canonical backend** | **`resolved: true`, `reason: "ok"`, `ports_probed: 0`** ✅ |
| Word HTTPS child reports `word-https` | **UNOBSERVED** — `word_https_configured()` requires dev certs that are not installed on this machine |
| Tunnel target reports `tunnel-target` | **UNOBSERVED** — needs cloudflared plus Remote Access enabled, which would alter real user settings |
| macOS / Linux | **UNTESTED** — not assumed equivalent |

The two unobserved siblings are covered by test rather than observation, and the distinction is worth
keeping straight: `cargo test` proves the **shell sets** their roles, and `tests/test_health.py` proves
the **backend reports** any configured role. What has not been watched end to end is a packaged shell
actually spawning those two children. Reported as unobserved, not inferred.

**The connector-host resolution, end to end.** The real probe host was driven over its stdio framing,
exactly as a browser launches it, while the packaged app was up:

```json
{"resolved": true, "reason": "ok", "port": 54848,
 "port_file": "…\\com.callosum.desktop\\last-port.txt",
 "instance_role": "ui", "app_version": "0.5.15", "ports_probed": 0}
```

Its resolution is: read the authoritative port from `last-port.txt` → ask **that port only** for
`/health` → require `instance_role == "ui"`. Deliberately returned alongside, not folded in:
`app_version`, so the consumer composes its own eligibility policy.

## 31. Exit question

> **Can a future browser connector host deterministically identify the one packaged Callosum backend
> permitted to receive browser capture, without port probing or reliance on development conventions?**

**Yes — demonstrated, not argued.** On a real packaged build the host resolved the canonical UI
backend with `ports_probed: 0`, reading the port from packaged state and confirming the role. No dev
port, no checkout path, and no dev convention participates in the shipped path. A sibling cannot pass
the check (`word-https` / `tunnel-target` are distinct values), and a process that declares nothing
reports `null`, which fails it too — so the absence of a role can never be mistaken for the canonical
instance.

Two honest limits on that "yes": the sibling *refusals* are proven by test rather than watched in a
packaged run, and only Windows has been exercised.

**Phase 1 browser capture is unblocked.**

**The exact next increment** — the Phase 1 vertical slice, in the order the research document's §13
sets out, now that its prerequisite is met:

1. the connector host proper (production, re-derived against the packaged contract — the probe is
   throwaway and stays that way), registered by the installer under `HKCU`;
2. per-install pairing, issued over the native channel;
3. the bounded `/capture/*` router, served **only** when `instance_role == "ui"`, with the Host-header,
   origin, byte-cap and `%PDF-` validation the research document specifies;
4. the minimal Chromium extension (`activeTab` + explicit click), generic metadata / DOI / direct-PDF
   capture into the `CaptureEnvelope`;
5. **capture refuses any paper that already has a PDF** — the Option B constraint from §21 stands until
   the null-`attachment_id` annotation bleed and #72's detach/delete land.

That increment trips the security audit gate (`CLAUDE.md` items 1, 3, 4, 5, and 6 for the new host),
so it requires `.claude/security-audits/YYYY-MM-DD_browser-capture.md` before it is called done.

---

# Part IV — Stage 2 implementation and evidence status (2026-09-16)

The increment §31 called for is built: `src-tauri/src/bin/callosum_connector.rs` (the production
connector host), `connector/identity.json` (the single identity source), NSIS installer registration
in `installer-hooks.nsh`, the `app/desktop-shell/extension/` MV3 extension, `ensure_pairing_secret()`
wired at UI-instance startup, and a dev-only registration path in `tools/run_dev.py`. Full detail —
threat model, per-control test references, findings — lives in
`.claude/security-audits/2026-09-16_browser-capture.md`'s Stage 2 section; this entry records what
changed at the architecture level and, precisely, what has and has not been empirically exercised.

## 32. Four findings that changed the design mid-build

1. **The `/UPDATE` guard was not a hypothesis — it was verified against the actual NSIS template
   bytes** embedded in `@tauri-apps/cli-win32-x64-msvc` (grepped directly: `${GetOptions} $CMDLINE
   "/UPDATE" $UpdateMode` in `un.onInit`, and the installer's own re-invocation of the prior
   version's `uninstall.exe` with `/UPDATE` appended when itself launched in update mode). Without
   the identical `${If} $UpdateMode <> 1` guard on the new registry-removal code, every Tauri
   auto-update would have silently unregistered the connector. This is F4 in the Stage 2 audit.
2. Tauri's bundler validates every `bundle.resources` path exists on **any** `cargo build` of the
   package, not only during `tauri build` — so `packaging/stage_connector.py` must create
   `resources/connector/` (even empty) *before* compiling the connector binary, not after. A
   real, load-bearing ordering constraint, not a style choice.
3. Chrome's manifest `key` field only fixes an **unpacked** extension's id deterministically;
   neither store is known to honor a self-chosen id for a brand-new item. There is therefore no way
   to know this extension's real production id before it is actually published — `identity.json`'s
   `production_extension_ids` starts as an empty list on principle, not as a placeholder to be
   filled with a guess.
4. Chrome launches a native-messaging host with **its own environment**, never the manifest's — so a
   dev-only capability flag (`CALLOSUM_CONNECTOR_ALLOW_DEV_BUILD=1`) can only reach the connector
   process via a wrapper script the manifest's `path` points at instead of the binary directly
   (mirrors the research probe's own `host.bat` technique, §22).

## 33. Evidence status — the same four-way distinction the audit uses, at a glance

| Level | Status |
|---|---|
| Component behavior (Rust unit tests, Python unit/integration tests, JS unit tests, clippy, ruff) | **Proven, run for real.** `cargo test --release` for both packages (`src-tauri` + `connector-host`): 64/64 passed. `cargo clippy -D warnings`: clean for both. Focused `pytest` (capture + connector-identity + desktop-packaging + health): 88 passed, 0 pre-existing failures remaining (see §34). `node --test`: 12/12. `ruff check`/`format --check`: clean. |
| Packaged behavior, local | **Proven.** The full NSIS installer was built for real and silently installed (`/S`, `/D=<throwaway>`) without touching the maintainer's real install: correct-size main binary, connector resource, manifest, and both browsers' registry entries all directly inspected; the app launched and stayed running; `/UPDATE`-mode and ordinary uninstall were both run for real locally, including third-party-entry survival. |
| CI installer/update/uninstall run | **CI-proven.** Clean-runner Windows Actions run `35134478341` (commit `1c46a73e`, `workflow_dispatch`) executed every new step and passed, verified from actual log content: the backend became healthy (`healthy on port 55873 after 117s`), both browsers' manifests were resolved and validated, `/UPDATE` preservation and ordinary-uninstall removal were both confirmed with exact registry-value comparisons, and the third-party entry survived both paths. A screenshot shows the real, fully-rendered Callosum UI running on the runner. |
| Real Edge click-through acceptance, cases A–E | **Proven, dev/test identity path, including the direct-PDF contract.** `run_acceptance_AtoE.py` ran all five cases in one isolated session; A/C/D passed exactly. B/E were rerun a THIRD time on 2026-09-16 (§38 item 5) against the provisional-ingestion contract that superseded item 4's terminal refusal: `run_acceptance_direct_pdf_provisional.py`, fresh disposable instance — B genuinely queued for review (a real front-matter DOI resolved via live Crossref, but its title did not corroborate), and E genuinely reached `attachment_conflict` through a real Edge click plus live Crossref resolution of a real, independently-verified DOI, proving the attachment-safety branch reachable end to end rather than only at component level. No row remains unproven except real production store identity, which is not an implementation or acceptance gap — see §37. |

Getting to that CI-proven row took three real fixes, not one clean pass — see §36. None of the last
row is a security risk anyone has weighed and accepted — it is simply not yet exercised, and the
Stage 2 audit is explicit that it does not claim otherwise.

## 34. Baseline-proven pre-existing failures, not assumed

A full-repo `pytest tests/` run surfaced 41 failures across `test_citation_style_repository.py`,
`test_citations.py`, `test_demo_snapshot.py`, `test_frontend_assembly.py`, and
`test_website_how_it_works.py` — none of them files Stage 2 touches. Rather than infer irrelevance
from that alone, a temporary detached worktree was created at the Stage 1 baseline commit
`eddc97ed` and the same 41 tests were run there: **all 41 failed identically**, traced to a missing
`node_modules/` at the repo root (an environment gap present at both commits) and an unrelated
citeproc-styles cluster. `test_python_runtime_ids_are_current_deterministic_and_platform_specific`
was independently reproduced at that same baseline commit, failing with the identical stale-hash
value — proof, not inference, that it predates Stage 2. The reported regression result is: *full
regression suite passed excluding one baseline-confirmed pre-existing failure*, deliberately not
phrased as an unrestricted all-green run.

## 36. Three findings from actually running the installer, not from writing it

Getting CI to a genuine pass took three rounds of real failures, each root-caused rather than
patched around or re-run blind. None are security defects; all three would have shipped an
installer that produces an app that never starts — the gap between "the mechanism was designed
correctly" and "the mechanism was verified to actually work."

1. **A Stage 1 maintenance gap, not a Stage 2 or main-branch defect.** The first CI attempt failed
   before reaching any new code: the immutable Python runtime spec's stored `runtime_id` was stale.
   `origin/main`'s own `verify()` passes cleanly (checked directly); Stage 1 had edited
   `smoke_test_backend.py` — a declared `shared_inputs` identity file — without re-running
   `update-ids` afterward. Fixed mechanically, and the resulting four runtime IDs were published via
   the existing `desktop-python-runtime.yml` workflow and independently re-verified against the real
   GitHub releases before trusting them.
2. **A bare relative `!include` resolved against the wrong directory.** Tauri stages the hook file
   from a generated main script in a different build directory, so `!include
   "connector-identity.generated.nsh"` failed even though that exact file existed where the hook
   itself lives. Reproduced and fixed against the real cached NSIS 3.11 compiler before touching the
   real file: `${__FILEDIR__}` (NSIS's own "directory of the file being processed" built-in) is the
   correct, verified fix.
3. **The most severe: `callosum-shell.exe` silently never started at all.** Having the connector as
   a second `[[bin]]` in the SAME Cargo package as the Tauri app broke `cargo tauri build`'s
   main-binary selection — even with `mainBinaryName` explicitly set, the installer shipped the
   CONNECTOR's compiled bytes under `callosum-shell.exe`'s name. The "app" launching and exiting
   within milliseconds, exit code 0, no window, was actually the connector's own `main()` refusing a
   caller with no `argv[1]` and exiting cleanly — exactly as designed, for a different, legitimate
   scenario. This explains both prior CI failures under one root cause, not two. Fixed by giving the
   connector its own Cargo package (`connector-host/`) so `cargo tauri build` never sees it exist in
   the package it builds — removing the ambiguity at its root.

## 38. Five findings from actually clicking the real extension, not from writing it

Same pattern as §36: found by running the real product end to end, root-caused with direct evidence,
fixed, re-verified. Items 1-4 are defects; none are security defects; all four blocked the acceptance
run from completing or from meaning what it claimed. Item 5 is not a defect — it is a later product
reframing of item 4's fix, driven by user critique of the acceptance evidence item 4 itself produced.

1. **The dev connector's `.bat` launcher broke native messaging's own HTTP client.** Invoked as a
   grandchild of `cmd.exe` with piped stdio — exactly how Chrome invokes a native-messaging host —
   `reqwest`'s blocking client timed out connecting to `127.0.0.1` every single time; the identical
   binary invoked directly (no `cmd.exe` in the chain) connected instantly, every time, no code
   difference. Fixed by replacing the shell wrapper with `dev_connector_launcher.exe`, a tiny real
   native binary that sets the same env var and execs the real connector with no shell involved —
   dev-only, never shipped, no change to the production connector's trust model.
2. **Browser capture's admission path never fell back to a default `CrossrefClient`.** It read
   `app.state.crossref_client` directly, which is `None` for the real app's own default construction
   — the parameter exists for test injection only. `acquisition.py`'s sibling DOI-add endpoint
   already has the identical fallback, with a comment describing this exact failure mode. Effect:
   every DOI-bearing browser capture reported `unresolved_review_required` regardless of the DOI's
   real resolvability, reproduced against a real, live DOI before the fix and confirmed resolved
   (real title, `capture:browser` provenance, single row) after it.
3. **Real-machine test hazard, not a product defect: auto-scan-on-launch reached the maintainer's
   real document library.** Callosum unconditionally auto-scans "the library folder" on every
   launch, which defaults to the OS Documents directory — sensible for a real end user, but on the
   maintainer's own machine this is the same real, Dropbox-synced folder any real install would use,
   entirely independent of the isolated app-data directory this whole audit's isolation procedure
   covers. Every scan attempt failed harmlessly (confirmed zero file mutation via unchanged mtimes),
   but the request volume held the SQLite WAL writer lock long enough to cause unrelated
   "database is locked" failures and delayed a real capture past a real Edge extension service
   worker's lifetime, aborting it mid-flight. Fixed with `CALLOSUM_LIBRARY_DIR_OVERRIDE`, a new,
   narrowly-scoped env-var override in `backend.rs` (mirrors the existing `CALLOSUM_SETTINGS_PATH`
   pattern) that the acceptance harness sets to a disposable directory. A test-isolation gap the
   original isolation procedure did not cover (it isolated the database, not the separate "library
   folder" concept) — not a defect in the product's real-world behavior.
4. **A direct-PDF capture's title is a filename, not bibliographic identity — admission treated it
   as if it were.** Traced end to end: `handleCapture` branches on `looksLikePdfUrl(tab.url)` *before*
   any DOM extraction; Chrome's PDF viewer renders in its *own* extension origin (confirmed via CDP),
   which this extension has no host permission to script into, so extraction is not viable for a PDF
   tab under the current permission model at all. `buildDirectPdfEnvelope` sets only a filename-
   derived `title` — never a DOI, year, or creators. `admission.py`'s no-DOI branch (written for
   generic HTML captures, where a real title is genuine evidence) then unconditionally created a
   fresh, anonymous, unfindable paper from that filename. **Fixed at the single canonical enforcement
   point** (`admission.py`'s `admit()`, not the extension): any `pdf_bytes_from_active_tab` envelope
   reaching the no-DOI branch now returns a new, deliberately narrow status,
   `direct_pdf_identity_unresolved` — narrower than "PDFs are unsupported," since a direct-PDF
   envelope that *does* carry real identity never reaches this check and is handled by the unchanged
   rules around it. Zero mutation, no `capture_id`, so `/capture/item/{id}/pdf` cannot be called —
   which also makes the fresh-install missing-embedding-model 500 unreachable from this path,
   confirmed empirically (zero such log lines in the rerun), not just argued. Verified three ways:
   two new focused `tests/test_capture.py` tests (39 total, all passing); a direct HTTP round-trip
   against the real rebuilt packaged binary; and a real Edge rerun of B and E from a fresh disposable
   instance, both now rendering "Callosum couldn't tell what scholarly work this PDF is..." with zero
   paper/attachment/annotation mutation. A real build-pipeline gap surfaced during verification (the
   packaged binary reads Python from a build-time-copied `target/release/callosum-src/`, which
   `stage_source.py` alone does not refresh — only a full `npx tauri build` does) was caught via a
   direct HTTP check before trusting a second real-Edge run, root-caused, and closed by rebuilding
   for real. Case E's `attachment_review_required` branch remains proven separately at the component
   level, using an envelope shape today's real extension cannot produce — confirmed, not assumed, by
   the same real-Edge rerun showing E hits the identical `direct_pdf_identity_unresolved` refusal as
   B. Automatic real-browser direct-PDF-to-existing-paper reconciliation is an explicit architectural
   boundary of today's permission model, deferred beyond Phase 1, not a missing implementation.
   **(Superseded 2026-09-16 by item 5 below — kept verbatim as the correct statement for the
   terminal-refusal contract that was in force when it was written.)**
5. **(2026-09-16) A product reframing, not a defect: item 4's terminal refusal cost the user the
   artifact outright, so the contract changed to preserve-then-identify.** Item 4's invariant — a
   direct-PDF envelope's filename never becomes a canonical Paper's title — is permanent and
   unchanged; what changed is what happens instead of refusing. `admission.py`'s
   `direct_pdf_identity_unresolved` branch now accepts the bytes (`pdf_accepted=True`,
   `pdf_reason="provisional_capture"`); a new module (`app/backend/capture/provisional.py`) preserves
   them atomically in a durable Import Queue (`_Import Queue/<artifact_id>.pdf` plus a hidden
   `.provenance/artifacts/<artifact_id>.json` sidecar, both invisible to the ordinary non-recursive
   Library scan) before attempting identity from the PDF's own front-matter DOI plus title
   corroboration through the unchanged `add_paper_by_doi`/`attachment_decision` substrate. A DOI
   observed only inside a References section is excluded from consideration entirely; two competing
   strong candidates queue rather than picking a winner; the queue copy is never relinquished before a
   promotion durably succeeds (proven by a dedicated failure-injection test); content-hash dedup
   preserves the object while still recording each new encounter as its own provenance event; startup
   recovery adopts any queue file a crash left with no database row rather than discarding it.
   Verified: 51 focused `tests/test_capture.py` tests (including item 4's own refusal test, updated to
   assert the new acceptance behavior with its invariant intact); a direct-HTTP smoke check against
   the freshly rebuilt packaged binary; and a real Edge rerun of B and E
   (`run_acceptance_direct_pdf_provisional.py`) reaching genuine, non-manufactured outcomes for both —
   B queued for review (a real front-matter DOI resolved via live Crossref but its title did not
   corroborate), E reaching `attachment_conflict` through a real click and live Crossref resolution of
   a real, independently-verified-resolvable DOI seeded beforehand as an existing paper with an
   attachment — proving the attachment-safety branch reachable end to end, not merely at component
   level. Real application data verified byte-identical to baseline after isolate/restore.

## 37. Exit question for Stage 2

> **Given Stage 1 proved the backend boundary and this pass proved the host/installer/extension
> mechanism component-by-component, proved it again end to end on a clean runner, and then proved a
> real Edge click carries a real capture through to Library state — is Phase 1 browser capture ready
> to ship?**

**(2026-09-16: this answer was correct for the terminal-refusal contract §38 item 4 describes; kept
verbatim, superseded by the updated answer below, not edited to look like it anticipated item 5.)
Phase 1 browser-capture functional acceptance COMPLETE for the Edge + development/test identity
path. Direct PDFs without sufficient canonical identity are deliberately refused without mutation.
Automatic reconciliation of an identity-poor PDF tab to an existing scholarly object is deferred
beyond Phase 1.** Exactly one thing remains, and it is store-publication work, not implementation or
acceptance work: a real Chrome Web Store and/or Edge Add-ons submission producing an actual extension
id to populate `production_extension_ids` with — until then the production allowlist is empty and
fails closed by design, unchanged and untouched by anything in this session. Every other item this
document previously listed as open — CI installer lifecycle, real Edge click-through acceptance
including direct-PDF behavior — is now proven, not just complete (see §33, §36, §38). Kept explicitly
distinct: direct-PDF automatic attachment/reconciliation is a later capability; production store/
native-host identity is a later, separate distribution gate.

**2026-09-16 updated answer, superseding the above (§38 item 5):**

> Direct-PDF capture preserves the user-accessed artifact immediately without fabricating canonical
> identity. Callosum then attempts evidence-based identity resolution; sufficiently supported matches
> are promoted/reconciled into the Library, while uncertain captures remain in a durable Import Queue
> for review.

This is now proven, not just implemented: a real Edge rerun of B and E
(`run_acceptance_direct_pdf_provisional.py`) reached genuine `pending_review` (B) and
`attachment_conflict` (E) outcomes through real Crossref resolution, not a manufactured or forced
result. `production_extension_ids` remains `[]`, unchanged. Kept explicitly distinct: production
store/native-host identity is a later, separate distribution gate, untouched by this reframing.
