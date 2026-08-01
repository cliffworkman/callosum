from __future__ import annotations

import hashlib
import html
import json
import re
from collections import deque
from typing import Any

from app.backend.registration_acquisition.domain import AcquiredRegistration, RegistrationAcquisitionError
from app.backend.registration_discovery.http import JsonFetcher, RegistryHttpError, get_registry_json

_BASE = "https://api.osf.io/v2"
_GUID = re.compile(r"^[a-z0-9]{4,12}$")
_PROVIDER_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
_MAX_COLLECTION_PAGES = 20
_MAX_COLLECTION_ITEMS = 200


class OsfRegistrationAcquirer:
    id = "osf"

    def __init__(self, fetch_json: JsonFetcher = get_registry_json) -> None:
        self._fetch = fetch_json

    def acquire(self, link: dict[str, Any]) -> AcquiredRegistration:
        guid = str(link["external_id"]).casefold()
        if not _GUID.fullmatch(guid):
            raise RegistrationAcquisitionError("The confirmed OSF identifier is not a valid registration GUID.")
        try:
            registration = self._fetch(f"{_BASE}/registrations/{guid}/")
            schema_responses = self._collection(f"{_BASE}/registrations/{guid}/schema_responses/")
            contributors = self._optional_collection(f"{_BASE}/registrations/{guid}/contributors/?embed=users")
            identifiers = self._optional_collection(f"{_BASE}/registrations/{guid}/identifiers/")
            resources = self._optional_collection(f"{_BASE}/registrations/{guid}/resources/")
            file_providers = self._optional_collection(f"{_BASE}/registrations/{guid}/files/")
            file_manifest = self._file_manifest(guid, file_providers)
            schema_url = _related_href(registration, "registration_schema")
            schema = self._fetch(schema_url) if schema_url else {"data": None}
            blocks_url = f"{schema_url.rstrip('/')}/schema_blocks/" if schema_url else None
            schema_blocks = self._collection(blocks_url) if blocks_url else {"data": []}
        except RegistryHttpError as exc:
            raise RegistrationAcquisitionError(f"OSF acquisition failed: {exc}") from exc

        row = registration.get("data") or {}
        if str(row.get("id") or "").casefold() != guid:
            raise RegistrationAcquisitionError("OSF returned metadata for an unexpected registration identifier.")
        attrs = row.get("attributes") or {}
        schema_row = schema.get("data") or {}
        schema_attrs = schema_row.get("attributes") or {}
        response_row = _latest_schema_response(schema_responses)
        response_history = _response_history(schema_responses)
        questions = _canonical_questions(
            schema_blocks.get("data") or [],
            _response_values(attrs, response_row),
        )
        status = _status(attrs)
        structured = {
            "format": "callosum-registration-v1",
            "provider": "osf",
            "external_id": guid,
            "canonical_url": f"https://osf.io/{guid}/",
            "title": attrs.get("title"),
            "registered_at": attrs.get("date_registered") or attrs.get("date_created"),
            "registration_status": status,
            "schema": {
                "id": schema_row.get("id"),
                "name": schema_attrs.get("name") or attrs.get("registration_supplement"),
                "version": schema_attrs.get("schema_version"),
            },
            "questions": questions,
            "response_metadata": (response_row.get("attributes") or {}) if response_row else {},
            "response_history": response_history,
            "contributors": _contributors(contributors),
            "registration_doi": _registration_doi(identifiers),
            "publication_dois": _publication_dois(resources),
            "identifiers": identifiers.get("data") or [],
            "resources": resources.get("data") or [],
            "file_providers": file_providers.get("data") or [],
            "files": file_manifest["items"],
            "files_truncated": file_manifest["truncated"],
        }
        source_metadata = {
            "registration": registration,
            "schema": schema,
            "schema_blocks": schema_blocks,
            "schema_responses": schema_responses,
            "contributors": contributors,
            "identifiers": identifiers,
            "resources": resources,
            "file_providers": file_providers,
            "file_manifest": file_manifest,
        }
        canonical = json.dumps(structured, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        rendered = render_osf_registration(structured)
        return AcquiredRegistration(
            provider="osf",
            external_id=guid,
            canonical_url=f"https://osf.io/{guid}/",
            content_hash=hashlib.sha256(canonical).hexdigest(),
            registered_at=structured["registered_at"],
            registration_status=status,
            schema_name=structured["schema"]["name"],
            schema_version=str(structured["schema"]["version"] or "") or None,
            structured=structured,
            rendered_text=rendered,
            source_metadata=source_metadata,
            file_bytes=rendered.encode("utf-8"),
            file_suffix=".md",
            content_type="text/plain",
        )

    def _collection(self, url: str) -> dict:
        rows: list[dict] = []
        pages: list[dict[str, Any]] = []
        current: str | None = url
        seen: set[str] = set()
        first: dict[str, Any] = {}
        while current and current not in seen and len(pages) < _MAX_COLLECTION_PAGES:
            seen.add(current)
            payload = self._fetch(current)
            if not first:
                first = payload
            data = [row for row in payload.get("data") or [] if isinstance(row, dict)]
            remaining = _MAX_COLLECTION_ITEMS - len(rows)
            rows.extend(data[:remaining])
            pages.append({"url": current, "links": payload.get("links"), "meta": payload.get("meta")})
            if len(rows) >= _MAX_COLLECTION_ITEMS:
                current = _next_href(payload)
                break
            current = _next_href(payload)
        return {
            **first,
            "data": rows,
            "callosum_collection": {
                "pages_retrieved": len(pages),
                "items_retrieved": len(rows),
                "truncated": bool(current),
                "pages": pages,
            },
        }

    def _optional_collection(self, url: str) -> dict:
        try:
            return self._collection(url)
        except RegistryHttpError as exc:
            return {"data": [], "callosum_error": {"status": exc.status, "detail": str(exc)}}

    def _file_manifest(self, guid: str, providers: dict) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        collections: list[dict[str, Any]] = []
        queue: deque[tuple[str, str]] = deque()
        for row in providers.get("data") or []:
            provider_id = str(row.get("id") or "")
            if not _PROVIDER_ID.fullmatch(provider_id):
                continue
            related = _relationship_href(row, "files")
            queue.append((provider_id, related or f"{_BASE}/registrations/{guid}/files/{provider_id}/"))
        seen: set[str] = set()
        while queue and len(items) < _MAX_COLLECTION_ITEMS and len(collections) < _MAX_COLLECTION_PAGES:
            provider_id, url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            payload = self._optional_collection(url)
            collections.append({"provider_id": provider_id, "url": url, "payload": payload})
            for row in payload.get("data") or []:
                if len(items) >= _MAX_COLLECTION_ITEMS:
                    break
                item = {"provider_id": provider_id, **row}
                items.append(item)
                if str((row.get("attributes") or {}).get("kind") or "").casefold() == "folder":
                    child = _relationship_href(row, "files")
                    if child:
                        queue.append((provider_id, child))
        return {
            "items": items,
            "collections": collections,
            "truncated": bool(queue)
            or any(
                bool((item.get("payload") or {}).get("callosum_collection", {}).get("truncated"))
                for item in collections
            ),
        }


def render_osf_registration(structured: dict[str, Any]) -> str:
    title = str(structured.get("title") or f"OSF registration {structured['external_id']}")
    schema = structured.get("schema") or {}
    lines = [f"# {title}", "", f"Provider: OSF ({structured['external_id']})"]
    if structured.get("registered_at"):
        lines.append(f"Registered: {structured['registered_at']}")
    lines.extend(
        [
            f"Registry status: {structured.get('registration_status') or 'unknown'}",
            f"Registration schema: {schema.get('name') or 'unknown'} (version {schema.get('version') or 'unknown'})",
            f"Canonical URL: {structured.get('canonical_url')}",
            "",
        ]
    )
    section: str | None = None
    for question in structured.get("questions") or []:
        if question.get("section") and question["section"] != section:
            section = str(question["section"])
            lines.extend([f"## {section}", ""])
        lines.extend(
            [f"### {question.get('label') or question['response_key']}", "", _answer_text(question.get("answer")), ""]
        )
    if not structured.get("questions"):
        lines.extend(
            [
                "## Registration responses",
                "",
                "No structured responses were available from the public registry endpoint at retrieval time.",
                "",
            ]
        )
    revisions = [
        item
        for item in structured.get("response_history") or []
        if item.get("revision_justification")
        or item.get("updated_response_keys")
        or not item.get("is_original_response")
    ]
    if revisions:
        lines.extend(["## Registration revisions", ""])
        for revision in revisions:
            label = revision.get("date_modified") or revision.get("id") or "Recorded revision"
            lines.extend([f"### {label}", ""])
            if revision.get("revision_justification"):
                lines.extend([str(revision["revision_justification"]), ""])
            if revision.get("updated_response_keys"):
                lines.extend(["Updated response keys: " + ", ".join(map(str, revision["updated_response_keys"])), ""])
    return "\n".join(lines).rstrip() + "\n"


def _canonical_questions(block_rows: list[dict], responses: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = sorted(block_rows, key=lambda row: int((row.get("attributes") or {}).get("index") or 0))
    labels = {
        (row.get("attributes") or {}).get("schema_block_group_key"): (row.get("attributes") or {}).get("display_text")
        for row in blocks
        if (row.get("attributes") or {}).get("block_type") == "question-label"
    }
    result: list[dict[str, Any]] = []
    section: str | None = None
    for row in blocks:
        attrs = row.get("attributes") or {}
        if attrs.get("block_type") in {"page-heading", "section-heading", "subsection-heading"}:
            section = str(attrs.get("display_text") or section or "Registration responses")
        key = attrs.get("registration_response_key")
        if not key or key not in responses:
            continue
        result.append(
            {
                "response_key": key,
                "question_block_id": row.get("id"),
                "question_group_id": attrs.get("schema_block_group_key"),
                "label": labels.get(attrs.get("schema_block_group_key")) or attrs.get("display_text") or key,
                "section": section,
                "answer": responses[key],
                "answer_order": len(result),
                "input_type": attrs.get("block_type"),
                "required": attrs.get("required"),
            }
        )
    # Preserve response keys that the current schema snapshot cannot label (old schema/amendment edge case).
    known = {item["response_key"] for item in result}
    for key, answer in responses.items():
        if key not in known:
            result.append(
                {
                    "response_key": key,
                    "question_block_id": None,
                    "question_group_id": None,
                    "label": key,
                    "section": "Unmapped registration responses",
                    "answer": answer,
                    "answer_order": len(result),
                    "input_type": None,
                    "required": None,
                }
            )
    return result


def _response_values(registration_attrs: dict, response_row: dict | None) -> dict[str, Any]:
    if response_row:
        values = (response_row.get("attributes") or {}).get("revision_responses")
        if isinstance(values, dict):
            return values
    registered_meta = registration_attrs.get("registered_meta")
    if isinstance(registered_meta, dict):
        return {
            str(key): value.get("value") if isinstance(value, dict) and "value" in value else value
            for key, value in registered_meta.items()
        }
    values = registration_attrs.get("registration_responses")
    return dict(values) if isinstance(values, dict) else {}


def _latest_schema_response(payload: dict) -> dict | None:
    rows = [row for row in payload.get("data") or [] if isinstance(row, dict)]
    return max(rows, key=lambda row: str((row.get("attributes") or {}).get("date_modified") or ""), default=None)


def _response_history(payload: dict) -> list[dict[str, Any]]:
    history = []
    for row in payload.get("data") or []:
        attrs = row.get("attributes") or {}
        history.append(
            {
                "id": row.get("id"),
                "date_created": attrs.get("date_created"),
                "date_modified": attrs.get("date_modified"),
                "is_original_response": attrs.get("is_original_response"),
                "updated_response_keys": list(attrs.get("updated_response_keys") or []),
                "revision_justification": attrs.get("revision_justification"),
                "revision_responses": attrs.get("revision_responses") or {},
            }
        )
    return sorted(history, key=lambda item: (str(item.get("date_modified") or ""), str(item.get("id") or "")))


def _related_href(payload: dict, relationship: str) -> str | None:
    value = ((((payload.get("data") or {}).get("relationships") or {}).get(relationship) or {}).get("links") or {}).get(
        "related"
    )
    if isinstance(value, dict):
        value = value.get("href")
    return str(value) if value else None


def _relationship_href(row: dict, relationship: str) -> str | None:
    value = (((row.get("relationships") or {}).get(relationship) or {}).get("links") or {}).get("related")
    if isinstance(value, dict):
        value = value.get("href")
    return str(value) if value else None


def _next_href(payload: dict) -> str | None:
    value = (payload.get("links") or {}).get("next")
    if isinstance(value, dict):
        value = value.get("href")
    return str(value) if value else None


def _registration_doi(payload: dict) -> str | None:
    for row in payload.get("data") or []:
        attrs = row.get("attributes") or {}
        if str(attrs.get("category") or "").casefold() == "doi":
            return _normalize_doi(attrs.get("value"))
    return None


def _publication_dois(payload: dict) -> list[str]:
    result = []
    for row in payload.get("data") or []:
        attrs = row.get("attributes") or {}
        if str(attrs.get("resource_type") or "").casefold() not in {"paper", "papers"}:
            continue
        doi = _normalize_doi(attrs.get("pid"))
        if doi and doi not in result:
            result.append(doi)
    return result


def _normalize_doi(value: Any) -> str | None:
    token = str(value or "").strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        token = token.removeprefix(prefix)
    return token if token.startswith("10.") else None


def _contributors(payload: dict) -> list[dict[str, Any]]:
    result = []
    for row in payload.get("data") or []:
        user = ((row.get("embeds") or {}).get("users") or {}).get("data") or {}
        attrs = user.get("attributes") or {}
        result.append(
            {
                "id": user.get("id"),
                "name": attrs.get("full_name"),
                "bibliographic": (row.get("attributes") or {}).get("bibliographic"),
            }
        )
    return result


def _status(attrs: dict) -> str:
    if attrs.get("withdrawn"):
        return "withdrawn"
    if attrs.get("embargoed"):
        return "embargoed"
    if attrs.get("public") is False:
        return "unavailable"
    return "public"


def _answer_text(value: Any) -> str:
    if value in (None, "", []):
        return "[No response]"
    if isinstance(value, list):
        return "\n".join(f"- {html.unescape(str(item))}" for item in value) or "[No response]"
    if isinstance(value, dict):
        return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"
    return html.unescape(str(value)).strip() or "[No response]"
