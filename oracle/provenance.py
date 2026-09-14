"""Raw hashing + ingest receipts (DEVINSTRUCT §2 / E1)."""
from . import ids


def raw_hash(payload: bytes) -> str:
    """Same payload -> same hash. Parser replays from the snapshot, not memory."""
    return ids.sha256_hex(payload)


def ingest_receipt(source_id: str, raw_sha256: str, parser_version: str) -> dict:
    return {"source_id": source_id, "raw_sha256": raw_sha256,
            "parser_version": parser_version}
