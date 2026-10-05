"""Sufficiency-semantics identity (Phase 32 / I1c). One stamping path, one reader, explicit fail-closed rules.

What the identity answers: which mapping, completion, recovery and stop-search semantics produced a diagnostic sufficiency
map. It is separate from two other identities:

- frozen contract identity: authored content (the frozen v9 contract and its review), changed only by a new frozen version;
- code revision: external git provenance. This module does not record a commit hash, to avoid self-reference and
  dirty-tree nondeterminism.

Authored contracts (sufficiency_authoring.build_qaib_contract) are NOT stamped. They feed the frozen artifact, and stamping
them would change frozen content. Only produced diagnostic maps are stamped, through ``stamp_map``.

Three states are distinguished, and they are never inferred from one another:

- ``current``: every child contract carries a supported SUFFICIENCY_SEMANTICS_VERSION.
- ``historical_unversioned``: no child contract carries the key. This is a historical map (for example the preserved
  Phase-28 map). It is recognised explicitly. It is never treated as current merely because the key is absent.
- anything else (mixed, partial, unsupported, non-string): an error, in every mode.

Production rule: a new artifact must be ``current``. Only an explicit historical compatibility path may accept
``historical_unversioned``.
"""

from __future__ import annotations

import copy

from experiments.ask_cli_revised import sufficiency_engine as se

STATUS_CURRENT = "current"
STATUS_HISTORICAL_UNVERSIONED = "historical_unversioned"
_MISSING = object()


class SemanticsIdentityError(ValueError):
    """Raised when a sufficiency-semantics identity is missing where required, unsupported, mixed, or tampered."""


def stamp_map(mapped: dict) -> dict:
    """The single authoritative stamping path for produced diagnostic sufficiency maps. Mutates and returns ``mapped``."""
    for contract in mapped.values():
        contract[se.SEMANTICS_VERSION_KEY] = se.SUFFICIENCY_SEMANTICS_VERSION
    return mapped


def read_map_identity(smap: dict, *, require_current: bool = False) -> dict:
    """Return ``{"status": ..., "version": ...}`` for a map. Raises ``SemanticsIdentityError`` on any inconsistency.

    ``require_current=True`` is the production rule: a historical or unversioned map is an error.
    """
    if not smap:
        raise SemanticsIdentityError("an empty sufficiency map carries no semantics identity")
    values = []
    for child_id, contract in smap.items():
        if not isinstance(contract, dict):
            raise SemanticsIdentityError(f"child {child_id!r} is not a contract mapping")
        values.append(contract.get(se.SEMANTICS_VERSION_KEY, _MISSING))
    present = [value for value in values if value is not _MISSING]
    if not present:
        if require_current:
            raise SemanticsIdentityError(
                "production requires a current sufficiency-semantics identity; this map is historical_unversioned"
            )
        return {"status": STATUS_HISTORICAL_UNVERSIONED, "version": None}
    if len(present) != len(values):
        raise SemanticsIdentityError("partial sufficiency-semantics identity: some children are unversioned")
    if any(not isinstance(value, str) for value in present):
        raise SemanticsIdentityError("sufficiency-semantics version must be a string")
    if len(set(present)) != 1:
        raise SemanticsIdentityError("mixed sufficiency-semantics versions across children")
    (version,) = set(present)
    if version not in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS:
        raise SemanticsIdentityError(f"unsupported sufficiency-semantics version {version!r}")
    return {"status": STATUS_CURRENT, "version": version}


def check_authorization_binding(bound: dict, smap: dict) -> None:
    """A replay authorization's recorded identity must equal the identity read from the map it binds. Mismatch fails closed."""
    if not isinstance(bound, dict) or set(bound) != {"status", "version"}:
        raise SemanticsIdentityError("authorization carries a malformed sufficiency-semantics binding")
    actual = read_map_identity(smap)
    if bound != actual:
        raise SemanticsIdentityError(
            f"authorization binds sufficiency-semantics {bound!r} but the map carries {actual!r}"
        )


def strip_identity(smap: dict) -> dict:
    """A deep copy with ONLY the sufficiency-semantics identity key removed from each contract. Used for parity projection."""
    projected = copy.deepcopy(smap)
    for contract in projected.values():
        contract.pop(se.SEMANTICS_VERSION_KEY, None)
    return projected
