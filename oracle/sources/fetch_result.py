"""FetchResult: Source adapter return type. Replaces the old fetch → [] pattern.

DEVINSTRUCT §9: FAILED ≠ SUCCESS_EMPTY. Source outage is UNKNOWN.
Empty data is factual. They cannot share representation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FetchStatus(str, Enum):
    SUCCESS = "SUCCESS"
    SUCCESS_EMPTY = "SUCCESS_EMPTY"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SnapshotSemantics(str, Enum):
    FULL = "FULL"
    DELTA = "DELTA"
    STREAM = "STREAM"
    PARTIAL = "PARTIAL"


@dataclass
class FetchResult:
    """Structured return from every source adapter.

    A source returning [] with status=200 is SUCCESS_EMPTY.
    A source returning [] because it is down is FAILED.
    A stream that disconnects early is PARTIAL.
    """
    status: FetchStatus
    artifacts: list = field(default_factory=list)   # list of raw byte payloads
    cursor: str = ""                                # for streaming/-pagination
    watermark: str = ""                             # latest timestamp in source
    snapshot_semantics: SnapshotSemantics = SnapshotSemantics.FULL
    complete: bool = True                           # false if partial/interrupted
    error: dict = None                              # structured error details
    source_id: str = ""
    adapter_version: str = ""
    started_at: str = ""
    finished_at: str = ""

    @property
    def is_success(self) -> bool:
        return self.status in (FetchStatus.SUCCESS, FetchStatus.SUCCESS_EMPTY)

    @property
    def has_data(self) -> bool:
        return bool(self.artifacts)

    def validate(self):
        reasons = []
        if not isinstance(self.status, FetchStatus):
            reasons.append("bad:status:not-FetchStatus")
        if not isinstance(self.snapshot_semantics, SnapshotSemantics):
            reasons.append("bad:snapshot_semantics:not-SnapshotSemantics")
        if self.status == FetchStatus.PARTIAL and self.complete:
            reasons.append("partial:but:complete=true")
        if self.status == FetchStatus.FAILED and self.complete:
            reasons.append("failed:but:complete=true")
        return (not reasons), reasons
