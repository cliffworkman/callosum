"""What the user sees about background modernization (inc 620): one summary derived from the inc-617 status.

Pure: it reads the dict ``ModernizationCoordinator.status()`` returns (stored counts, run row, provisioning state) plus
the index-run message the Settings panel already shows, and returns plain sentences and flags. It owns no state, runs
no query and never invents progress: a ``progress`` block appears only when its denominator is stored work (papers
with classifiable chunks, or eligible passages), there is never a combined percentage across stages, and there is
never a time estimate.

Classification and indexing run independently, so the summary names the *current* activity and keeps a note per
stage; a terminal problem in one stage is reported as ``attention`` without hiding the stage that is still working.
"""

from __future__ import annotations

WORKING, WAITING, PAUSED, ATTENTION, COMPLETE, DISABLED = (
    "working",
    "waiting",
    "paused",
    "action_required",
    "complete",
    "disabled",
)

_INDEX_WORKING = {"queued", "running", "pausing", "pending"}
_INDEX_WAITING = {"retrying", "waiting_resources", "waiting_disk", "waiting_for_model"}
_CLASS_WAITING = {"waiting_disk", "waiting_resources", "database_busy", "shutdown", "unknown"}
_MODEL_WAITING = {"waiting_for_network", "interrupted", "insufficient_resources", "absent", "present_unverified"}


def _n(value: object) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _model_note(model: dict) -> tuple[str, str]:
    """(kind, sentence) for the Arctic S download. Kinds: ready, working, waiting, attention, off."""
    state = model.get("state")
    automatic = bool(model.get("automatic_provisioning"))
    if state == "verified":
        return "ready", "Arctic S retrieval model: downloaded and verified."
    if state == "invalid":
        return "attention", (
            "Arctic S retrieval model: the downloaded files failed verification, so Callosum will not use them and "
            "will not retry by itself. Ask keeps using MiniLM. There is no in-app repair yet; please report this."
        )
    if not automatic:
        return "off", "Arctic S retrieval model: not installed, and automatic download is off in this build."
    if state == "downloading":
        return "working", "Arctic S retrieval model: downloading."
    if state == "waiting_for_network":
        return (
            "waiting",
            "Arctic S retrieval model: waiting for an internet connection. The download resumes by itself.",
        )
    if state == "insufficient_resources":
        return (
            "waiting",
            "Arctic S retrieval model: waiting for disk space to finish the download. It retries by itself.",
        )
    if state == "interrupted":
        return "waiting", "Arctic S retrieval model: the download was interrupted and will resume."
    if state == "present_unverified":
        return "waiting", "Arctic S retrieval model: downloaded, waiting to be verified."
    return "waiting", "Arctic S retrieval model: waiting to download."


def _class_note(c: dict) -> tuple[str, str]:
    state = c.get("state")
    eligible, current = _n(c.get("papers_with_classified_chunks")), _n(c.get("papers_current"))
    pending, failed = _n(c.get("papers_pending")), _n(c.get("papers_failed_this_session"))
    counts = f"{current:,} of {eligible:,} papers current, {pending:,} pending" if eligible else "no papers to classify"
    failed_text = (
        f" {failed:,} could not be classified this session; each is retried when its text changes or Callosum restarts."
        if failed
        else ""
    )
    if state == "complete" or (pending == 0 and state != "running"):
        return "done", f"Source classification: complete ({counts}).{failed_text}"
    if state == "running":
        return "working", f"Source classification: in progress ({counts}).{failed_text}"
    if state == "owned_elsewhere":
        return "working", f"Source classification: running in another Callosum window ({counts})."
    if state == "failed_papers":
        return "done", f"Source classification: finished what it could ({counts}).{failed_text}"
    if state == "paused":
        return "paused", f"Source classification: paused ({counts})."
    waits = {
        "waiting_disk": "waiting for disk space",
        "waiting_resources": "waiting for available memory",
        "database_busy": "waiting for the library database to be free",
    }
    if state in waits:
        return "waiting", f"Source classification: {waits[state]} ({counts}). It resumes by itself."
    if state == "disabled":
        return "off", f"Source classification: not running in this build ({counts})."
    return "waiting", f"Source classification: starting ({counts})."


def _index_note(i: dict, run_message: str | None) -> tuple[str, str]:
    state = i.get("state")
    eligible, indexed, missing = _n(i.get("eligible_chunks")), _n(i.get("indexed_chunks")), _n(i.get("missing_chunks"))
    counts = f"{indexed:,} of {eligible:,} passages indexed, {missing:,} missing"
    if state == "complete":
        return "done", f"Arctic S index: complete ({counts})."
    if state == "failed":
        return (
            "attention",
            f"Arctic S index: stopped after repeated failures ({counts}). Completed work is saved; Resume retries.",
        )
    if state == "cancelled":
        return "attention", f"Arctic S index: cancelled ({counts}). Completed work is saved; Resume continues from it."
    if state == "paused":
        return "paused", f"Arctic S index: paused ({counts}). Completed work is saved."
    if state == "disabled":
        return "off", f"Arctic S index: not built automatically in this build ({counts})."
    if state == "waiting_for_model":
        return "waiting", f"Arctic S index: starts after the model is downloaded and verified ({counts})."
    if state in _INDEX_WAITING:
        return "waiting", f"Arctic S index: {run_message or 'waiting'} ({counts})."
    if state == "pending":
        return "working", f"Arctic S index: starting ({counts})."
    return "working", f"Arctic S index: building ({counts})."


def summarize(status: dict, *, run_message: str | None = None) -> dict:
    """The one modernization summary for Status and Settings. ``run_message`` is the index run's own plain message
    (``embedding_index._message``), reused so disk/memory waits read the same everywhere."""
    model_kind, model_text = _model_note(status.get("model") or {})
    class_kind, class_text = _class_note(status.get("classification") or {})
    index_kind, index_text = _index_note(status.get("indexing") or {}, run_message)
    indexing, classification = status.get("indexing") or {}, status.get("classification") or {}
    if index_kind == "waiting" and indexing.get("state") == "waiting_for_model" and model_kind in ("attention", "off"):
        # The model will not arrive by itself, so the index is not "waiting" for it: it cannot start (§8).
        index_kind = "blocked" if model_kind == "attention" else "off"
        index_text = (
            index_text.split(" (", 1)[0].replace(
                "starts after the model is downloaded and verified",
                "cannot be built until the retrieval model is available",
            )
            + " ("
            + index_text.split(" (", 1)[1]
        )
    notes = {"model": model_text, "classification": class_text, "indexing": index_text}
    attention = [text for kind, text in ((model_kind, model_text), (index_kind, index_text)) if kind == "attention"]

    progress = None
    if not status.get("enabled"):
        state, headline = DISABLED, "Automatic modernization is off in this build. Ask uses the models you select."
    elif status.get("intent") == "paused":
        state, headline = PAUSED, "Library modernization is paused. Completed work is saved. Resume when you're ready."
    elif index_kind == "working" and indexing.get("state") != "pending":
        state, headline = WORKING, "Building the Arctic S retrieval index."
        progress = _progress(indexing.get("indexed_chunks"), indexing.get("eligible_chunks"), "passages indexed")
    elif class_kind == "working":
        state, headline = WORKING, "Classifying scientific sources in your library."
        progress = _progress(
            classification.get("papers_current"),
            classification.get("papers_with_classified_chunks"),
            "papers classified",
        )
    elif model_kind == "working":
        state, headline = WORKING, "Downloading the Arctic S retrieval model."
    elif index_kind == "working":
        state, headline = WORKING, "Starting the Arctic S retrieval index."
    elif "waiting" in (index_kind, class_kind, model_kind):
        state = WAITING
        headline = next(
            text.split(": ", 1)[1]
            for kind, text in ((index_kind, index_text), (class_kind, class_text), (model_kind, model_text))
            if kind == "waiting"
        )
        headline = headline[0].upper() + headline[1:]
    elif attention:
        state, headline = ATTENTION, "Library modernization needs your attention."
    elif index_kind == "off" or model_kind == "off":
        state, headline = DISABLED, "Arctic S is not available in this build. Ask uses MiniLM."
    else:
        state, headline = COMPLETE, "Library modernization is complete."
    return {
        "state": state,
        "headline": headline,
        "automatic_recovery": state in {WORKING, WAITING},
        "needs_user": bool(attention) or state == PAUSED,
        "attention": attention,
        "notes": notes,
        "progress": progress,
        "eta_seconds": None,  # no estimate: modernization throughput is not yet measured on user machines
    }


def _progress(current: object, total: object, label: str) -> dict | None:
    total_n, current_n = _n(total), _n(current)
    if total_n <= 0:
        return None
    return {"current": min(current_n, total_n), "total": total_n, "label": label}
