"""Bounded reason-sized literal copying, without semantic evaluation or real loaders."""

from dataclasses import dataclass

from .core import ROLES, SyntheticCase, canonical, semantic_prompt, sha

MAX_INPUT_BYTES = 20480  # includes any submission wrapper
WRAPPER_RESERVE = 128
PROMPT_RESERVE = 2048
MAX_REASON_BYTES = 512
MAX_ID_BYTES = 80
MAX_CANDIDATES = 2
MAX_RESPONSE_BYTES = 1216  # 2 * (80 + 3 + 9 + 3 + 512 + 1)
WRAPPER = "Execute only the mechanical copying instructions in the attached synthetic packet."


@dataclass(frozen=True)
class ReasonEnvelope:
    """Fixed generated fixture, not a constructor accepting external observations."""

    @property
    def expected(self):
        rows = []
        for i in range(2):
            identifier = "s-" + (sha(f"synthetic-reason-{i}".encode()) * 2)[:78]
            anchor = f'Fabricated source anchor "tile {i}". This is a literal copying fixture, not an assessment. '
            words = "amber birch cloud dune elm fern grove hill iris jade kite lake moss north oak pine "
            reason = (anchor + words * 10)[:509] + "END"
            rows.append(f"{identifier} | UNCERTAIN | {reason}")
        return ("\n".join(rows) + "\n").encode()

    def _payload(self, long_padding):
        instructions = (
            "MECHANICAL SYNTHETIC REASON ENVELOPE v3. All material is fabricated.\n"
            "Do not evaluate meaning or scientific fidelity. Labels and reasons below are literal test data.\n"
            "Copy each complete line after RECEIPT_TO_COPY verbatim, once, in order.\n"
            "Return only the two lines, without headings, prose, tables or fences. Preserve spaces and END.\n"
            "The eventual row syntax is candidate_id | FLAG / UNCERTAIN / NO_FLAG | reason.\n"
            "This test uses two maximal UNCERTAIN rows; never decide or change their labels.\n"
            "The following inert reservation stands for the future shared prompt; it gives no semantic task.\n"
        ).encode()
        payload = instructions + b"PROMPT_RESERVATION " + b"p" * PROMPT_RESERVE + b"\nBEGIN PACKET\n"
        for i, row in enumerate(self.expected.decode().splitlines()):
            case = SyntheticCase(i, "fixture_b" if i else "fixture_a", 512 if i else long_padding).content()
            case["candidate_id"] = row.split(" | ")[0]
            payload += b"CASE " + canonical(case) + b"\nRECEIPT_TO_COPY\n" + row.encode() + b"\n"
        return payload + b"END PACKET\n"

    @property
    def payload(self):
        padding = MAX_INPUT_BYTES - WRAPPER_RESERVE - len(self._payload(0))
        assert padding >= 0
        return self._payload(padding)

    def receipt(self):
        return {
            "origin": "SYNTHETIC",
            "fixture_version": 3,
            "packet_id": "reason3-" + sha(self.payload)[:24],
            "input_bytes": len(self.payload),
            "wrapper_bytes": len(WRAPPER.encode()),
            "expected_output_bytes": len(self.expected),
            "payload_sha256": sha(self.payload),
            "expected_sha256": sha(self.expected),
            "max_input_bytes_including_wrapper": MAX_INPUT_BYTES,
            "max_candidates": MAX_CANDIDATES,
            "max_reason_utf8_bytes": MAX_REASON_BYTES,
            "max_identifier_ascii_bytes": MAX_ID_BYTES,
            "max_response_utf8_bytes": MAX_RESPONSE_BYTES,
            "reserved_prompt_bytes": PROMPT_RESERVE,
            "current_shared_prompt_all_roles_bytes": len(semantic_prompt(ROLES).encode()),
            "token_limits": "UNKNOWN; UTF-8 budgets do not establish provider token limits",
            "real_corpus_access": False,
        }

    def check_response(self, raw, *, empty_lines=False):
        try:
            text = raw.decode("utf-8").replace("\r\n", "\n").rstrip("\n")
        except UnicodeError:
            return "FAIL_ENCODING"
        if empty_lines:
            text = "\n".join(line for line in text.split("\n") if line != "")
        return "PASS" if text == self.expected.decode().rstrip("\n") else "FAIL_ROWS"
