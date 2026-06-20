# Callosum — Approach / Avoidance

*The value substrate beneath `PRINCIPLES.md`.

`PRINCIPLES.md` says **what** to build and **how** (with worked code contrasts). This document sits
*beneath* it: the deeper commitments that **explain why those principles exist**, surfaced from what
Callosum actually is. Where a principle is a rule, a value here is the thing the rule serves — fewer,
more abstract, and **generative**: when a future-track has no principle covering it yet, you derive
the right one from the value.

The name is deliberate. A value has two faces. **Approach** is what Callosum moves *toward* — the
commitments its features optimize for. **Avoidance** is what it moves *away from* — and some of that
is not merely the shadow of an approach value but a standalone refusal (a hard boundary the tool will
not cross regardless of utility). Both belong in the value space.

## How these were surfaced (and the honest limits of the method)

This is **revealed preference**: values read off the choices in the built code, not professed in the
abstract. That yields the *operative* value structure — what the artifact actually optimizes for —
which is more trustworthy than a wish list, and occasionally more revealing than its author expected.

Three guards keep it honest:

- **Value vs. constraint vs. contingency.** A real value is load-bearing across *independent* choices
  and shows up where the easy path was available and declined. A property forced by environment
  (local because no compute budget) is a constraint, not a value — unless it recurs as a commitment
  beyond what the constraint requires, at which point it has *become* a value. Noted inline where it
  matters.
- **Evidence-linked.** Each value cites the specific code/choices that reveal it — applying
  Callosum's own inspectability rule to itself. A value asserted without its evidence is the
  verdict-without-pointer the project forbids.
- **Settled vs. unsettled.** The **built codebase** (through Increment 73, already past the
  worth-building filter) is treated as primary evidence of operative values. The **future-tracks** are
  treated as unsettled — hypotheses about the value space, not yet earned. *Caveat:* a feature can be
  worth-building yet trade against a value held elsewhere, so internal tensions in the built code are
  findings too, not assumed away.

---

## Part I — Approach (what Callosum moves toward)

### A1. The user's judgment is the product; the tool's is not.
The system exists to strengthen the reader's own discernment, never to stand in for it.
**Evidence:** synthesis is presented "as inspectable evidence rather than authority" (README thesis);
manual axis assignments are stored as `confidence=NULL` to mark them as human overrides and are
**preserved across every re-score** (`axis_scoring.restore_manual_assignments`) — the machine never
overwrites a human call; duplicate detection is **flag-only**, the user resolves every group;
confirm-and-learn on uncertain axis members. **Generates:** PRINCIPLES #2 (signal not verdict), #5
(human is the filter).

### A2. A claim is earned against its source, or it does not stand.
Grounding is not a feature of the output; it is the precondition for the output existing.
**Evidence:** the local verification layer scores three *independent* axes — retrieval, verbatim
quote, and NLI entailment — and resolves to **verified / weak / unverified**
(`summarization/verification.py`); the quote must be literally contained in the cited chunk
(`canonical_text_contains`); evidence carries coordinate precision marked honestly as `exact` vs
`region`; and the token cache "**never serves stale verification**" — verification reruns on every
cache hit (`llm/cache.py`), so the cost optimization is not allowed to weaken the grounding.
**Generates:** PRINCIPLES #1 (evidence), #4 (deterministic substrate).

### A3. Uncertainty and limits are shown, never hidden — including the project's own.
The tool would rather show a weak signal honestly than a strong one falsely.
**Evidence:** the verified/weak/unverified tiers; `uncertain` as a first-class axis status with
`_never_empty_uncertain` (show the closest few, *marked uncertain*, rather than an empty axis or false
confidence); confidence shown literally ("a paper shown as 0.35 is never tagged uncertain"); and the
reflexive case — the README instructs that "implementation should not claim more certainty than the
code can show," deferred integrations are labeled "Planned - not yet implemented," and dead
directories are named as such. **Generates:** PRINCIPLES #6 (silence is not a certificate), #8
(inspectability).

### A4. The user owns every irreversible act; their data and corrections are never silently overwritten.
**Evidence:** Details edits merge **only the changed fields** into a copy of the record — "never a
blind full re-projection, which would wipe csl fields the edit didn't touch" — and stamp
`user-edited` provenance that keeps them out of the batch-enrich path (`metadata/paper_edits.py`);
authors round-trip losslessly with "no fragile name parsing"; `RESERVED_CSL_KEYS` protect structured
fields from corruption; deletion is **soft-delete → trash → restore**, with permanent delete explicit
and trashed-only; **nothing is auto-merged**, and library merge is deferred *precisely because* it is
destructive. **Generates:** the care/anti-clobber commitments under PRINCIPLES #3 and #5.

### A5. Local-first, and the user is sovereign over what leaves the machine.
This began partly as a constraint (privacy, no compute budget) but is now **load-bearing as a value**:
the egress gate is enforced even where a cloud call was the easy path.
**Evidence:** embeddings, retrieval, and verification are fully local (`sentence-transformers`,
`sqlite-vec`, in-process); Gemini is **off by default**; any source-text egress must pass the
`CALLOSUM_ALLOW_DATA_EGRESS` consent gate, enforced at the DI seam as the *authoritative* boundary and
checked **outermost** so "a cache hit can never bypass the gate" (`llm/egress.py`); the help assistant
has a **separate, narrower** toggle because it sends only the question + public docs, never library
text. Its other face is **access**: a local, free tool needs no subscription or institutional login,
which is where this value meets equity (A8). **Generates:** PRINCIPLES #10 (local-first / provider-swappable).

### A6. Deterministic, inspectable mechanism first; the model is the last resort, and always swappable.
**Evidence:** duplicate detection runs **deterministic layers first** (shared IDs → title/author/year)
and admits the fuzzy embedding signal only at a high threshold, "so the deterministic ones lead";
planned author resolution is **LLM-free**; Gemini only *polishes* cluster labels with a guaranteed
local fallback ("never 503"); providers sit behind Protocols with an injected-or-default seam; and
provider-generated TLDRs are to be "kept distinct from source evidence." **Generates:** PRINCIPLES #4
(deterministic substrate), #10 (provider-swappable).

### A7. Cost is measured, not guessed — and never traded against verification or consent.
A revealed *ordering*: where thrift conflicts with grounding or consent, thrift yields.
**Evidence:** token usage is logged read-only "so real spend can be measured and the deferred cost
levers sized" (measure before optimizing, `llm/usage.py`); the cache is the "dominant cost lever" yet
sits **inside** both the egress gate and the verification step, so neither is ever skipped to save
tokens (`llm/cache.py`). **Generates:** the cost-discipline posture behind the future-tracks' "frugal,
cached, on-demand" rules.

### A8. Access to the tool, and to the research it engages, should not be gated by wealth or position.
This is the **generative** value — the prestige-bias observation that motivated HACKADEMIA and seeded
several of the features now planned here. It is revealed not in feature behavior but in the project's
**political economy**, which is a revealed choice as much as any line of code.
**Evidence:** **AGPL-3.0** — a strong *network* copyleft, chosen deliberately for open-science
alignment: its Affero clause (Section 13) closes the SaaS loophole that ordinary GPL leaves open, so
even a **modified, network-hosted** Callosum must offer its source. Anything built on Callosum's bones
— including as a hosted service — must stay as open as Callosum itself; a **public repository**;
**local-first reread as free access** — a tool
that runs on your own machine needs no subscription and no institutional login (A5's other face); and
the acquisition resolver's whole premise — an ordered **free-and-legal** OA chain whose explicit point
is that ability to pay must not gate access to research. Money should not decide who can engage with
work that bears on everyone. **Two faces, at different stages:** *access equity* (who can use the tool
and reach the literature) is **revealed in the built project today**; *attention/credit equity*
(countering prestige bias in *what* gets read and valued — the overlooked-work lens, citation-credit
signals) is endorsed and planned but not yet built. **Generates:** the access posture behind Track D,
the equity/integrity signals, and the no-circumvention boundary (equity pursued *within* legal limits).

---

## Part II — Avoidance (what Callosum moves away from)

### Refusals enforced in the built code (the disciplined inverse of the approach values)
- **No AI output as authority.** Nothing renders a verdict; synthesis is evidence the user judges (A1, A2).
- **No opaque composite score.** There is, in fact, no composite quality number anywhere in the code —
  verification keeps its three confidences *separate*; dedup shows reason *and* confidence as distinct
  fields. The temptation to collapse signals into one rank is declined structurally (A3).
- **No silent or automatic destruction.** No auto-merge, no blind re-projection, no hard delete without
  an explicit trashed-only step (A4).
- **No egress without consent, and no bypass of the gate** by cache or convenience (A5).
- **No provider summary masquerading as source evidence** (A6).
- **No overclaiming** — not in the UI, not in the READMEs about themselves (A3).
- **No becoming a gated, proprietary, or extractive tool** — the AGPL-3.0 network copyleft enforces that
  Callosum and its descendants stay open and free to run, even as a hosted service; access is not to be
  re-gated behind payment (A8).

### Standalone hard boundaries (avoidance that no approach value generates)
- **No paywall circumvention.** The acquisition resolver is free-and-legal only; Sci-Hub-style
  bypass is excluded "in any form — fetcher or link-builder," and the chain ends at an honest "no free
  full text found." This is not the shadow of a value Callosum approaches; it is a line it will not
  cross. *(This is the clearest case for the approach/avoidance framing — it has no approach face.)*
- **No reaching into other tools' protected stores.** Mendeley import is to go "through Zotero's
  bridge or exported BibTeX/RIS/CSL-JSON rather than direct encrypted local-database reads" — a refusal
  to circumvent another system's boundary even when it would be convenient.
- **No accusation of individuals.** Carried from the integrity/forensic future-tracks ("signal, never
  accusation"); in the built code it shows up as the absence of any feature that judges a person.
  A standalone boundary the equity/integrity tracks must inherit.

---

## Part III — The built value space vs. the planned one

Built values are treated as settled; the future-tracks are characterized against them four ways.
Most are **confirmed** — unsurprising, since they passed ideation and the principles gate. The useful
content is in the other three columns.

**Confirmed** (planned extends a built value consistently):
- Highlight-to-evaluate (Track C) reuses the verification spine wholesale (A2).
- The gap-finder and My-Publications attach **provenance per candidate** and stay add-or-dismiss (A1, A4).
- The findings subsystem's **FACT vs. candidate** split mirrors verified vs. uncertain (A2, A3).
- The literature feed's "highlight, **never filter** the complete list" mirrors augment-not-replace (A1).
- The acquisition resolver's honest "not found" terminal mirrors show-the-limits (A3).
- **Access equity (A8) is already revealed** — AGPL copyleft, the public repo, local-first-as-free-access,
  and the free-legal acquisition chain; the planned discovery/acquisition tracks extend it consistently.

**Extended** (a value the built code can only partially express; planned features complete it):
- **A5 local-first is incompletely encoded.** The stack is local for embeddings/retrieval/verification
  but still cloud (Gemini) for *generation*. The value reaches further than the code does; planned
  local-LLM work would complete it. This is the "incomplete capture" case exactly.
- **A2 verification is built for *citation* grounding only.** The THEORY contract (retrieve-then-attribute
  for conceptual synthesis) extends the same value to a harder surface the code hasn't reached.
- **A6 determinism** is extended by the planned deterministic Methods producers (statcheck, GRIM, p-curve).

**Emergent** (present in the plans, absent from the built artifact — adopt deliberately, do not drift into):
- **Attention/credit equity.** Access equity (A8) is already revealed (above); its *other* face — the
  overlooked-work lens and citation-credit-concentration signals that counter prestige bias in *what*
  gets read — is endorsed and planned but not yet built. This half is the emergent one: adopt it
  deliberately and in the repointed, non-accusatory form, not by drift.
- **Writing assistance.** The built tool reads and organizes; Track B/C make it *act on a draft* — a
  posture shift the code comments themselves flag ("this is where Callosum becomes a writing-assistance
  tool"). Emergent, and to be examined against A1.

**Divergent** (a planned direction that pulls *against* a built value — the actionable flags):
- **Opinionated AI under time pressure vs. always-run verification (A2).** Track C and the
  critical-review supplement are stronger, more opinionated actions; their verification risks being
  *higher-friction* exactly when the built value is "verification actually happens." The backlog
  already names this as the **auditability standard** open question — a well-flagged divergence, not a
  hidden one.
- **The scoring temptation vs. no-opaque-score (A3/Part II).** Effect-size, and any HACKADEMIA-derived
  "index," tempt toward the composite number the built code scrupulously avoids. A divergence *risk*,
  fenced by PRINCIPLES' worked examples — keep watching it.
- **Equity-as-exposure vs. no-accusation (Part II).** If equity features are built in HACKADEMIA's
  native posture (public flagging, indices, indictment), they violate the built no-accusation and
  user-private boundaries. The repointing to private signal is the fix, and it is mandatory, not optional.

---

## Part IV — Candidate heuristics for future-tracks

The sticking points above, distilled into best-practice rules to design *toward*:

1. **Keep signals separable.** If you are tempted to combine components into one number, that impulse
   *is* the divergence. Surface the parts (the way verification keeps three confidences and dedup keeps
   reason + confidence). No composite quality score, ever.
2. **Make verification cheaper as features get more opinionated, not merely present.** The value is
   "verification happens under stress," so measure its friction. A stronger AI action raises the bar
   for how low-friction its check must be.
3. **The stronger the action, the more the human gates it.** Suggest, evaluate, critique, acquire — each
   leaves the irreversible act and the final judgment to the user. Never auto-insert, auto-merge,
   auto-judge.
4. **Repoint imported capabilities before they touch the code.** Anything carried from an exposure/activist
   posture becomes private, inspectable signal-for-the-user first — the built values reject accusation
   and public indictment.
5. **Extend local-first as capability grows.** A new external dependency must justify why it can't be
   local, and must route through the egress consent gate and the swappable-provider seam.
6. **State coverage; never let absence read as a clean bill.** Every new signal says what it did and did
   not check (the never-empty-uncertain and honest-not-found pattern, generalized).
7. **Adopt emergent values on purpose.** Writing-assistance, and the *attention/credit* face of equity,
   did not come through the artifact; name them as new commitments and check them against this value set
   before building, rather than letting the tool drift into a posture no one chose. (Access equity, by
   contrast, is already revealed in the licensing and distribution choices.)

---

## Status and open findings

This is a **first draft for refinement**, not a verdict. Three diagnostic findings fall out:

- **A scope correction (made in this revision).** The first pass read "the built artifact" as *feature
  behavior* and concluded equity was emergent/unbuilt. That was too narrow: **licensing, distribution,
  and access-design are revealed choices too** — and read there, equity (A8) is one of the
  better-evidenced values (AGPL copyleft, public repo, local-first-as-free-access, the free-legal
  acquisition chain). The lesson generalizes: revealed preference lives in a project's political economy,
  not only its functions.
- **Operative-but-unarticulated values** — present in the project, absent from PRINCIPLES, candidates to
  promote: **A8 access-equity** (and the copyleft commitment behind it), **A7 cost-honesty** (thrift
  yields to verification/consent), **A4's no-silent-clobber**, and the **standalone hard boundaries** (no
  paywall circumvention, no encrypted-store reads), which read more as ethics than as build-rules and may
  deserve their own explicit home.
- **Aspirational-vs-encoded** — PRINCIPLES' commitments are, encouragingly, all evidenced; the one
  *partially* encoded is local-first (A5), cloud generation being the gap. Healthy aspiration ahead of
  implementation, not a contradiction — but worth tracking as the local-LLM work is weighed. (Note the
  symmetry: the *attention/credit* face of equity is the mirror case — a value endorsed ahead of the
  features that would encode it.)
