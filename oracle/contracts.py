"""E0 contracts: schemas-as-code for all Oracle record types.

DEVINSTRUCT §3-15. Binary validation: valid or rejected with reasons.
No scores at the gate layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from oracle import ids


SOURCE_CLASSES = {"primary-government", "primary-commercial", "secondary",
                  "user", "model-derived"}
OBS_STATUSES = {"OBSERVED", "INVALID", "SUPERSEDED"}
GRADES = {"HYPOTHESIS", "SUPPORTED", "QUANTIFIED", "VALIDATED"}
OPPORTUNITY_TYPES = {"BUSINESS", "PLUGIN", "TRADE", "AD", "PRODUCT"}
RELATION_TYPES = {"OPERATES_AT", "HAS_IDENTIFIER", "HAS_LOCATION",
                  "SAME_AS", "SAME_AS_CANDIDATE", "PUBLISHED",
                  "AWARDED_TO", "GOVERNED_BY", "IN_CATEGORY",
                  "BRANDED_BY", "LISTS", "ON_MARKETPLACE",
                  "TRIGGERS", "SUPERSEDES"}
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 1.0


def _req(name, value, reasons):
    if value is None or (isinstance(value, str) and not value.strip()):
        reasons.append("missing:" + name)
        return False
    return True


def _check_range(name, value, lo, hi, reasons):
    if value is not None:
        try:
            v = float(value)
        except (TypeError, ValueError):
            reasons.append(f"bad:{name}:not-numeric")
            return
        if not (lo <= v <= hi):
            reasons.append(f"bad:{name}:out-of-range")
            if math.isnan(v) or math.isinf(v):
                reasons.append(f"bad:{name}:non-finite")


import math


# ── Source ──

@dataclass
class Source:
    source_id: str
    jurisdiction: str = "GB"
    access: str = ""
    auth_class: str = ""
    cost: float = 0.0
    license: str = ""
    terms_url: str = ""
    terms_hash: str = ""
    commercial_use: str = "UNKNOWN"       # ALLOWED / FORBIDDEN / UNKNOWN
    raw_storage: str = "UNKNOWN"          # ALLOWED / FORBIDDEN / LIMITED / UNKNOWN
    redistribution: str = "UNKNOWN"       # ALLOWED / FORBIDDEN / LIMITED / UNKNOWN
    attribution_required: bool = False
    personal_data_class: str = "NONE"     # NONE / PUBLIC_PERSONAL / SENSITIVE_RESTRICTED
    allowed_uses: list = field(default_factory=list)
    prohibited_uses: list = field(default_factory=list)
    cadence: str = ""
    entity_keys: list = field(default_factory=list)
    raw_retention: bool = True
    adapter: str = ""
    parser_version: str = "v1"
    last_success: str = ""
    cursor: str = ""
    schema_hash: str = ""

    def to_dict(self) -> dict:
        """Canonical contract fields for hashing into receipts."""
        return {
            "source_id": self.source_id,
            "jurisdiction": self.jurisdiction,
            "access": self.access,
            "auth_class": self.auth_class,
            "cost": self.cost,
            "license": self.license,
            "terms_url": self.terms_url,
            "terms_hash": self.terms_hash,
            "commercial_use": self.commercial_use,
            "raw_storage": self.raw_storage,
            "redistribution": self.redistribution,
            "attribution_required": self.attribution_required,
            "personal_data_class": self.personal_data_class,
            "allowed_uses": self.allowed_uses,
            "prohibited_uses": self.prohibited_uses,
            "cadence": self.cadence,
            "entity_keys": self.entity_keys,
            "raw_retention": self.raw_retention,
            "adapter": self.adapter,
            "parser_version": self.parser_version,
        }

    def validate(self):
        reasons = []
        _req("source_id", self.source_id, reasons)
        _req("license", self.license, reasons)
        _req("terms_url", self.terms_url, reasons)
        # Fail closed: raw retention + unknown storage = blocked
        if self.raw_retention and self.raw_storage == "UNKNOWN":
            reasons.append("blocked:raw_storage_unknown_with_retention")
        if self.commercial_use not in ("ALLOWED", "FORBIDDEN", "UNKNOWN"):
            reasons.append("bad:commercial_use")
        if self.raw_storage not in ("ALLOWED", "FORBIDDEN", "LIMITED", "UNKNOWN"):
            reasons.append("bad:raw_storage")
        if self.redistribution not in ("ALLOWED", "FORBIDDEN", "LIMITED", "UNKNOWN"):
            reasons.append("bad:redistribution")
        if self.personal_data_class not in ("NONE", "PUBLIC_PERSONAL", "SENSITIVE_RESTRICTED"):
            reasons.append("bad:personal_data_class")
        return (not reasons), reasons


# ── RawObject ──

@dataclass
class RawObject:
    raw_sha256: str
    source_id: str
    raw_uri: str = ""
    byte_length: int = 0
    media_type: str = ""
    parser_version: str = "v1"
    ingested_at: str = ""

    def validate(self):
        reasons = []
        _req("raw_sha256", self.raw_sha256, reasons)
        _req("source_id", self.source_id, reasons)
        if self.byte_length < 0:
            reasons.append("bad:byte_length:negative")
        return (not reasons), reasons


# ── Entity ──

@dataclass
class Entity:
    entity_id: str
    entity_type: str
    country: str = "GB"
    canonical_name: str = ""
    status: str = "active"
    created_at: str = ""

    def validate(self):
        reasons = []
        _req("entity_id", self.entity_id, reasons)
        _req("entity_type", self.entity_type, reasons)
        return (not reasons), reasons


# ── Identifier ──

@dataclass
class Identifier:
    entity_id: str
    id_type: str
    id_value: str

    def validate(self):
        reasons = []
        _req("entity_id", self.entity_id, reasons)
        _req("id_type", self.id_type, reasons)
        _req("id_value", self.id_value, reasons)
        return (not reasons), reasons


# ── Relation ──

@dataclass
class Relation:
    from_entity_id: str
    to_entity_id: str
    relation_type: str
    relation_id: str = ""
    valid_from: str = ""
    valid_to: str = ""
    evidence_refs: list = field(default_factory=list)
    confidence: float = None
    lineage_root: str = ""

    def __post_init__(self):
        if not self.relation_id:
            self.relation_id = ids.record_id("REL", {
                "from": self.from_entity_id,
                "to": self.to_entity_id,
                "type": self.relation_type,
            })

    def validate(self):
        reasons = []
        _req("from_entity_id", self.from_entity_id, reasons)
        _req("to_entity_id", self.to_entity_id, reasons)
        _req("relation_type", self.relation_type, reasons)
        if self.relation_type != self.relation_type.upper().replace(" ", "_"):
            reasons.append("relation_type:not-upper-snake")
        if not self.evidence_refs:
            reasons.append("missing:evidence_refs")
        _check_range("confidence", self.confidence, CONFIDENCE_MIN, CONFIDENCE_MAX, reasons)
        return (not reasons), reasons


# ── Observation ──

@dataclass
class Observation:
    observation_id: str = ""
    subject_entity_id: str = ""
    predicate: str = ""
    value: object = None
    value_type: str = "string"       # string / number / boolean / null / object / array
    source_id: str = ""
    source_class: str = ""
    raw_receipt_id: str = ""
    record_locator: str = ""
    observed_at: str = ""
    valid_from: str = ""
    valid_to: str = ""
    ingested_at: str = ""
    parser_version: str = ""
    normalizer_version: str = ""
    status: str = "OBSERVED"
    confidence: float = None
    lineage_root: str = ""

    def validate(self):
        reasons = []
        _req("subject_entity_id", self.subject_entity_id, reasons)
        _req("predicate", self.predicate, reasons)
        _req("source_id", self.source_id, reasons)
        _req("raw_receipt_id", self.raw_receipt_id, reasons)
        _req("record_locator", self.record_locator, reasons)
        _req("observed_at", self.observed_at, reasons)
        if self.source_class and self.source_class not in SOURCE_CLASSES:
            reasons.append("bad:source_class")
        if self.status not in OBS_STATUSES:
            reasons.append("bad:status")
        _check_range("confidence", self.confidence, CONFIDENCE_MIN, CONFIDENCE_MAX, reasons)
        if self.value_type not in ("string", "number", "boolean", "null",
                                    "object", "array"):
            reasons.append("bad:value_type")
        return (not reasons), reasons


# ── Event ──

@dataclass
class Event:
    event_type: str
    event_id: str = ""
    subject: str = ""
    observed_at: str = ""
    ingested_at: str = ""
    payload: dict = field(default_factory=dict)
    triggering_observation_ids: list = field(default_factory=list)

    def validate(self):
        reasons = []
        _req("event_type", self.event_type, reasons)
        _req("observed_at", self.observed_at, reasons)
        if not self.triggering_observation_ids:
            reasons.append("missing:triggering_observation_ids")
        return (not reasons), reasons


# ── Signal ──

@dataclass
class Signal:
    signal_id: str
    formula_id: str
    formula_version: str = "v1"
    input_ids: list = field(default_factory=list)
    value: object = None
    computed_at: str = ""
    code_hash: str = ""

    def validate(self):
        reasons = []
        _req("signal_id", self.signal_id, reasons)
        _req("formula_id", self.formula_id, reasons)
        _req("input_ids", self.input_ids or None, reasons)
        _req("computed_at", self.computed_at, reasons)
        return (not reasons), reasons


# ── Hypothesis ──

@dataclass
class Hypothesis:
    hypothesis_id: str
    thesis: str = ""
    supporting: list = field(default_factory=list)
    contradicting: list = field(default_factory=list)
    falsifiers: list = field(default_factory=list)

    def validate(self):
        reasons = []
        _req("hypothesis_id", self.hypothesis_id, reasons)
        _req("thesis", self.thesis, reasons)
        _req("falsifiers", self.falsifiers or None, reasons)
        return (not reasons), reasons


# ── Outcome ──

@dataclass
class Outcome:
    outcome_id: str
    opportunity_id: str = ""
    campaign_id: str = ""
    action: str = ""
    metrics: dict = field(default_factory=dict)
    evidence_refs: list = field(default_factory=list)
    qp_receipt_ids: list = field(default_factory=list)
    observed_at: str = ""
    verification_status: str = "UNVERIFIED"  # UNVERIFIED / VERIFIED / REJECTED

    def validate(self):
        reasons = []
        _req("outcome_id", self.outcome_id, reasons)
        _req("action", self.action, reasons)
        _req("observed_at", self.observed_at, reasons)
        if self.verification_status not in ("UNVERIFIED", "VERIFIED", "REJECTED"):
            reasons.append("bad:verification_status")
        return (not reasons), reasons


# ── CandidateOpportunity ────

@dataclass
class CandidateOpportunity:
    opportunity_id: str
    detector_id: str = ""
    detector_version: str = "v1"
    subject: str = ""
    type: str = ""
    thesis: str = ""
    supporting_signal_ids: list = field(default_factory=list)
    contradicting_signal_ids: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    affected_entity_ids: list = field(default_factory=list)
    possible_moat: list = field(default_factory=list)
    falsifiers: list = field(default_factory=list)
    probe_request_ids: list = field(default_factory=list)
    input_root: str = ""
    created_at: str = ""

    def validate(self):
        reasons = []
        _req("opportunity_id", self.opportunity_id, reasons)
        _req("thesis", self.thesis, reasons)
        _req("falsifiers", self.falsifiers or None, reasons)
        if self.type and self.type not in OPPORTUNITY_TYPES:
            reasons.append("bad:type")
        if not self.supporting_signal_ids:
            reasons.append("missing:supporting_signal_ids")
        return (not reasons), reasons


# ── IngestRun ──

@dataclass
class IngestRun:
    run_id: str
    source_id: str = ""
    started_at: str = ""
    finished_at: str = ""
    status: str = "running"
    rows_in: int = 0
    rows_out: int = 0
    quarantined: int = 0
    error: str = ""
    semantic_root: str = ""
    rows_inserted: int = 0
    rows_existing: int = 0

    def validate(self):
        reasons = []
        _req("run_id", self.run_id, reasons)
        _req("source_id", self.source_id, reasons)
        _req("started_at", self.started_at, reasons)
        return (not reasons), reasons


# ── Quarantine ──

@dataclass
class Quarantine:
    quarantine_id: str
    record_type: str = ""
    record_data: object = None
    gate_failures: list = field(default_factory=list)
    quarantined_at: str = ""
    source_id: str = ""
    run_id: str = ""
    stage: str = ""
    failure_code: str = ""
    receipt_id: str = ""
    record_locator: str = ""

    def validate(self):
        reasons = []
        _req("quarantine_id", self.quarantine_id, reasons)
        _req("quarantined_at", self.quarantined_at, reasons)
        if self.stage and self.stage not in ("fetch", "parse", "normalize",
                                             "gate", "store"):
            reasons.append("bad:stage")
        return (not reasons), reasons
