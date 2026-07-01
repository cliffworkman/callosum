# Increment 233 — Citation context SP2: "how this paper cites its sources" (completes B4)

The outgoing mirror of the inc-232 SP1 panel. A toggle in the same METHODS panel: **How it's cited** (SP1, incoming —
how others cite this paper) ⇄ **How it cites its sources** (SP2, outgoing — how this paper uses each of its own
references).

## The realization that made SP2 easy

I'd flagged SP2 as "fiddly — needs in-text-citation → reference linking." But Semantic Scholar's **`/references`**
edge returns, for each paper the focal cites, the **context sentences** — the sentences *in the focal paper* where it
cites that reference. **S2 has already done the linking.** So SP2 is a near-mirror of SP1 (`/citations`), with no
local citation parsing: the only differences are the edge, and that each item's NLI hypothesis is the **cited paper's
own claim** (not the single focal-paper claim).

## Implemented

- **`integrations/semantic_scholar/adapter.py`** — generalized the fetch into `_fetch_edge(conn, doi, *, edge)`
  (`edge` is a fixed literal `"citations"`/`"references"`, never request-derived). `fetch_citation_contexts` and the
  new `fetch_reference_contexts` are thin wrappers. `CitingContext` gained a `claim` field: for the `references` edge,
  `_parse` sets it to the cited paper's abstract (else title) — S2 abstracts are plain text, so no cleaning + no
  cross-layer import. The `references` fetch requests `citedPaper.abstract`; caches under `references:{doi}` (separate
  from `citations:{doi}`). Removed the now-unused `S2_CITATION_FIELDS` constant (rule #5).
- **`app/backend/methods/citation_context.py`** — the classifier's hypothesis is `ctx.claim or focal_claim` (the
  per-item cited claim for SP2; the constant focal claim for SP1). SP1 is untouched (ctx.claim=None → focal_claim).
- **`app/backend/api/routers/citation_context.py`** — a strict `direction: Literal["citations","references"] =
  "citations"` on the request; the worker branches (references → `fetch_reference_contexts`, `focal_claim=""` since
  the claim is per-item; citations → the SP1 path).
- **`app/frontend/js/08c_methods_citation_context.jsx`** — an `[How it's cited | How it cites its sources]` toggle
  (`.citec-toggle`) that resets to idle on switch; the intro / button label ("Fetch citations" vs "Fetch references")
  / empty-state copy / coverage noun adapt to the direction; the POST carries `direction`. The per-item card is
  direction-agnostic (a paper + its sentence + stance).

## Honesty (inherited from SP1)

Same posture: counts never a composite score; the citing sentence is always the evidence; a labeled signal, not a
verdict; an unclassifiable citation counted not guessed. For the outgoing direction, a "contrast" describes the
**focal paper's own** rhetorical move *in the shown sentence* (e.g. "unlike X, we found…"), never an accusation.

## Verification

`HF_HUB_OFFLINE=1 python -m pytest tests/test_citation_context.py -q` → **9 passed** (+3: the `references` edge parses
`citedPaper` + the per-item claim [abstract else title] + requests `citedPaper.abstract`; the classifier uses the
per-item claim; the endpoint runs with `direction=references` and classifies outgoing). Full suite **834 passed, 1
skipped**. QA surface **169/169 API + 737/737 FE, 0 uncovered** (the `direction` param rides the existing endpoint;
the toggle is claimed by `route_53`). No migration, no new dependency; public-metadata egress (DOI → Semantic
Scholar), NOT the Gemini gate; classification local. Audit addendum PASS.

**The live Semantic Scholar round-trip on a real DOI is the maintainer's spot-check.**

## B4 complete

SP1 (incoming, inc 232) + SP2 (outgoing, inc 233). Possible later: Semantic Scholar intents as a supplementary tag; a
library-wide most-contested/most-supported facet; report caching.
