"""Background source-role v2 classification for an existing library (inc 617).

Runs the packaged inc-613 derivation (``structure_backfill.derive_paper``) one paper per transaction, on the
coordinator's thread, inside the process that holds the library's modernization lock. Nothing here is a new source
of truth: what is pending is recomputed every pass from ``papers_with_current_structure`` (with the inc-614
article-fulltext currentness rule), so an interrupted pass resumes by recomputing, and a paper whose chunks change
becomes pending again on its own.

Properties, all deliberate:

* **No network, no PDF reads, no rechunking.** Reference metadata comes from local caches only, as in the CLI.
* **Bounded.** One paper at a time; memory and disk are checked before every paper; a pass stops after a fixed
  number of papers so the coordinator can re-read the user's intent and the index state between passes.
* **One failing paper never restarts the library.** Its failure is remembered for this session against a fingerprint
  of its classified chunks, so it is skipped until its chunks change or the app restarts. Every other paper's
  committed rows stay.
* **Shortages are not failures.** A full disk, low memory or a locked database stops the pass; the coordinator
  waits and tries again. Nothing is deleted to make room.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import Engine, select
from sqlalchemy.exc import OperationalError

from app.backend.embeddings import disk_guard
from app.backend.embeddings.resources import ResourcePolicy, ResourceSnapshot, measure
from app.backend.pdf_processing.structure_backfill import derive_paper, load_reference_metadata
from app.backend.persistence.chunk_structure_repo import (
    classified_chunks_clause,
    papers_with_classified_chunks,
    papers_with_current_structure,
)
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.persistence.schema_chunk_structure import DERIVATION_VERSION

PAPERS_PER_PASS = 50

# Why a pass ended early. None means it ran out of pending papers (or hit the per-pass limit).
STOP_PAUSED = "paused"
STOP_SHUTDOWN = "shutdown"
STOP_DISK = "waiting_disk"
STOP_MEMORY = "waiting_resources"
STOP_BUSY = "database_busy"

Derive = Callable[[object, int, dict], int | None]


@dataclass
class PassResult:
    derived: int = 0
    rows: int = 0
    skipped_failed: int = 0
    newly_failed: int = 0
    stopped: str | None = None
    remaining: int = 0  # pending papers not attempted in this pass (excluding remembered failures)
    disk: dict = field(default_factory=dict)


def _is_busy(exc: BaseException) -> bool:
    return isinstance(exc, OperationalError) and "locked" in str(exc).lower()


class SourceRoleClassifier:
    def __init__(
        self,
        engine: Engine,
        db_url: str,
        *,
        probe: Callable[[], ResourceSnapshot] = measure,
        disk_usage: disk_guard.DiskUsage | None = None,
        derive: Derive = derive_paper,  # type: ignore[assignment]
        papers_per_pass: int = PAPERS_PER_PASS,
    ) -> None:
        self.engine = engine
        self.db_url = db_url
        self.probe = probe
        self.disk_usage = disk_usage
        self.derive = derive
        self.papers_per_pass = papers_per_pass
        # paper_id -> (fingerprint of its classified chunks, exception class name). Session-scoped on purpose: a
        # restart retries once, and a paper whose chunks change is retried immediately.
        self.failures: dict[int, tuple[str, str]] = {}

    def _fingerprint(self, paper_id: int) -> str:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(chunks.c.id, chunks.c.chunk_version, chunks.c.text)
                .select_from(chunks.join(attachments, attachments.c.id == chunks.c.attachment_id))
                .where(chunks.c.paper_id == paper_id, classified_chunks_clause())
                .order_by(chunks.c.id)
            ).fetchall()
        digest = hashlib.sha256()
        for chunk_id, version, text in rows:
            digest.update(f"{chunk_id}\x1f{version or ''}\x1f".encode())
            digest.update(hashlib.sha256((text or "").encode("utf-8")).digest())
        return digest.hexdigest()

    def pending(self) -> list[int]:
        """Live papers with classified chunks that are not current at this derivation version."""
        with self.engine.connect() as conn:
            live = {int(r[0]) for r in conn.execute(select(papers.c.id).where(papers.c.deleted_at.is_(None)))}
            with_chunks = papers_with_classified_chunks(conn)
            current = papers_with_current_structure(conn, DERIVATION_VERSION)
        return sorted((live & with_chunks) - current)

    def failed_pending(self, pending: list[int]) -> int:
        return sum(1 for pid in pending if pid in self.failures)

    def _blocked(self) -> tuple[str | None, dict]:
        snapshot = self.probe()
        if ResourcePolicy.for_machine(snapshot).should_pause(snapshot):
            return STOP_MEMORY, {}
        disk = disk_guard.check(self.db_url, batch_size=1, remaining_chunks=0, usage=self.disk_usage)
        return (None, {}) if disk.ok else (STOP_DISK, disk.row_values())

    def run_pass(self, should_stop: Callable[[], str | None]) -> PassResult:
        result = PassResult()
        targets = self.pending()
        if not targets:
            return result
        references: dict | None = None
        attempted = 0
        for index, paper_id in enumerate(targets):
            if attempted >= self.papers_per_pass:
                result.remaining = sum(1 for pid in targets[index:] if pid not in self.failures)
                return result
            reason = should_stop()
            if reason is None:
                reason, result.disk = self._blocked()
            if reason is not None:
                result.stopped = reason
                result.remaining = sum(1 for pid in targets[index:] if pid not in self.failures)
                return result
            fingerprint = self._fingerprint(paper_id)
            remembered = self.failures.get(paper_id)
            if remembered is not None and remembered[0] == fingerprint:
                result.skipped_failed += 1
                continue
            if references is None:
                with self.engine.connect() as conn:
                    references = load_reference_metadata(conn)
            attempted += 1
            try:
                with self.engine.begin() as conn:  # one paper, one transaction: committed whole or not at all
                    written = self.derive(conn, paper_id, references)
            except Exception as exc:  # noqa: BLE001 -- classify the cause; never let one paper end the library
                if disk_guard.is_disk_full(exc):
                    result.stopped = STOP_DISK
                elif _is_busy(exc):
                    result.stopped = STOP_BUSY
                else:
                    self.failures[paper_id] = (fingerprint, type(exc).__name__)
                    result.newly_failed += 1
                    continue
                result.remaining = sum(1 for pid in targets[index:] if pid not in self.failures)
                return result
            self.failures.pop(paper_id, None)
            if written is not None:
                result.derived += 1
                result.rows += written
        return result
