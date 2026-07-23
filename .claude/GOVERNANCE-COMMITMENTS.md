# Callosum Founder and Governance Commitments

## Status and purpose

Callosum is presently a founder-led project.

At the time of writing, I, Cliff Workman, retain practical control over its product direction, codebase, feature priorities, design principles, and governance documents.

This concentration of authority is useful during early development. It allows Callosum to move quickly and maintain a coherent vision. It also creates risk.

A single person cannot reliably identify every ethical problem, affected stakeholder, conflict of interest, or unintended consequence. Expertise does not eliminate blind spots. Good intentions do not prevent self-serving interpretations. Confidence in one's principles can create its own shadowy spaces.

This document is therefore a public precommitment.

It records the standards under which I intend to develop Callosum before adoption, revenue, investment, institutional pressure, or organizational complexity make those standards harder to establish or easier to weaken.

It is not evidence that Callosum has solved its governance problems. It is a record against which the project, and I, can be evaluated.

## The central commitment

> **Callosum shines a light. It does not replace the researcher's eyes.**

Callosum exists to make scientific work easier to inspect, understand, conduct, and evaluate.

It should reduce the cost of scrutiny without removing the need for scrutiny.

It should help researchers find evidence, preserve provenance, identify uncertainty, detect discrepancies, coordinate work, and make considered decisions.

It should not ask users to surrender intellectual responsibility in exchange for convenience.

Callosum may direct attention. It may reveal patterns. It may identify possible problems. It may generate candidates for consideration.

It should not pretend to see, reason, decide, or judge on the researcher's behalf.

## Core purpose

Callosum exists to make rigorous, inspectable, and open scientific work easier to conduct and evaluate.

Its purpose is not to automate science into existence.

Its purpose is to increase researchers' capacity to reason without increasing their capacity to hide how they reasoned.

Callosum should support scientific judgment without presenting automation as a substitute for scientific judgment.

It should make evidence easier to examine, uncertainty harder to conceal, and decisions easier to trace.

It should not manufacture confidence, convenient conclusions, accusations, or assessments of personal worth.

## Illumination, not substitution

A central design question for every major Callosum feature is:

> Does this feature improve the user's ability to see and reason, or does it ask the system to see and reason in the user's place?

Features should generally illuminate:

* The evidence underlying a claim
* The source and provenance of generated material
* Uncertainty and disagreement
* Contradictions between sources
* Discrepancies between plans and implementation
* Missing information
* Unresolved decisions
* Workflow dependencies
* Project blockers
* The limits of what an automated system can determine

Features should not substitute for:

* Reading
* Interpretation
* Statistical judgment
* Theoretical reasoning
* Methodological justification
* Ethical deliberation
* Responsibility for scientific claims
* Responsibility for decisions affecting other people

The goal is not frictionless science.

Some friction is wasteful and should be removed. Other friction is the experienced cost of necessary judgment and accountability.

Callosum should remove friction from scrutiny while preserving friction where scientific responsibility requires thought.

## Founder accountability

While Callosum remains founder-controlled, I commit to the following:

1. Ethically or epistemically consequential features will be evaluated before implementation, not only after harm becomes visible.

2. Feature evaluation will consider both the legitimate purpose of a feature and the behavior it could reward, normalize, conceal, or make easier.

3. A feature will not be justified solely by user demand, commercial value, technical feasibility, competitive pressure, or the preferences of powerful users.

4. The interests of purchasers, administrators, principal investigators, institutions, or funders will not automatically override the interests of people subjected to the resulting systems.

5. Rejected proposals may be documented when their rejection expresses an important product boundary.

6. Ethical language will not be used to market ordinary product decisions as moral accomplishments.

7. Known limitations, unresolved risks, and areas of uncertainty should remain visible.

8. Material changes to Callosum's governing principles should remain visible in version history rather than being silently rewritten.

9. When I make a consequential exception to a stated principle, the exception and its reasoning should be documented.

10. Founder control should be treated as provisional rather than as the natural permanent governance structure of the project.

## Product boundaries

Callosum should not become a motivated-reasoning machine.

It should not be designed to:

* Find whichever evidence best supports a conclusion the user has already chosen
* Present citations as supporting a claim when they merely mention, contextualize, or contradict it
* Hide disagreement or contradictory evidence because it is inconvenient
* Automate undisclosed searches across analyses in pursuit of a desirable result
* Convert ambiguous evidence into categorical judgments
* Encourage statistical significance to substitute for theoretical or methodological reasoning
* Conceal deviations from preregistered or otherwise declared plans
* Produce accusations about researchers, authors, laboratories, or institutions from incomplete signals
* Present generated language as independently established evidence
* Optimize rhetoric while obscuring provenance, uncertainty, or contradiction
* Infer personal worth, competence, effort, or character from software activity
* Provide administrators with hidden surveillance capabilities
* Make questionable research practices faster, easier, or more difficult to detect

Callosum may simplify considered reasoning.

It should not make bad reasoning look rigorous.

## Signal, not verdict

Callosum should distinguish among:

* Established facts
* Candidate matches
* Supporting evidence
* Contradictory evidence
* Mere discussion or semantic similarity
* Missing or unavailable information
* Unresolved ambiguity
* Automated signals requiring human interpretation
* User-provided judgments
* System-generated inferences

Automated systems should not claim more precision, certainty, or authority than their evidence permits.

When Callosum cannot distinguish among benign, concerning, or technically ambiguous explanations, it should surface that uncertainty rather than select the most dramatic interpretation.

A missing database record is not proof that an article does not exist.

A statistical discrepancy is not proof of misconduct.

A retracted citation is not proof that a researcher endorsed the retracted claim.

A similarity match is not proof of evidentiary support.

A missed deadline is not proof of negligence.

Callosum should show the signal and preserve the user's responsibility to interpret it.

## Provenance and intellectual agency

AI-generated material should remain subordinate to inspectable evidence.

Where practical, generated claims should be connected to:

* Their source material
* Exact or appropriately qualified source locations
* Relevant quotations or excerpts
* Confidence or verification status
* Contradictory evidence
* Scope limitations
* Interpretive steps introduced by the system
* Unresolved ambiguities

Researchers should remain able to inspect, contest, reject, and revise generated outputs.

Callosum should not require users to hand over intellectual responsibility in exchange for convenience.

The system may help users reach the evidence.

It should not declare that the evidence has already been adequately understood.

## Citation assistance and motivated reasoning

Citation assistance requires particular caution.

A citation is not merely a formatting object. It can create the appearance that a sentence has evidentiary support.

Callosum should distinguish among sources that:

* Support a proposition
* Contradict a proposition
* Discuss a proposition without resolving it
* Report the proposition as someone else's claim
* Support only a narrower proposition
* Have been retracted or materially corrected
* Cannot license the claim because of methodological limitations
* Are semantically similar but evidentially irrelevant

Callosum should not function as a machine for locating plausible-looking citations for conclusions the user already prefers.

The preferred task is not:

> Find a citation for this sentence.

The preferred task is closer to:

> Check this claim against the available literature.

That check should be capable of returning support, contradiction, ambiguity, and scope mismatch together.

## Research automation

Automation should reduce clerical and procedural friction without silently taking over decisions that require scientific judgment.

Potential analysis-related features require particular caution.

Callosum should not automatically search across analytic choices, transformations, exclusions, subgroups, models, outcomes, or stopping rules in ways that increase undisclosed researcher degrees of freedom.

Callosum may eventually support carefully bounded analysis assistance when it:

* Implements a previously declared and justified plan
* Makes unresolved decisions explicit
* Preserves links between written plans and code
* Clearly distinguishes confirmatory and exploratory work
* Records deviations rather than concealing them
* Does not optimize analytic choices after inspecting whether results are favorable
* Makes assumptions and user decisions visible
* Produces an implementation draft rather than claiming to produce the uniquely correct analysis

A preregistration-to-code comparison tool is consistent with these commitments when it:

* Compares declared plans against code without running the analysis
* Identifies possible alignments, omissions, additions, and deviations
* Shows the relevant preregistration text and code
* Distinguishes "not located" from "not performed"
* Allows users to document justified deviations
* Does not determine whether a researcher is compliant, trustworthy, or blameworthy
* Does not rewrite analyses in pursuit of a preferred result

The purpose of such a tool would be to shine a light on the relationship between plans and implementation.

It would not replace the user's eyes or judgment.

No statement in this section commits Callosum to implementing automated analysis. More immediate and obvious sources of friction should be addressed first. High-risk automation should be considered slowly.

## Workplace power and surveillance

Features intended for laboratories, principal investigators, project leads, administrators, or institutions must be evaluated in light of existing power differences.

Callosum should help teams identify:

* Active manuscripts
* Project stages
* Deadlines
* Unresolved dependencies
* Required checks
* Decisions that need attention
* Work that is blocked
* Missing information

It should not convert those functions into covert worker surveillance.

Callosum should prefer:

* Manuscript status over worker scoring
* Blockers over blame
* Dependencies over inferred motivation
* Visible expectations over hidden evaluation
* Inspectable flags over secret judgments
* Project coordination over activity monitoring
* Contestable records over unilateral conclusions
* Team memory over email archaeology

Callosum should not infer effort, commitment, productivity, competence, reliability, or moral character from software activity.

Administrative access should not automatically imply unrestricted access to every form of user activity or private work.

A principal investigator may need to know that a manuscript is blocked.

That does not imply a right to monitor every document opened, every note written, every reading action, or every moment of inactivity.

Features that could create coercive monitoring should be constrained at the permissions and data-model level, not merely described with reassuring interface language.

## Junior researchers and affected users

People affected by a feature may perceive risks that are invisible to the person requesting, purchasing, or building it.

This is particularly important in research environments, where differences in rank, employment security, authorship power, immigration status, funding, and career dependence can make nominally optional systems functionally compulsory.

Feature evaluation should seek perspectives from relevant groups, including where applicable:

* Graduate students
* Postdoctoral researchers
* Research staff
* Principal investigators
* Methodologists and statisticians
* Open-science researchers
* Privacy and research-ethics specialists
* AI skeptics
* Disabled researchers
* Users outside the founder's immediate professional network

Junior researchers must not be treated merely as end users of systems designed around senior researchers' preferences.

Their participation should have substantive influence rather than ceremonial representation.

The priority-ranked reading queue provides one model for this process. It addressed a major source of friction that was less visible to senior researchers who had already accumulated the literature knowledge and reading habits that junior researchers were still trying to build.

User uptake should reveal pain points that expertise, seniority, discipline, or personal experience have made invisible to me.

## User requests and product judgment

Callosum should be responsive to users without becoming an undifferentiated collection of requested features.

Each substantial request should be considered in terms of:

* The immediate request
* The underlying research job
* The broader group affected
* The generalizability of the problem
* The epistemic or ethical risks
* The additional interface complexity
* Whether the feature removes wasteful friction or necessary friction
* Whether the feature fits Callosum's central purpose

Some requests should be implemented quickly.

Some should be redesigned.

Some should be deferred until their consequences can be examined properly.

Some should be rejected.

User enthusiasm does not remove the need for judgment.

## Documentation and decision records

Callosum's principles should be reflected in durable project infrastructure.

Depending on the significance of the decision, this may include:

* `PRINCIPLES.md`
* `APPROACH-AVOIDANCE.md`
* This governance commitment
* Feature-level ethical assessments
* Rejection rationales
* Security and privacy reviews
* Architecture decision records
* User research notes
* Tests that encode critical constraints
* A public decision log for high-risk features

The purpose is not to create paperwork for its own sake.

The purpose is to externalize product judgment that would otherwise remain tacit in one person's head.

A future contributor should be able to determine whether an absent feature was overlooked, deferred, or intentionally rejected.

A future version of the project should not have to rely on my memory or personal presence to understand its boundaries.

## Governance should scale with consequences

Founder control is provisional.

The appropriate governance structure depends on the consequences of Callosum's decisions.

A private tool used by one person does not require the same governance as software used across laboratories, institutions, careers, and publishing pipelines.

As adoption grows, governance should become broader, more formal, and less dependent on my sole judgment.

Potential triggers for expanded governance include:

* Sustained use by multiple independent laboratories
* Institutional deployment
* Meaningful recurring revenue
* External investment
* Collection or synchronization of sensitive collaborative data
* Product decisions that materially affect trainees or employees
* Use in research assessment, hiring, promotion, compliance, or funding
* Dependence on Callosum for consequential parts of the scientific record
* Commercial partnerships capable of reshaping product priorities

These triggers should be reconsidered as evidence accumulates.

They are not excuses to postpone outside scrutiny until every threshold has been crossed.

## Future advisory and governing bodies

If Callosum achieves meaningful adoption, I intend to convene an external body to help review and shape documents such as:

* `PRINCIPLES.md`
* `APPROACH-AVOIDANCE.md`
* This governance commitment
* Policies governing high-risk features
* Data and privacy practices

Such a body should include structurally different perspectives rather than only prominent supporters of the project.

Its composition should include protected representation for junior researchers.

It should avoid control by any single purchaser, funder, institution, professional class, or commercial interest.

Depending on Callosum's scale and consequences, its responsibilities may include:

* Reviewing changes to core principles
* Evaluating high-risk feature categories
* Reviewing surveillance and labor implications
* Reviewing statistical and inferential automation
* Reviewing data-governance decisions
* Reviewing major commercial partnerships
* Publishing objections or minority opinions
* Recommending, delaying, or blocking changes that conflict with Callosum's commitments

The authority of such a body should be defined explicitly.

An advisory board should not be presented as an independent governing body if the founder can ignore it without disclosure.

## Risks of plural governance

A board does not automatically make governance ethical.

Collective governance can reproduce or create:

* Prestige-based deference
* Senior domination of junior members
* Institutional capture
* Commercial capture
* Token representation
* Ceremonial ethical review
* Diffusion of responsibility
* Suppression of minority objections
* Excessive caution that protects existing systems from useful change

Any future governance body should therefore have safeguards of its own, potentially including:

* Public membership
* Disclosed conflicts of interest
* Term limits
* Staggered appointments
* Protected junior representation
* Recusal procedures
* Published rationales
* Recorded minority opinions
* Transparent revision procedures
* Limits on purchaser and funder control
* Periodic review of whether the governance structure remains fit for purpose

The goal is not to eliminate discretion.

It is to make discretion visible, contestable, and distributed.

## Changes to these commitments

This document may need to change.

Revision is not itself a violation.

Substantial revisions should include:

1. A description of what changed
2. The reason for the change
3. The risks introduced or addressed
4. The people or perspectives consulted
5. Any objections or unresolved disagreements
6. Whether the change weakens, strengthens, or clarifies an earlier commitment

Changes should remain available through public version history.

A later version of this document should not imply that an earlier commitment never existed.

## Conflicts between mission and growth

Commercial success, institutional adoption, investment, and user growth may create pressure to weaken these commitments.

Potential pressures include requests for:

* Employee or trainee monitoring
* Productivity scoring
* Hidden administrative visibility
* Automated analysis optimized for favorable findings
* Citation tools optimized for argumentative persuasion
* Proprietary restrictions inconsistent with the project's mission
* Data access that exceeds what is necessary to provide the service
* Partnerships that compromise independence or user trust
* Features that please purchasers while imposing hidden costs on less powerful users

Such requests should be treated as governance decisions, not ordinary sales or feature decisions.

A commercially valuable feature is not necessarily an acceptable feature.

A refusal that protects Callosum's purpose may be more important than an opportunity that expands Callosum's reach.

## Present limitations

At present, these commitments depend substantially on my willingness to honor them.

Public documentation, version control, tests, design principles, and decision records provide accountability mechanisms.

They do not create independent enforcement.

I may fail to identify relevant harms.

I may interpret principles in self-serving ways.

I may give insufficient weight to objections.

I may become attached to features, opportunities, or narratives that impair my judgment.

I may mistake coherence for correctness.

I may mistake benevolent intent for adequate governance.

This document does not resolve those risks.

It records that I recognize them and that I intend to build structures capable of challenging my judgment if Callosum becomes consequential enough that one person's intentions are no longer an adequate safeguard.

## Commitment

I am publishing these commitments while Callosum remains early, founder-led, and uncertain.

The odds that Callosum becomes widely consequential may be low.

That uncertainty does not make governance planning premature. It makes this the least costly time to state what success should not be allowed to erase.

If Callosum grows, this document should be usable to hold the project, and me, accountable.

If Callosum does not grow, these commitments still describe the kind of system I intended to build.

Callosum should shine a light.

It should never claim that the light has made human eyes unnecessary.

Signed,

Cliff Workman
Founder and lead developer, Callosum

Date adopted: 2026-07-23