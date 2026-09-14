"""SourceRegistry v2 (DEVINSTRUCT §11): executable source config + adapter interface."""
from __future__ import annotations

from oracle.contracts import Source  # noqa: E402


class SourceAdapter:
    """Every adapter implements fetch() -> list of (payload_bytes, format).
    Fetch fails -> [] (never raise). Raw bytes hashed downstream."""

    source_id = ""

    def fetch(self) -> list:
        raise NotImplementedError


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
