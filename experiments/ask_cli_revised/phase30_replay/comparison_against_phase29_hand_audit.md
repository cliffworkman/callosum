# Comparison against the Phase-29 hand audit (Appendix A)

Mechanically derived by `answer_plan/replay.py`. The 'Agree' column compares only whether a claim appears in
Layer 1. Duplicates and subsumed claims fold into another claim and are not compared separately.

| # | ParentClaim | Child | Phase-29 hand role | Mechanical role | Hand: in Layer 1? | Mechanical: in Layer 1? | Agree |
|---|---|---|---|---|---|---|---|
| 1 | `relational::5d178917787a…` | c4 | primary | suppressed: referentially_closed | yes | no | **NO** |
| 2-6 | `relational::6d3e9d91766c…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::bac1b3e1196e…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::99d44d22bc14…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::629c3c06bf89…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 2-6 | `relational::6e5d1f4ca669…` | c8 | suppressed (identity: stimulus ratings) | suppressed: not_stimulus_rating | no | no | yes |
| 7 | `direction_or_effectivene…` | c6 | primary as value-level valence | displayed (value-level) | yes | yes | yes |
| 8 | `role_value::8d0ce9c4405f…` | c1 | attributed_primary (facet 2) | suppressed: passage_not_generic_summary | yes | no | **NO** |
| 9 | `role_value::57b25a887d32…` | c1 | context (operand of 1) | suppressed: referentially_closed | no | no | yes |
| 10 | `role_value::b9591e4fba42…` | c2 | duplicate_of 8 | suppressed: passage_not_generic_summary | n/a | n/a | n/a (folds into another claim) |
| 11 | `role_value::34d05796cc1d…` | c3 | duplicate_of 8 | suppressed: passage_not_generic_summary | n/a | n/a | n/a (folds into another claim) |
| 12 | `role_value::161d9d5825b7…` | c4 | attributed_only | attributed_only | no | no | yes |
| 13 | `role_value::1f1af648ebc4…` | c4 | subsumed_by 1 | suppressed: referentially_closed | n/a | n/a | n/a (folds into another claim) |
| 14 | `role_value::c33c4ccf244a…` | c6 | context (keyword operand) | displayed via another claim's identical sentence | no | yes | **NO** |
| 15 | `category_list::775fda777…` | c10 | context (population operand) | suppressed: passage_complete | no | no | yes |
| 16 | `category_list::d47465340…` | c12 | primary for p30/p31; p24 suppressed | displayed | yes | yes | yes |
| 17 | `category_list::10ddc38db…` | c2 | primary for p46/p47 (construct-adjacent labelled) | suppressed: requested_construct_direct | yes | no | **NO** |
| 20 | `category_list::9fd341f1b…` | c3 | primary (verbatim p36 sentence) | displayed | yes | yes | yes |
| 19 | `category_list::f1f51b4ba…` | c8 | suppressed (speculative, identity) | suppressed: attribution_aim_or_hypothesis | no | no | yes |
| 18 | `category_list::7af59a3e5…` | c5 | duplicate_of 17 (facet 4A) | suppressed: requested_construct_direct | n/a | n/a | n/a (folds into another claim) |
| 21 | `category_list::f453ebb75…` | c6 | primary (measure name) | displayed via another claim's identical sentence | yes | yes | yes |
