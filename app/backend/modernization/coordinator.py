"""Automatic background modernization of an existing library (inc 617).

When Callosum opens a library whose stored truth shows outdated work, this coordinator starts it without the user
asking: source-role v2 classification (``classification.SourceRoleClassifier``) and Arctic S indexing (by asking the
existing inc-610 ``IndexSupervisor`` to start; it owns the worker, its batches, checkpoints, resources, disk waits and
recovery). The coordinator adds no indexing machinery and no progress counter of its own: every decision is re-read
from the chunks, ``chunk_structure``, ``embeddings`` and ``embedding_index_runs`` tables.

Rules:

* **Explicit intent wins.** ``modernization_intent`` in ``library_settings`` is ``auto`` (default) or ``paused``. A
  pause stops classification between papers and pauses the Arctic build; both stay stopped across restarts until an
  explicit resume. An index build the user paused or cancelled from Settings is never restarted automatically --
  not after an import, not after a restart -- unless the user resumes it there, or resumes modernization *after*
  that pause or cancel (``modernization_resumed_at`` is compared with the run row's ``updated_at``).
* **One coordinator per library.** The process holding ``<library>.modernization.lock`` leads; other Callosum
  processes on the same library only report. The OS releases the lock if the leader exits or is killed, and a
  follower takes over on its next check.
* **Never an unverified model.** Arctic indexing is started only once the inc-615 provisioning state says the pinned
  checkpoint is verified. Until then indexing stays pending; provisioning recovers on its own schedule.
* **No busy loop.** With nothing to do the coordinator re-checks at ``check_seconds``; a cheap row-count signature
  gates the expensive coverage queries; a shortage waits ``retry_seconds``.
* **Scheduling only.** It never changes the selected retrieval profile and never activates DeBERTa (inc 618+).
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, func, select

from app.backend.embeddings import index_runs
from app.backend.embeddings.index_lock import WorkerLock, named_lock_path, try_lock
from app.backend.embeddings.profiles import ARCTIC_S_PROFILE_KEY, get_profile, profile_coverage
from app.backend.embeddings.retrieval_resolution import (
    SOURCE_MODERNIZATION,
    Preference,
    activate_arctic,
    read_preference,
)
from app.backend.modernization.classification import STOP_PAUSED, STOP_SHUTDOWN, SourceRoleClassifier
from app.backend.pdf_processing.structure_backfill import coverage as classification_coverage
from app.backend.persistence.chunk_structure_repo import classified_chunks_clause
from app.backend.persistence.schema import attachments, chunks, library_settings, papers
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION, chunk_structure
from app.backend.persistence.sqlite_retry import run_write

_log = logging.getLogger(__name__)

INTENT_SETTING = "modernization_intent"
RESUMED_AT_SETTING = "modernization_resumed_at"
AUTO, PAUSED = "auto", "paused"
_ACTIVE = set(index_runs.ACTIVE_STATES)


@dataclass(frozen=True)
class CoordinatorConfig:
    db_url: str
    check_seconds: float = 60.0
    retry_seconds: float = 60.0
    full_check_seconds: float = 1800.0  # safety net: recompute coverage even if the signature never moved


def _get_setting(engine: Engine, key: str) -> str | None:
    with engine.connect() as conn:
        return conn.execute(select(library_settings.c.value).where(library_settings.c.key == key)).scalar_one_or_none()


def _set_setting(engine: Engine, key: str, value: str) -> None:
    def write(conn) -> None:  # type: ignore[no-untyped-def]
        values = {"value": value, "updated_at": func.current_timestamp()}
        exists = conn.execute(select(library_settings.c.key).where(library_settings.c.key == key)).first()
        if exists is None:
            conn.execute(library_settings.insert().values(key=key, **values))
        else:
            conn.execute(library_settings.update().where(library_settings.c.key == key).values(**values))

    run_write(engine, write)


def _version_crc(version: str | None, chunk_id: int | None) -> int:
    if not version:
        return 0
    return (zlib.crc32(version.encode("utf-8")) * ((chunk_id or 0) % 1_000_003)) % 2_147_483_647


def _register_checksum(conn) -> None:  # type: ignore[no-untyped-def]
    """Per-connection deterministic SQL function for the signature (stdlib ``zlib``; no SQL text from data)."""
    conn.connection.driver_connection.create_function("callosum_version_crc", 2, _version_crc, deterministic=True)


def read_intent(engine: Engine) -> str:
    return PAUSED if _get_setting(engine, INTENT_SETTING) == PAUSED else AUTO


class ModernizationCoordinator:
    def __init__(
        self,
        engine: Engine,
        config: CoordinatorConfig,
        *,
        supervisor: Callable[[], object],
        model_status: Callable[[], dict],
        classifier: SourceRoleClassifier | None = None,
        enabled: bool = True,
        disabled_reason: str | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.engine = engine
        self.config = config
        self._supervisor = supervisor
        self._model_status = model_status
        self.classifier = classifier or SourceRoleClassifier(engine, config.db_url)
        self.enabled = enabled
        self.disabled_reason = disabled_reason
        self.clock = clock
        self._lock = threading.RLock()
        self._leader: WorkerLock | None = None
        self._closing = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._signature: tuple | None = None
        self._settled_signature: tuple | None = None
        self._index_marker: tuple | None = None
        self._last_full = float("-inf")
        self._index_coverage: dict | None = None
        self._class_coverage: dict | None = None
        self._class_state = "unknown"
        self._class_detail: str | None = None
        self._index_note: str | None = None
        self._checked_at: datetime | None = None

    # ---- user intent --------------------------------------------------------------------------------------------

    def pause(self) -> dict:
        """Durable: classification stops between papers and the Arctic build pauses; both stay stopped on restart."""
        _set_setting(self.engine, INTENT_SETTING, PAUSED)
        row = self._run_row()
        if row is not None and row["state"] in _ACTIVE and row["intent"] == "run":
            self._supervisor().pause(ARCTIC_S_PROFILE_KEY)  # type: ignore[attr-defined]
        self._wake.set()
        return self.status()

    def resume(self) -> dict:
        """Explicit resume: automatic work may restart, including an index build paused or cancelled before now."""
        _set_setting(self.engine, RESUMED_AT_SETTING, index_runs.now().isoformat())
        _set_setting(self.engine, INTENT_SETTING, AUTO)
        self._settled_signature = None  # retry papers that settled as failed before the resume
        self._wake.set()
        return self.status()

    # ---- lifecycle ------------------------------------------------------------------------------------------------

    def start(self) -> None:
        if self.enabled and self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="modernization-coordinator", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while not self._closing.is_set():
            delay = self.config.retry_seconds
            try:
                delay = self.tick()
            except Exception as exc:  # noqa: BLE001 -- the coordinator must never take the app down
                _log.warning("modernization check failed: %s", type(exc).__name__)
            self._wake.wait(delay)
            self._wake.clear()

    def shutdown(self, timeout: float = 10.0) -> None:
        """App exit: a classification pass stops before its next paper; the paper in flight commits or rolls back."""
        self._closing.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)
        with self._lock:
            if self._leader is not None:
                self._leader.release()
                self._leader = None

    @property
    def is_leader(self) -> bool:
        return self._leader is not None

    def _lead(self) -> bool:
        if self._leader is None:
            self._leader = try_lock(named_lock_path(self.config.db_url, "modernization"))
        return self._leader is not None

    # ---- one check --------------------------------------------------------------------------------------------------

    def tick(self) -> float:
        """One check; returns how long to wait before the next. Safe to call directly (tests, API reads)."""
        with self._lock:
            if not self.enabled:
                return self.config.check_seconds
            leader = self._lead()
            intent = read_intent(self.engine)
            self._refresh_classification()
            pending = self._class_pending()
            if not leader:
                self._class_state = "owned_elsewhere" if pending else self._settled_class_state()
                return self.config.check_seconds
            self._activate()  # inc 618: recording a complete index is not background work, so Pause does not block it
            if intent == PAUSED:
                self._class_state = "paused" if pending else self._settled_class_state()
                return self.config.check_seconds
            self._schedule_index()
            if not pending:
                self._class_state = self._settled_class_state()
                return self.config.check_seconds
            self._class_state = "running"
            result = self.classifier.run_pass(self._should_stop)
            self._refresh_classification(force=True)
            if result.stopped is not None:
                self._class_state = result.stopped
            elif result.remaining == 0:
                self._settled_signature = self._signature  # only remembered failures (if any) are left
                self._class_state = self._settled_class_state()
            self._class_detail = (
                "Some papers could not be classified; each is retried when its text changes or Callosum restarts."
                if self.classifier.failures
                else None
            )
        if result.stopped in (STOP_PAUSED, STOP_SHUTDOWN):
            return self.config.check_seconds
        if result.stopped is not None:
            return self.config.retry_seconds
        return 0.0 if result.remaining > 0 else self.config.check_seconds

    def _should_stop(self) -> str | None:
        if self._closing.is_set():
            return STOP_SHUTDOWN
        return STOP_PAUSED if read_intent(self.engine) == PAUSED else None

    def _class_pending(self) -> bool:
        needing = int((self._class_coverage or {}).get("papers_needing_derivation") or 0)
        return needing > 0 and self._signature != self._settled_signature

    def _settled_class_state(self) -> str:
        needing = int((self._class_coverage or {}).get("papers_needing_derivation") or 0)
        return "complete" if needing == 0 else "failed_papers"  # nothing is retried in a loop

    # ---- stored truth -----------------------------------------------------------------------------------------------

    def _signature_now(self) -> tuple:
        """Cheap aggregate over the rows that decide pending work, in the one chunk scan 617 already made.

        Inc 618: a length total missed an in-place change between two versions of equal length (``chunk_version`` is
        fixed-width), and a count missed an attachment-role swap with equal chunk counts. Each row now contributes
        a CRC32 of its version weighted by its id, and the classified population contributes the sum of its ids, so
        either change moves the signature (bar a ~2^-31 arithmetic coincidence, which the 30-minute safety refresh
        and the per-Ask coverage check still cover)."""
        with self.engine.connect() as conn:
            _register_checksum(conn)
            classified = conn.execute(
                select(func.count(), func.total(chunks.c.id))
                .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
                .where(classified_chunks_clause())
            ).one()
            totals = conn.execute(
                select(
                    func.count(),
                    func.coalesce(func.max(chunks.c.id), 0),
                    func.coalesce(func.sum(func.callosum_version_crc(chunks.c.chunk_version, chunks.c.id)), 0),
                )
            ).one()
            return (
                tuple(totals),
                tuple(classified),
                conn.execute(select(func.count()).select_from(chunk_structure)).scalar_one(),
                tuple(
                    conn.execute(
                        select(func.count(), func.total(papers.c.id)).where(papers.c.deleted_at.is_(None))
                    ).one()
                ),
            )

    def _refresh_classification(self, *, force: bool = False) -> None:
        signature = self._signature_now()
        due = self.clock() - self._last_full >= self.config.full_check_seconds
        if due:
            self._settled_signature = None  # the safety net also retries remembered settles
        if not force and not due and signature == self._signature and self._class_coverage is not None:
            return
        self._class_coverage = classification_coverage(self.engine)
        self._index_marker = None  # chunks moved: index coverage must be re-read too
        self._signature = signature
        self._last_full = self.clock()
        self._checked_at = index_runs.now()

    def _fresh_index_coverage(self, row: dict | None) -> dict:
        """Index coverage, re-read whenever chunks or the run row moved since it was last read."""
        marker = (self._signature, None if row is None else (row["state"], row["updated_at"]))
        if self._index_coverage is None or marker != self._index_marker:
            with self.engine.connect() as conn:
                self._index_coverage = profile_coverage(conn, get_profile(ARCTIC_S_PROFILE_KEY))
            self._index_marker = marker
        return self._index_coverage

    def _run_row(self) -> dict | None:
        with self.engine.connect() as conn:
            return index_runs.get_run(conn, ARCTIC_S_PROFILE_KEY)

    def _resumed_after(self, row: dict) -> bool:
        stamp = _get_setting(self.engine, RESUMED_AT_SETTING)
        if not stamp:
            return False
        try:
            return row["updated_at"] is not None and row["updated_at"] <= datetime.fromisoformat(stamp)
        except ValueError:
            return False

    def _schedule_index(self) -> None:
        """Ask the supervisor for a build when vectors are missing, the model is verified, and nothing the user did
        forbids it. Everything after that -- batches, waits, recovery -- is the supervisor's."""
        row = self._run_row()
        self._index_note = None
        if row is not None and row["state"] in _ACTIVE:
            return
        if int(self._fresh_index_coverage(row).get("missing_chunks") or 0) == 0:
            return
        if row is not None:
            if row["state"] == "failed":
                return  # the circuit breaker: only an explicit Resume restarts it
            if row["state"] in ("paused", "cancelled") and not self._resumed_after(row):
                return  # the user's own pause or cancel of this build
        if self._safe_model_status().get("state") != "verified":
            self._index_note = "waiting_for_model"
            return
        self._supervisor().start(get_profile(ARCTIC_S_PROFILE_KEY))  # type: ignore[attr-defined]

    def _activate(self) -> None:
        """Record Arctic S as the modernization-managed retrieval preference once its index is complete and its
        checkpoint verified. The cached coverage only decides whether to try; ``activate_arctic`` rechecks everything
        inside one write transaction, so a stale cache can never activate a partial index."""
        coverage = self._fresh_index_coverage(self._run_row())
        if int(coverage.get("missing_chunks") or 0) != 0 or not int(coverage.get("eligible_chunks") or 0):
            return
        with self.engine.connect() as conn:
            current = read_preference(conn)
        if current.explicit or current == Preference(ARCTIC_S_PROFILE_KEY, SOURCE_MODERNIZATION):
            return
        verified = self.model_status().get("state") == "verified"
        if verified:
            run_write(self.engine, lambda conn: activate_arctic(conn, model_verified=True))

    def model_status(self) -> dict:
        """The inc-615 state of the Arctic S checkpoint; an unreadable state is reported as unknown."""
        return self._safe_model_status()

    def _safe_model_status(self) -> dict:
        try:
            return dict(self._model_status())
        except Exception:  # noqa: BLE001 -- an unreadable status file means "not verified", never a crash
            return {"state": "unknown"}

    # ---- the status contract -------------------------------------------------------------------------------------------

    def status(self) -> dict:
        """Structured state for the forthcoming UI. Counts come from stored rows at ``checked_at``; no combined
        percentage, ETA or invented progress."""
        with self._lock:
            row = self._run_row()
            with contextlib.suppress(Exception):
                if self._class_coverage is None:
                    self._refresh_classification(force=True)
                if row is None or row["state"] not in _ACTIVE:  # an active build's row carries reconciled counts
                    self._fresh_index_coverage(row)
            intent = read_intent(self.engine)
            model = self._safe_model_status()
            with self.engine.connect() as conn:
                preference = read_preference(conn)
            return build_status(
                enabled=self.enabled,
                disabled_reason=self.disabled_reason,
                intent=intent,
                leader=self.is_leader,
                class_state=self._class_state if self.enabled else "disabled",
                class_detail=self._class_detail,
                class_coverage=self._class_coverage or {},
                failed=len(self.classifier.failures),
                index_coverage=self._index_coverage or {},
                run=row,
                model=model,
                index_note=self._index_note,
                checked_at=self._checked_at,
                preference=preference,
            )


def _index_state(enabled: bool, intent: str, coverage: dict, run: dict | None, model: dict, note: str | None) -> str:
    if run is not None and run["state"] in _ACTIVE | {"paused", "cancelled", "failed"}:
        return run["state"]
    if int(coverage.get("missing_chunks") or 0) == 0 and coverage:
        return "complete"
    if not enabled:
        return "disabled"
    if intent == PAUSED:
        return "paused"
    if note == "waiting_for_model" or model.get("state") != "verified":
        return "waiting_for_model"
    return "pending"


def build_status(
    *,
    enabled: bool,
    disabled_reason: str | None,
    intent: str,
    leader: bool,
    class_state: str,
    class_detail: str | None,
    class_coverage: dict,
    failed: int,
    index_coverage: dict,
    run: dict | None,
    model: dict,
    index_note: str | None,
    checked_at: datetime | None,
    preference: Preference | None = None,
) -> dict:
    index_state = _index_state(enabled, intent, index_coverage, run, model, index_note)
    if run is not None and run["state"] in _ACTIVE:
        # The supervisor re-derives these from stored vectors and checkpoints them inside each batch's transaction.
        eligible, indexed = int(run["eligible_chunks"]), int(run["indexed_chunks"])
    else:
        eligible, indexed = index_coverage.get("eligible_chunks"), index_coverage.get("indexed_chunks")
    missing = None if eligible is None or indexed is None else max(0, eligible - indexed)
    return {
        "enabled": enabled,
        "disabled_reason": disabled_reason,
        "intent": intent,
        "coordinating_here": leader,
        "checked_at": checked_at.isoformat() if checked_at else None,
        "classification": {
            "state": class_state,
            "derivation_version": DERIVATION_VERSION,
            "papers_with_classified_chunks": class_coverage.get("papers_with_chunks"),
            "papers_current": class_coverage.get("papers_current"),
            "papers_pending": class_coverage.get("papers_needing_derivation"),
            "papers_failed_this_session": failed,
            "papers_without_classified_chunks": class_coverage.get("papers_without_classified_chunks"),
            "automatic_recovery": class_state in {"running", "waiting_disk", "waiting_resources", "database_busy"},
            "needs_user": class_state == "paused",
            "detail": class_detail,
        },
        "indexing": {
            "profile": ARCTIC_S_PROFILE_KEY,
            "state": index_state,
            "eligible_chunks": eligible,
            "indexed_chunks": indexed,
            "missing_chunks": missing,
            "run_state": run["state"] if run else None,
            "run_intent": run["intent"] if run else None,
            "run_failure_kind": run["failure_kind"] if run else None,
            "automatic_recovery": index_state in _ACTIVE or index_state == "waiting_for_model",
            "needs_user": index_state in {"paused", "cancelled", "failed", "interrupted"},
        },
        "retrieval_preference": {
            "profile": preference.key if preference else None,
            "source": preference.source if preference else None,
            "legacy": bool(preference and preference.legacy),
            "arctic_activated": preference == Preference(ARCTIC_S_PROFILE_KEY, SOURCE_MODERNIZATION),
        },
        "model": {
            "track": model.get("track", ARCTIC_S_PROFILE_KEY),
            "state": model.get("state"),
            "verified": model.get("state") == "verified",
            "automatic_provisioning": bool(model.get("automatic_provisioning")),
        },
    }
