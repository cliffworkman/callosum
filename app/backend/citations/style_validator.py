"""Local validation against the official CSL 1.0.2 schemas."""

from __future__ import annotations

import threading
from functools import lru_cache
from pathlib import Path

from lxml import etree, isoschematron

_SCHEMA_DIR = Path(__file__).parent / "csl" / "schema"
_validation_lock = threading.Lock()


@lru_cache(maxsize=1)
def _validators() -> tuple[etree.RelaxNG, isoschematron.Schematron]:
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    relaxng = etree.RelaxNG(etree.parse(str(_SCHEMA_DIR / "csl-1.0.2.rng"), parser))
    schematron = isoschematron.Schematron(
        etree.parse(str(_SCHEMA_DIR / "csl-1.0.2.sch"), parser),
        store_report=True,
    )
    return relaxng, schematron


def _parse(xml: str) -> etree._Element:
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        remove_comments=False,
    )
    try:
        return etree.fromstring(xml.encode("utf-8"), parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc


def _relaxng_error(validator: etree.RelaxNG) -> str:
    errors = []
    for item in validator.error_log:
        location = f"line {item.line}: " if item.line else ""
        message = " ".join(item.message.split())
        value = f"{location}{message}"
        if value not in errors:
            errors.append(value)
        if len(errors) == 3:
            break
    return "; ".join(errors) or "the style does not match the CSL 1.0.2 schema"


def _schematron_error(validator: isoschematron.Schematron) -> str:
    report = validator.validation_report
    if report is None:
        return "a macro reference is invalid"
    messages = [
        " ".join("".join(node.itertext()).split())
        for node in report.xpath(
            "//svrl:failed-assert",
            namespaces={"svrl": "http://purl.oclc.org/dsdl/svrl"},
        )
    ]
    return "; ".join(dict.fromkeys(messages[:3])) or "a macro reference is invalid"


def validate_csl_schema(xml: str) -> None:
    """Raise a concise error unless ``xml`` satisfies CSL 1.0.2 and its macro rules."""
    root = _parse(xml)
    with _validation_lock:
        relaxng, schematron = _validators()
        if not relaxng.validate(root):
            raise ValueError(f"CSL 1.0.2 schema validation failed: {_relaxng_error(relaxng)}")
        if not schematron.validate(root):
            raise ValueError(f"CSL macro validation failed: {_schematron_error(schematron)}")
