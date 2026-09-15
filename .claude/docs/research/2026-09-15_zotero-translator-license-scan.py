"""Experimental harness: license-header inventory of the Zotero translator corpus + translate runtime.

Answers one bounded question for the browser-capture research doc: what licenses actually govern
the files Callosum would have to vendor. Not product code.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent

AGPL = re.compile(r"GNU Affero General Public License", re.I)
OR_LATER = re.compile(r"either version 3 of the License, or\s*\n?\s*\**\s*\(at your option\) any later version", re.I)
GPL_NOT_AFFERO = re.compile(r"GNU General Public License", re.I)
MIT = re.compile(r"\bMIT License\b|Permission is hereby granted, free of charge", re.I)
W3C = re.compile(r"W3C[^\n]{0,40}licen[sc]e", re.I)
BSD = re.compile(r"Redistribution and use in source and binary forms", re.I)
COPYRIGHT = re.compile(r"Copyright\s*(?:\(c\)|©)\s*(.{0,80})", re.I)


def classify(head: str) -> str:
    if AGPL.search(head):
        return "AGPL-3.0-or-later" if OR_LATER.search(head) else "AGPL-3.0-only"
    if W3C.search(head):
        return "W3C"
    if MIT.search(head):
        return "MIT"
    if BSD.search(head):
        return "BSD"
    if GPL_NOT_AFFERO.search(head):
        return "GPL (non-Affero)"
    return "NONE / unrecognized"


def scan(files):
    rows = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # unreadable file is a finding, not a crash
            rows.append({"path": str(path), "license": f"UNREADABLE: {exc}", "holder": ""})
            continue
        head = text[:4000]
        holder = COPYRIGHT.search(head)
        rows.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "license": classify(head),
                "holder": (holder.group(1).strip().rstrip(".,") if holder else ""),
            }
        )
    return rows


def report(title, rows):
    print(f"\n=== {title} — {len(rows)} files ===")
    counts = Counter(r["license"] for r in rows)
    for lic, n in counts.most_common():
        print(f"  {n:>4}  {lic}")
    odd = [r for r in rows if not r["license"].startswith("AGPL")]
    if odd:
        print(f"  -- non-AGPL / unrecognized ({len(odd)}):")
        for r in odd[:40]:
            print(f"     {r['license']:<22} {r['path']}")
        if len(odd) > 40:
            print(f"     ... and {len(odd) - 40} more")
    holders = Counter(r["holder"] for r in rows if r["holder"])
    print(f"  -- distinct copyright holders: {len(holders)}")
    for h, n in holders.most_common(10):
        print(f"     {n:>4}  {h}")
    return rows


translators = sorted((ROOT / "translators").glob("*.js"))
translate_src = sorted((ROOT / "translate" / "src").rglob("*.js"))

all_rows = {
    "translators": report("zotero/translators (*.js at repo root)", scan(translators)),
    "translate_src": report("zotero/translate (src/**/*.js)", scan(translate_src)),
}

(ROOT / "license_inventory.json").write_text(json.dumps(all_rows, indent=2), encoding="utf-8")
print(f"\nWrote {ROOT / 'license_inventory.json'}")

# Repo-level license files present?
print("\n=== repo-level license files ===")
for repo in ("translators", "translate"):
    found = [p.name for p in (ROOT / repo).glob("*") if p.is_file() and re.match(r"COPYING|LICEN[SC]E", p.name, re.I)]
    print(f"  {repo}: {found or 'NONE'}")
