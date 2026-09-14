"""Quarantine gates. Every observation passes gates before promotion.

DEVINSTRUCT §20. Failure → quarantine. Never silently discard.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GateResult:
    gate_name: str
    passed: bool
    reason: str = ""

    def to_dict(self):
        return {"gate": self.gate_name, "passed": self.passed,
                "reason": self.reason}


def gate_source_registered(source_id: str, registered_sources: set) -> GateResult:
    ok = source_id in registered_sources
    return GateResult("SOURCE_REGISTERED", ok,
                      "" if ok else f"source {source_id!r} not registered")


def gate_raw_hash_valid(raw_sha256: str) -> GateResult:
    ok = bool(raw_sha256) and len(raw_sha256) == 64 and all(
        c in "0123456789abcdef" for c in raw_sha256
    )
    return GateResult("RAW_HASH_VALID", ok,
                      "" if ok else "raw_sha256 invalid format")


def gate_raw_receipt_valid(receipt: dict) -> GateResult:
    required = ("source_id", "raw_sha256", "parser_version",
                "snapshot_semantics", "fetched_at")
    missing = [f for f in required if not receipt.get(f)]
    ok = not missing
    return GateResult("RAW_RECEIPT_VALID", ok,
                      "" if ok else f"missing receipt fields: {missing}")


def gate_provenance_complete(observation: dict) -> GateResult:
    required = ("raw_receipt_id", "record_locator", "observed_at", "source_id")
    missing = [f for f in required if not observation.get(f)]
    ok = not missing
    return GateResult("PROVENANCE_COMPLETE", ok,
                      "" if ok else f"missing provenance: {missing}")


def gate_identity_valid(entity_id: str) -> GateResult:
    ok = bool(entity_id) and ":" in entity_id
    return GateResult("IDENTITY_VALID", ok,
                      "" if ok else "entity_id missing type: prefix")


def gate_temporal_valid(observation: dict) -> GateResult:
    observed_at = observation.get("observed_at", "")
    ok = bool(observed_at) and len(observed_at) >= 10
    return GateResult("TEMPORAL_FIELDS_VALID", ok,
                      "" if ok else "observed_at missing or too short")


def gate_observation_status_valid(status: str) -> GateResult:
    from oracle.contracts import OBS_STATUSES
    ok = status in OBS_STATUSES
    return GateResult("OBSERVATION_STATUS_VALID", ok,
                      "" if ok else f"bad status: {status!r}")


def gate_confidence_range(confidence) -> GateResult:
    if confidence is None:
        return GateResult("CONFIDENCE_RANGE", True)
    try:
        v = float(confidence)
        ok = 0.0 <= v <= 1.0
        return GateResult("CONFIDENCE_RANGE", ok,
                          "" if ok else f"confidence {v} out of [0,1]")
    except (TypeError, ValueError):
        return GateResult("CONFIDENCE_RANGE", False,
                          f"confidence not numeric: {confidence!r}")


# Full default gate sequence
DEFAULT_GATES = [
    gate_source_registered,
    gate_raw_hash_valid,
    gate_raw_receipt_valid,
    gate_provenance_complete,
    gate_identity_valid,
    gate_temporal_valid,
    gate_observation_status_valid,
    gate_confidence_range,
]


def run_gates(observation: dict, registered_sources: set,
              gates=None) -> tuple[bool, list[GateResult]]:
    """Run all gates. Returns (all_passed, results)."""
    if gates is None:
        gates = DEFAULT_GATES

    results = []
    source_id = observation.get("source_id", "")

    for gate in gates:
        if gate is gate_source_registered:
            r = gate(source_id, registered_sources)
        elif gate is gate_raw_hash_valid:
            r = gate(observation.get("raw_receipt_id", ""))
        elif gate is gate_raw_receipt_valid:
            r = gate(observation)
        elif gate is gate_provenance_complete:
            r = gate(observation)
        elif gate is gate_identity_valid:
            r = gate(observation.get("subject_entity_id", ""))
        elif gate is gate_temporal_valid:
            r = gate(observation)
        elif gate is gate_observation_status_valid:
            r = gate(observation.get("status", ""))
        elif gate is gate_confidence_range:
            r = gate(observation.get("confidence"))
        else:
            continue
        results.append(r)
        if not r.passed:
            # Continue checking but record all failures
            pass

    all_passed = all(r.passed for r in results)
    return all_passed, results
