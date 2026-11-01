"""Automatic, restart-safe acquisition and verification of pinned model checkpoints (inc 615).

Provisioning makes a checkpoint available and proves its bytes and static contract; it does not activate a model,
qualify it scientifically, or change any threshold. Activation of Arctic S retrieval and DeBERTa verification
belongs to later increments.
"""

from app.backend.model_provisioning.manifests import ARCTIC_S_TRACK, DEBERTA_TRACK, MANIFESTS
from app.backend.model_provisioning.provisioner import STATES, Provisioner
from app.backend.model_provisioning.runner import (
    DEBERTA_RELEASE_GATES,
    ProvisioningRunner,
    checkpoint_pending,
    deberta_auto_provisioning_armed,
    local_files_only_for,
    start_model_provisioning,
    stop_model_provisioning,
)

__all__ = [
    "ARCTIC_S_TRACK",
    "DEBERTA_RELEASE_GATES",
    "DEBERTA_TRACK",
    "MANIFESTS",
    "STATES",
    "Provisioner",
    "ProvisioningRunner",
    "checkpoint_pending",
    "deberta_auto_provisioning_armed",
    "local_files_only_for",
    "start_model_provisioning",
    "stop_model_provisioning",
]
