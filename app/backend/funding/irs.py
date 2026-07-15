"""Bounded EO-BMF and 990-PF parsing for Funding Discovery.

The parser is deterministic and intentionally narrow. It extracts organization
identity cues, historical grants, explicit application posture text, and source
batch state without running a global backfill on a user search path.
"""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import StringIO
from typing import Any

from app.backend.funding.domain import ApplicationSurface, HistoricalAward, ProvenanceRecord


@dataclass(frozen=True)
class EoBmfRecord:
    ein: str
    name: str
    organization_type: str | None
    geography: dict[str, Any]
    is_private_foundation: bool
    raw: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EoBmfBatch:
    records: list[EoBmfRecord]
    watermark: dict[str, Any]


@dataclass(frozen=True)
class PfParseResult:
    awards: list[HistoricalAward]
    surfaces: list[ApplicationSurface]
    errors: list[str]
    tax_year: int | None
    filing_identity: str


def parse_eo_bmf_csv(text: str, *, dataset_key: str = "manual") -> EoBmfBatch:
    reader = csv.DictReader(StringIO(text))
    records: list[EoBmfRecord] = []
    for row in reader:
        norm = {str(k or "").strip().upper(): str(v or "").strip() for k, v in row.items()}
        ein = norm.get("EIN") or norm.get("EIN_NUM") or norm.get("EMPLOYER_IDENTIFICATION_NUMBER")
        name = norm.get("NAME") or norm.get("ORGANIZATION_NAME") or norm.get("ORG_NAME")
        if not ein or not name:
            continue
        foundation_code = norm.get("FOUNDATION_CODE") or norm.get("FNDNCD")
        subsection = norm.get("SUBSECTION_CODE") or norm.get("SUBSECCD")
        is_pf = foundation_code in {"02", "03", "04"} or norm.get("PRIVATE_FOUNDATION") in {"1", "Y", "TRUE"}
        records.append(
            EoBmfRecord(
                ein=ein.zfill(9),
                name=name,
                organization_type="foundation" if is_pf else "nonprofit",
                geography={
                    "city": norm.get("CITY") or None,
                    "state": norm.get("STATE") or norm.get("STATE_CODE") or None,
                    "country": norm.get("COUNTRY") or "US",
                    "subsection": subsection or None,
                },
                is_private_foundation=is_pf,
                raw=norm,
            )
        )
    return EoBmfBatch(
        records=records,
        watermark={
            "dataset_key": dataset_key,
            "record_count": len(records),
            "indexed_at": datetime.now(UTC).isoformat(),
        },
    )


def parse_990pf_xml(text: str, *, source_record_id: str) -> PfParseResult:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        return PfParseResult([], [], [f"xml_parse_error:{exc}"], None, source_record_id)
    tax_year = _int(_first_text(root, ["TaxYr", "TaxYear", "TaxPeriodEndDt"]))
    filer_name = _first_text(root, ["BusinessNameLine1Txt", "BusinessNameLine1", "NameLine1Txt"]) or "Unresolved filer"
    filer_ein = _first_text(root, ["EIN", "FilerEIN"]) or source_record_id
    provider = "irs-990-pf"
    retrieved = datetime.now(UTC).isoformat()
    provenance = [
        ProvenanceRecord(
            provider_id=provider,
            source_record_id=source_record_id,
            retrieved_at=retrieved,
            extraction_method="deterministic_parse",
        )
    ]
    awards: list[HistoricalAward] = []
    errors: list[str] = []
    for node in _grant_nodes(root):
        try:
            recipient = _first_text(node, ["RecipientBusinessNameLine1Txt", "BusinessNameLine1Txt", "RecipientName"])
            person = _first_text(node, ["PersonNm", "RecipientPersonNm"])
            purpose = _first_text(node, ["PurposeOfGrantTxt", "GrantOrContributionPurposeTxt", "PurposeTxt"])
            amount = _int(_first_text(node, ["Amt", "Amount", "CashGrantAmt"]))
            approved = _node_name(node).lower().find("future") >= 0
            rid_bits = [source_record_id, str(len(awards) + 1)]
            if approved:
                rid_bits.append("future")
            awards.append(
                HistoricalAward(
                    organization_name=filer_name,
                    source_kind="irs_990_pf",
                    source_record_id="-".join(rid_bits),
                    purpose_text=purpose,
                    amount={"value": amount, "currency": "USD"} if amount is not None else {},
                    tax_year=tax_year,
                    recipient_name_raw=recipient if not person else person,
                    recipient_is_individual=bool(person),
                    provenance=provenance,
                )
            )
        except Exception as exc:
            errors.append(f"grant_parse_error:{type(exc).__name__}")
    surfaces: list[ApplicationSurface] = []
    posture = _application_posture(root)
    if posture:
        surfaces.append(
            ApplicationSurface(
                organization_name=filer_name,
                surface_type="structured_html",
                access_mode=posture["access_mode"],
                actionability="prospect_only",
                details=posture["details"],
                provenance=provenance,
            )
        )
    return PfParseResult(awards, surfaces, errors, tax_year, f"{filer_ein}:{source_record_id}")


def ui_award_record(award: HistoricalAward) -> dict[str, Any]:
    """UI-safe award evidence. Individual names and addresses are not exposed."""
    provenance = [p.to_dict() for p in award.provenance]
    first_provenance = provenance[0] if provenance else {}
    return {
        "organization_name": award.organization_name,
        "source_kind": award.source_kind,
        "source_record_id": award.source_record_id,
        "source_url": first_provenance.get("source_url"),
        "provider_id": first_provenance.get("provider_id"),
        "source_field": first_provenance.get("source_field"),
        "extraction_method": first_provenance.get("extraction_method"),
        "title": award.title,
        "purpose_text": award.purpose_text,
        "amount": award.amount,
        "tax_year": award.tax_year,
        "scheme_name": award.scheme_name,
        "award_number": award.award_number,
        "recipient_name": award.ui_recipient(),
        "recipient_withheld": award.recipient_is_individual,
        "provenance": provenance,
    }


def _first_text(node: ET.Element, names: list[str]) -> str | None:
    wanted = set(names)
    for child in node.iter():
        if _strip_ns(child.tag) in wanted and child.text and child.text.strip():
            return child.text.strip()
    return None


def _grant_nodes(root: ET.Element) -> list[ET.Element]:
    nodes: list[ET.Element] = []
    for child in root.iter():
        name = _node_name(child).lower()
        if "grant" not in name and "contribution" not in name:
            continue
        if len(list(child)) == 0:
            continue
        purpose = _first_text(child, ["PurposeOfGrantTxt", "GrantOrContributionPurposeTxt", "PurposeTxt"])
        amount = _first_text(child, ["Amt", "Amount", "CashGrantAmt"])
        recipient = _first_text(
            child, ["RecipientBusinessNameLine1Txt", "BusinessNameLine1Txt", "RecipientName", "PersonNm"]
        )
        if purpose or amount or recipient:
            nodes.append(child)
    return nodes


def _application_posture(root: ET.Element) -> dict[str, str] | None:
    blob = " ".join(t.strip() for t in root.itertext() if t and t.strip())
    lower = blob.lower()
    if "unsolicited" in lower and "not accept" in lower:
        return {"access_mode": "unknown", "details": "Source text indicates unsolicited applications are not accepted."}
    if "letter of inquiry" in lower or "loi" in lower:
        return {"access_mode": "letter_of_inquiry", "details": "Source text mentions a letter-of-inquiry route."}
    if "application guidelines" in lower:
        return {"access_mode": "unknown", "details": "Source text mentions application guidelines."}
    return None


def _strip_ns(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _node_name(node: ET.Element) -> str:
    return _strip_ns(str(node.tag))


def _int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d{4,}", value.replace(",", ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None
