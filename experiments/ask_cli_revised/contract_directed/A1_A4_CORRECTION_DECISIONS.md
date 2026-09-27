# Decisions: Cliff's two corrections to A1/A3/A4 (recorded before implementation, per his request)

## Correction 1 — attribution and rescue are clause-scoped, not span-scoped

`attribution.derive_attribution` no longer promotes a whole span to `own_established`/`METHODS_OWN` because one
clause qualifies. `split_clauses`/the clause records are the only thing closure reads for acceptance; the returned
`state` is informational only (agreeing clauses → that state; disagreeing → `mixed`), never used by closure for a
decision.

`closure._slot_state` now decides per listed id via its **clauses**, with the accepted clause recorded
(`accepted_clause`: exact offsets + text — the "linking rationale"):
- **Descriptive slots** (`relatum_a`, `relatum_b`, `population_named`, `item_named`, `instrument_named`,
  `manner_described`, `tied_to_subject`, `tied_to_finding`, `paired_with_construct`): accepted if *any* clause of
  the id is `own_established` (or `METHODS_OWN` where `(kind, slot)` is in `METHODS_ELIGIBLE`).
- **Relation-bearing slots** (`("relationship","relation_stated")`, `("relationship","polarity")`,
  `("existence","outcome_reported")`, `("existence","finding_of_type")`): accepted only if *the same clause* is
  both an accepted state (own/methods-eligible) **and** carries a result/relation predicate
  (`attribution._RESULT_PREDICATE`). A clean clause that never states a result cannot validate a relationship
  asserted only in a different, speculative clause of the same span. This is the exact shape of the required
  negative control (factual clause about something else + speculative clause stating the actual relationship →
  the slot fails).
- `METHODS_OWN` remains excluded from every relation-bearing slot, unchanged.

## Correction 2 — `pairing_expressed` requires one connecting proposition, not two independently-accepted slots

A4 no longer derives `pairing_expressed` merely because the same span id is accepted for both paired units' primary
slots. It now requires either:
1. **Same-clause proof**: the accepted clause for unit A's primary slot and the accepted clause for unit B's
   primary slot are the *same clause* (identical offsets) of the same id — one proposition genuinely states both
   (the real Hadza sentence: one clause names the population *and* states what they were asked to judge). The
   linking rationale recorded is that clause's exact text/offsets.
2. **Verified cross-span link**: `packet["links"]` already carries a designator-verified connection
   (`links.find_links`) between the two accepted spans — the existing, auditable across-section mechanism Cliff
   confirmed should remain available. Bare co-occurrence in the same packet, with no shared clause and no verified
   link, does **not** establish a pairing.

An abstract-sourced `study_context` (Task B) that fails to establish `on_topic` is recorded as "not established from
the abstract for this unit" — never as "no connection exists in the paper." `on_topic_uncertain` recovery may
still try a different, targeted action (e.g. `other_section_family`) for the same unit; only the identical
"re-attach the abstract" action is not repeated.
