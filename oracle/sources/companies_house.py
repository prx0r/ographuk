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

from oracle.contracts import Source  # noqa: E402


def source_contract() -> Source:
    """Canonical Companies House source contract (fail-closed rights).

    Free Company Data Product + streaming API. OGL reuse allows raw
    retention and derivation; contract hash is bound into every receipt.
    """
    from oracle.normalize.companies_house import PARSER_VERSION

    return Source(
        source_id=SOURCE_ID,
        jurisdiction="GB",
        access="public",
        auth_class="keyless-bulk",
        cost=0.0,
        license="OGL-3.0",
        terms_url="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        commercial_use="ALLOWED",
        raw_storage="ALLOWED",
        redistribution="ALLOWED",
        attribution_required=True,
        personal_data_class="NONE",
        allowed_uses=["ingest", "retain_raw", "derive", "redistribute_derived"],
        prohibited_uses=[],
        cadence="monthly-bulk+streaming",
        entity_keys=["company_number"],
        raw_retention=True,
        adapter=f"{SOURCE_ID}:{ADAPTER_VERSION}",
        parser_version=PARSER_VERSION,
    )

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parent.parent.parent
    / "fixtures" / "companies_house" / "small_snapshot.json"
)


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _file_watermark(path: Path) -> str:
    """Deterministic watermark for a fixture/snapshot file.

    Prefer the snapshot date embedded in official filenames
    (BasicCompanyData-2026-09-01-part1_7.zip → 2026-09-01T00:00:00Z):
    same snapshot → same watermark even if re-downloaded. Fall back to
    the file mtime, then wall-clock.
    """
    import re

    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", path.name)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00Z"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return _utcnow()
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))


def _is_empty_payload(raw: bytes) -> bool:
    """Factual emptiness across formats: blank, `[]`, or header-only ZIP."""
    if not raw.strip() or raw.strip() == b"[]":
        return True
    if raw[:4] == b"PK\x03\x04":
        import io
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for name in z.namelist():
                    if not name.lower().endswith(".csv"):
                        continue
                    with z.open(name) as fh:
                        content = fh.read().strip()
                        # header-only (single line) or blank → empty
                        lines = [ln for ln in content.splitlines() if ln.strip()]
                        if len(lines) > 1:
                            return False
            return True
        except zipfile.BadZipFile:
            return False
    return False


def _first_n_records(raw: bytes, n: int) -> bytes:
    """Slice the first n data records, preserving the artifact format."""
    if raw[:4] == b"PK\x03\x04":
        import csv
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            inner = sorted(n for n in z.namelist()
                           if n.lower().endswith(".csv"))[0]
            text = z.read(inner).decode("utf-8")
        lines = text.splitlines()
        head, body = lines[0], lines[1:1 + n]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(inner, "\n".join([head] + body) + "\n")
        return buf.getvalue()
    import json

    rows = json.loads(raw.decode("utf-8"))
    return json.dumps(rows[:n]).encode("utf-8")


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
        self.artifact_name = self.fixture_path.name
        self._error = error or {"code": "SOURCE_UNREACHABLE", "detail": "simulated outage"}

    def fetch(self) -> FetchResult:
        started = _utcnow()
        watermark = _file_watermark(self.fixture_path)
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
                watermark=watermark,
            )
        raw = self.fixture_path.read_bytes()
        if self.mode == "partial":
            raw = _first_n_records(raw, self.partial_records)
            return FetchResult(
                status=FetchStatus.PARTIAL,
                artifacts=[raw],
                snapshot_semantics=SnapshotSemantics.PARTIAL,
                complete=False,
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
                watermark=watermark,
            )
        # fixture (default): full snapshot semantics
        if _is_empty_payload(raw):
            return FetchResult(
                status=FetchStatus.SUCCESS_EMPTY,
                artifacts=[],
                snapshot_semantics=SnapshotSemantics.FULL,
                complete=True,
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
                watermark=watermark,
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
            watermark=watermark,
        )


class FileArtifact:
    """Path-based artifact for bulk snapshots (review item 5, first step).

    Carries location + metadata instead of bytes. RawStore.put_file()
    hashes while copying; the parser streams rows off the stored copy.
    """

    def __init__(self, path: str | Path, media_type: str = "application/zip"):
        self.path = str(path)
        self.media_type = media_type
        try:
            self.byte_length = Path(path).stat().st_size
        except OSError:
            self.byte_length = 0

    def __repr__(self):
        return f"FileArtifact({self.path}, {self.byte_length} bytes)"


class CompaniesHouseBulkAdapter(SourceAdapter):
    """Live bulk snapshot adapter: local paths of official part ZIPs.

    Artifacts are FileArtifacts (never loaded into memory). Watermark is
    the snapshot date embedded in official filenames.
    """

    source_id = SOURCE_ID
    ADAPTER_VERSION = ADAPTER_VERSION

    def __init__(self, part_paths: list):
        self.part_paths = [str(p) for p in part_paths]
        self.artifact_name = ",".join(Path(p).name for p in self.part_paths)

    def fetch(self) -> FetchResult:
        from oracle.sources.fetch_result import SnapshotSemantics

        started = _utcnow()
        missing = [p for p in self.part_paths if not Path(p).is_file()]
        if missing:
            return FetchResult(
                status=FetchStatus.FAILED,
                artifacts=[],
                snapshot_semantics=SnapshotSemantics.PARTIAL,
                complete=False,
                error={"code": "PARTS_MISSING", "detail": missing},
                source_id=self.source_id,
                adapter_version=ADAPTER_VERSION,
                started_at=started,
                finished_at=_utcnow(),
            )
        watermarks = {_file_watermark(Path(p)) for p in self.part_paths}
        watermark = sorted(watermarks)[0] if len(watermarks) == 1 else started
        return FetchResult(
            status=FetchStatus.SUCCESS,
            artifacts=[FileArtifact(p) for p in self.part_paths],
            snapshot_semantics=SnapshotSemantics.FULL,
            complete=True,
            source_id=self.source_id,
            adapter_version=ADAPTER_VERSION,
            started_at=started,
            finished_at=_utcnow(),
            watermark=watermark,
        )
