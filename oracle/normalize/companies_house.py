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

import csv
import io
import json
import zipfile

from oracle import ids
from oracle.batch import CanonicalBatch

SOURCE_ID = "companies-house"
NAMESPACE = "companies-house"
SOURCE_CLASS = "primary-government"
PARSER_VERSION = "ch-json-v1"
NORMALIZER_VERSION = "ch-norm-v1"
ZIP_MAGIC = b"PK\x03\x04"

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

# Real Companies House BasicCompanyData CSV headers → intermediate fields.
# NOTE: the real files ship inconsistent leading spaces in header names
# (' CompanyNumber') and SicText-only SIC columns — keys are stripped and
# SIC codes are extracted from the SicText prefix on read.
CSV_FIELD_MAP = {
    "CompanyName": "company_name",
    "CompanyNumber": "company_number",
    "CompanyStatus": "company_status",
    "CompanyCategory": "type",
    "IncorporationDate": "incorporation_date",
    "DissolutionDate": "dissolution_date",
    "RegAddress.PostCode": "registered_postcode",
    "RegAddress.AddressLine1": "address_line_1",
    "RegAddress.PostTown": "locality",
    "Accounts.NextDueDate": "accounts_next_due",
    "ConfStmtNextDueDate": "confirmation_next_due",
}
CSV_SIC_TEXT_HEADERS = [
    "SICCode.SicText_1", "SICCode.SicText_2",
    "SICCode.SicText_3", "SICCode.SicText_4",
]
CSV_SIC_CODE_HEADERS = [
    "SICCode.Code_1", "SICCode.Code_2",
    "SICCode.Code_3", "SICCode.Code_4",
]
CSV_DATE_FIELDS = {
    "incorporation_date", "dissolution_date",
    "accounts_next_due", "confirmation_next_due",
}


def _clean_row(row: dict) -> dict:
    """Strip header whitespace and values (real CH headers are ragged)."""
    return {(k.strip() if isinstance(k, str) else k):
            (v.strip() if isinstance(v, str) else v)
            for k, v in row.items()}


def _sic_from_text(text: str) -> str:
    """'62012 - Business ...' → '62012'. No leading digits → ''."""
    import re

    m = re.match(r"(\d+)", (text or "").strip())
    return m.group(1) if m else ""


def _iso_date(value: str | None) -> str | None:
    """DD/MM/YYYY → YYYY-MM-DD. ISO input passes through. Else raw/None."""
    import re

    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
    if m:
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"
    return v


def csv_row_to_company(row: dict) -> dict:
    """Real-format CSV row → intermediate company dict (same shape as JSON)."""
    row = _clean_row(row)
    company = {}
    for header, field in CSV_FIELD_MAP.items():
        value = row.get(header) or ""
        company[field] = value or None
    status = (company.get("company_status") or "").strip().lower()
    company["company_status"] = status or "active"
    codes = []
    for h in CSV_SIC_CODE_HEADERS:
        code = (row.get(h) or "").strip()
        if code:
            codes.append(code)
    if not codes:
        for h in CSV_SIC_TEXT_HEADERS:
            code = _sic_from_text(row.get(h) or "")
            if code:
                codes.append(code)
    company["sic_codes"] = codes
    for field in CSV_DATE_FIELDS:
        company[field] = _iso_date(company.get(field))
    return company


def iter_zip_rows_from_path(zip_path: str):
    """Stream (inner_name, line_number, row_dict) from a ZIP file on disk.

    The archive is never fully loaded: rows flow straight from the
    decompressor through the CSV reader.
    """
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("parse_error:zip-without-csv")
        for inner in sorted(names):
            with z.open(inner) as fh:
                reader = csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig"),
                    skipinitialspace=True)
                for row in reader:
                    yield inner, reader.line_num, row


def iter_batches(zip_path: str, *, receipt_id: str, raw_sha256: str,
                 observed_at: str, artifact_name: str,
                 chunk_rows: int = 5000):
    """Yield CanonicalBatch per chunk_rows CSV rows (bounded memory)."""
    csv_labels = {v: k for k, v in CSV_FIELD_MAP.items()}
    csv_labels["sic_codes"] = "SICCode.SicText_*"
    batch = CanonicalBatch()
    n = 0
    for inner, lineno, row in iter_zip_rows_from_path(zip_path):
        base = f"{artifact_name}#{inner}:row={lineno}"
        _add_company(batch, csv_row_to_company(row), lineno, base,
                     receipt_id, raw_sha256, observed_at,
                     field_labels=csv_labels)
        n += 1
        if n >= chunk_rows:
            yield batch
            batch = CanonicalBatch()
            n = 0
    if n or batch.rejects:
        yield batch


def iter_zip_rows(raw_bytes: bytes):
    """Stream (inner_name, line_number, row_dict) straight out of the ZIP.

    Rows are read incrementally — the 469 MB bulk snapshot never sits in
    memory as parsed objects.
    """
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not names:
            raise ValueError("parse_error:zip-without-csv")
        for inner in sorted(names):
            with z.open(inner) as fh:
                reader = csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig"),
                    skipinitialspace=True)
                for row in reader:
                    yield inner, reader.line_num, row


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
    locator_base: str,
    observed_at: str,
    field_labels: dict | None = None,
) -> list[dict]:
    """One company record → list of gate-ready observation dicts."""
    entity = company_to_entity(company)  # validates company_number
    subject = entity["entity_id"]
    labels = field_labels or {}
    observations = []
    for field, predicate in FIELD_PREDICATES.items():
        value = company.get(field)
        if is_unknown(value):
            continue  # Unknown = null: emit nothing
        vtype = value_type_of(value)
        label = labels.get(field, field)
        locator = f"{locator_base}/{label}"
        observations.append({
            "observation_id": ids.observation_id(
                subject, predicate, value, vtype, SOURCE_ID,
                receipt_id, locator, observed_at,
                PARSER_VERSION, NORMALIZER_VERSION),
            "subject_entity_id": subject,
            "predicate": predicate,
            "value": value,
            "value_type": vtype,
            "source_id": SOURCE_ID,
            "source_class": SOURCE_CLASS,
            "raw_receipt_id": receipt_id,
            "record_locator": locator,
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
) -> CanonicalBatch:
    """Parse one raw artifact (JSON fixture or real-format ZIP/CSV).

    Returns a CanonicalBatch. Malformed artifacts raise ValueError
    (stage=parse quarantine, bytes retained). Per-record failures become
    structured rejects, never silent drops. ZIP rows stream — memory stays
    bounded regardless of snapshot size.
    """
    batch = CanonicalBatch()
    if raw_bytes[:4] == ZIP_MAGIC:
        _parse_zip(batch, raw_bytes, receipt_id=receipt_id,
                   raw_sha256=raw_sha256, observed_at=observed_at,
                   artifact_name=artifact_name)
        return batch
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValueError(f"parse_error:not-json: {e}")
    if not isinstance(payload, list):
        raise ValueError("parse_error:expected-top-level-array")
    for i, company in enumerate(payload):
        _add_company(batch, company, i, f"{artifact_name}#/[{i}]",
                     receipt_id, raw_sha256, observed_at,
                     field_labels=None)
    return batch


def _add_company(batch: CanonicalBatch, company, index: int, locator: str,
                 receipt_id: str, raw_sha256: str, observed_at: str,
                 field_labels: dict | None = None):
    if not isinstance(company, dict):
        batch.rejects.append({
            "stage": "parse",
            "failure_code": "parse_error:record-not-object",
            "record_locator": locator,
            "reason": "parse_error:record-not-object",
            "index": index,
        })
        return
    try:
        entity = company_to_entity(company)
        observations = company_to_observations(
            company, receipt_id=receipt_id, raw_sha256=raw_sha256,
            locator_base=locator, observed_at=observed_at,
            field_labels=field_labels,
        )
    except ValueError as e:
        batch.rejects.append({
            "stage": "parse",
            "failure_code": str(e),
            "record_locator": locator,
            "reason": str(e),
            "index": index,
            "source_id": SOURCE_ID,
        })
        return
    number = (company.get("company_number") or "").strip()
    batch.entities.append(entity)
    batch.identifiers.append({
        "entity_id": entity["entity_id"],
        "id_type": "companies-house:company_number",
        "id_value": number,
    })
    batch.observations.extend(observations)


def _parse_zip(batch: CanonicalBatch, raw_bytes: bytes, *, receipt_id: str,
               raw_sha256: str, observed_at: str, artifact_name: str):
    csv_labels = {v: k for k, v in CSV_FIELD_MAP.items()}
    csv_labels["sic_codes"] = "SICCode.Code_*"
    try:
        rows = iter_zip_rows(raw_bytes)
        for inner, lineno, row in rows:
            base = f"{artifact_name}#{inner}:row={lineno}"
            _add_company(batch, csv_row_to_company(row), lineno, base,
                         receipt_id, raw_sha256, observed_at,
                         field_labels=csv_labels)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"parse_error:zip-unreadable: {e}")


class CompaniesHouseParser:
    """Runner-compatible parser. parse() returns envelope dicts.

    Envelope convention (see oracle/ingest/runner.py): each item is
    {"entity": {...}, "observations": [...]}. The runner stores entities,
    runs gates on each observation, and quarantines failures.
    """

    PARSER_VERSION = PARSER_VERSION
    NORMALIZER_VERSION = NORMALIZER_VERSION
    source_id = SOURCE_ID

    def parse(self, artifact: bytes, fetch_result=None, receipt=None,
              artifact_name: str = "small_snapshot.json") -> CanonicalBatch:
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
        return parse_artifact(
            artifact, receipt_id=receipt_id, raw_sha256=raw_sha,
            observed_at=observed, artifact_name=artifact_name,
        )

    def iter_batches(self, zip_path: str, *, receipt_id: str,
                     raw_sha256: str, observed_at: str, artifact_name: str,
                     chunk_rows: int = 5000):
        """Stream CanonicalBatch per chunk_rows rows (bulk path)."""
        return iter_batches(
            zip_path, receipt_id=receipt_id, raw_sha256=raw_sha256,
            observed_at=observed_at, artifact_name=artifact_name,
            chunk_rows=chunk_rows)


def _utcnow() -> str:
    import time

    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
