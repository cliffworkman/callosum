"""Background provisioning: independent per-track runners, the DeBERTa release gate, and app-lifespan wiring.

Each track runs on its own daemon thread, so ordinary startup never waits for a download, and Arctic and DeBERTa
never wait on each other. A runner stops when its track is ``verified`` or terminally ``invalid``; retryable states
sleep until the recorded ``next_attempt_at`` and try again, indefinitely, so a lost connection never needs a manual
restart. Shutdown is a request, not a wait: an in-flight file transfer is abandoned and resumed next launch.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from app.backend.model_provisioning.manifests import ARCTIC_S_TRACK, DEBERTA_TRACK, MANIFESTS, TRACK_FOR_MODEL
from app.backend.model_provisioning.provisioner import DOWNLOADING, TERMINAL, Provisioner, default_cache_dir

_log = logging.getLogger(__name__)

# DeBERTa is the product's intended verifier for 0.6.0, but it is downloaded automatically only once every gate
# below is recorded true. These are recorded facts, not derived from provisioning, so the gate cannot be circular.
DEBERTA_RELEASE_GATES: dict[str, bool] = {
    # G1 CONDITIONAL result accepted by product decision (not a PASS) + G2 conditional runtime acceptance (inc 615).
    "runtime_qualification_recorded": True,
    "operation_memory_guard": True,  # inc 619: per-operation memory precheck, recorded MiniLM2 fallback reason
    "verifier_provenance_and_failure": True,  # inc 619: actual verifier recorded; no mid-operation substitution
    "packaged_runtime_acceptance": False,  # PENDING: cold/warm 21-pair recheck on the packaged runtime (release step)
}


def deberta_auto_provisioning_armed(gates: dict[str, bool] | None = None) -> bool:
    return all((gates or DEBERTA_RELEASE_GATES).values())


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def auto_provisioning_enabled() -> bool:
    """On in the packaged app (Tauri sets ``CALLOSUM_APP_DATA_DIR``) or when explicitly requested; off for source
    checkouts and tests by default so development never starts an unrequested download."""
    if _truthy("CALLOSUM_DISABLE_MODEL_PROVISIONING"):
        return False
    return _truthy("CALLOSUM_MODEL_PROVISIONING") or bool(os.environ.get("CALLOSUM_APP_DATA_DIR"))


def default_state_dir() -> Path:
    explicit = os.environ.get("CALLOSUM_MODEL_PROVISIONING_DIR")
    if explicit:
        return Path(explicit)
    app_data = os.environ.get("CALLOSUM_APP_DATA_DIR")
    base = Path(app_data) if app_data else Path.home() / ".callosum"
    return base / "model-provisioning"


def default_provisioner(track: str) -> Provisioner:
    return Provisioner(MANIFESTS[track], cache_dir=default_cache_dir(), state_dir=default_state_dir())


def local_files_only_for(model_name: str) -> bool:
    """True once ``model_name``'s pinned checkpoint is verified: its consumers then load with ``local_files_only``
    and cannot reach the network. Unknown models and unreadable state keep the pre-615 behaviour (False)."""
    track = TRACK_FOR_MODEL.get(model_name)
    if track is None:
        return False
    try:
        return default_provisioner(track).is_verified()
    except Exception:  # noqa: BLE001 -- a status-file problem must never break inference
        return False


def checkpoint_pending(model_name: str) -> bool:
    """True when automatic provisioning manages ``model_name`` and its checkpoint is not yet verified (inc 618).

    Nothing may then load the model: an unprovisioned load would fetch weights from the Hugging Face Hub outside
    the inc-615 provisioner, unpinned to its byte manifest. Source checkouts without automatic provisioning keep the
    pre-615 developer path. An unreadable provisioning state counts as pending: never risk a network load on it.
    """
    track = TRACK_FOR_MODEL.get(model_name)
    if track is None or not auto_provisioning_enabled():
        return False
    try:
        return not default_provisioner(track).is_verified()
    except Exception:  # noqa: BLE001
        return True


class ProvisioningRunner:
    def __init__(
        self,
        provisioner: Provisioner,
        *,
        clock: Callable[[], float] = time.time,
        busy_poll_seconds: float = 60.0,
        min_wait_seconds: float = 1.0,
    ) -> None:
        self.provisioner = provisioner
        self._clock = clock
        self._busy_poll = busy_poll_seconds
        self._min_wait = min_wait_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_status: dict | None = None

    def run(self) -> dict:
        """Attempt until the track settles or a stop is requested; returns the last status."""
        status = self.provisioner.status()
        while not self._stop.is_set():
            try:
                status = self.provisioner.provision_once()
            except Exception as exc:  # noqa: BLE001 -- the runner must outlive any single failed attempt
                _log.warning("model provisioning attempt failed for %s: %s", self.provisioner.manifest.track, exc)
                status = {**self.provisioner.status(), "next_attempt_at": self._clock() + self._busy_poll}
            self.last_status = status
            if status["state"] in TERMINAL:
                break
            if status["state"] == DOWNLOADING:  # another instance owns the track
                wait = self._busy_poll
            else:
                wait = max(self._min_wait, float(status.get("next_attempt_at") or 0) - self._clock())
            self._stop.wait(wait)
        return status

    def start(self) -> ProvisioningRunner:
        self._thread = threading.Thread(
            target=self.run, name=f"model-provisioning-{self.provisioner.manifest.track}", daemon=True
        )
        self._thread.start()
        return self

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)


def provisioning_tracks(gates: dict[str, bool] | None = None) -> list[str]:
    tracks = [ARCTIC_S_TRACK]
    if deberta_auto_provisioning_armed(gates):
        tracks.append(DEBERTA_TRACK)
    return tracks


def start_model_provisioning(api: object) -> None:
    """Lifespan hook. Starts nothing unless enabled; never blocks startup."""
    runners: dict[str, ProvisioningRunner] = {}
    if auto_provisioning_enabled():
        for track in provisioning_tracks():
            try:
                runners[track] = ProvisioningRunner(default_provisioner(track)).start()
            except Exception as exc:  # noqa: BLE001 -- provisioning must never prevent the app from starting
                _log.warning("could not start model provisioning for %s: %s", track, exc)
    api.state.model_provisioning = runners  # type: ignore[attr-defined]


def stop_model_provisioning(api: object) -> None:
    for runner in (getattr(api.state, "model_provisioning", None) or {}).values():  # type: ignore[attr-defined]
        runner.stop()
