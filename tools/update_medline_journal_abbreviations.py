"""Refresh the bundled, render-time MEDLINE journal-title abbreviation index.

The source is NLM's public ``J_Medline.txt`` journal catalog. Runtime rendering never
downloads it: this maintainer-only script distills the official records into one
deterministic gzip-compressed JSON file committed with the application.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://ftp.ncbi.nlm.nih.gov/pubmed/J_Medline.txt"
OUTPUT = ROOT / "app" / "backend" / "citations" / "data" / "medline_journals.json.gz"
MAX_SOURCE_BYTES = 15_000_000
SEPARATOR = "--------------------------------------------------------"


def _title_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", normalized).split())


def _issn_keys(value: str) -> list[str]:
    return [match.replace("-", "").upper() for match in re.findall(r"\b[0-9]{4}-?[0-9]{3}[0-9Xx]\b", value)]


def _field(record: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.+?)\s*$", record, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _insert_unambiguous(target: dict[str, str], conflicts: set[str], key: str, value: str) -> None:
    if not key or key in conflicts:
        return
    previous = target.get(key)
    if previous is None or previous == value:
        target[key] = value
    else:
        target.pop(key, None)
        conflicts.add(key)


def build_index(source: bytes, *, last_modified: str) -> dict:
    text = source.decode("utf-8")
    by_title: dict[str, str] = {}
    by_issn: dict[str, str] = {}
    title_conflicts: set[str] = set()
    issn_conflicts: set[str] = set()
    record_count = 0
    for record in text.split(SEPARATOR):
        abbreviation = _field(record, "MedAbbr")
        title = _field(record, "JournalTitle")
        if not abbreviation or not title:
            continue
        record_count += 1
        _insert_unambiguous(by_title, title_conflicts, _title_key(title), abbreviation)
        for field_name in ("ISSN (Print)", "ISSN (Online)"):
            for issn in _issn_keys(_field(record, field_name)):
                _insert_unambiguous(by_issn, issn_conflicts, issn, abbreviation)
    if record_count < 30_000 or len(by_title) < 30_000:
        raise RuntimeError("The NLM journal catalog was unexpectedly small; refusing to replace the bundled index.")
    return {
        "source": SOURCE_URL,
        "last_modified": last_modified,
        "sha256": hashlib.sha256(source).hexdigest(),
        "record_count": record_count,
        "by_title": dict(sorted(by_title.items())),
        "by_issn": dict(sorted(by_issn.items())),
    }


def main() -> None:
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Callosum-MEDLINE-index/1"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed official HTTPS source
        if response.geturl() != SOURCE_URL:
            raise RuntimeError("The NLM journal catalog redirected away from its pinned official URL.")
        source = response.read(MAX_SOURCE_BYTES + 1)
        if len(source) > MAX_SOURCE_BYTES:
            raise RuntimeError("The NLM journal catalog exceeded the 15 MB maintenance bound.")
        modified = response.headers.get("Last-Modified", "")
    last_modified = parsedate_to_datetime(modified).date().isoformat() if modified else "unknown"
    payload = json.dumps(
        build_index(source, last_modified=last_modified),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    temporary.replace(OUTPUT)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes compressed; {len(payload):,} bytes JSON)")


if __name__ == "__main__":
    main()
