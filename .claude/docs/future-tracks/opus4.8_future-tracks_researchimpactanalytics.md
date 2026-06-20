# Future track — Research-impact analytics (opt-in, local-first, commons)

**Disposition for CC:** capture this into the backlog (`INCREMENT-BACKLOG.md` + this file under
`.claude/docs/future-tracks/`). **Do not build yet.** This track touches the **egress posture** and the
**equity / data-sovereignty values** directly, so it must pass the **Principles alignment gate + the values
layer (APPROACH-AVOIDANCE.md)** at graduation. Only the two local-first, **zero-egress** early stages
(instrumentation seam, personal dashboard) are near-term candidates; everything that transmits is gated on an
unresolved accounts/hosting decision and on N growing past 1. Graduation is the user's call.

---

## One line
Optionally, voluntarily, and pseudonymously measure **whether and how Callosum changes the way people do
research** — built local-first, summary-only, and structured as a research **commons**, gated behind a real
**research-grade consent form**.

## Two distinct projects — keep them separate
- **A. Local usage analytics.** What gets used, how long operations take. Values-consistent; the **user is the
  first beneficiary** (self-knowledge). Buildable now, no server, no egress.
- **B. Cross-user research-impact signal.** Reconstructing a flourishing signal across users. Needs N>1, an
  egress path, and a consent regime. Rides on top of A and the accounts/hosting decision. Far future.

A is not a means to B. A stands on its own value; B is an opt-in possibility layered on top.

## This is research, not telemetry
The *surface* resembles product telemetry, but the *purpose* is human-subjects research: studying whether a
tool changes how people do research, with intent to learn generalizable things and possibly publish. Callosum
has **no IRB**, so the discipline is **self-imposed** — we hold this to the consent standard of true HSR, not
the checkbox standard of analytics. If findings ever leave the apartment as research, ask the review question
*before*, not after.

---

## Staged architecture

1. **Instrumentation seam (near-term, no egress).** A local event-emitter abstraction + an append-only
   **local** sink. Capture event *types*, timestamps, durations, counts — **never payloads** (no PDF text, no
   queries, no library contents). Build the seam, defer the collection policy — mirrors how the egress seam was
   built before anything was turned on.

2. **Personal dashboard (near-term, no egress).** The user sees their own usage — time saved, citations
   exported, flagged citations caught and corrected. Delivers value at **N=1** (Cliff, now), dogfoods the
   schema, and is fully **inspectable / exportable / deletable** by the user.

3. **Opt-in local aggregation (later).** Flourishing metrics are computed **on the user's device** from the
   local log. Only derived summary statistics ever become candidates for contribution.

4. **Contribution (far future; gated).** Opt-in, pseudonymous, **summary-only** egress behind a consent gate
   identical in spirit to `CALLOSUM_ALLOW_DATA_EGRESS` (default-deny). **Prefer the serverless option:** the
   user manually exports a summary file and *chooses* to send it, so no infrastructure ever holds their data.
   A server/accounts model is a larger values step (see Open decisions) and must be decided deliberately, not
   drifted into.

---

## Hard constraints — the values envelope (non-negotiable)

- **Opt-in, default off, box unchecked,** explained in plain language at the moment of asking. Matches the
  egress gate's deny-by-default posture. (Not opt-out — opt-out is the surveillance-capitalism default and
  contradicts the architecture.)
- **Plain language, no corporate framing.** State the purpose directly; do not dress data collection in
  mission-speak.
- **Pseudonymous, not anonymous — named honestly.** Longitudinal measurement needs to link one user's data
  across time, which requires a persistent **locally-generated random ID** tied to no identity. That is
  *pseudonymous*. Calling it "anonymous" is the exact sleight-of-hand we refuse. True anonymity is available
  only for cross-sectional questions; we name the tradeoff out loud.
- **Compute locally, transmit only summaries.** The raw event log never leaves the machine. Only on-device
  derived statistics, tagged with the pseudonym, are ever offered for contribution. Smallest possible egress
  surface; a rich behavioral stream is re-identifiable by its pattern, a handful of summary stats far less so.
- **Scope only to the goal.** A surface is instrumented only if it serves the research question. No
  collect-it-in-case.
- **Coarsen everything that survives.** Even article count can re-identify in a small academic population —
  include it *only* if it earns its place as a career-stage covariate, and then as a **bucketed range**, not an
  exact number. Timestamps to the week, not the second. **No IPs, no device IDs, no field/topic strings, no
  library contents.**
- **Field registry as a gate (see below).**
- **Inspectability extended to the analytics.** The user can preview the **exact payload** before it transmits
  and read/delete the local log anytime. The transmission is auditable evidence, not a black box — same ethos
  as "every claim carries its evidence."
- **Revocable, with a stated deletion asymmetry.** Opting out stops future contribution. Be straight that
  **de-identified aggregate contributions cannot be retroactively pulled** (no identifier to find them by); the
  **local raw log** is fully user-deletable. State the asymmetry; do not imply a clean "delete my data" that
  pseudonymized aggregates can't honor.
- **Commons, not dataset.** Open the methods; if anything is ever aggregated and analyzed, the findings (and
  ideally the aggregate data) **return to the community that produced them.** The line between surveillance and
  a research commons is whether data is extracted for the platform or contributed to shared knowledge that
  comes back. Reciprocity is the point, not a courtesy.

---

## Measurement framework (Project B target)

**Abandoned as the primary metric: publication count.** It is the corrupted proxy academia already
over-optimizes — the exact thing the equity / anti-credit-concentration work pushes against — and it is
reverse-causal (a productive period drives library growth, which drives usage), badly lagged (research→pub runs
years), lumpy and low-N per person, construct-invalid for "flourishing," and possibly **oppositely valenced** on
the dimension we most care about (careful research is often slower and yields fewer, better papers). A
flourishing-meter calibrated to throughput would penalize care.

**Target: proximal, mechanism-level, within-app signals** — local-first and high-N, where the distal outcome is
not:
- **Tedium reduction (strongest).** Time-on-task for mechanical operations: citation export, duplicate
  resolution, metadata re-resolve, locating a quote. Every operation is a data point; the delta is real and
  attributable.
- **Care-in-action.** Verification catches the user acts on, source-tracing frequency, flagged-citation
  corrections. Callosum is **unusually positioned** to instrument rigor *behaviors* because it is built around
  verification — most software cannot.
- **Energy redirection (weakest, most distal).** Reachable only by an opt-in micro-survey ("did this save you
  time this week; what did you do with it?"). Self-report is weak, but for this face it is the only honest
  instrument — do not dress a proxy as a measurement.

**Valence rule (bake in from the start).** Engagement is **not** the metric. For tedium operations, *less time*
is the win — a reference manager that optimizes time-in-app is anti-flourishing. **Define the
flourishing-positive direction per feature explicitly**, or the analytics will quietly invert the values
(Goodhart).

**Standing commitment.** Abandon any candidate metric that requires slipping the principles — the metric is not
worth the cost of the slip. **Whatever survives the principles is the target.**

**Causal honesty.** The distal question ("does Callosum raise research output") is likely **not answerable** to
a standard we'd accept from observational app data; the installer-who-doesn't-use "control" is selection-
confounded; only randomized feature rollout cleanly breaks selection, and that imports its own consent/equipoise
ethics. Do not oversell. The proximal questions are answerable; the distal one is, at most, a far-future
randomized question we may decide isn't worth the cost.

---

## The consent form

**Required elements (research-grade):** purpose; what is collected; what is explicitly *not* collected;
voluntariness; how to withdraw; the deletion asymmetry; pseudonymity (named as such); residual re-identification
risk; who sees the data; what is published; that findings return to the community; contact. Plain language
throughout.

**Draft (plain language — refine, don't ship as-is):**

> **Help us find out if Callosum actually helps.**
>
> This is off by default. You can use everything in Callosum without turning it on, and nothing here is
> collected unless you opt in below.
>
> **What this is.** Callosum is built on a claim — that it makes research more careful and takes some of the
> tedium out of the work. We'd like to find out whether that's true. This is a small research study, run by the
> person who builds Callosum, and you'd be choosing to take part in it.
>
> **What we'd collect.** Counts and timings of *how the app is used* — how often you export citations, resolve
> duplicates, correct a flagged citation, and how long those take. We compute summary numbers **on your own
> machine** and only those summaries are ever sent — never the raw record of what you did.
>
> **What we never collect.** The contents of your library, your PDFs, your searches, your IP address, your
> device, or your name. We don't want them and we don't take them.
>
> **How we keep you unidentified.** To see whether things change over time, your contributions carry a random
> ID generated on your machine. It isn't linked to your identity. This is *pseudonymous*, not anonymous — we're
> telling you plainly rather than overpromising. With a small number of users, rich data can sometimes be traced
> back, which is why we collect so little and coarsen what's left.
>
> **You're in control.** You can turn this off at any time, which stops all future collection. You can read and
> delete the local record on your machine whenever you like. One honest limit: once a summary has been
> contributed without your identity attached, we can't go back and find it to remove it — there's no name on it
> to search for.
>
> **What happens to it.** Anything we learn goes back to the people who made it possible — open methods, and
> findings shared with the community, not kept as a private dataset.
>
> ☐ **Yes, I'd like to contribute usage summaries to help measure whether Callosum works.** *(unchecked by
> default)*

---

## The field registry (a data-minimization harness)

Maintain a registry — ideally **public, in-repo** — of every field that may be transmitted. **No field enters
the transmission schema without (a) the research question it answers and (b) a note on why a coarser version
won't do.** A field nobody can attach a question to gets cut. This converts data-minimization from an intention
into a fitness function for the analytics itself (the convention→enforcement move), and makes the
data-collection schema an open, reviewable artifact rather than a privacy policy nobody reads.

---

## Open decisions (resolve before graduating the contribution stage)
- **Accounts/hosting vs serverless manual-export.** The serverless option (user exports a summary file and
  chooses to send it) keeps Callosum free of any infrastructure that holds user data, and is the most
  principle-aligned. A server/accounts model is a larger values step.
- **Public field registry?** (Leaning yes.)
- **Co-investigator / credit model.** If findings return to the community, early contributors are closer to
  co-investigators than subjects — should consent and credit reflect that, tying the analytics to the
  anti-credit-concentration commitment?
- **N>1 prerequisite.** Project B is inert at N=1; this is build-the-seam-now so we're ready later.

## Buildable now vs gated
- **Now (no egress, no server, purely additive):** the instrumentation seam + the personal dashboard.
- **Gated (needs the decisions above + N>1):** on-device aggregation + the opt-in contribution path + the
  consent form in-product.
