"""SourceRegistry v2 (DEVINSTRUCT §11): executable source config + adapter interface."""
from __future__ import annotations

from oracle import ids
from oracle.contracts import Source  # noqa: E402


class SourceAdapter:
    """Every adapter implements fetch() -> FetchResult.

    Fetch failure is FetchStatus.FAILED (outage = UNKNOWN), never [].
    Empty source data is FetchStatus.SUCCESS_EMPTY (factual emptiness).
    Raw bytes are hashed downstream; adapters never invent observations.
    """

    source_id = ""

    def fetch(self):  # -> FetchResult
        raise NotImplementedError


def contract_hash(source: Source) -> str:
    """Stable hash of the canonical source contract. Bound into receipts."""
    return ids.sha256_hex(ids.canonical(source.to_dict()))


class SourceRegistry:
    def __init__(self):
        self._sources = {}

    def register(self, source: Source, adapter: SourceAdapter | None = None):
        ok, reasons = source.validate()
        if not ok:
            return {"error": reasons}
        self._sources[source.source_id] = {"source": source, "adapter": adapter}
        return {"registered": source.source_id}

    def get(self, source_id: str):
        return self._sources.get(source_id)

    def list(self):
        return sorted(self._sources)

    def policy_check(self, source_id: str) -> dict:
        """Preflight PolicyDecision: can fetch / retain raw / derive.

        Fail closed: unknown source, invalid contract, or rights that
        forbid retention-with-ingest all deny.
        """
        entry = self._sources.get(source_id)
        if entry is None:
            return {"allowed": False, "reasons": ["source_not_registered"],
                    "contract_hash": ""}
        source = entry["source"]
        ok, reasons = source.validate()
        if not ok:
            return {"allowed": False, "reasons": reasons, "contract_hash": ""}
        denials = []
        if source.raw_retention and source.raw_storage not in ("ALLOWED", "LIMITED"):
            denials.append("raw_retention_forbidden")
        if source.commercial_use == "FORBIDDEN":
            denials.append("commercial_use_forbidden")
        if denials:
            return {"allowed": False, "reasons": denials, "contract_hash": ""}
        return {
            "allowed": True,
            "reasons": [],
            "contract_hash": contract_hash(source),
            "can_fetch": True,
            "can_retain_raw": True,
            "can_derive": True,
            "can_redistribute": source.redistribution in ("ALLOWED", "LIMITED"),
        }
