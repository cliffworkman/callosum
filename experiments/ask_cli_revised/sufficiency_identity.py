"""Sufficiency-semantics identity (Phase 32 / I1c, versioned in I1d). One stamping path, one reader, explicit fail-closed rules.

What the identity answers: which mapping, completion, recovery, stop-search and witness semantics produced a diagnostic
sufficiency map. It is separate from two other identities:

- frozen contract identity: authored content (the frozen v9 contract and its review), changed only by a new frozen version;
- code revision: external git provenance. This module does not record a commit hash, to avoid self-reference and
  dirty-tree nondeterminism.

Authored contracts (sufficiency_authoring.build_qaib_contract) are NOT stamped. They feed the frozen artifact, and stamping
them would change frozen content. Only produced diagnostic maps are stamped, through ``stamp_map``.

Four valid dispositions and an error state are distinguished:

- ``current``: every child carries SUFFICIENCY_SEMANTICS_VERSION (the only version new production accepts).
- ``supported_noncurrent``: every child carries a supported version that is neither current nor historical. It is
  readable only through an explicit supported-noncurrent path and applies its own recorded version.
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
STATUS_SUPPORTED_NONCURRENT = "supported_noncurrent"
STATUS_HISTORICAL_VERSIONED = "historical_versioned"
STATUS_HISTORICAL_UNVERSIONED = "historical_unversioned"
_MISSING = object()


class SemanticsIdentityError(ValueError):
    """Raised when a sufficiency-semantics identity is missing where required, unsupported, mixed, or tampered."""


def stamp_map(mapped: dict, *, semantics_version: str) -> dict:
    """The single authoritative stamping path for produced diagnostic sufficiency maps. Mutates and returns ``mapped``.

    The caller supplies the version (I2-0). Stamping never selects the current version by default.
    """
    se.require_supported_semantics_version(semantics_version)
    for contract in mapped.values():
        contract[se.SEMANTICS_VERSION_KEY] = semantics_version
    return mapped


def read_map_identity(
    smap: dict,
    *,
    accept_historical_versioned: bool = False,
    accept_historical_unversioned: bool = False,
    accept_supported_noncurrent: bool = False,
) -> dict:
    """Return ``{"status": ..., "version": ...}`` for a map. Raises ``SemanticsIdentityError`` on any inconsistency.

    ``current`` is always accepted. Each other disposition requires its own independent opt-in flag. With all flags
    false (production), anything other than the current version is an error.
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
    if version in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS:
        if accept_supported_noncurrent:
            return {"status": STATUS_SUPPORTED_NONCURRENT, "version": version}
        raise SemanticsIdentityError(
            f"sufficiency-semantics version {version!r} is supported_noncurrent; it is not accepted without an "
            "explicit supported-noncurrent path"
        )
    raise SemanticsIdentityError(f"unsupported sufficiency-semantics version {version!r}")


def applied_semantics_version(identity: dict) -> str:
    """The sufficiency-semantics rules the answer layer applies for a map with this identity: inherited-referent containment
    (I1d) and direction-target semantics (I3), which change together by version. Pure.

    - current, supported_noncurrent and historical_versioned: the map's own recorded version.
      That version's behaviour is what the map encodes.
    - historical_unversioned: the CONTEMPORARY rule, applied explicitly. The artifact does not record a version, so it is
      not attributed one. The application is recorded in the replay identity (see answer_plan.replay).
    """
    status = identity.get("status")
    if status in (STATUS_CURRENT, STATUS_HISTORICAL_VERSIONED, STATUS_SUPPORTED_NONCURRENT):
        return identity["version"]
    if status == STATUS_HISTORICAL_UNVERSIONED:
        return se.SUFFICIENCY_SEMANTICS_VERSION
    raise SemanticsIdentityError(f"unknown sufficiency-semantics identity status {status!r}")


def check_authorization_binding(bound: dict, smap: dict) -> None:
    """A replay authorization's recorded identity must equal the identity read from the map it binds. Mismatch fails closed.

    Any of the four valid states is accepted here: this checks consistency, not whether a path may use the map.
    """
    if not isinstance(bound, dict) or set(bound) != {"status", "version"}:
        raise SemanticsIdentityError("authorization carries a malformed sufficiency-semantics binding")
    actual = read_map_identity(
        smap,
        accept_historical_versioned=True,
        accept_historical_unversioned=True,
        accept_supported_noncurrent=True,
    )
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
