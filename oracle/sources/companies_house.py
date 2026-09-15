"""Companies House source adapter (E1/E2).

Fixture-backed adapter implementing the FetchResult contract
(DEVINSTRUCT §9): FAILED ≠ SUCCESS_EMPTY ≠ PARTIAL. Never returns bare [].
"""

from __future__ import annotations

import time
from pathlib import Path

from oracle.sources.fetch_result import FetchResult, FetchStatus, SnapshotSemantics
from oracle.sources.registry import SourceAdapter

SOURCE_ID = "companies-house"
ADAPTER_VERSION = "ch-adapter-v1"

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures" / "companies_house" / "small_snapshot.json"
)


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class CompaniesHouseAdapter(SourceAdapter):
    """Fixture-backed Companies House adapter.

    mode:
      fixture — read fixture_path bytes → SUCCESS
      empty   — SUCCESS_EMPTY, no artifacts (factual emptiness)
      failed  — FAILED, complete=False (outage is UNKNOWN, not empty)
      partial — PARTIAL, first `partial_records` rows, complete=False
    """

    source_id = SOURCE_ID
    ADAPTER_VERSION = ADAPTER_VERSION

    def __init__(
        self,
        fixture_path: str | Path | None = None,
        mode: str = "fixture",
        partial_records: int = 3,
        error: dict | None = None,
    ):
        self.fixture_path = Path(fixture_path) if fixture_path else DEFAULT_FIXTURE
        self.mode = mode
        self.partial_records = partial_records
        self._error = error or {"code": "SOURCE_UNREACHABLE", "detail": "simulated outage"}

    def fetch(self) -> FetchResult:
        started = _utcnow()
        if self.mode == "failed":
            return FetchResult(
                status=FetchStatus.FAILED,
                artifacts=[],
                snapshot_semantics=SnapshotSemantics.PARTIAL,
                complete=False,
                error=self._error,
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
            )
        if self.mode == "empty":
            return FetchResult(
                status=FetchStatus.SUCCESS_EMPTY,
                artifacts=[],
                snapshot_semantics=SnapshotSemantics.FULL,
                complete=True,
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
                watermark=started,
            )
        raw = self.fixture_path.read_bytes()
        if self.mode == "partial":
            import json

            rows = json.loads(raw.decode("utf-8"))
            raw = json.dumps(rows[: self.partial_records]).encode("utf-8")
            return FetchResult(
                status=FetchStatus.PARTIAL,
                artifacts=[raw],
                snapshot_semantics=SnapshotSemantics.PARTIAL,
                complete=False,
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
                watermark=started,
            )
        # fixture (default): full snapshot semantics
        if not raw.strip() or raw.strip() == b"[]":
            return FetchResult(
                status=FetchStatus.SUCCESS_EMPTY,
                artifacts=[],
                snapshot_semantics=SnapshotSemantics.FULL,
                complete=True,
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
                watermark=started,
            )
        return FetchResult(
            status=FetchStatus.SUCCESS,
            artifacts=[raw],
            snapshot_semantics=SnapshotSemantics.FULL,
            complete=True,
            source_id=self.source_id,
            adapter_version=ADAPTER_VERSION,
            started_at=started,
            finished_at=_utcnow(),
            watermark=started,
        )
