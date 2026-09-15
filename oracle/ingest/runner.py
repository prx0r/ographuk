"""Ingest runner. Full pipeline from fetch to staging.

DEVINSTRUCT §21. One run returns IngestRunReceipt. Runs must be replayable.

Pipeline per artifact:
  fetch → RawStore.put → RawEvidenceReceipt → store.put_receipt
        → parser.parse → entities → observations → gates → store/quarantine

Parser envelope convention: parser.parse() may return a mix of
  {"entity": {...}, "observations": [...]}  (preferred: entity + obs bundle)
  {"entities": [...], "observations": [...]}
  {observation...}                            (plain gate-ready observation)
  {"_error": {...}}                           (per-record parse failure)
Plain dicts without an "observations" key are treated as observations.
"""

from __future__ import annotations

import inspect
import time


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _call_parser(parser, artifact: bytes, fetch_result, receipt):
    """Call parser.parse with receipt context if it accepts it."""
    try:
        sig = inspect.signature(parser.parse)
        params = list(sig.parameters.keys())
    except (TypeError, ValueError):
        return parser.parse(artifact, fetch_result)
    if "receipt" in params:
        return parser.parse(artifact, fetch_result, receipt)
    return parser.parse(artifact, fetch_result)


def _split_envelope(item):
    """Split one parser output item → (entities, observations, record_error).

    Returns (entities: list, observations: list, error: dict|None).
    """
    if not isinstance(item, dict):
        return [], [], {"reason": "parse_error:record-not-dict"}, []
    if "_error" in item:
        err = item["_error"]
        if isinstance(err, dict):
            return [], [], err, []
        return [], [], {"reason": str(err)}, []
    if "observations" in item and isinstance(item["observations"], list):
        entities = []
        if isinstance(item.get("entity"), dict):
            entities.append(item["entity"])
        if isinstance(item.get("entities"), list):
            entities.extend(e for e in item["entities"] if isinstance(e, dict))
        identifiers = []
        if isinstance(item.get("identifiers"), list):
            identifiers = [d for d in item["identifiers"] if isinstance(d, dict)]
        observations = [o for o in item["observations"] if isinstance(o, dict)]
        return entities, observations, None, identifiers
    return [], [item], None, []


def run_ingest(source_id: str, adapter, raw_store, store,
               parser=None, normalizer=None,
               registered_sources: set = None) -> dict:
    """Execute full ingest pipeline for a source.

    Returns IngestRunReceipt with stats.
    """
    from oracle.provenance import RawEvidenceReceipt
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
            final = {**stats, "status": "error", "error": "bad_fetch_return"}
            return {**final, **store.commit_ingest_run(run_id, final)}

        ok, reasons = fetch_result.validate()
        if not ok:
            stats["errors"].append(f"invalid FetchResult: {reasons}")
            final = {**stats, "status": "error",
                     "error": f"bad_fetch_result:{reasons}"}
            return {**final, **store.commit_ingest_run(run_id, final)}

        if fetch_result.status == FetchStatus.FAILED:
            final = {**stats, "status": "failed",
                     "error": str(fetch_result.error) if fetch_result.error else "fetch_failed"}
            return {**final, **store.commit_ingest_run(run_id, final)}

        # 2. Store raw artifacts + mint receipts (provenance first)
        staged = []  # [(artifact_bytes, receipt, receipt_dict)]
        raw_hashes, receipt_ids = [], []
        fetched_at = fetch_result.watermark or _utcnow()
        parser_version = getattr(parser, "PARSER_VERSION", None) or "v1"
        for artifact in fetch_result.artifacts:
            if not isinstance(artifact, bytes):
                stats["errors"].append("artifact_not_bytes:skipped")
                continue
            date = time.strftime("%Y-%m-%d", time.gmtime())
            put = raw_store.put(source_id, date, artifact)
            raw_sha = put["raw_sha256"]
            receipt = RawEvidenceReceipt(
                source_id=source_id,
                source_contract_hash="",
                raw_sha256=raw_sha,
                byte_length=put["byte_length"],
                media_type="application/json",
                fetched_at=fetched_at,
                snapshot_semantics=fetch_result.snapshot_semantics.value,
                complete=fetch_result.complete,
                cursor=fetch_result.cursor,
                watermark=fetch_result.watermark,
                adapter_version=getattr(adapter, "ADAPTER_VERSION", "")
                or getattr(adapter, "adapter_version", ""),
                parser_version=parser_version,
                ingest_run_id=run_id,
            )
            store.put_receipt(receipt.to_dict())
            staged.append((artifact, receipt, receipt.to_dict()))
            raw_hashes.append(raw_sha)
            receipt_ids.append(receipt.receipt_id)

        # 3. Parse (per artifact, with receipt context)
        items = []
        for artifact, receipt, _rdict in staged:
            if parser is None:
                continue
            try:
                parsed = _call_parser(parser, artifact, fetch_result, receipt)
            except Exception as e:
                stats["errors"].append(f"parse_error: {e}")
                continue
            if parsed:
                items.extend(parsed if isinstance(parsed, list) else [parsed])

        stats["rows_in"] = len(items)

        # 4. Expand envelopes → entities + observations; store entities
        observations = []
        quarantined = []
        receipts_by_id = {}
        for _a, _r, rdict in staged:
            receipts_by_id[rdict["receipt_id"]] = rdict

        def _quarantine(record, reason):
            quarantined.append({"record": record, "reason": reason})
            try:
                store.quarantine(
                    record if isinstance(record, dict) else {"value": str(record)},
                    str(reason),
                )
            except Exception as e:
                stats["errors"].append(f"quarantine_error: {e}")

        for item in items:
            entities, obs_list, record_error, identifiers = _split_envelope(item)
            if record_error is not None:
                _quarantine(item, record_error.get("reason", "parse_error"))
                continue
            for entity in entities:
                try:
                    store.put_entity(entity)
                except Exception as e:
                    stats["errors"].append(f"entity_store_error: {e}")
            for ident in identifiers:
                try:
                    store.put_identifier(ident)
                except Exception as e:
                    stats["errors"].append(f"identifier_store_error: {e}")
            for record in obs_list:
                # 5. Optional legacy normalizer hook
                if normalizer:
                    try:
                        record = normalizer.normalize(record)
                    except Exception as e:
                        _quarantine(record, f"normalize_error: {e}")
                        continue

                # 6. Run gates (receipt-aware)
                all_passed, gate_results = run_gates_lazy(
                    record, registered_sources, receipts_by_id)

                if all_passed:
                    store.put_observation(record)
                    observations.append(record)
                else:
                    failed_gates = [r.gate_name for r in gate_results if not r.passed]
                    _quarantine(record, f"gates_failed: {failed_gates}")

        stats["rows_out"] = len(observations)
        stats["quarantined"] = len(quarantined)

        # 7. Commit run (merge stats into the returned receipt)
        final_stats = {
            **stats,
            "status": "completed" if not stats["errors"] else "completed_with_errors",
            "artifacts": len(raw_hashes),
            "raw_hashes": raw_hashes,
            "receipt_ids": receipt_ids,
            "fetch_status": fetch_result.status.value,
            "cursor": fetch_result.cursor,
            "watermark": fetch_result.watermark,
        }
        committed = store.commit_ingest_run(run_id, final_stats)
        return {**final_stats, **committed}

    except Exception as e:
        stats["errors"].append(f"ingest_error: {e}")
        final = {**stats, "status": "error", "error": str(e)}
        try:
            return {**final, **store.commit_ingest_run(run_id, final)}
        except Exception:
            return final


def run_gates_lazy(observation: dict, registered_sources: set,
                   receipts: dict | None):
    from oracle.gates import run_gates

    return run_gates(observation, registered_sources, receipts=receipts)
