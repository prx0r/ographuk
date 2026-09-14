"""Seesaw export (DEVINSTRUCT §24): feature vectors, not prose.

No Seesaw scoring here — pass through measured fields + unknowns + evidence
refs. Seesaw applies its own economic model.
"""
from __future__ import annotations


def export_candidate(candidate: dict) -> dict:
    """CandidateOpportunity-shaped dict -> feature vector. Binary validation
    first; rejected candidates never export (reasons attached)."""
    from oracle.contracts import CandidateOpportunity
    c = CandidateOpportunity(
        opportunity_id=candidate.get("opportunity_id", ""),
        subject=candidate.get("subject", ""),
        type=candidate.get("type", ""),
        thesis=candidate.get("thesis", ""),
        supporting_signals=candidate.get("supporting_signals", []),
        contradicting_signals=candidate.get("contradicting_signals", []),
        unknowns=candidate.get("unknowns", []),
        affected_entities=candidate.get("affected_entities", []),
        estimated_market_surface=candidate.get("estimated_market_surface", {}),
        possible_moat=candidate.get("possible_moat", []),
        suggested_probe=candidate.get("suggested_probe", []),
        falsifiers=candidate.get("falsifiers", []),
        created_at=candidate.get("created_at", ""))
    ok, reasons = c.validate()
    if not ok:
        return {"error": reasons}
    vec = {"opportunity": c.opportunity_id, "subject": c.subject,
           "type": c.type, "thesis": c.thesis,
           "supporting_signals": c.supporting_signals,
           "contradicting_signals": c.contradicting_signals,
           "unknowns": c.unknowns,
           "affected_entities": c.affected_entities,
           "estimated_market_surface": c.estimated_market_surface,
           "possible_moat": c.possible_moat,
           "suggested_probe": c.suggested_probe,
           "falsifiers": c.falsifiers}
    feats = candidate.get("features", {})
    if isinstance(feats, dict):
        vec.update({k: v for k, v in feats.items()
                    if isinstance(v, (int, float)) or v is None})
    return vec
