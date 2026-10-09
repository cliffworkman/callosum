"""Bounded discourse context, v1. Pure supplied-data transport; never performs a lookup.

R1 is NOT a general coreference/anaphora engine, synonym matcher, or semantic discourse parser.
Only the preregistered 'Across these levels' / 'At the level' list grammar is recognized.
Widening that grammar requires new preregistration and versioned behavior.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re

SCHEMA = "ownership-context-v1"
PROOF_SCHEMA = "verified-local-owner-v1"
RULE = "owner.local_antecedent.v1"
RELATIONS = {"this_study": "current_document", "prior_work": "attributed_external"}


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_hash(value):
    return text_hash(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def physical_quote_key(row):
    return content_hash(
        [row["paper_id"], row["evidence_anchor_chunk_id"], row["evidence_span_id"], text_hash(row["quote"])]
    )


def failure(reason, status="unavailable"):
    return {"status": status, "failure": reason, "proofs": []}


def _span(value, length):
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(type(x) is int for x in value)
        and 0 <= value[0] < value[1] <= length
    )


def _paragraphs(text):
    start = 0
    for m in re.finditer(r"\n[ \t]*\n", text):
        yield [start, m.start()]
        start = m.end()
    yield [start, len(text)]


def build_context_index(sealed, packets):
    """Snapshot only resident packet bytes. Entry identity is independent of unrelated later entries."""
    sources, entries, bindings = {}, {}, {}
    available = {}
    for packet in packets:
        if packet.get("discarded"):
            continue
        for chunk in packet.get("chunks", []):
            available.setdefault((packet.get("paper_id"), chunk.get("chunk_id")), []).append(chunk)
    for row in sealed.get("verified_propositions", []):
        key = physical_quote_key(row)
        if key in bindings:
            continue
        quote = row["quote"]
        cid = row["evidence_anchor_chunk_id"]
        if cid not in row.get("provenance", {}).get("context_read", []):
            bindings[key] = failure("anchor_not_in_recorded_context")
            continue
        copies = available.get((row["paper_id"], cid), [])
        if not copies:
            bindings[key] = failure("source_chunks_unavailable")
            continue
        normalized = []
        for c in copies:
            text = c.get("text")
            if not isinstance(text, str) or not c.get("attachment_id") or not c.get("source_attachment_checksum"):
                continue
            normalized.append(
                {
                    "paper_id": row["paper_id"],
                    "attachment_id": c["attachment_id"],
                    "chunk_id": cid,
                    "source_attachment_checksum": c["source_attachment_checksum"],
                    "chunk_text_sha256": text_hash(text),
                    "text": text,
                    "extraction_tool": c.get("extraction_tool"),
                    "extraction_version": c.get("extraction_version"),
                    "chunk_version": c.get("chunk_version"),
                    "chunk_type": c.get("chunk_type"),
                }
            )
        unique = {content_hash(c): c for c in normalized}
        if len(unique) != 1:
            bindings[key] = failure("source_identity_conflict", "invalid")
            continue
        source_id, source = next(iter(unique.items()))
        text = source["text"]
        if source["chunk_type"] not in ("body_prose", "abstract_prose"):
            bindings[key] = failure("paragraph_boundary_unavailable")
            continue
        occurrences = (
            [[m.start(), m.start() + len(quote)] for m in re.finditer(re.escape(quote), text)] if quote else []
        )
        supplied = row.get("provenance", {}).get("quote_span_in_chunk")
        if supplied is not None:
            occurrences = [supplied] if _span(supplied, len(text)) and text[slice(*supplied)] == quote else []
        if len(occurrences) != 1:
            bindings[key] = failure("quote_occurrence_not_unique", "ambiguous")
            continue
        occurrence = list(occurrences[0])
        paragraphs = [p for p in _paragraphs(text) if p[0] <= occurrence[0] and occurrence[1] <= p[1]]
        if len(paragraphs) != 1:
            bindings[key] = failure("quote_crosses_paragraph", "invalid")
            continue
        entry = {
            "schema_version": SCHEMA,
            "source_id": source_id,
            "quote_sha256": text_hash(quote),
            "quote_span_in_chunk": occurrence,
            "paragraph_span_in_chunk": paragraphs[0],
            "boundary_provenance": "preserved_source_block_and_blank_lines",
        }
        eid = content_hash(entry)
        sources[source_id] = source
        entries[eid] = entry
        bindings[key] = {"status": "available", "entry_id": eid}
    result = {"schema_version": SCHEMA, "sources": sources, "entries": entries, "bindings": bindings}
    return {**result, "manifest_sha256": content_hash(result)}


def context_for(index, row):
    """Validate supplied snapshot before returning a defensive, bounded context view."""
    if index is None:
        return failure("context_index_unavailable")
    try:
        raw = {k: v for k, v in index.items() if k != "manifest_sha256"}
        if index["schema_version"] != SCHEMA or content_hash(raw) != index["manifest_sha256"]:
            return failure("context_index_invalid", "invalid")
        binding = index["bindings"].get(physical_quote_key(row))
        if not binding:
            return failure("context_anchor_unavailable")
        if binding["status"] != "available":
            return copy.deepcopy(binding)
        eid = binding["entry_id"]
        entry = index["entries"][eid]
        source = index["sources"][entry["source_id"]]
        text = source["text"]
        if (
            content_hash(entry) != eid
            or content_hash(source) != entry["source_id"]
            or text_hash(text) != source["chunk_text_sha256"]
            or entry["quote_sha256"] != text_hash(row["quote"])
            or source["paper_id"] != row["paper_id"]
            or source["chunk_id"] != row["evidence_anchor_chunk_id"]
            or not _span(entry["quote_span_in_chunk"], len(text))
            or not _span(entry["paragraph_span_in_chunk"], len(text))
            or text[slice(*entry["quote_span_in_chunk"])] != row["quote"]
        ):
            return failure("context_entry_invalid", "invalid")
        a, b = entry["paragraph_span_in_chunk"]
        qa, qb = entry["quote_span_in_chunk"]
        if not a <= qa < qb <= b:
            return failure("context_span_mismatch", "invalid")
        return copy.deepcopy(
            {"status": "available", "entry_id": eid, "entry": entry, "source": source, "paragraph_text": text[a:b]}
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return failure("context_index_invalid", "invalid")


def _opaque(text):
    return re.sub(r"^(?:the|a|an)\s+", "", " ".join(text.casefold().split()))


def _list_items(text):
    # Parenthetical material is masked, retaining original coordinates; it is never a synonym source.
    masked = list(text)
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        if depth:
            masked[i] = " "
        if ch == ")":
            depth -= 1
        if depth < 0:
            return None
    if depth:
        return None
    cleaned = "".join(masked)
    m = re.search(r"\b(?:at levels|in)\s+(.+)$", cleaned, re.I)
    if not m:
        return None
    parts = re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", m.group(1), flags=re.I)
    items = [_opaque(x.strip()) for x in parts]
    if len(items) < 2 or any(not x or not re.fullmatch(r"[\w' -]+", x) for x in items):
        return None
    return items


def resolve_local_antecedent(context, quote, assertion_span, owner_records):
    """Consume supplied legacy owner records; never imports or calls a classifier.

    Unrecognized bodies are opaque. Ownership is proved only for the anchored target, never propagated
    into every sentence. Missing or invalid context leaves that target unresolved.
    """
    if not isinstance(context, dict):
        return failure("context_unavailable")
    if context.get("status") != "available":
        return copy.deepcopy(context)
    try:
        entry, source = context["entry"], context["source"]
        full = source["text"]
        pa, pb = entry["paragraph_span_in_chunk"]
        qa, qb = entry["quote_span_in_chunk"]
        paragraph = full[pa:pb]
        if (
            entry["schema_version"] != SCHEMA
            or content_hash(entry) != context["entry_id"]
            or content_hash(source) != entry["source_id"]
            or text_hash(full) != source["chunk_text_sha256"]
            or paragraph != context["paragraph_text"]
            or full[qa:qb] != quote
            or entry["quote_sha256"] != text_hash(quote)
            or not _span(assertion_span, len(quote))
        ):
            return failure("context_proof_identity_invalid", "invalid")
        target_start = qa - pa + assertion_span[0]
        sentence_start = qa - pa
        anaphor = re.match(r"Across these levels(?: of [A-Za-z][A-Za-z -]*)?,\s*", paragraph[sentence_start:], re.I)
        if not anaphor or sentence_start + anaphor.end() > target_start + 1:
            return failure("unsupported_anaphor", "unavailable")
        introductions = []
        for record in owner_records:
            if record["span"][1] > sentence_start or record["assertion_source"] not in RELATIONS:
                continue
            if record["assertion_kind"] != "method_or_description":
                continue
            text = paragraph[slice(*record["span"])]
            items = _list_items(text)
            if items:
                introductions.append((record, items))
        if len(introductions) != 1:
            return failure("antecedent_not_unique", "ambiguous")
        owner, items = introductions[0]
        start = owner["span"][1]
        body = paragraph[start:sentence_start]
        headers = list(re.finditer(r"\bAt (?:the )?level(?: of)? ([^,.;:\n]+),", body, re.I))
        if [_opaque(m.group(1)) for m in headers] != items or len(set(items)) != len(items):
            return failure("level_headers_mismatch", "ambiguous")
        chain = paragraph[owner["span"][0] : qa - pa + assertion_span[1]]
        if re.search(
            r"\n[ \t]*\n|(?:^|[.!?]\s+)(?:however|by contrast|in contrast|in this study|in the present study|here)\b",
            chain,
            re.I,
        ):
            return failure("discourse_reset", "ambiguous")
        for record in owner_records:
            if record["span"][0] < owner["span"][0] or record["span"][0] >= qa - pa + assertion_span[1]:
                continue
            if record.get("citation_marked"):
                return failure("citation_conflict", "ambiguous")
            if record["assertion_source"] in RELATIONS and record["assertion_source"] != owner["assertion_source"]:
                return failure("owner_conflict", "conflicting")
        proof = {
            "schema_version": PROOF_SCHEMA,
            "rule_id": RULE,
            "resolver_version": "local-antecedent-v1",
            "context_entry_id": context["entry_id"],
            "source": {k: v for k, v in source.items() if k != "text"},
            "quote_sha256": text_hash(quote),
            "target_assertion_span": list(assertion_span),
            "quote_span_in_chunk": [qa, qb],
            "paragraph_span_in_chunk": [pa, pb],
            "owner_assertion_span_in_chunk": [pa + x for x in owner["span"]],
            "list_items": items,
            "header_spans_in_chunk": [[pa + start + m.start(), pa + start + m.end()] for m in headers],
            "anaphor_span_in_chunk": [qa, qa + anaphor.end()],
            "relation": RELATIONS[owner["assertion_source"]],
        }
        return {
            "status": "applied",
            "failure": None,
            "proofs": [proof],
            "validation": [
                {
                    "context_entry_id": context["entry_id"],
                    "source_text": full,
                    "entry": copy.deepcopy(entry),
                    "source_identity": {k: v for k, v in source.items() if k != "text"},
                }
            ],
        }
    except (KeyError, TypeError, ValueError, AttributeError, IndexError):
        return failure("context_proof_invalid", "invalid")


def combine_proofs(results):
    """Every distinct pooled physical source must agree. Do not pick the first available source."""
    if not results:
        return failure("context_unavailable")
    failed = [r for r in results if r.get("status") != "applied"]
    if failed:
        return copy.deepcopy(failed[0])
    relations = {p["relation"] for r in results for p in r["proofs"]}
    if len(relations) != 1:
        return failure("pooled_owner_conflict", "conflicting")
    proofs, validation, seen = [], [], set()
    for result in results:
        for proof, material in zip(result["proofs"], result["validation"], strict=True):
            if proof["context_entry_id"] not in seen:
                seen.add(proof["context_entry_id"])
                proofs.append(copy.deepcopy(proof))
                validation.append(copy.deepcopy(material))
    return {"status": "applied", "failure": None, "proofs": proofs, "validation": validation}
