"""Sufficiency-semantics identity (Phase 32 / I1c, versioned in I1d). One stamping path, one reader, explicit fail-closed rules.

What the identity answers: which mapping, completion, recovery, stop-search and witness semantics produced a diagnostic
sufficiency map. It is separate from two other identities:

- frozen contract identity: authored content (the frozen v9 contract and its review), changed only by a new frozen version;
- code revision: external git provenance. This module does not record a commit hash, to avoid self-reference and
  dirty-tree nondeterminism.

Authored contracts (sufficiency_authoring.build_qaib_contract) are NOT stamped. They feed the frozen artifact, and stamping
them would change frozen content. Only produced diagnostic maps are stamped, through ``stamp_map``.

Four states are distinguished. None is inferred from another:

- ``current``: every child carries SUFFICIENCY_SEMANTICS_VERSION (the only version new production accepts).
- ``historical_versioned``: every child carries a supported HISTORICAL version (for example v1). It is readable only
  through an explicit historical path, and its exact version is recorded. It is never current.
- ``historical_unversioned``: no child carries the key. Recognised only through an explicit historical path. It is never
  treated as current, and its semantics are not attributed to any version the artifact does not record.
- anything else (mixed, partial, unknown, non-string): an error in every mode.

Membership in ``SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS`` means only that a version can be READ. It does not make a
version current.
"""

from __future__ import annotations

import copy

from experiments.ask_cli_revised import sufficiency_engine as se

STATUS_CURRENT = "current"
STATUS_HISTORICAL_VERSIONED = "historical_versioned"
STATUS_HISTORICAL_UNVERSIONED = "historical_unversioned"
_MISSING = object()


class SemanticsIdentityError(ValueError):
    """Raised when a sufficiency-semantics identity is missing where required, unsupported, mixed, or tampered."""


def stamp_map(mapped: dict) -> dict:
    """The single authoritative stamping path for produced diagnostic sufficiency maps. Mutates and returns ``mapped``."""
    for contract in mapped.values():
        contract[se.SEMANTICS_VERSION_KEY] = se.SUFFICIENCY_SEMANTICS_VERSION
    return mapped


def read_map_identity(
    smap: dict,
    *,
    accept_historical_versioned: bool = False,
    accept_historical_unversioned: bool = False,
) -> dict:
    """Return ``{"status": ..., "version": ...}`` for a map. Raises ``SemanticsIdentityError`` on any inconsistency.

    ``current`` is always accepted. The historical states are accepted only when their explicit flag is set. With both
    flags false (production), anything other than the current version is an error.
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
        if accept_historical_unversioned:
            return {"status": STATUS_HISTORICAL_UNVERSIONED, "version": None}
        raise SemanticsIdentityError(
            "this map has no sufficiency-semantics identity (historical_unversioned); it is not accepted without an "
            "explicit historical-unversioned path"
        )
    if len(present) != len(values):
        raise SemanticsIdentityError("partial sufficiency-semantics identity: some children are unversioned")
    if any(not isinstance(value, str) for value in present):
        raise SemanticsIdentityError("sufficiency-semantics version must be a string")
    if len(set(present)) != 1:
        raise SemanticsIdentityError("mixed sufficiency-semantics versions across children")
    (version,) = set(present)
    if version == se.SUFFICIENCY_SEMANTICS_VERSION:
        return {"status": STATUS_CURRENT, "version": version}
    if version in se.HISTORICAL_SUFFICIENCY_SEMANTICS_VERSIONS:
        if accept_historical_versioned:
            return {"status": STATUS_HISTORICAL_VERSIONED, "version": version}
        raise SemanticsIdentityError(
            f"sufficiency-semantics version {version!r} is a historical version and is not current; it is not accepted "
            "without an explicit historical-versioned path"
        )
    raise SemanticsIdentityError(f"unsupported sufficiency-semantics version {version!r}")


def applied_containment_version(identity: dict) -> str:
    """The inherited-referent containment rule the answer layer applies for a map with this identity. Pure.

    - current and historical_versioned: the map's own recorded version. That version's behaviour is what the map encodes.
    - historical_unversioned: the CONTEMPORARY rule, applied explicitly. The artifact does not record a version, so it is
      not attributed one. The application is recorded in the replay identity (see answer_plan.replay).
    """
    status = identity.get("status")
    if status in (STATUS_CURRENT, STATUS_HISTORICAL_VERSIONED):
        return identity["version"]
    if status == STATUS_HISTORICAL_UNVERSIONED:
        return se.SUFFICIENCY_SEMANTICS_VERSION
    raise SemanticsIdentityError(f"unknown sufficiency-semantics identity status {status!r}")


def check_authorization_binding(bound: dict, smap: dict) -> None:
    """A replay authorization's recorded identity must equal the identity read from the map it binds. Mismatch fails closed.

    Any of the three states is accepted here: this checks consistency of the binding, not whether a path may use the map.
    """
    if not isinstance(bound, dict) or set(bound) != {"status", "version"}:
        raise SemanticsIdentityError("authorization carries a malformed sufficiency-semantics binding")
    actual = read_map_identity(smap, accept_historical_versioned=True, accept_historical_unversioned=True)
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
