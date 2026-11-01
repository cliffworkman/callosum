"""Automatic background modernization of an existing library (inc 617): source-role v2 classification and Arctic S
index scheduling, coordinated from stored truth. See ``coordinator`` for the rules."""

from __future__ import annotations

import os

from app.backend.modernization.coordinator import (
    AUTO,
    PAUSED,
    CoordinatorConfig,
    ModernizationCoordinator,
    read_intent,
)

__all__ = [
    "AUTO",
    "PAUSED",
    "CoordinatorConfig",
    "ModernizationCoordinator",
    "arctic_model_status",
    "modernization_enabled",
    "read_intent",
]


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def modernization_enabled() -> tuple[bool, str | None]:
    """On in the packaged app (Tauri sets ``CALLOSUM_APP_DATA_DIR``) or when requested; off for source checkouts and
    tests by default, like inc-615 provisioning, so development never starts unrequested background work."""
    if _truthy("CALLOSUM_DISABLE_MODERNIZATION"):
        return False, "disabled_by_environment"
    if _truthy("CALLOSUM_MODERNIZATION") or os.environ.get("CALLOSUM_APP_DATA_DIR"):
        return True, None
    return False, "development_checkout"


def arctic_model_status() -> dict:
    """The inc-615 provisioning state of the pinned Arctic S checkpoint: local reads only, no hashing, no network."""
    from app.backend.model_provisioning.manifests import ARCTIC_S_TRACK
    from app.backend.model_provisioning.runner import auto_provisioning_enabled, default_provisioner

    status = default_provisioner(ARCTIC_S_TRACK).status()
    return {"track": ARCTIC_S_TRACK, "state": status["state"], "automatic_provisioning": auto_provisioning_enabled()}
