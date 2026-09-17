"""Phase -1 machinery: purely mechanical synthetic copying, never semantic judging."""

from dataclasses import asdict, dataclass

from .core import ROLES, ROSTER, SyntheticCase, digest, identifier, require, sha
from .transport import render

HIDDEN_CHECKS = ("viewport", "notifications", "previews", "clipboard_history", "terminal", "exceptions")


@dataclass(frozen=True)
class CapabilityPacket:
    profile: str
    count: int
    padding: int
    response_width: int
    format: str = "txt"

    def __post_init__(self):
        require(self.profile in ("compact", "intended", "largest"), "INVALID_PROFILE")
        require(type(self.count) is int and 1 <= self.count <= 1000, "INVALID_PACKET_COUNT")
        require(type(self.response_width) is int and 8 <= self.response_width <= 4096, "INVALID_RESPONSE_WIDTH")

    @property
    def cases(self):
        return tuple(
            SyntheticCase(i, "fixture_b" if i % 2 or self.profile == "largest" else "fixture_a", self.padding)
            for i in range(self.count)
        )

    @property
    def packet_id(self):
        return "cap-" + digest(asdict(self))[:24]

    @property
    def expected(self):
        return (
            "\n".join(f"{c.candidate_id} | COPY_OK | " + "z" * self.response_width for c in self.cases) + "\n"
        ).encode("utf-8")

    @property
    def payload(self):
        prompt = (
            "MECHANICAL SYNTHETIC CAPABILITY AUDIT. Do not evaluate meaning or scientific fidelity.\n"
            "For every candidate_id in the packet, copy the identifier exactly, in order, then output\n"
            f"candidate_id | COPY_OK | followed by exactly {self.response_width} lowercase z characters.\n"
            "One line per identifier, no header or commentary. All material is fabricated.\n"
        ).encode("utf-8")
        return prompt + render(self.cases, self.format)

    def receipt(self):
        return {
            "origin": "SYNTHETIC",
            "packet_id": self.packet_id,
            "profile": self.profile,
            "candidate_count": self.count,
            "input_bytes": len(self.payload),
            "expected_response_bytes": len(self.expected),
            "payload_sha256": sha(self.payload),
            "expected_response_sha256": sha(self.expected),
            "parameters": asdict(self),
        }

    def check_response(self, raw):
        # Only line-ending variation is mechanically normalized; no semantic repair.
        try:
            actual = raw.decode("utf-8").replace("\r\n", "\n").rstrip("\n")
        except UnicodeError:
            return "MECHANICAL_FAILURE"
        return "PASS" if actual == self.expected.decode().rstrip("\n") else "MECHANICAL_FAILURE"


def suite(*, intended_count=8, intended_padding=2048, largest_padding=16000, response_width=160, format="txt"):
    return (
        CapabilityPacket("compact", 2, 64, 8, format),
        CapabilityPacket("intended", intended_count, intended_padding, response_width, format),
        CapabilityPacket("largest", 1, largest_padding, response_width, format),
    )


def capability_template(surface_id, intended_label):
    identifier(surface_id)
    return {
        "surface_id": surface_id,
        "intended_label": intended_label,
        "origin": "UNOBSERVED",
        "displayed_model": None,
        "surface": None,
        "account_plan_alias": None,
        "observed_at_utc": None,
        "accepted_formats": [],
        "transport": None,
        "tested_input_bytes": None,
        "tested_output_bytes": None,
        "tested_file_count": None,
        "hard_context_limit": None,
        "output_constraints": None,
        "rate_limits": None,
        "source_only_controls": None,
        "hidden_checks": {key: None for key in HIDDEN_CHECKS},
        "hidden_evidence_sha256": None,
        "profile_receipts": [],
        "mechanical_failures": [],
        "status": "UNTESTED",
    }


def assess_capability(record, packets):
    """Does not perform a trial; assesses documented receipts without inventing availability."""
    if record.get("mechanical_failures") or any(v is False for v in record.get("hidden_checks", {}).values()):
        return "TECHNICALLY_UNAVAILABLE"
    required = (
        "displayed_model",
        "surface",
        "account_plan_alias",
        "observed_at_utc",
        "transport",
        "hidden_evidence_sha256",
        "source_only_controls",
    )
    if record.get("origin") not in ("SYNTHETIC", "ACTUAL") or not all(record.get(k) for k in required):
        return "UNTESTED"
    hidden = record.get("hidden_checks", {})
    if set(hidden) != set(HIDDEN_CHECKS) or not all(v is True for v in hidden.values()):
        return "UNTESTED"
    if record["transport"] not in ("hidden_capture", "direct_export", "qualified_clipboard"):
        return "TECHNICALLY_UNAVAILABLE"
    if any(p.format not in record.get("accepted_formats", []) for p in packets):
        return "TECHNICALLY_UNAVAILABLE"
    receipts = record.get("profile_receipts", [])
    if len(receipts) != len(packets) or len({r.get("packet_id") for r in receipts}) != len(packets):
        return "UNTESTED"
    by_id = {r["packet_id"]: r for r in receipts}
    for packet in packets:
        receipt = by_id.get(packet.packet_id, {})
        if receipt.get("status") == "MECHANICAL_FAILURE":
            return "TECHNICALLY_UNAVAILABLE"
        if (
            receipt.get("status") != "PASS"
            or receipt.get("payload_sha256") != sha(packet.payload)
            or not receipt.get("raw_sha256")
        ):
            return "UNTESTED"
    if (
        not isinstance(record.get("tested_input_bytes"), int)
        or record["tested_input_bytes"] < max(len(p.payload) for p in packets)
        or not isinstance(record.get("tested_output_bytes"), int)
        or record["tested_output_bytes"] < max(len(p.expected) for p in packets)
        or not isinstance(record.get("tested_file_count"), int)
    ):
        return "UNTESTED"
    return "QUALIFIED_SYNTHETIC" if record["origin"] == "SYNTHETIC" else "QUALIFIED"


def assign_roles(records, packets, *, synthetic_only=True):
    require(synthetic_only is True, "REAL_STUDY_DISABLED")
    require(len({r["surface_id"] for r in records}) == len(records), "DUPLICATE_RATER")
    require({r["surface_id"] for r in records} <= {sid for sid, _ in ROSTER}, "UNREGISTERED_RATER")
    qualified = [r for r in records if assess_capability(r, packets) == "QUALIFIED_SYNTHETIC"]
    rank = {sid: i for i, (sid, _) in enumerate(ROSTER)}
    qualified.sort(key=lambda r: rank[r["surface_id"]])
    require(len(qualified) >= 3, "ATTENTIONAL_COVERAGE_AMENDMENT_REQUIRED")
    assignments = {r["surface_id"]: [] for r in qualified}
    for i, role in enumerate(ROLES):
        assignments[qualified[i % len(qualified)]["surface_id"]].append(role)
    for roles in assignments.values():
        if not roles:
            roles.append("skeptical_review")
    require(max(map(len, assignments.values())) <= 3, "ATTENTIONAL_COVERAGE_AMENDMENT_REQUIRED")
    return {key: tuple(value) for key, value in assignments.items()}


def synthetic_evidence(surface_id, packets):
    """Explicit fake evidence for tests/demo; never masquerades as actual qualification."""
    labels = dict(ROSTER)
    require(surface_id in labels, "UNREGISTERED_RATER")
    value = capability_template(surface_id, labels[surface_id])
    value.update(
        {
            "origin": "SYNTHETIC",
            "displayed_model": "FAKE_MODEL",
            "surface": "FAKE_SURFACE",
            "account_plan_alias": "FAKE_ACCOUNT",
            "observed_at_utc": "2000-01-01T00:00:00Z",
            "accepted_formats": [p.format for p in packets],
            "transport": "hidden_capture",
            "tested_input_bytes": max(len(p.payload) for p in packets),
            "tested_output_bytes": max(len(p.expected) for p in packets),
            "tested_file_count": 1,
            "hidden_checks": dict.fromkeys(HIDDEN_CHECKS, True),
            "hidden_evidence_sha256": digest("FAKE"),
            "source_only_controls": "SYNTHETIC ONLY; no provider contacted",
            "profile_receipts": [
                {
                    "packet_id": p.packet_id,
                    "status": "PASS",
                    "payload_sha256": sha(p.payload),
                    "raw_sha256": sha(p.expected),
                }
                for p in packets
            ],
        }
    )
    return value
