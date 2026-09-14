"""Ingest runner. Full pipeline from fetch to staging.

DEVINSTRUCT §21. One run returns IngestRunReceipt. Runs must be replayable.
"""
from __future__ import annotations

import time

from oracle import ids
from oracle.gates import run_gates


def run_ingest(source_id: str, adapter, raw_store, store,
               parser=None, normalizer=None,
               registered_sources: set = None) -> dict:
    """Execute full ingest pipeline for a source.

    Returns IngestRunReceipt with stats.
    """
    from oracle.sources.fetch_result import FetchResult, FetchStatus

    if registered_sources is None:
        registered_sources = {source_id}

    # Begin run
    run_receipt = store.begin_ingest_run(source_id)
    run_id = run_receipt["run_id"]
    stats = {"rows_in": 0, "rows_out": 0, "quarantined": 0, "errors": []}

    try:
        # 1. Fetch
        fetch_result = adapter.fetch()

        if not isinstance(fetch_result, FetchResult):
            stats["errors"].append("adapter.fetch() did not return FetchResult")
            return store.commit_ingest_run(run_id, {
                **stats, "status": "error", "error": "bad_fetch_return"
            })

        if fetch_result.status == FetchStatus.FAILED:
            return store.commit_ingest_run(run_id, {
                **stats, "status": "failed",
                "error": str(fetch_result.error) if fetch_result.error else "fetch_failed"
            })

        # 2. Store raw artifacts
        raw_hashes = []
        for artifact in fetch_result.artifacts:
            if isinstance(artifact, bytes):
                date = time.strftime("%Y-%m-%d", time.gmtime())
                result = raw_store.put(source_id, date, artifact)
                raw_hashes.append(result["raw_sha256"])

        # 3. Parse (if parser provided)
        records = []
        if parser and fetch_result.artifacts:
            for artifact in fetch_result.artifacts:
                try:
                    parsed = parser.parse(artifact, fetch_result)
                    if parsed:
                        records.extend(parsed)
                except Exception as e:
                    stats["errors"].append(f"parse_error: {e}")

        stats["rows_in"] = len(records)

        # 4. Normalize and validate
        observations = []
        quarantined = []
        for record in records:
            if normalizer:
                try:
                    normalized = normalizer.normalize(record)
                except Exception as e:
                    quarantined.append({"record": record, "reason": f"normalize_error: {e}"})
                    continue
            else:
                normalized = record

            # 5. Run gates
            all_passed, gate_results = run_gates(normalized, registered_sources)

            if all_passed:
                store.put_observation(normalized)
                observations.append(normalized)
            else:
                failed_gates = [r.gate_name for r in gate_results if not r.passed]
                quarantined.append({
                    "record": normalized,
                    "reason": f"gates_failed: {failed_gates}"
                })
                store.quarantine(normalized, str(failed_gates))

        stats["rows_out"] = len(observations)
        stats["quarantined"] = len(quarantined)

        # 6. Commit run
        return store.commit_ingest_run(run_id, {
            **stats,
            "status": "completed" if not stats["errors"] else "completed_with_errors",
            "artifacts": len(raw_hashes),
            "raw_hashes": raw_hashes,
            "fetch_status": fetch_result.status.value,
            "cursor": fetch_result.cursor,
            "watermark": fetch_result.watermark,
        })

    except Exception as e:
        stats["errors"].append(f"ingest_error: {e}")
        return store.commit_ingest_run(run_id, {
            **stats, "status": "error", "error": str(e)
        })
