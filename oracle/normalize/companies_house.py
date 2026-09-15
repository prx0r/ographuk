"""Companies House JSON parser + normalizer (E1).

Fixture → stable Entities + provenance-linked Observations.

Conventions (DEVINSTRUCT §§12-16, decdev.md §§13-16):
- Entity identity is stable: entity_id(company, companies-house, number).
  Survives name/status/address changes.
- Unknown = null: null/empty-unknown source fields emit NO observation.
  Known-empty (sic_codes == []) IS factual and is emitted as [].
- Every observation carries: raw_receipt_id, record_locator (exact JSON
  pointer within the artifact), observed_at, parser/normalizer versions,
  lineage_root = raw_sha256.
- parse_artifact() is pure: same bytes + same receipt context → same output.
"""

from __future__ import annotations

import json

from oracle import ids

SOURCE_ID = "companies-house"
NAMESPACE = "companies-house"
SOURCE_CLASS = "primary-government"
PARSER_VERSION = "ch-json-v1"
NORMALIZER_VERSION = "ch-norm-v1"

# source field → canonical predicate
FIELD_PREDICATES = {
    "company_name": "company.name",
    "company_status": "company.status",
    "type": "company.type",
    "incorporation_date": "company.incorporation_date",
    "dissolution_date": "company.dissolution_date",
    "registered_postcode": "company.postcode",
    "sic_codes": "company.sic_codes",
    "address_line_1": "company.address_line_1",
    "locality": "company.locality",
    "accounts_next_due": "company.accounts_next_due",
    "confirmation_next_due": "company.confirmation_next_due",
}


def value_type_of(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def is_unknown(value) -> bool:
    """Unknown = null/blank → no observation. Known-empty list is factual."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def company_to_entity(company: dict) -> dict:
    """Stable entity for one company record. Raises ValueError if no key."""
    number = (company.get("company_number") or "").strip()
    if not number:
        raise ValueError("missing:company_number")
    return {
        "entity_id": ids.entity_id("company", NAMESPACE, number),
        "entity_type": "company",
        "country": "GB",
        "canonical_name": company.get("company_name") or "",
        "status": company.get("company_status") or "active",
        "created_at": company.get("incorporation_date") or "",
    }


def company_to_observations(
    company: dict,
    *,
    receipt_id: str,
    raw_sha256: str,
    index: int,
    observed_at: str,
    artifact_name: str = "small_snapshot.json",
) -> list[dict]:
    """One company record → list of gate-ready observation dicts."""
    entity = company_to_entity(company)  # validates company_number
    subject = entity["entity_id"]
    observations = []
    for field, predicate in FIELD_PREDICATES.items():
        value = company.get(field)
        if is_unknown(value):
            continue  # Unknown = null: emit nothing
        observations.append({
            "subject_entity_id": subject,
            "predicate": predicate,
            "value": value,
            "value_type": value_type_of(value),
            "source_id": SOURCE_ID,
            "source_class": SOURCE_CLASS,
            "raw_receipt_id": receipt_id,
            "record_locator": f"{artifact_name}#/[{index}]/{field}",
            "observed_at": observed_at,
            "valid_from": "",
            "valid_to": "",
            "ingested_at": "",
            "parser_version": PARSER_VERSION,
            "normalizer_version": NORMALIZER_VERSION,
            "status": "OBSERVED",
            "confidence": None,
            "lineage_root": raw_sha256,
        })
    return observations


def parse_artifact(
    raw_bytes: bytes,
    *,
    receipt_id: str,
    raw_sha256: str,
    observed_at: str,
    artifact_name: str = "small_snapshot.json",
) -> tuple[list[dict], list[dict]]:
    """Parse one raw JSON artifact.

    Returns (bundles, errors) where bundles = [{"entity", "observations"}]
    and errors = [{"index", "reason", "record_locator"}] for records that
    cannot become entities (e.g. missing company_number). Malformed JSON
    raises ValueError (artifact-level failure → run-level error, the bytes
    are still retained in RawStore).
    """
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"parse_error:not-json: {e}")
    if not isinstance(payload, list):
        raise ValueError("parse_error:expected-top-level-array")
    bundles, errors = [], []
    for i, company in enumerate(payload):
        if not isinstance(company, dict):
            errors.append({
                "index": i,
                "reason": "parse_error:record-not-object",
                "record_locator": f"{artifact_name}#/[{i}]",
            })
            continue
        try:
            entity = company_to_entity(company)
            observations = company_to_observations(
                company, receipt_id=receipt_id, raw_sha256=raw_sha256,
                index=i, observed_at=observed_at, artifact_name=artifact_name,
            )
        except ValueError as e:
            errors.append({
                "index": i,
                "reason": str(e),
                "record_locator": f"{artifact_name}#/[{i}]",
                "source_id": SOURCE_ID,
            })
            continue
        number = (company.get("company_number") or "").strip()
        bundles.append({
            "entity": entity,
            "identifiers": [{
                "entity_id": entity["entity_id"],
                "id_type": "companies-house:company_number",
                "id_value": number,
            }],
            "observations": observations,
        })
    return bundles, errors


class CompaniesHouseParser:
    """Runner-compatible parser. parse() returns envelope dicts.

    Envelope convention (see oracle/ingest/runner.py): each item is
    {"entity": {...}, "observations": [...]}. The runner stores entities,
    runs gates on each observation, and quarantines failures.
    """

    PARSER_VERSION = PARSER_VERSION
    NORMALIZER_VERSION = NORMALIZER_VERSION
    source_id = SOURCE_ID

    def parse(self, artifact: bytes, fetch_result=None, receipt=None) -> list[dict]:
        from oracle.provenance import raw_hash

        if receipt is not None:
            receipt_id = receipt.receipt_id if hasattr(receipt, "receipt_id") else receipt.get("receipt_id", "")
            raw_sha = receipt.raw_sha256 if hasattr(receipt, "raw_sha256") else receipt.get("raw_sha256", "")
            observed = (receipt.fetched_at if hasattr(receipt, "fetched_at") else receipt.get("fetched_at", "")) or _utcnow()
        else:
            # No receipt context (replay/dry-run): derive deterministic
            # placeholders so output shape is still inspectable. These
            # records must NOT be stored without a real receipt.
            raw_sha = raw_hash(artifact)
            receipt_id = ids.record_id("RECEIPT", {
                "source_id": SOURCE_ID, "raw_sha256": raw_sha,
                "parser_version": PARSER_VERSION,
                "snapshot_semantics": "FULL", "complete": True,
                "fetched_at": "REPLAY-NO-RECEIPT",
            })
            observed = _utcnow()
        bundles, errors = parse_artifact(
            artifact, receipt_id=receipt_id, raw_sha256=raw_sha,
            observed_at=observed,
        )
        out = [{
            "entity": b["entity"],
            "identifiers": b.get("identifiers", []),
            "observations": b["observations"],
        } for b in bundles]
        for e in errors:
            out.append({"_error": e})
        return out


def _utcnow() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
