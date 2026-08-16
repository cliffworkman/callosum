"""Create, review, and explicitly approve a sanitized current-Feed demo candidate.

The default command writes only under ``.local``.  Nothing enters the public demo until a human supplies the
exact SHA-256 printed by the review step to ``--approve-digest``.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.backend.demo_extended_state import DemoExtendedState, DemoFeedItem, DemoFeedState, DemoFeedSubscription


def _get(base: str, path: str, params: dict[str, Any] | None = None) -> Any:
    url = base.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - loopback is enforced below
        return json.load(response)


def _candidate_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def export_review(api_base: str, output_dir: Path) -> str:
    parsed = urllib.parse.urlparse(api_base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Feed review export accepts a loopback Callosum API only")
    raw = _get(api_base, "/feed/subscriptions")
    subscriptions = [DemoFeedSubscription.model_validate(item) for item in raw.get("subscriptions", [])]
    subscriptions.sort(key=lambda item: (item.kind.casefold(), item.label or item.value, item.id))
    remap = {item.id: index + 1 for index, item in enumerate(subscriptions)}
    public_subscriptions = [item.model_copy(update={"id": remap[item.id]}) for item in subscriptions]
    items: list[DemoFeedItem] = []
    for subscription in subscriptions:
        page = _get(api_base, "/feed", {"subscription_id": subscription.id, "limit": 500})
        for item in page.get("items", []):
            clean = DemoFeedItem.model_validate(item)
            items.append(clean.model_copy(update={"id": 0, "subscription_id": remap[subscription.id]}))
    items.sort(
        key=lambda item: (
            item.subscription_id,
            item.posted_date or "",
            item.doi or "",
            item.url or "",
            item.title.casefold(),
        )
    )
    public_items = [item.model_copy(update={"id": index + 1}) for index, item in enumerate(items)]
    source_meta = raw.get("source_meta", [])
    kinds = sorted({str(item.get("kind")) for item in source_meta if item.get("kind")})
    journals = _get(api_base, "/feed/library-journals").get("journals", [])
    candidate = {
        "subscriptions": [item.model_dump(mode="json") for item in public_subscriptions],
        "items": [item.model_dump(mode="json") for item in public_items],
        "kinds": kinds,
        "source_meta": source_meta,
        "library_journals": journals,
    }
    payload = _candidate_bytes(candidate)
    digest = hashlib.sha256(payload).hexdigest()
    lowered = payload.decode("utf-8").lower()
    for marker in ("c:\\users\\", "/users/", "/home/", "api_key", "access_token", "sk-proj-"):
        if marker in lowered:
            raise ValueError(f"Feed candidate contains forbidden marker {marker!r}")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "candidate.json").write_bytes(payload)
    rows = io.StringIO(newline="")
    writer = csv.writer(rows)
    writer.writerow(["id", "subscription", "posted_date", "title", "journal", "doi", "url"])
    labels = {item.id: item.label or item.value for item in public_subscriptions}
    for item in public_items:
        writer.writerow(
            [item.id, labels[item.subscription_id], item.posted_date, item.title, item.journal, item.doi, item.url]
        )
    (output_dir / "items.csv").write_text(rows.getvalue(), encoding="utf-8-sig")
    (output_dir / "REVIEW.md").write_text(
        "# Feed public-demo review\n\n"
        f"Candidate SHA-256: `{digest}`\n\n"
        f"Subscriptions: {len(public_subscriptions)}  \nItems: {len(public_items)}\n\n"
        "Review `candidate.json` or `items.csv`. Approval publishes these exact whitelisted records into the "
        "versioned demo snapshot; it never exports keys, notes, local paths, sync state, or other database fields.\n",
        encoding="utf-8",
    )
    return digest


def approve(candidate_path: Path, digest: str, extended_path: Path) -> DemoExtendedState:
    payload = candidate_path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != digest:
        raise ValueError(f"Feed approval digest mismatch: supplied {digest}, candidate is {actual}")
    raw = json.loads(payload)
    allowed = {"subscriptions", "items", "kinds", "source_meta", "library_journals"}
    if set(raw) != allowed:
        raise ValueError("Feed candidate contains missing or unrecognized top-level fields")
    feed = DemoFeedState(included=True, approved_digest=digest, **raw)
    state = DemoExtendedState.model_validate_json(extended_path.read_bytes()).model_copy(update={"feed": feed})
    state = DemoExtendedState.model_validate(state.model_dump(mode="json"))
    extended_path.write_text(
        json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8888")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local" / "demo-feed-review")
    parser.add_argument("--approve-digest")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--extended-state", type=Path, default=ROOT / "demo" / "extended-state-v1.json")
    args = parser.parse_args()
    if args.approve_digest:
        candidate = args.candidate or args.output_dir / "candidate.json"
        state = approve(candidate, args.approve_digest, args.extended_state)
        print(f"approved {len(state.feed.items)} Feed items into {args.extended_state}")
    else:
        digest = export_review(args.api_base, args.output_dir)
        print(f"Feed review candidate written to {args.output_dir}; approve exact SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
