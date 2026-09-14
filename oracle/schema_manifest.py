"""Canonical schema manifest. One source of truth for all record shapes.

DEVINSTRUCT §6. Python ↔ SQL parity enforcement. Any field that exists in
one representation but not the other is a test failure.
"""
from __future__ import annotations


# Schema definitions: name → {field: type}
# Types map to both Python dataclass fields and BQ SQL types.

SCHEMAS = {
    "Source": {
        "source_id": "str",
        "jurisdiction": "str",
        "access": "str",
        "auth_class": "str",
        "cost": "float",
        "license": "str",
        "terms_url": "str",
        "terms_hash": "str",
        "commercial_use": "str",
        "raw_storage": "str",
        "redistribution": "str",
        "attribution_required": "bool",
        "personal_data_class": "str",
        "allowed_uses": "list<str>",
        "prohibited_uses": "list<str>",
        "cadence": "str",
        "entity_keys": "list<str>",
        "raw_retention": "bool",
        "adapter": "str",
        "parser_version": "str",
    },
    "RawObject": {
        "raw_sha256": "str",
        "source_id": "str",
        "raw_uri": "str",
        "byte_length": "int",
        "media_type": "str",
        "parser_version": "str",
    },
    "Entity": {
        "entity_id": "str",
        "entity_type": "str",
        "country": "str",
        "canonical_name": "str",
        "status": "str",
        "created_at": "str",
    },
    "Identifier": {
        "entity_id": "str",
        "id_type": "str",
        "id_value": "str",
    },
    "Relation": {
        "relation_id": "str",
        "from_entity_id": "str",
        "to_entity_id": "str",
        "relation_type": "str",
        "valid_from": "str",
        "valid_to": "str",
        "evidence_refs": "list<str>",
        "confidence": "float",
        "lineage_root": "str",
    },
    "Observation": {
        "observation_id": "str",
        "subject_entity_id": "str",
        "predicate": "str",
        "value": "json",
        "value_type": "str",
        "source_id": "str",
        "source_class": "str",
        "raw_receipt_id": "str",
        "record_locator": "str",
        "observed_at": "str",
        "valid_from": "str",
        "valid_to": "str",
        "ingested_at": "str",
        "parser_version": "str",
        "normalizer_version": "str",
        "status": "str",
        "confidence": "float",
        "lineage_root": "str",
    },
    "Event": {
        "event_id": "str",
        "event_type": "str",
        "subject": "str",
        "observed_at": "str",
        "payload": "json",
        "triggering_observation_ids": "list<str>",
    },
    "Signal": {
        "signal_id": "str",
        "formula_id": "str",
        "formula_version": "str",
        "input_ids": "list<str>",
        "value": "float",
        "computed_at": "str",
        "code_hash": "str",
    },
    "Hypothesis": {
        "hypothesis_id": "str",
        "thesis": "str",
        "supporting": "list<str>",
        "contradicting": "list<str>",
        "falsifiers": "list<str>",
    },
    "Outcome": {
        "outcome_id": "str",
        "opportunity_id": "str",
        "campaign_id": "str",
        "action": "str",
        "metrics": "json",
        "evidence_refs": "list<str>",
        "qp_receipt_ids": "list<str>",
        "observed_at": "str",
        "verification_status": "str",
    },
    "CandidateOpportunity": {
        "opportunity_id": "str",
        "detector_id": "str",
        "detector_version": "str",
        "subject": "str",
        "type": "str",
        "thesis": "str",
        "supporting_signal_ids": "list<str>",
        "contradicting_signal_ids": "list<str>",
        "unknowns": "list<str>",
        "affected_entity_ids": "list<str>",
        "possible_moat": "list<str>",
        "falsifiers": "list<str>",
        "probe_request_ids": "list<str>",
        "input_root": "str",
        "created_at": "str",
    },
    "FetchResult": {
        "status": "str",
        "artifacts": "list<bytes>",
        "cursor": "str",
        "watermark": "str",
        "snapshot_semantics": "str",
        "complete": "bool",
        "error": "dict",
        "source_id": "str",
        "adapter_version": "str",
        "started_at": "str",
        "finished_at": "str",
    },
    "RawEvidenceReceipt": {
        "receipt_id": "str",
        "source_id": "str",
        "source_contract_hash": "str",
        "raw_sha256": "str",
        "raw_uri": "str",
        "byte_length": "int",
        "media_type": "str",
        "compression": "str",
        "fetched_at": "str",
        "request_fingerprint": "str",
        "response_status": "int",
        "snapshot_semantics": "str",
        "complete": "bool",
        "cursor": "str",
        "watermark": "str",
        "adapter_version": "str",
        "parser_version": "str",
        "ingest_run_id": "str",
    },
}


# BQ DDL type mapping
PYTHON_TO_BQ = {
    "str": "STRING",
    "int": "INT64",
    "float": "FLOAT64",
    "bool": "BOOL",
    "json": "JSON",
    "list<str>": "ARRAY<STRING>",
    "list<bytes>": "ARRAY<BYTES>",
    "dict": "JSON",
}


def schema_fields(schema_name: str) -> dict:
    """Return field→type for a named schema."""
    return dict(SCHEMAS.get(schema_name, {}))


def bq_columns(schema_name: str) -> list[tuple[str, str]]:
    """Return [(field, BQ_SQL_TYPE)] for a named schema."""
    fields = SCHEMAS.get(schema_name, {})
    return [(f, PYTHON_TO_BQ.get(t, "STRING")) for f, t in fields.items()]


def check_parity(schema_name: str, sql_columns: dict[str, str]) -> list[str]:
    """Compare schema manifest against SQL table columns.
    Returns list of discrepancies (empty = parity OK)."""
    discrepancies = []
    manifest = SCHEMAS.get(schema_name, {})

    # Fields in manifest but not in SQL
    for field in manifest:
        if field not in sql_columns:
            discrepancies.append(f"in_manifest_not_sql:{schema_name}.{field}")

    # Fields in SQL but not in manifest
    for field in sql_columns:
        if field not in manifest:
            discrepancies.append(f"in_sql_not_manifest:{schema_name}.{field}")

    return discrepancies
