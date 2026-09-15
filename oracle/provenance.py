"""RawEvidenceReceipt v2. Complete provenance record for raw evidence.

DEVINSTRUCT §12. No normalized observation can exist without a receipt.
receipt_id = content hash of receipt semantic fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from oracle import ids


def raw_hash(payload: bytes) -> str:
    """Same payload → same hash. Parser replays from the snapshot, not memory."""
    return ids.sha256_hex(payload)


@dataclass
class RawEvidenceReceipt:
    source_id: str
    source_contract_hash: str
    raw_sha256: str
    receipt_id: str = ""
    raw_uri: str = ""
    byte_length: int = 0
    media_type: str = ""
    compression: str = ""
    fetched_at: str = ""
    request_fingerprint: str = ""
    response_status: int = 0
    snapshot_semantics: str = "FULL"       # FULL / DELTA / STREAM / PARTIAL
    complete: bool = True
    cursor: str = ""
    watermark: str = ""
    adapter_version: str = ""
    parser_version: str = "v1"
    ingest_run_id: str = ""

    def __post_init__(self):
        """Compute receipt_id from semantic fields (immutable after creation)."""
        if not hasattr(self, 'receipt_id') or not self.receipt_id:
            self.receipt_id = ids.record_id("RECEIPT", {
                "source_id": self.source_id,
                "raw_sha256": self.raw_sha256,
                "parser_version": self.parser_version,
                "snapshot_semantics": self.snapshot_semantics,
                "complete": self.complete,
                "fetched_at": self.fetched_at,
            })

    def validate(self):
        reasons = []
        for field_name in ("source_id", "raw_sha256", "parser_version",
                           "snapshot_semantics", "fetched_at"):
            val = getattr(self, field_name)
            if not val or (isinstance(val, str) and not val.strip()):
                reasons.append(f"missing:{field_name}")
        if self.byte_length < 0:
            reasons.append("bad:byte_length:negative")
        return (not reasons), reasons

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "source_id": self.source_id,
            "source_contract_hash": self.source_contract_hash,
            "raw_sha256": self.raw_sha256,
            "raw_uri": self.raw_uri,
            "byte_length": self.byte_length,
            "media_type": self.media_type,
            "compression": self.compression,
            "fetched_at": self.fetched_at,
            "request_fingerprint": self.request_fingerprint,
            "response_status": self.response_status,
            "snapshot_semantics": self.snapshot_semantics,
            "complete": self.complete,
            "cursor": self.cursor,
            "watermark": self.watermark,
            "adapter_version": self.adapter_version,
            "parser_version": self.parser_version,
            "ingest_run_id": self.ingest_run_id,
        }
