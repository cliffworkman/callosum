"""Small content-addressed contracts. No archive loader or inference interface."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass


class BoundaryError(ValueError):
    """Messages are fixed codes, never caller-supplied semantic content."""


def require(condition, code):
    if not condition:
        raise BoundaryError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return sha(canonical(value))


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value), "INVALID_IDENTIFIER")
    return value


ROLES = (
    "literal_fidelity",
    "subject_population",
    "relationships_endpoints_direction",
    "null_mixed_uncertain",
    "unsupported_addition_neighboring_import",
    "qualifiers_modality",
    "proposition_reconstructability",
    "skeptical_review",
)
ROSTER = (
    ("claude", "Claude Opus 5"),
    ("gemini", "Gemini Pro"),
    ("grok", "Grok Instant"),
    ("copilot", "Microsoft Copilot"),
    ("deepseek", "DeepSeek"),
    ("kimi", "Kimi"),
    ("glm", "GLM / Z.AI"),
    ("chatgpt", "Separate ChatGPT account"),
    ("github_copilot", "GitHub Copilot"),
)
CRITERION = (
    "Is there a scientifically material reason this representation should not be promoted "
    "as a faithful carrier of the supplied source information?"
)
SOURCE_RULES = (
    "Compare the effective representation, including annotations, with the exact excerpt. "
    "Use surrounding context only to resolve references, not to import neighboring findings. "
    "Retained quotation does not excuse erroneous interpretation. Source-supported absence or "
    "uncertainty is permissible. Query irrelevance is not source infidelity. Omission of unrelated "
    "independent material is not automatically loss. Raw output cannot silently repair the effective "
    "representation. Flag unsupported additions, material loss, subject/population/construct substitution, "
    "changed direction or modality, null reversal, lost mixed/uncertain qualifications, invented relations, "
    "causal strengthening, or unusable representation. No external evidence or other raters' answers. "
    "NO_FLAG is not certification. Return candidate_id | FLAG / UNCERTAIN / NO_FLAG | short reason. "
    "Give a short source-anchored reason for FLAG or UNCERTAIN; no reason for NO_FLAG."
)


@dataclass(frozen=True)
class SyntheticCase:
    index: int
    configuration: str
    padding: int = 64

    def __post_init__(self):
        require(type(self.index) is int and 0 <= self.index < 10000, "INVALID_SYNTHETIC_INDEX")
        require(self.configuration in ("fixture_a", "fixture_b"), "SYNTHETIC_CONFIGURATION_ONLY")
        require(type(self.padding) is int and 0 <= self.padding <= 100000, "INVALID_PADDING")

    @property
    def candidate_id(self):
        return "s-" + digest(asdict(self))[:24]

    @property
    def unit_id(self):
        return f"synthetic-unit-{self.index}"

    def content(self):
        # Content is generated here, never accepted from a file or caller.
        marker = f"SYNTHETIC_SECRET_{self.index}"
        representation = {"value": f"token-{self.index}", "annotation": {"status": "UNVALIDATED"}}
        if self.configuration == "fixture_b":
            representation = {
                "annotation": {
                    f"slot_{slot}": {
                        "value": f"token-{self.index}-{slot}",
                        "anchor": "Fabricated Ω",
                        "status": "UNVALIDATED",
                    }
                    for slot in range(10)
                }
            }
        return {
            "origin": "SYNTHETIC",
            "candidate_id": self.candidate_id,
            "source": {
                "exact_excerpt": f"{marker}: tile Ω has code {self.index}.\nLiteral separator | and tab\tretained.",
                "grown_context": "Fabricated surrounding text. " + "x" * self.padding,
                "task_context": "Fabricated task; not scientific evidence.",
            },
            "raw_output": f"Synthetic token {self.index}",
            "effective_representation": representation,
        }


def synthetic_cases(count=12, padding=64):
    require(type(count) is int and 1 <= count <= 1000, "INVALID_SYNTHETIC_COUNT")
    return tuple(SyntheticCase(i, config, padding) for i in range(count) for config in ("fixture_a", "fixture_b"))


def validate_cases(cases):
    require(bool(cases) and all(type(c) is SyntheticCase for c in cases), "SYNTHETIC_CASES_ONLY")
    require(len({c.candidate_id for c in cases}) == len(cases), "DUPLICATE_CANDIDATE")


def semantic_prompt(roles):
    require(bool(roles) and len(set(roles)) == len(roles) and set(roles) <= set(ROLES), "INVALID_ROLES")
    return CRITERION + "\n" + SOURCE_RULES + "\nAttentional emphasis: " + ", ".join(roles)
