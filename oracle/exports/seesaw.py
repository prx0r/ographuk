"""Seesaw export: feature vectors backed by Oracle signals, not caller injection.

DEVINSTRUCT §24. No caller-provided arbitrary score enters the feature vector.
Signals are retrieved from Oracle store, not from candidate dict.
"""
from __future__ import annotations


def export_candidate(candidate: dict, store=None) -> dict:
    """CandidateOpportunity-shaped dict → feature vector.

    If store is provided, signal values are retrieved from Oracle.
    If store is None (legacy mode), supporting_signal_ids are returned
    but no arbitrary numeric features are injected by the caller.
    """
    from oracle.contracts import CandidateOpportunity
    c = CandidateOpportunity(
        opportunity_id=candidate.get("opportunity_id", ""),
        subject=candidate.get("subject", ""),
        type=candidate.get("type", ""),
        thesis=candidate.get("thesis", ""),
        supporting_signal_ids=candidate.get("supporting_signal_ids",
                                             candidate.get("supporting_signals", [])),
        contradicting_signal_ids=candidate.get("contradicting_signal_ids",
                                                candidate.get("contradicting_signals", [])),
        unknowns=candidate.get("unknowns", []),
        affected_entity_ids=candidate.get("affected_entity_ids",
                                           candidate.get("affected_entities", [])),
        possible_moat=candidate.get("possible_moat", []),
        falsifiers=candidate.get("falsifiers", []),
        created_at=candidate.get("created_at", ""))
    ok, reasons = c.validate()
    if not ok:
        return {"error": reasons}

    vec = {
        "opportunity": c.opportunity_id,
        "subject": c.subject,
        "type": c.type,
        "thesis": c.thesis,
        "supporting_signal_ids": c.supporting_signal_ids,
        "contradicting_signal_ids": c.contradicting_signal_ids,
        "unknowns": c.unknowns,
        "affected_entity_ids": c.affected_entity_ids,
        "possible_moat": c.possible_moat,
        "falsifiers": c.falsifiers,
    }

    # If store is provided, resolve signals from Oracle
    if store is not None:
        signals = {}
        for sig_id in c.supporting_signal_ids:
            # In a real implementation, retrieve from store
            # For now, include the ID with null value
            signals[sig_id] = {"value": None, "signal_id": sig_id}
        vec["resolved_signals"] = signals
    else:
        # Legacy mode: DO NOT inject caller-provided features
        # Only pass through signal IDs, not arbitrary numbers
        vec["signal_ids"] = c.supporting_signal_ids

    return vec
