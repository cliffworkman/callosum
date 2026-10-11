"""Recorded identity binding after event authentication, independent of runtime routing."""

from experiments.ask_cli_revised import sufficiency_engine as se
from experiments.ask_cli_revised.sufficiency_identity import SemanticsIdentityError


def check_recorded_binding(bound, smap, *, authorized_identity):
    """The caller first authenticates an event/profile; that event owns its disposition."""
    if not isinstance(bound, dict) or set(bound) != {"status", "version"} or bound != authorized_identity:
        raise SemanticsIdentityError("recorded identity differs from authorized event")
    if bound["status"] not in {"current", "supported_noncurrent", "historical_versioned"}:
        raise SemanticsIdentityError("unknown recorded disposition")
    if bound["version"] not in se.SUPPORTED_SUFFICIENCY_SEMANTICS_VERSIONS:
        raise SemanticsIdentityError("unknown recorded semantic version")
    if not smap or any(
        not isinstance(c, dict) or c.get(se.SEMANTICS_VERSION_KEY) != bound["version"] for c in smap.values()
    ):
        raise SemanticsIdentityError("recorded semantic version/map mismatch")
