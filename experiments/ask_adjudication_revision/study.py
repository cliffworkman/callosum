"""Synthetic two-freeze rehearsal. No real-study execution path is provided."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from .capability import assign_roles
from .core import CRITERION, SOURCE_RULES, canonical, digest, require, semantic_prompt, validate_cases
from .transport import normalize

CHALLENGES = ("unflagged", "screen_independent", "relation", "value_class")
DIAGNOSTICS = (
    "subject",
    "population",
    "direction",
    "modality",
    "null_retention",
    "mixed_retention",
    "uncertain_retention",
    "relation_endpoints",
    "relation_stated_in_excerpt",
    "neighboring_context_import",
    "invented_target_construct",
)


@dataclass(frozen=True)
class Review:
    candidate_id: str
    label: str
    session: str
    note: str = ""
    severe: bool = False
    origin: str = "SYNTHETIC"
    reviewer_id: str = "FAKE_REVIEWER"
    recorded_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        require(self.origin == "SYNTHETIC", "GENUINE_HUMAN_LABELS_DISABLED")
        require(self.label in ("PROMOTE", "REJECT", "UNCERTAIN"), "INVALID_REVIEW_LABEL")
        require(bool(self.session), "SESSION_REQUIRED")
        require(self.label == "PROMOTE" or bool(self.note.strip()), "SOURCE_NOTE_REQUIRED")
        require(not self.severe or self.label == "REJECT", "SEVERE_REQUIRES_REJECT")


class SyntheticStudy:
    def __init__(self, cases, *, origin="SYNTHETIC"):
        require(origin == "SYNTHETIC", "REAL_STUDY_DISABLED")
        validate_cases(cases)
        self._cases = {c.candidate_id: c for c in cases}
        self._state = "PREPARATION"
        self._a = None
        self._b = None
        self._amendment = None
        self._screen = {}
        self._reviews = {}
        self._diagnostics = {}
        self._exposed = False

    @property
    def state(self):
        return self._state

    def freeze_a(self, records, packets):
        require(self._state == "PREPARATION", "FREEZE_A_IMMUTABLE")
        assignments = assign_roles(records, packets)
        payload = {
            "origin": "SYNTHETIC",
            "stage": "FREEZE_A_SIMULATION",
            "criterion": CRITERION,
            "source_rules": SOURCE_RULES,
            "corpus": {cid: digest(c.content()) for cid, c in self._cases.items()},
            "capabilities_sha256": digest(records),
            "roles": assignments,
            "prompts": {r: semantic_prompt(roles) for r, roles in assignments.items()},
            "labels": ["FLAG", "UNCERTAIN", "NO_FLAG"],
            "missing_policy": "NO_LABEL; terminal technical disposition required",
            "retry_policy": "one logged mechanical resubmission; preserve first response",
            "orchestration_access": "after closure: individual labels, reasons, disagreement, patterns, provenance",
            "interstudy_adaptation": "explicit private amendment; exact human design frozen only at B",
            "cliff_visibility": "no frontier semantics or selection basis",
            "interpretation": "triage only; no IID, consensus truth, certification or prevalence estimate",
        }
        self._a = canonical(payload)  # Snapshot; caller mutations cannot alter this freeze.
        self._state = "FRONTIER_OPEN"
        return digest(payload)

    def record_screen(self, rater, candidate_ids, raw, *, truncated=False):
        require(self._state == "FRONTIER_OPEN", "FRONTIER_NOT_OPEN")
        require(rater in json.loads(self._a)["roles"], "UNREGISTERED_RATER")
        require(set(candidate_ids) <= set(self._cases), "UNKNOWN_SYNTHETIC_CANDIDATE")
        require(not any((rater, cid) in self._screen for cid in candidate_ids), "SCREEN_OBSERVATION_IMMUTABLE")
        result = normalize(raw, candidate_ids, truncated=truncated)
        labels = {cid: (label, reason) for cid, label, reason in result.rows}
        for cid in candidate_ids:
            label, reason = labels.get(cid, (None, None))
            self._screen[rater, cid] = {
                "rater": rater,
                "candidate_id": cid,
                "technical_status": result.technical_status,
                "label": label,
                "reason": reason,
                "raw_sha256": result.raw_sha256,
                "origin": "SYNTHETIC",
            }
        return result.technical_status

    def close_frontier(self):
        require(self._state == "FRONTIER_OPEN", "FRONTIER_NOT_OPEN")
        expected = {(r, cid) for r in json.loads(self._a)["roles"] for cid in self._cases}
        require(set(self._screen) == expected, "FRONTIER_INCOMPLETE")
        self._state = "INTERSTUDY"

    def private_frontier(self):
        require(self._state in ("INTERSTUDY", "HUMAN_OPEN"), "INTERSTUDY_ACCESS_NOT_YET_ALLOWED")
        # Full content intentionally available to private orchestration, not a vote-only algorithm.
        return json.loads(canonical(list(self._screen.values())))

    def amend_interstudy(self, *, findings, changes, why, accessed_by, cliff_blinded=True):
        require(self._state == "INTERSTUDY", "INTERSTUDY_NOT_OPEN")
        require(self._amendment is None, "AMENDMENT_ALREADY_RECORDED")
        require(findings and changes and why and accessed_by, "AMENDMENT_JUSTIFICATION_REQUIRED")
        require(cliff_blinded is True and not self._exposed, "BLINDING_REVIEW_REQUIRED")
        self._amendment = canonical(
            {
                "origin": "SYNTHETIC",
                "kind": "INTERSTUDY_ORCHESTRATION_AMENDMENT",
                "findings": findings,
                "changes": changes,
                "why": why,
                "accessed_by": accessed_by,
                "cliff_blinded": True,
                "freeze_a_sha256": digest(json.loads(self._a)),
                "when_utc": datetime.now(timezone.utc).isoformat(),
                "frontier_sha256": digest(self.private_frontier()),
            }
        )

    def freeze_b(self, design):
        require(self._state == "INTERSTUDY" and self._b is None, "FREEZE_B_IMMUTABLE")
        require(self._amendment is not None and not self._exposed, "INTERSTUDY_AMENDMENT_REQUIRED")
        require(design.get("origin") == "SYNTHETIC", "REAL_QUEUE_DISABLED")
        require(design.get("max_unique_per_configuration") == 24, "BURDEN_AMENDMENT_REQUIRED")
        require(design.get("session_minutes") == 20, "ATTENTION_SAFEGUARD_REQUIRED")
        require(design.get("reread_rule") == "fresh_session_hidden_prior_label", "REREAD_RULE_REQUIRED")
        require(design.get("severe_rule") == "one_fresh_confirmed_severe", "SEVERE_RULE_REQUIRED")
        require(
            design.get("eligibility_rule") and design.get("selection_rationale") and design.get("seed"),
            "DESIGN_INCOMPLETE",
        )
        require(
            design.get("expansion_rule")
            == "four preselected screen-independent cases after any confirmed unanimous-NO_FLAG miss",
            "UNSUPPORTED_EXPANSION_RULE",
        )
        require(
            design.get("replacement_rule")
            == "no automatic replacement; explicit amendment for corruption or source-ineligibility",
            "UNSUPPORTED_REPLACEMENT_RULE",
        )
        configurations = {c.configuration for c in self._cases.values()}
        require(set(design["allocations"]) == configurations, "CONFIGURATION_COVERAGE_REQUIRED")
        all_ids = []
        for config, allocation in design["allocations"].items():
            require(set(allocation) == {"discovery", "challenges", "expansion"}, "DESIGN_INCOMPLETE")
            require(
                3 <= len(allocation["discovery"]) <= 9 and len(allocation["discovery"]) % 3 == 0, "INVALID_TRANCHES"
            )
            require(set(allocation["challenges"]) == set(CHALLENGES), "CHALLENGE_COVERAGE_REQUIRED")
            require(all(allocation["challenges"][kind] for kind in CHALLENGES), "CHALLENGE_COVERAGE_REQUIRED")
            require(len(allocation["expansion"]) == 4, "MISS_EXPANSION_REQUIRED")
            ids = allocation["discovery"] + sum(allocation["challenges"].values(), []) + allocation["expansion"]
            require(len(ids) <= 24 and len(set(ids)) == len(ids), "BURDEN_OR_DUPLICATION_ERROR")
            require(
                all(cid in self._cases and self._cases[cid].configuration == config for cid in ids),
                "WRONG_CONFIGURATION",
            )
            require(len({self._cases[cid].unit_id for cid in ids}) == len(ids), "DUPLICATE_SOURCE_UNIT")
            all_ids.extend(ids)
        require(len(set(all_ids)) == len(all_ids), "DUPLICATE_SELECTION")
        self._b = canonical(
            {
                **design,
                "freeze_a_sha256": digest(json.loads(self._a)),
                "amendment_sha256": digest(json.loads(self._amendment)),
            }
        )
        self._state = "HUMAN_OPEN"
        return digest(json.loads(self._b))

    def expose(self):
        self._exposed = True

    def _confirmed_severe(self, cid):
        reviews = self._reviews.get(cid, [])
        return len(reviews) == 2 and all(r.severe and r.label == "REJECT" for r in reviews)

    def _screen_miss(self):
        for cid in self._reviews:
            rows = [row for (_, c), row in self._screen.items() if c == cid]
            if self._confirmed_severe(cid) and rows and all(r["label"] == "NO_FLAG" for r in rows):
                return True
        return False

    def _allocation(self, config):
        require(self._b is not None, "FREEZE_B_REQUIRED")
        return json.loads(self._b)["allocations"][config]

    def _stable(self, cid):
        reviews = self._reviews.get(cid, [])
        return len(reviews) == 2 and all(r.label == "PROMOTE" for r in reviews)

    def next_cases(self, config):
        require(self._state == "HUMAN_OPEN" and not self._exposed, "HUMAN_RELEASE_BLOCKED")
        allocation = self._allocation(config)
        selected = allocation["discovery"] + sum(allocation["challenges"].values(), []) + allocation["expansion"]
        if any(self._confirmed_severe(cid) for cid in selected):
            return ()
        # A detected concern is resolved before further case expansion; at most two reviews.
        for cid in selected:
            reviews = self._reviews.get(cid, [])
            if reviews and any(r.label != "PROMOTE" for r in reviews):
                return (cid,) if len(reviews) == 1 else ()
        stable = [cid for cid in allocation["discovery"] if self._stable(cid)]
        if len(stable) < 3:
            for start in range(0, len(allocation["discovery"]), 3):
                tranche = allocation["discovery"][start : start + 3]
                pending = [cid for cid in tranche if cid not in self._reviews]
                if pending:
                    return tuple(pending)
                rereads = [cid for cid in tranche if len(self._reviews[cid]) == 1]
                if rereads:
                    return tuple(rereads)
        challenges = sum(allocation["challenges"].values(), [])
        if self._screen_miss():
            challenges += allocation["expansion"]
        return tuple(cid for cid in challenges if cid not in self._reviews)

    def human_packet(self, config):
        ids = self.next_cases(config)
        # Randomized display order within the eligible release, never ranking or phase labels.
        seed = json.loads(self._b)["seed"]
        ids = sorted(ids, key=lambda cid: digest([seed, cid]))
        return {
            "origin": "SYNTHETIC",
            "instruction": "Is this representation sufficiently faithful to carry downstream without materially distorting the supplied scientific information?",
            "cases": [
                {
                    "candidate_id": cid,
                    "source": self._cases[cid].content()["source"],
                    "raw_output": self._cases[cid].content()["raw_output"],
                    "effective_representation": self._cases[cid].content()["effective_representation"],
                }
                for cid in ids
            ],
            "response_fields": ["candidate_id", "PROMOTE / REJECT / UNCERTAIN", "note_if_not_promote"],
        }

    def review(self, review):
        require(type(review) is Review, "SYNTHETIC_REVIEW_ONLY")
        require(review.candidate_id in self._cases, "UNKNOWN_SYNTHETIC_CANDIDATE")
        config = self._cases[review.candidate_id].configuration
        require(review.candidate_id in self.next_cases(config), "CASE_NOT_RELEASED")
        previous = self._reviews.get(review.candidate_id, [])
        require(len(previous) < 2, "REREAD_LIMIT")
        require(not previous or previous[0].session != review.session, "FRESH_SESSION_REQUIRED")
        self._reviews.setdefault(review.candidate_id, []).append(review)

    def outcome(self, config):
        require(not self._exposed, "BLINDING_REVIEW_REQUIRED")
        allocation = self._allocation(config)
        selected = allocation["discovery"] + sum(allocation["challenges"].values(), []) + allocation["expansion"]
        if any(self._confirmed_severe(cid) for cid in selected):
            return "HALT_CONFIGURATION"
        if any(any(r.label != "PROMOTE" for r in self._reviews.get(cid, [])) for cid in selected):
            return "INSUFFICIENT_EVIDENCE"
        if sum(self._stable(cid) for cid in allocation["discovery"]) < 3:
            return "INSUFFICIENT_EVIDENCE"
        challenges = sum(allocation["challenges"].values(), [])
        if self._screen_miss():
            challenges += allocation["expansion"]
        if any(not self._reviews.get(cid) for cid in challenges):
            return "INSUFFICIENT_EVIDENCE"
        return "ELIGIBLE_FOR_INTEGRATION_REVIEW"

    def diagnostic_form(self, cid):
        require(self._state == "HUMAN_OPEN" and not self._exposed, "HUMAN_RELEASE_BLOCKED")
        require(any(r.label != "PROMOTE" for r in self._reviews.get(cid, [])), "POST_FAILURE_ONLY")
        return {
            "candidate_id": cid,
            "optional_dimensions": list(DIAGNOSTICS),
            "instruction": "Record only source-anchored diagnostics needed to resolve this detected concern.",
        }

    def record_diagnostics(self, cid, notes, *, origin="SYNTHETIC"):
        require(origin == "SYNTHETIC", "GENUINE_HUMAN_LABELS_DISABLED")
        self.diagnostic_form(cid)
        require(cid not in self._diagnostics, "DIAGNOSTICS_IMMUTABLE")
        require(isinstance(notes, dict) and bool(notes) and set(notes) <= set(DIAGNOSTICS), "INVALID_DIAGNOSTICS")
        require(all(isinstance(note, str) and note.strip() for note in notes.values()), "DIAGNOSTIC_NOTE_REQUIRED")
        self._diagnostics[cid] = json.loads(canonical(notes))

    def private_artifacts(self):
        require(self._state in ("INTERSTUDY", "HUMAN_OPEN"), "INTERSTUDY_ACCESS_NOT_YET_ALLOWED")
        return {
            "freeze_a": json.loads(self._a) if self._a else None,
            "interstudy": json.loads(self._amendment) if self._amendment else None,
            "freeze_b": json.loads(self._b) if self._b else None,
            "frontier": list(self._screen.values()),
            "reviews": {cid: [asdict(r) for r in reviews] for cid, reviews in self._reviews.items()},
            "diagnostics": self._diagnostics.copy(),
        }


def synthetic_design(cases, *, seed="synthetic-v1", rationale="Fabricated concern patterns for workflow testing"):
    """Example only. Actual eligibility and allocations are decided after real Study 1."""
    validate_cases(cases)
    allocations = {}
    for config in sorted({c.configuration for c in cases}):
        pool = sorted([c for c in cases if c.configuration == config], key=lambda c: c.index)
        require(len(pool) >= 16, "SYNTHETIC_DEMO_NEEDS_16_UNITS")
        discovery = pool[:3]
        remainder = sorted(pool[3:], key=lambda c: digest([seed, config, c.candidate_id]))
        ids = [c.candidate_id for c in discovery + remainder]
        allocations[config] = {
            "discovery": ids[:3],
            "challenges": {
                "unflagged": ids[3:5],
                "screen_independent": ids[5:7],
                "relation": ids[7:9],
                "value_class": ids[9:12],
            },
            "expansion": ids[12:16],
        }
    return {
        "origin": "SYNTHETIC",
        "eligibility_rule": "Fabricated low-concern fixture region; no real ranking",
        "selection_rationale": rationale,
        "seed": seed,
        "max_unique_per_configuration": 24,
        "session_minutes": 20,
        "reread_rule": "fresh_session_hidden_prior_label",
        "severe_rule": "one_fresh_confirmed_severe",
        "allocations": allocations,
        "expansion_rule": "four preselected screen-independent cases after any confirmed unanimous-NO_FLAG miss",
        "replacement_rule": "no automatic replacement; explicit amendment for corruption or source-ineligibility",
        "visibility": "source, representation, opaque ID only; no phase/selection/frontier labels",
    }
