"""CRediTer — the deterministic core of the CRediT contribution-statement builder (inc 261).

Formats an authors × role assignment (the **NISO CRediT** taxonomy — 14 fixed contributor roles, each optionally
qualified by a degree of contribution: lead / equal / supporting) into a human-readable contributorship statement,
in two layouts: **by author** (each contributor → their roles) and **by role** (each role → its contributors).

THE LOAD-BEARING BOUNDARY — build, never infer. This is an authoring aid: it formats the contributions the human
*asserts*. It NEVER reads a PDF, never infers who did what, never judges or verifies a contribution — there is no
model, no scoring, no aggregation here (test-pinned). The human is the source of truth; Callosum only formats. It is
deterministic, local, no-LLM, no-egress.

Lineage (credited in-context in the UI + THIRD-PARTY-NOTICES, per CREDIT-THE-LINEAGE.md): the **CRediT / NISO**
taxonomy itself (Brand, Allen, Altman, Hlava & Scott 2015, *Learned Publishing*; ANSI/NISO Z39.104-2022) and
**tenzing**, the prior tool this operationalizes the idea of (Holcombe, Kovacs, Aust & Aczel 2020, *PLOS ONE*).
Deliberately named "CRediTer", never "tenzing".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# The 14 NISO CRediT roles, canonical taxonomy order. Keys are stable snake_case; labels are the official strings
# (the two "Writing" roles carry the official en-dash + ampersand forms).
CREDIT_ROLES: list[dict] = [
    {"key": "conceptualization", "label": "Conceptualization"},
    {"key": "data_curation", "label": "Data curation"},
    {"key": "formal_analysis", "label": "Formal analysis"},
    {"key": "funding_acquisition", "label": "Funding acquisition"},
    {"key": "investigation", "label": "Investigation"},
    {"key": "methodology", "label": "Methodology"},
    {"key": "project_administration", "label": "Project administration"},
    {"key": "resources", "label": "Resources"},
    {"key": "software", "label": "Software"},
    {"key": "supervision", "label": "Supervision"},
    {"key": "validation", "label": "Validation"},
    {"key": "visualization", "label": "Visualization"},
    {"key": "writing_original_draft", "label": "Writing – original draft"},
    {"key": "writing_review_editing", "label": "Writing – review & editing"},
]

_ROLE_LABEL = {r["key"]: r["label"] for r in CREDIT_ROLES}
_ROLE_ORDER = {r["key"]: i for i, r in enumerate(CREDIT_ROLES)}
ROLE_KEYS = frozenset(_ROLE_LABEL)

# Optional degree of contribution (CRediT allows lead/equal/supporting; unset = contributed, degree unstated).
DEGREES = ("lead", "equal", "supporting")

# This module INFERS nothing and AGGREGATES nothing — it formats asserted facts. It defines no read/infer/score/
# judge/verify/aggregate function; a test pins that (the fact-vs-candidate boundary — the statement is the author's
# asserted fact, not a Callosum claim about the literature).
NO_INFERENCE = True

# Caps (rule #4 — bound untrusted request input).
MAX_AUTHORS = 50
MAX_ROLES_PER_AUTHOR = len(CREDIT_ROLES)  # 14
MAX_NAME_LEN = 200


@dataclass(frozen=True)
class CreditStatement:
    """A formatted contributorship statement in both layouts, plus the taxonomy legend."""

    by_author: list[str] = field(default_factory=list)  # one line per contributing author (input order)
    by_role: list[str] = field(default_factory=list)  # one line per used role (canonical taxonomy order)
    roles: list[dict] = field(default_factory=lambda: list(CREDIT_ROLES))  # the fixed taxonomy (for the UI legend)

    def to_dict(self) -> dict:
        return asdict(self)


def _degree_suffix(degree) -> str:
    return f" ({degree})" if degree in DEGREES else ""


def _join_names(names: list[str], *, use_and: bool) -> str:
    """Join a role's contributor names. Plain `", "` by default (unchanged); an opt-in `use_and` (backlog #26,
    debated in the inc-261 experience pass) inserts an Oxford "and" before the last name for 2+ names — a pure
    formatting choice, never a claim about the contributors."""
    if not use_and or len(names) < 2:
        return ", ".join(names)
    return ", ".join(names[:-1]) + ", and " + names[-1] if len(names) > 2 else " and ".join(names)


def _normalise(authors) -> list[dict]:
    """Validate + normalise the request into [{name, roles: [{role, degree}]}] with canonical, de-duped roles.

    Raises ValueError on any unknown role / degree or a cap violation (rule #4). An author's blank name or empty
    role set is *not* an error (a mid-entry grid row) — such rows are simply omitted from the formatted output.
    """
    if not isinstance(authors, list):
        raise ValueError("authors must be a list")
    if len(authors) > MAX_AUTHORS:
        raise ValueError(f"too many authors (max {MAX_AUTHORS})")

    out = []
    for author in authors:
        if not isinstance(author, dict):
            raise ValueError("each author must be an object")
        name = str(author.get("name") or "").strip()
        if len(name) > MAX_NAME_LEN:
            raise ValueError(f"author name too long (max {MAX_NAME_LEN} chars)")
        raw_roles = author.get("roles") or []
        if not isinstance(raw_roles, list):
            raise ValueError("roles must be a list")
        if len(raw_roles) > MAX_ROLES_PER_AUTHOR:
            raise ValueError(f"too many roles for one author (max {MAX_ROLES_PER_AUTHOR})")
        seen = {}
        for r in raw_roles:
            if not isinstance(r, dict):
                raise ValueError("each role must be an object")
            key = r.get("role")
            if key not in ROLE_KEYS:
                raise ValueError(f"unknown CRediT role: {key!r}")
            degree = r.get("degree")
            if degree is not None and degree not in DEGREES:
                raise ValueError(f"unknown degree: {degree!r}")
            seen[key] = degree  # last write wins; de-dupes a repeated role
        roles = [{"role": k, "degree": seen[k]} for k in sorted(seen, key=_ROLE_ORDER.__getitem__)]
        out.append({"name": name, "roles": roles})
    return out


def validate(authors) -> None:
    """Public validation hook (raises ValueError on malformed input); mirrors _normalise's checks."""
    _normalise(authors)


def format_statement(authors, *, use_and: bool = False) -> CreditStatement:
    """Format the asserted authors × roles into a CreditStatement (both layouts). Empty input → empty statement.
    `use_and` (default off — opt-in, backlog #26) inserts an Oxford "and" before the last name in each **by-role**
    contributor list; the by-author per-author role list is unaffected (the backlog's own scoping — only the
    by-role name lists were the debated case)."""
    norm = _normalise(authors)

    # by-author: each contributing author (blank name or no roles omitted), roles in canonical order.
    by_author = []
    for a in norm:
        if not a["name"] or not a["roles"]:
            continue
        parts = [f"{_ROLE_LABEL[r['role']]}{_degree_suffix(r['degree'])}" for r in a["roles"]]
        by_author.append(f"{a['name']}: {', '.join(parts)}.")

    # by-role: each used role (canonical order), its contributors in input order.
    contributors: dict[str, list[str]] = {}
    for a in norm:
        if not a["name"]:
            continue
        for r in a["roles"]:
            contributors.setdefault(r["role"], []).append(f"{a['name']}{_degree_suffix(r['degree'])}")
    by_role = []
    for role in CREDIT_ROLES:
        names = contributors.get(role["key"])
        if names:
            by_role.append(f"{role['label']}: {_join_names(names, use_and=use_and)}.")

    return CreditStatement(by_author=by_author, by_role=by_role, roles=list(CREDIT_ROLES))
