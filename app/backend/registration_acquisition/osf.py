from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any

from app.backend.registration_acquisition.domain import AcquiredRegistration, RegistrationAcquisitionError
from app.backend.registration_discovery.http import JsonFetcher, RegistryHttpError, get_registry_json

_BASE = "https://api.osf.io/v2"
_GUID = re.compile(r"^[a-z0-9]{4,12}$")


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
            schema_responses = self._fetch(f"{_BASE}/registrations/{guid}/schema_responses/")
            contributors = self._optional(f"{_BASE}/registrations/{guid}/contributors/?embed=users")
            identifiers = self._optional(f"{_BASE}/registrations/{guid}/identifiers/")
            resources = self._optional(f"{_BASE}/registrations/{guid}/resources/")
            files = self._optional(f"{_BASE}/registrations/{guid}/files/")
            schema_url = _related_href(registration, "registration_schema")
            schema = self._fetch(schema_url) if schema_url else {"data": None}
            blocks_url = f"{schema_url.rstrip('/')}/schema_blocks/" if schema_url else None
            schema_blocks = self._fetch(blocks_url) if blocks_url else {"data": []}
        except RegistryHttpError as exc:
            raise RegistrationAcquisitionError(f"OSF acquisition failed: {exc}") from exc

        row = registration.get("data") or {}
        if str(row.get("id") or "").casefold() != guid:
            raise RegistrationAcquisitionError("OSF returned metadata for an unexpected registration identifier.")
        attrs = row.get("attributes") or {}
        schema_row = schema.get("data") or {}
        schema_attrs = schema_row.get("attributes") or {}
        response_row = _latest_schema_response(schema_responses)
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
            "contributors": _contributors(contributors),
            "identifiers": identifiers.get("data") or [],
            "resources": resources.get("data") or [],
            "files": files.get("data") or [],
        }
        source_metadata = {
            "registration": registration,
            "schema": schema,
            "schema_blocks": schema_blocks,
            "schema_responses": schema_responses,
            "contributors": contributors,
            "identifiers": identifiers,
            "resources": resources,
            "files": files,
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

    def _optional(self, url: str) -> dict:
        try:
            return self._fetch(url)
        except RegistryHttpError as exc:
            return {"data": [], "callosum_error": {"status": exc.status, "detail": str(exc)}}


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


def _related_href(payload: dict, relationship: str) -> str | None:
    value = ((((payload.get("data") or {}).get("relationships") or {}).get(relationship) or {}).get("links") or {}).get(
        "related"
    )
    if isinstance(value, dict):
        value = value.get("href")
    return str(value) if value else None


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
