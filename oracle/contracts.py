"""E0 contracts: schemas-as-code for the 10 Oracle objects (DEVINSTRUCT §34 E0).

source, raw object, entity, identifier, relation, observation, event, signal,
hypothesis, outcome — plus CandidateOpportunity (§23). Validation is binary:
valid or rejected with reasons (no scores at the gate layer).
"""
from __future__ import annotations

from dataclasses import dataclass, field


SOURCE_CLASSES = {"primary-government", "primary-commercial", "secondary",
                  "user", "model-derived"}
OBS_STATUSES = {"OBSERVED", "INVALID", "SUPERSEDED"}
GRADES = {"HYPOTHESIS", "SUPPORTED", "QUANTIFIED", "VALIDATED"}
OPPORTUNITY_TYPES = {"BUSINESS", "PLUGIN", "TRADE", "AD", "PRODUCT"}


def _req(name, value, reasons):
    if value is None or (isinstance(value, str) and not value.strip()):
        reasons.append("missing:" + name)
        return False
    return True


@dataclass
class Source:
    source_id: str
    jurisdiction: str = "GB"
    access: str = ""
    auth_class: str = ""
    cost: float = 0.0
    license: str = ""
    allowed_uses: list = field(default_factory=list)
    prohibited_uses: list = field(default_factory=list)
    cadence: str = ""
    entity_keys: list = field(default_factory=list)
    raw_retention: bool = True
    adapter: str = ""
    parser_version: str = "v1"

    def validate(self):
        reasons = []
        _req("source_id", self.source_id, reasons)
        _req("license", self.license, reasons)
        return (not reasons), reasons


@dataclass
class RawObject:
    raw_sha256: str
    source_id: str
    raw_uri: str = ""
    parser_version: str = "v1"

    def validate(self):
        reasons = []
        _req("raw_sha256", self.raw_sha256, reasons)
        _req("source_id", self.source_id, reasons)
        return (not reasons), reasons


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


@dataclass
class Relation:
    source_id: str
    target_id: str
    rel_type: str
    valid_from: str = ""
    valid_to: str = ""

    def validate(self):
        reasons = []
        _req("source_id", self.source_id, reasons)
        _req("target_id", self.target_id, reasons)
        _req("rel_type", self.rel_type, reasons)
        if self.rel_type != self.rel_type.upper().replace(" ", "_"):
            reasons.append("rel_type:not-upper-snake")
        return (not reasons), reasons


@dataclass
class Observation:
    subject: str
    predicate: str
    value: object = None
    source: str = ""
    source_class: str = ""
    observed_at: str = ""
    valid_from: str = ""
    valid_to: str = ""
    ingested_at: str = ""
    raw_sha256: str = ""
    status: str = "OBSERVED"
    confidence: object = None
    basis: str = ""

    def validate(self):
        reasons = []
        _req("subject", self.subject, reasons)
        _req("predicate", self.predicate, reasons)
        _req("source", self.source, reasons)
        _req("raw_sha256", self.raw_sha256, reasons)
        if self.source_class and self.source_class not in SOURCE_CLASSES:
            reasons.append("bad:source_class")
        if self.status not in OBS_STATUSES:
            reasons.append("bad:status")
        if self.confidence is not None and not isinstance(self.confidence, (int, float)):
            reasons.append("bad:confidence")
        return (not reasons), reasons


@dataclass
class Event:
    event_type: str
    subject: str = ""
    observed_at: str = ""
    payload: dict = field(default_factory=dict)

    def validate(self):
        reasons = []
        _req("event_type", self.event_type, reasons)
        return (not reasons), reasons


@dataclass
class Signal:
    signal_id: str
    formula_id: str
    formula_version: str = "v1"
    inputs: list = field(default_factory=list)
    value: object = None
    computed_at: str = ""

    def validate(self):
        reasons = []
        _req("signal_id", self.signal_id, reasons)
        _req("formula_id", self.formula_id, reasons)
        _req("inputs", self.inputs or None, reasons)
        return (not reasons), reasons


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


@dataclass
class Outcome:
    subject: str
    action: str = ""
    metrics: dict = field(default_factory=dict)
    observed_at: str = ""

    def validate(self):
        reasons = []
        _req("subject", self.subject, reasons)
        _req("action", self.action, reasons)
        return (not reasons), reasons


@dataclass
class CandidateOpportunity:
    opportunity_id: str
    subject: str = ""
    type: str = ""
    thesis: str = ""
    supporting_signals: list = field(default_factory=list)
    contradicting_signals: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    affected_entities: list = field(default_factory=list)
    estimated_market_surface: dict = field(default_factory=dict)
    possible_moat: list = field(default_factory=list)
    suggested_probe: list = field(default_factory=list)
    falsifiers: list = field(default_factory=list)
    created_at: str = ""

    def validate(self):
        reasons = []
        _req("opportunity_id", self.opportunity_id, reasons)
        _req("thesis", self.thesis, reasons)
        _req("falsifiers", self.falsifiers or None, reasons)
        if self.type and self.type not in OPPORTUNITY_TYPES:
            reasons.append("bad:type")
        return (not reasons), reasons
