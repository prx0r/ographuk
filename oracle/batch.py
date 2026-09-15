"""CanonicalBatch: the typed parser → runner boundary (E1).

Every source parser emits CanonicalBatch; the ingest runner validates and
commits each category. Replaces the assumption that every parser record is
an observation.

Rejects carry the structured failure context needed to persist a
quarantine entry and replay it later:
  stage (parse|normalize|gate), failure_code, record_locator, reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CanonicalBatch:
    entities: list = field(default_factory=list)
    identifiers: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    relations: list = field(default_factory=list)
    events: list = field(default_factory=list)
    rejects: list = field(default_factory=list)

    def counts(self) -> dict:
        return {
            "entities": len(self.entities),
            "identifiers": len(self.identifiers),
            "observations": len(self.observations),
            "relations": len(self.relations),
            "events": len(self.events),
            "rejects": len(self.rejects),
        }

    def record_ids(self) -> list[str]:
        """Canonical output record IDs covered by the run semantic root."""
        out = []
        for o in self.observations:
            if isinstance(o, dict) and o.get("observation_id"):
                out.append(o["observation_id"])
        for e in self.entities:
            if isinstance(e, dict) and e.get("entity_id"):
                out.append(e["entity_id"])
        return out
