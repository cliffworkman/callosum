# Future track — PUBLISHERS (a where-to-submit METHODS tool)

**Disposition for CC:** Capture into the backlog + `.claude/docs/future-tracks/`. **Do not build yet.** More
controversial than most tracks; the principled design below is the point of the doc — build only this shape, and
run it through the Principles gate + values layer at graduation. Depends on the Word bidirectional link and local
embeddings.

## One line
At the moment of deciding where to submit, surface **verifiable facts** about each candidate journal — who can
read the result, what it costs *you* to make it open, and whether the journal is a vetted part of the scholarly
record — and let the author weigh them, with the open-science weighting they choose.

## Governing principle (the whole rescue)
**It surfaces facts and lets the user weigh them; it never computes a verdict.** This is Callosum's
verify-everything ethos applied to journal choice: a journal profile is the same kind of object as a citation —
inspectable evidence, traceable to a source, never authority.

## Elevation, not denigration (the valence rule)
When open-aligned journals rank above the rest, the meaning is **"these carry goods worth underscoring"**
(diamond OA, a green route, registered-reports support), **never "the others are bad."** Copy frames positively —
what the elevated journals *offer*, not what the rest *lack*. Subordination is a relative absence of underscored
goods, not a verdict of badness.

## Scope — three tiers
- **Minimum (build this):** the factual profiles (incl. explicit APC) + an open-science **weighting** that lets
  the user's preference move the ranking (the thumb) + the equitable legitimacy gate that keeps the weighting from
  boosting predators + local matching + egress discipline. This is the one thing the tool *needs*: factoring
  open-science alignment into the recommendations.
- **Near-term enhancement:** the **first-use choice gate** — no default until the user sets one (open-science
  weighting as one local, never-transmitted setting); dissolves the default dilemma on the answer by privileging
  neither on nor off; legibility carried at the output thumb.
- **Far reach (persist with caveats, don't build yet):** user filtering/exclusion (disfavored vs. elevation — see
  below), thumb auditability, stale-preference re-surfacing. Kept here **with their ethical caveats** so the thread
  survives.

## Veto-level lines (this tool specifically)
- **No predatory classifier and no "predatory" tag.** Strongest form of advocating against a named journal;
  defamation risk, undefinable category, reproduces an anti-non-Western bias. Forbidden.
- **No composite score** — not "openness," not "legitimacy." Show the components.
- **No "accessible through Callosum" framing.** Anchor on access in the world (readers + authors).
- **The abstract never leaves the machine.** Match locally; do **not** integrate Elsevier/Wiley JournalFinder
  (leaks the unpublished abstract to a closed publisher and biases toward their journals).
- **No editorial judgment on any journal** — only transparent, user-weightable facts.

## Workflow
1. Author highlights the abstract in the linked manuscript (Word bidirectional link).
2. **Local match** — local embeddings compare the abstract against open journal metadata (aims/scope, recent
   titles). The abstract is never transmitted.
3. A **uniform factual profile** is shown for each candidate (same schema for every journal).
4. The author sees results under their chosen open-science weighting, and can adjust it.

## The uniform journal profile (same fields for every journal; every field links to its source)
- **Fit / similarity** (local embedding match to the abstract).
- **OA status + color** (gold / hybrid / green-only / diamond / closed), from OpenAlex/DOAJ.
- **APC + waiver policy** — listed fee *and* whether a waiver/discount policy exists (DOAJ records both): "listed
  fee, may vary; waiver policy: yes/no/link." Diamond OA (no fee, free both ends) surfaced as the equity ideal.
  High APC is **cost information, not a flag**.
- **Self-archiving / green route + embargo** (Open Policy Finder / Sherpa-RoMEO).
- **License** (CC-BY, CC-BY-NC, etc.).
- **Registered-reports / preregistration support** (Cortex as exemplar).
- **Data / code sharing policy.**
- **Transparency (TOP Factor)**, from the Center for Open Science.
- **Open-sourced impact metric** (SJR/Scimago or OpenAlex-derived), shown as **one fact among many, not the
  headline**, with the caveat that impact metrics carry their own Matthew-effect bias. **Not** the licensed JCR
  impact factor.
- **Legitimacy signals** (see the equitable gate).

## The open-science weighting (the thumb)
- **Visible, adjustable, overridable.** The user sees *how much* openness is moving a given ranking and can dial
  it — visibility is what separates honest advocacy from steering.
- **No default — the user chooses (and why):** there is no value-free default. Ranking by abstract-to-scope fit
  alone (thumb off) is itself a value choice that passively inherits the field's prestige structure (favoring
  established, well-resourced, often closed venues); a thumb on is a visible value. Since *neither* is neutral, the
  honest move is to privilege neither — no pre-selected default; the user authors the choice (see the first-use
  choice gate). **Legibility:** the chosen weighting's state is always shown at output, so it never operates
  unseen.
- **Advocacy is structural, not a soapbox:** elevate the leaders (transparently), show every journal's facts, let
  informed choices pressure publishers. No banners preaching open science.

## First-use choice gate (no default until the user sets one)
The open-science preference is **one setting among ordinary tool settings**, not a standalone values question — a
dedicated open-science questionnaire singles out the value and reads as a loyalty test, and given how pervasively
open-science-flavored Callosum is, that anxiety persists no matter the assurances. But the deeper move is that
**there is no default — on, off, or otherwise — until the user sets one.** Nothing is pre-selected; the tool
produces no output until the user makes the choice. This **dissolves** the no-neutral-default problem on the
answer rather than relocating it: with no option privileged as the starting state, neither on nor off is imposed,
and the user genuinely authors the weighting. It also gives the gate a real job a pre-fill never had —
guaranteeing a genuine choice precedes the first output.
- **Gate first use on a light "set your preferences" step**, justified by workflow: the tool pulls the abstract
  from Word, so the choice should exist before the first run for the first output to reflect it. First invocation
  from Word bounces focus back to Callosum; thereafter it runs inline.
- **No pre-selection.** The weighting starts unset; the user must actively choose before output. Residual
  influence shrinks to presentation framing (order, wording), handled by neutral copy — not a pass-through default.
- **The de-singularization resolution:** *force all the consequential publisher defaults*, not just the
  open-science weighting — so the weighting is one forced choice among peers, never the lone unset field that
  would re-singularize it as a purity test. (Cosmetic-only prefs needn't be forced; don't pad the set with
  invented choices.) See the dedicated gate spec, `opus4.8_future-tracks_publishers-choice-gate.md`.
- **Forced choice has its own failure mode:** a flippant click-to-proceed is noise dressed as a choice, arguably
  worse than an honest default because it launders a thoughtless click as "chosen." The always-visible **output
  thumb** recovers it — a hasty pick is visible and adjustable exactly where it bites.
- **The irreducible floor:** compelling the choice is itself a (mild) meta-stance — that the weighting matters
  enough to require an answer. Not neutral either, but the most defensible residual: the imposition is pushed to
  "you must decide," not "we decided for you."
- **De-singularize is not conceal.** "Don't draw attention" means *don't dramatize or moralize* — never *make it
  easy to miss*. A setting the user clicks past without registering is the invisible thumb we rejected as less
  honest.
- **Legibility lives at the output, not the onboarding.** The results view always shows the thumb's state inline
  ("open-science weighting: on — N journals elevated for [goods]; adjust"). That inline cue prevents the
  expectation-mismatch misread in the moment it would occur, and it lets onboarding stay quiet (anxiety down)
  while use stays legible. **Pull the output thumb and quiet onboarding becomes the dishonest invisible-default**
  — so the output thumb is non-negotiable; it earns the right to a low-key setup.
- **Local-only, never transmitted, inspectable:** preferences live in the never-transmitted local store, behind
  the egress gate; device-local or E2E-encrypted if ever synced. Stated where the user sets them.
- **Modifiable anytime** in the settings modal; a shared local open-science-preferences mechanism, kept light.

## The legitimacy gate — done equitably (the heart of the rescue)
- **Positive signals only, gating the *boost* never the *listing*.** A journal clearing nothing still appears,
  with its facts. Legitimacy is the presence of checkable facts, never a verdict.
- **Multiple independent routes:** DOAJ inclusion, COPE membership, OASPA membership, indexing in
  PubMed/Scopus/MEDLINE, society affiliation, a verifiable named editorial board.
- **Global-South / regional infrastructure on equal footing** — African Journals Online, SciELO, Redalyc,
  Latindex, the DOAJ Seal — the indexes carrying legitimate non-Western journals that Scopus/WoS miss. The active
  anti-bias move, not just bias-avoidance.
- **Absence is shown as absence**, stated as fact, with explicit text that it is common for new and regional
  journals and is **not** a judgment.
- **Never let "open" or "indexed" substitute** for the author's own scope/quality judgment.
- **Warn by showing, not judging.** A journal clearing no signal presents an empty factual profile a careful
  author can read. For more, surface **attributed third-party** assessments (a Cabells listing if licensed, a
  DOAJ delisting) as facts the named source vouches for — never a Callosum-computed label.

## Equity as a first-class constraint
The tool must not code *unfamiliar / non-Western / new = bad*. The positive-signal, multi-route,
regional-inclusive, gate-the-boost-not-the-listing design is how that constraint is met — the
anti-overgeneralization commitment made operational.

## Reach-toward: user filtering (persist, don't build yet)
Per the valence rule, the deferred mechanism should **elevate**, not exclude. Hard exclusion is the disfavored
extreme — it reintroduces the "these are bad" valence. If ever built:
- **Collapse, never delete** — "N journals hidden by your filter — show," so nothing happens behind the user's
  back and the option to peek remains.
- **User-initiated only; the tool imposes no filter.** A user hiding closed-access journals applies *their*
  criterion to transparent facts; Callosum does not label those journals.
- Auditability of the thumb (a neutral pre-weighting ordering viewable beside the weighted one) and periodic
  re-surfacing of stale preferences belong here too.

## Data sources (all facts traceable/linkable)
DOAJ (OA, APC, waiver, Seal), OpenAlex (OA color, metadata, impact), Open Policy Finder / Sherpa-RoMEO
(self-archiving), TOP Factor (COS), COPE & OASPA (membership), PubMed/Scopus/MEDLINE (indexing),
AJOL / SciELO / Redalyc / Latindex (regional legitimacy), SJR/Scimago (open impact). Local embeddings for matching.

## Egress / privacy
The abstract is matched **locally** and never transmitted. Open-science preferences are **never transmitted**
(local store, behind the egress gate, inspectable). External calls fetch **journal metadata** only, behind the
egress consent gate. No closed-publisher JournalFinder integration.

## Callosum-fit
Lives in the METHODS module; uses the Word bidirectional link and the local-embeddings stack; profiles are
inspectable facts (verify-everything); no composite scores (consistent with PRINCIPLES). The corrected
augment-never-filter reading: the tool never *imposes* a filter; the user always may (same correction applies to
the discovery spec). Preferences are a shared, local, never-transmitted mechanism.

## Open decisions
- **Default state of the thumb** — *resolved: on*, on the no-neutral-default reasoning, conditional on legibility;
  elicitation is the preferred way to set it, with default-on as the skip-default.
- **Grain of the open-science preferences** — per-feature toggles vs. one coherent "how much should Callosum's
  open-science commitments shape what I see" control (fragmenting into many toggles may obscure the overall thumb).
- **How the weighting is set** — *resolved:* no default until the user sets one (no pre-selection; no output until
  chosen), and *all* consequential publisher defaults are forced together so the weighting is never the lone
  spotlighted choice. On the meta-stance (that compelling the choice signals the question matters): *accepted, not
  neutralized* — Callosum is itself a perspective on how science could work, so the goal is to minimize the
  imposition, not counterfeit neutrality. Friction is deliberate and one-time. See
  `opus4.8_future-tracks_publishers-choice-gate.md`.
- **Regional-index rigor equivalence** — counting inclusion-in-any equally risks laundering a weak journal through
  a lax regional index.
- **Licensing Cabells** for attributed third-party signals — optional, deferred.
- **Separate tool vs. a weighting on discovery/search** — folding in may reduce surface area and the editorializing
  feel; standing up "PUBLISHERS" makes it discoverable.

## Tests / acceptance criteria
- **No composite score** ever emitted; **no journal ever labeled predatory.**
- The **abstract never leaves the machine** (test asserts no transmission of selected manuscript text).
- **Open-science preferences never leave the machine** (test asserts no transmission).
- A journal with **no legitimacy signals still appears** (gate-the-boost-not-the-listing).
- **Regional-index signals count equally** toward legitimacy with Western indexes.
- The thumb's influence is **visible and adjustable**, and fully overridable; the legibility bar is met.
- First use is gated on a **choice step** with **no pre-selected default** for the open-science weighting (no
  output until the user chooses), the weighting presented as **one setting among others**; the **results view
  always shows the chosen weighting's state inline** (output legibility).
- **Every shown fact links to its source.** Absence of a signal renders as neutral fact, not a flag.
- Ranking copy frames **positively** (goods the elevated journals offer), never as a deficit of the others.

## OUTPUT
A METHODS tool that, from a highlighted abstract, matches candidate journals locally and presents a uniform,
fully-sourced factual profile per journal — fit, OA color, APC + waiver, green route, license, RR/data policies,
TOP factor, open impact, and multi-route legitimacy signals including regional infrastructure — under a visible,
adjustable open-science weighting the user sets (elicited locally at onboarding, never transmitted, skippable);
emitting no composite score and no predatory label, elevating by underscoring goods rather than flagging
deficits, warning only by showing facts, with equity and privacy guards as first-class acceptance criteria.
