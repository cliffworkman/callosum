"""Versioned literal-copy preflight; original counting fixtures remain immutable."""

from dataclasses import asdict, dataclass

from .capability import CapabilityPacket
from .core import SyntheticCase, digest, require
from .transport import render


@dataclass(frozen=True)
class CopyCapabilityPacket(CapabilityPacket):
    long_padding: int = 16000

    def __post_init__(self):
        super().__post_init__()
        require(self.format == "txt", "COPY_FIXTURE_REQUIRES_TXT")
        require(type(self.long_padding) is int and 0 <= self.long_padding <= 100000, "INVALID_LONG_PADDING")

    @property
    def cases(self):
        return tuple(
            SyntheticCase(i, "fixture_b" if i % 2 else "fixture_a", self.long_padding if i == 0 else self.padding)
            for i in range(self.count)
        )

    @property
    def packet_id(self):
        return "copy2-" + digest({"fixture_version": 2, **asdict(self)})[:24]

    def receipt_line(self, case):
        # Output size is supplied literally, never calculated by the surface.
        words = "amber birch cloud dune elm fern grove hill iris jade kite lake moss north oak pine "
        literal = (words * (self.response_width // len(words) + 1))[: self.response_width]
        return f"{case.candidate_id} | COPY_OK | {literal}END"

    @property
    def expected(self):
        return ("\n".join(self.receipt_line(c) for c in self.cases) + "\n").encode("utf-8")

    @property
    def payload(self):
        prompt = (
            "MECHANICAL SYNTHETIC CAPABILITY AUDIT v2. All material is fabricated.\n"
            "Do not evaluate meaning or scientific fidelity. Do not count or generate padding.\n"
            "Each synthetic record ends with RECEIPT_TO_COPY. Copy the complete line immediately\n"
            "after each marker verbatim, in packet order. Return only those lines, once each,\n"
            "without commentary, headings, tables, or code fences. Preserve spaces and END.\n"
            "Read through the final record. BEGIN PACKET\n"
        ).encode("utf-8")
        return (
            prompt
            + b"\n".join(
                render((c,), "txt") + b"\nRECEIPT_TO_COPY\n" + self.receipt_line(c).encode("utf-8") + b"\n"
                for c in self.cases
            )
            + b"END PACKET\n"
        )

    def receipt(self):
        return {**super().receipt(), "fixture_version": 2}


def copy_suite():
    """One combined envelope: eight records, including one long record, ~1.6 KB output."""
    return (CopyCapabilityPacket("intended", 8, 2048, 160),)


def packet_from_receipt(record):
    version = record.get("fixture_version", 1)
    require(version in (1, 2), "UNKNOWN_FIXTURE_VERSION")
    cls = CapabilityPacket if version == 1 else CopyCapabilityPacket
    packet = cls(**record["parameters"])
    require(packet.receipt() == record, "PACKET_IDENTITY_MISMATCH")
    return packet
