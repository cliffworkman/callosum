# Build now — Literature acquisition: the legally-clear lane

**Disposition for CC:** BUILD. This is the legally-clear lane of the acquisition track; the legally-ambiguous
lane is a separate, deferred, counsel-gated prompt (`…_nuanced-lane_DEFER.md`) — keep it **strictly out of
scope here.** Build into the current **local-first app; no accounts required** (this lane is low-risk and
local-first-compatible). **Run the Principles alignment gate (rule #9)** — expect a clean pass; OA fetch is the
cleanest possible acquisition — **and the security audit gate** (this adds new external fetches + a new
file-ingestion path). Build in the increment order below; **ship Increment A first** so it can be tested against
a real "wanted" list.

## What this lane is
Resolve a paper (by DOI / PMID / title) to a **rights-holder-authorized open-access copy** and import it into
the local library, fully in-app. Every copy that lands is one a maintained legal-OA database says is free —
**never decided by our own crawler.** Files land in the **user's local library; nothing is hosted or relayed
server-side.**

## Bright lines (veto-level — do not cross)
- OA judgment is **delegated to the databases** (OpenAlex / DOAJ / CORE), never to a Callosum crawler.
- **Local-first ingestion** — fetched PDFs go to the local library; no server-side storage.
- The **resolver registry is not a generic fetcher** — resolvers return only authorized-OA copies/links; there
  is **no "fetch arbitrary URL / fetch non-OA" escape hatch.**
- The **wanted-list re-checks OA databases only** — no hook to anything else; the connector and the other
  nuanced tiers **do not exist in this build.**

## Increment A — minimal viable clean fetch (ship this first)
- A **resolver registry** behind a Protocol (mirror the discovery SourceProvider-registry pattern; swappable,
  self-registering).
- The **OpenAlex resolver** as primary — it covers gold/green/bronze via its OA-location data and supersedes the
  now-legacy Unpaywall; send the `email` polite-pool parameter. Given a DOI/PMID/title → the best authorized OA
  PDF location.
- **Fetch + import** to the local library via the existing save/import path.
- **Labeling on every copy:** version (version-of-record / accepted-manuscript / preprint) + **OA color, with a
  distinct "bronze" flag marked unstable** (free-to-read-without-license can revert to paywalled — never present
  it as durable) + provenance + the resolving source.
- Validate the fetched PDF at ingest (rule #4: cap size, verify it is a PDF, never build a path from an
  unsanitized title); httpx timeouts; fail closed on a bad response.

This alone gives a working OA-fetch that a real wanted/dire list can be run through.

## Increment B — fan out the resolvers
Add, as registry providers, **gold-first** in the cascade: **DOAJ** (confirm gold), **CORE** (repository full
text — the main green resolver beyond OpenAlex; free key, accept its T&C, respect rate limits), direct
**arXiv / bioRxiv / PsyArXiv / PMC OA-subset** fetch, and **Crossref** (preprint↔VoR relations + license
metadata; `mailto` polite-pool). The cascade tries gold → green → preprint, stops at the first authorized copy,
and labels the version.

## Increment C — the wanted-list (+ optional measurement)
For misses, record a **wanted item**; a periodic re-check queries **only the OA databases** (a paper locked
today may be self-archived later). **No other code path may touch the wanted-list.** Optional but recommended:
a small **coverage readout** — what fraction of saved/wanted records resolved to a clean copy, by tier and
field — so the clean-first → measure → decide gate for the deferred nuanced lane runs on real numbers. (This is
the instrument for evaluating a real "dire papers" list.)

## Gates
- **Principles gate (rule #9):** run it; expect a clean pass — label honestly, show provenance/version/OA-color.
- **Security audit gate:** fires (new external fetches + new file-ingestion path). Document input validation
  (API response shapes, PDF validation at ingest, size caps, file-path safety), external-call handling
  (timeouts, fail-closed, SSRF), supply-chain (pin + audit any new deps), and the OA-only-wanted-list guarantee.
  End **PASS** or **RISK ACCEPTED BY USER.**
- **Terms / attribution:** OpenAlex / CORE / Crossref polite-pool identifier (`email`/`mailto`); CORE T&C; honor
  rate limits — ignoring these turns a "clean" integration into a terms violation.

## Out of scope (the separate deferred lane)
The browser connector, entitled-subscription fetch, GetFTR/LibKey signaling, author-request, ILL handoff, and
paid document delivery — all in `…_nuanced-lane_DEFER.md`, gated behind a tiered-account structure and Penn
legal counsel. **Do not build them, scaffold a seam for them, or reference them as reachable here.**

## Callosum-fit
Resolver registry mirrors the SourceProvider registry; deterministic-first cascade; provenance/version/OA-color
labeling feeds the integrity layer (and the planned RETRACTED cross-cut); reuse the library save/import path.

## Tests
- The cascade resolves a DOI to an authorized OA copy via OpenAlex (then DOAJ/CORE/preprint) and imports it,
  **labeled with version + OA color**, bronze flagged distinct.
- A new resolver registers **without editing the cascade** (registry proven).
- The wanted-list re-check queries **only** OA databases; a test asserts **no code path** lets it reach anything
  else.
- The registry exposes **no arbitrary-URL / non-OA fetch path** (structural test).
- No fetched copy transits a server; everything lands in the local library.
- A fetched non-PDF / oversized response is rejected at ingest.

## OUTPUT
The resolver registry + OpenAlex resolver (Increment A); the fanned-out resolvers (B); the OA-only wanted-list +
optional coverage readout (C); version/OA-color/provenance labeling with the bronze instability flag; the
security-audit doc; and confirmation the bright lines hold (delegated OA judgment, local-first ingestion, no
escape hatch, nuanced tiers absent).
