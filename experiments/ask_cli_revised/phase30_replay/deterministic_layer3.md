# Mechanical audit (Layer 3, deterministic replay)

- plan_sha256: `d965a6144377de37f2c688df3cd59a7f8c2354c54c3103b1dfbe61f2207d6c0c`
- plan_version: `answer-plan-step2-v1`
- replay_authorization_sha256: `74ecd832ea88fce183e7c72762a926d84c61e77578ce73e20885389671a61509`
- source_label_extract_sha256: `96c8e5ba71da6f7803dde9f94cb71579793b7eeb61d373af8c430eb1b3a5a80b`
- library_fingerprint_sha256: `4f2e98a54c92790e791d841ef63e2fd60c4b411246f9c29590c19e56da892523`
- grounded acronyms: ['IAT', 'NAME']
- introduced in Layer 1: ['IAT', 'NAME']
- promoted limitations: 4 of 158 candidates scanned
- structural section metadata present in sealed spans: False
- node states: {'answered': 0, 'partial': 3, 'not_established': 6, 'searched_empty': 0}

## Engine-complete relations not witnessed by one AnswerPlan passage

- c5 c5#suff:brain-behavior i::b140e60509ac4c8b::4a3f8a1c59aaa360
- c5 c5#suff:brain-behavior i::b140e60509ac4c8b::e4796948ec530e13
- c6 c6#suff:brain-attitude i::b140e60509ac4c8b::2f2b08aa35e6e926
- c6 c6#suff:brain-attitude i::b140e60509ac4c8b::9fe92674ba934ce3

## Node 1 (not_established) — children c1

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c1#suff:neural-manifestation` | not_established | - | neural_manifestation_evidence | - | - | `role_value::8d0ce9c4405f714b`, `role_value::57b25a887d32ec58` |

Limitation decisions (every candidate from a contributing paper):

Definition decisions:

Disclosure items (raw, before consolidation):
- `c1#suff:neural-manifestation` not_established
- `c1#suff:neural-manifestation` reason code `passage_not_generic_summary`
- `c1#suff:neural-manifestation` reason code `attribution_prior_work`

## Node 2 (not_established) — children c2

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c2#suff:behavioral-manifestation` | not_established | - | behavior_or_behavioral_measure, behavioral_manifestation_evidence | - | incomplete | `role_value::b9591e4fba42edb1`, `category_list::10ddc38dbb7cb05e` |

Limitation decisions (every candidate from a contributing paper):

Definition decisions:

Disclosure items (raw, before consolidation):
- `c2#suff:behavioral-manifestation` not_established
- `c2#suff:behavioral-manifestation` reason code `passage_not_generic_summary`
- `c2#suff:behavioral-manifestation` reason code `attribution_prior_work`

## Node 3 (partial) — children c3

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c3#suff:attitude-manifestation` | not_established | - | attitude_manifestation_evidence | - | - | `role_value::34d05796cc1dd8a3` |
| `c3#suff:implicit-explicit-coverage` | answered | category_evidence | - | - | - | `category_list::9fd341f1bbff788b` |

Limitation decisions (every candidate from a contributing paper):
- span `e11` paper 67 cues ['proxies']: not promoted (not closed and complete on its own); excluded: no; basis: []
- span `e12` paper 67 cues ['might not']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e10` paper 67 cues ['limited']: not promoted (not closed and complete on its own); excluded: no; basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e11` paper 67 cues ['proxies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e12` paper 67 cues ['might not']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e5` paper 67 cues ['may not']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e11` paper 67 cues ['interpreted']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e5` paper 67 cues ['may not']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []

Definition decisions:

Disclosure items (raw, before consolidation):
- `c3#suff:attitude-manifestation` not_established
- `c3#suff:attitude-manifestation` reason code `passage_not_generic_summary`
- `c3#suff:attitude-manifestation` reason code `attribution_prior_work`

## Node 4 (not_established) — children c4

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c4#suff:specific-region` | not_established | - | named_brain_region_or_network, region_bears_on_bias_evidence | - | witnessed | `relational::5d178917787a4805`, `role_value::161d9d5825b7df74`, `role_value::1f1af648ebc4dd29` |

Limitation decisions (every candidate from a contributing paper):

Definition decisions:

Disclosure items (raw, before consolidation):
- `c4#suff:specific-region` not_established
- `c4#suff:specific-region` reason code `referentially_closed`
- `c4#suff:specific-region` reason code `attribution_prior_work`

## Node 4A (not_established) — children c5

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c5#suff:brain-behavior` | not_established | - | behavior_or_behavioral_measure, named_brain_region_or_network | - | unwitnessed_complete | `category_list::7af59a3e5749152a` |

Limitation decisions (every candidate from a contributing paper):

Definition decisions:

Disclosure items (raw, before consolidation):
- `c5#suff:brain-behavior` relation_unwitnessed
- `c5#suff:brain-behavior` reason code `requested_construct_direct`

## Node 4B (partial) — children c6

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c6#suff:brain-attitude` | partial | attitude_type_or_measure | named_brain_region_or_network | - | unwitnessed_complete | `direction_or_effectiveness::97e9b66f0fd3c1c2`, `category_list::f453ebb75104e61d` |
| `c6#suff:implicit-explicit-coverage` | partial | category_evidence | - | implicit | - | `role_value::c33c4ccf244a45a8` |

Limitation decisions (every candidate from a contributing paper):
- span `e11` paper 67 cues ['proxies']: not promoted (not closed and complete on its own); excluded: no; basis: []
- span `e12` paper 67 cues ['might not']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e10` paper 67 cues ['limited']: not promoted (not closed and complete on its own); excluded: no; basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e1` paper 67 cues ['limitations']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e10` paper 67 cues ['limited']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e11` paper 67 cues ['proxies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e12` paper 67 cues ['might not']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e5` paper 67 cues ['may not']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e11` paper 67 cues ['interpreted']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e5` paper 67 cues ['may not']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []

Definition decisions:

Disclosure items (raw, before consolidation):
- `c6#suff:brain-attitude` relation_unwitnessed
- `c6#suff:implicit-explicit-coverage` not_established

## Node 5 (not_established) — children c8, c9

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c8#suff:trait-construct` | not_established | - | individual_difference_trait_or_construct, relationship_to_bias_manifestation | - | witnessed | `relational::6d3e9d91766ca2c1`, `relational::bac1b3e1196e3527`, `relational::99d44d22bc14a8e3`, `relational::629c3c06bf89e330`, `relational::6e5d1f4ca6697f91`, `category_list::f1f51b4ba55bad3c` |
| `c9#suff:trait-scale-pairing` | not_established | - | individual_difference_trait_or_construct, named_scale_or_instrument | - | incomplete | - |

Limitation decisions (every candidate from a contributing paper):

Definition decisions:

Disclosure items (raw, before consolidation):
- `c8#suff:trait-construct` not_established
- `c8#suff:trait-construct` reason code `not_stimulus_rating`
- `c8#suff:trait-construct` reason code `attribution_aim_or_hypothesis`
- `c9#suff:trait-scale-pairing` relation_unwitnessed

## Node 6 (not_established) — children c10, c11

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c10#suff:culture-existence` | not_established | - | bias_evidence_in_population, named_culture_or_population | - | incomplete | `category_list::775fda7778860372` |
| `c11#suff:culture-operationalization-pairing` | not_established | - | culture_or_population, operationalization_or_measure | - | incomplete | - |

Limitation decisions (every candidate from a contributing paper):

Definition decisions:

Disclosure items (raw, before consolidation):
- `c10#suff:culture-existence` not_established
- `c10#suff:culture-existence` reason code `passage_complete`
- `c11#suff:culture-operationalization-pairing` relation_unwitnessed

## Node 7 (partial) — children c12

| facet | state | covered roles | uncovered roles | uncovered categories | relation | claims |
|---|---|---|---|---|---|---|
| `c12#suff:intervention-effectiveness` | partial | observed_effect_or_outcome | intervention, target_manifestation | - | incomplete | `category_list::d47465340e922bca` |

Limitation decisions (every candidate from a contributing paper):
- span `e4` paper 248 cues ['generalization']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e7` paper 248 cues ['limited']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e13` paper 248 cues ['generalized']: promoted; excluded: no; basis: ['closed and complete on its own', 'shares 3 content words with a displayed finding of its paper']
- span `e15` paper 248 cues ['interpretation']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e16` paper 248 cues ['directly test', 'future research', 'generalization']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e24` paper 248 cues ['future studies']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e25` paper 248 cues ['limits']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e7` paper 248 cues ['interpreted']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e8` paper 248 cues ['interpret']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e12` paper 248 cues ['future studies']: not promoted (not closed and complete on its own); excluded: no; basis: ["refers back to the paper's own findings"]
- span `e15` paper 248 cues ['generalizability', 'interpreted']: not promoted (not closed and complete on its own); excluded: no; basis: ['shares 2 content words with a displayed finding of its paper']
- span `e4` paper 248 cues ['generalization']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e7` paper 248 cues ['limited']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e13` paper 248 cues ['generalized']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e15` paper 248 cues ['interpretation']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e16` paper 248 cues ['directly test', 'future research', 'generalization']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e24` paper 248 cues ['future studies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e25` paper 248 cues ['limits']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e5` paper 248 cues ['interpreted']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e33` paper 248 cues ['interpret', 'proxies']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e7` paper 248 cues ['interpreted']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e4` paper 248 cues ['generalization']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e7` paper 248 cues ['limited']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e13` paper 248 cues ['generalized']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e15` paper 248 cues ['interpretation']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e16` paper 248 cues ['directly test', 'future research', 'generalization']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e24` paper 248 cues ['future studies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e25` paper 248 cues ['limits']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e7` paper 248 cues ['interpreted']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e14` paper 248 cues ['durability', 'further research', 'generalizability']: not promoted (not closed and complete on its own); excluded: no; basis: ['shares 5 content words with a displayed finding of its paper', "refers back to the paper's own findings"]
- span `e4` paper 248 cues ['generalization']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e7` paper 248 cues ['limited']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e13` paper 248 cues ['generalized']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e15` paper 248 cues ['interpretation']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e16` paper 248 cues ['directly test', 'future research', 'generalization']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e24` paper 248 cues ['future studies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e25` paper 248 cues ['limits']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e7` paper 248 cues ['interpreted']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e8` paper 248 cues ['interpret']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e12` paper 248 cues ['future studies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e15` paper 248 cues ['generalizability', 'interpreted']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e4` paper 248 cues ['generalization']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e7` paper 248 cues ['limited']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e13` paper 248 cues ['generalized']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e15` paper 248 cues ['interpretation']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e16` paper 248 cues ['directly test', 'future research', 'generalization']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e24` paper 248 cues ['future studies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e25` paper 248 cues ['limits']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e7` paper 248 cues ['interpreted']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e8` paper 248 cues ['interpret']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e12` paper 248 cues ['future studies']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e15` paper 248 cues ['generalizability', 'interpreted']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e17` paper 248 cues ['generalization']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e19` paper 248 cues ['generalize']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e2` paper 248 cues ['directly test']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e4` paper 248 cues ['cannot']: promoted; excluded: no; basis: ['closed and complete on its own', 'shares 4 content words with a displayed finding of its paper']
- span `e5` paper 248 cues ['future research']: not promoted (background (aim_or_hypothesis)); excluded: background (aim_or_hypothesis); basis: []
- span `e15` paper 248 cues ['generalization']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e18` paper 248 cues ['limited']: not promoted (already stated in this answer); excluded: already stated in this answer; basis: []
- span `e24` paper 248 cues ['generalized']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e26` paper 248 cues ['interpretation']: not promoted (background (literature)); excluded: background (literature); basis: []
- span `e27` paper 248 cues ['directly test', 'future research', 'generalization']: not promoted (same sentence already listed for this item (overlapping source span)); excluded: same sentence already listed for this item (overlapping source span); basis: []
- span `e5` paper 248 cues ['interpreting']: not promoted (background (design rationale)); excluded: background (design rationale); basis: []
- span `e7` paper 248 cues ['interpreted']: promoted; excluded: no; basis: ['closed and complete on its own', "refers back to the paper's own findings"]
- span `e8` paper 248 cues ['durability']: not promoted (not closed and complete on its own); excluded: no; basis: ["refers back to the paper's own findings"]
- span `e12` paper 248 cues ['further research']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e13` paper 248 cues ['cannot']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e14` paper 248 cues ['future studies']: not promoted (background (prior_work)); excluded: background (prior_work); basis: []
- span `e17` paper 248 cues ['limitation']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e21` paper 248 cues ['limitation']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e24` paper 248 cues ['cannot']: promoted; excluded: no; basis: ['closed and complete on its own', 'shares 3 content words with a displayed finding of its paper']
- span `e30` paper 248 cues ['generalizability', 'limits']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e32` paper 248 cues ['limitation']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']
- span `e35` paper 248 cues ['generalizability', 'limit']: not promoted (does not directly interpret a displayed finding of its paper); excluded: no; basis: ['closed and complete on its own']

Definition decisions:
- `NAME` long form Normalizing Anomalies with Mobile Exposure; same-paper spans ['e3', 'e9']; other-paper spans []; explicit definition in the paper's sealed text
- `IAT` long form Implicit Association Test; same-paper spans ['e25', 'e25', 'e25', 'e25', 'e25', 'e7']; other-paper spans ['e16']; explicit definition in the paper's sealed text

Disclosure items (raw, before consolidation):
- `c12#suff:intervention-effectiveness` relation_unwitnessed
- `c12#suff:intervention-effectiveness` reason code `passage_not_generic_summary`
- `c12#suff:intervention-effectiveness` reason code `attribution_prior_work`

## Claim roles

- `relational::5d178917787a4805` role=suppressed layer=layer2 reasons=['referentially_closed'] children=['c4']
- `relational::6d3e9d91766ca2c1` role=suppressed layer=layer2 reasons=['not_stimulus_rating'] children=['c8']
- `relational::bac1b3e1196e3527` role=suppressed layer=layer2 reasons=['not_stimulus_rating'] children=['c8']
- `relational::99d44d22bc14a8e3` role=suppressed layer=layer2 reasons=['not_stimulus_rating'] children=['c8']
- `relational::629c3c06bf89e330` role=suppressed layer=layer2 reasons=['not_stimulus_rating'] children=['c8']
- `relational::6e5d1f4ca6697f91` role=suppressed layer=layer2 reasons=['not_stimulus_rating'] children=['c8']
- `direction_or_effectiveness::97e9b66f0fd3c1c2` role=value_level layer=layer1 reasons=- children=['c6']
- `role_value::8d0ce9c4405f714b` role=suppressed layer=layer2 reasons=['passage_not_generic_summary', 'attribution_prior_work'] children=['c1']
- `role_value::57b25a887d32ec58` role=suppressed layer=layer2 reasons=['referentially_closed'] children=['c1']
- `role_value::b9591e4fba42edb1` role=suppressed layer=layer2 reasons=['passage_not_generic_summary', 'attribution_prior_work'] children=['c2']
- `role_value::34d05796cc1dd8a3` role=suppressed layer=layer2 reasons=['passage_not_generic_summary', 'attribution_prior_work'] children=['c3']
- `role_value::161d9d5825b7df74` role=attributed_only layer=layer2 reasons=['attribution_prior_work'] children=['c4']
- `role_value::1f1af648ebc4dd29` role=suppressed layer=layer2 reasons=['referentially_closed'] children=['c4']
- `role_value::c33c4ccf244a45a8` role=primary layer=layer1 reasons=- children=['c6']
- `category_list::775fda7778860372` role=suppressed layer=layer2 reasons=['passage_complete'] children=['c10']
- `category_list::d47465340e922bca` role=primary layer=layer1 reasons=- children=['c12']
- `category_list::10ddc38dbb7cb05e` role=suppressed layer=layer2 reasons=['requested_construct_direct'] children=['c2']
- `category_list::9fd341f1bbff788b` role=primary layer=layer1 reasons=- children=['c3']
- `category_list::f1f51b4ba55bad3c` role=suppressed layer=layer2 reasons=['attribution_aim_or_hypothesis'] children=['c8']
- `category_list::7af59a3e5749152a` role=suppressed layer=layer2 reasons=['requested_construct_direct'] children=['c5']
- `category_list::f453ebb75104e61d` role=primary layer=layer1 reasons=- children=['c6']
