"""Ingest runner. Full pipeline from fetch to staging.

DEVINSTRUCT §21. One run returns IngestRunReceipt. Runs must be replayable.

Pipeline per artifact:
  policy preflight → fetch → RawStore.put → RawEvidenceReceipt →
  store.put_receipt → parser.parse → CanonicalBatch → commit each
  category (entities, identifiers, observations, relations, events) →
  gates → store/quarantine → semantic_root → run receipt.

Every failure stage (fetch, parse, normalize, gate) persists a structured
quarantine entry or a failed run receipt. Nothing is only logged.
"""

from __future__ import annotations

import inspect
import time

from oracle import ids
from oracle.batch import CanonicalBatch


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _commit_chunk(store, batch, receipts_by_id, receipt, stats,
                  _quarantine, registered_sources,
                  sample_observations, sampled_companies) -> list:
    """Gate + store one chunk. Returns chunk record IDs for the run root."""
    from oracle.gates import run_gates

    for reject in batch.rejects:
        _quarantine(reject, reject.get("reason", "parse_error"),
                    stage="parse",
                    failure_code=reject.get("failure_code", "parse_error"),
                    receipt_id=receipt.receipt_id,
                    record_locator=reject.get("record_locator", ""))
    for entity in batch.entities:
        try:
            store.put_entity(entity)
            stats["entities_stored"] += 1
        except Exception as e:
            stats["errors"].append(f"entity_store_error: {e}")
    for ident in batch.identifiers:
        try:
            store.put_identifier(ident)
        except Exception as e:
            stats["errors"].append(f"identifier_store_error: {e}")
    chunk_ids = [e["entity_id"] for e in batch.entities
                 if isinstance(e, dict) and e.get("entity_id")]
    for record in batch.observations:
        stats["observations_derived"] += 1
        all_passed, gate_results = run_gates(
            record, registered_sources, receipts=receipts_by_id)
        if not all_passed:
            failed = [r.gate_name for r in gate_results if not r.passed]
            _quarantine(record, f"gates_failed: {failed}", stage="gate",
                        failure_code=f"gates_failed:{','.join(failed)}",
                        receipt_id=record.get("raw_receipt_id", ""),
                        record_locator=record.get("record_locator", ""))
            continue
        if sampled_companies < sample_observations:
            res = store.put_observation(record)
            chunk_ids.append(record["observation_id"])
            stats["observations_stored"] += 1
            if res.get("inserted"):
                stats["inserted"] += 1
            else:
                stats["already_present"] += 1
        else:
            stats["observations_sampled_out"] += 1
    return chunk_ids


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _call_parser(parser, artifact: bytes, fetch_result, receipt,
                 artifact_name: str):
    """Call parser.parse with receipt context if it accepts it."""
    try:
        sig = inspect.signature(parser.parse)
        params = list(sig.parameters.keys())
    except (TypeError, ValueError):
        return parser.parse(artifact, fetch_result)
    kwargs = {}
    if "receipt" in params:
        kwargs["receipt"] = receipt
    if "artifact_name" in params:
        kwargs["artifact_name"] = artifact_name
    return parser.parse(artifact, fetch_result, **kwargs)


def _split_envelope(item):
    """Legacy envelope → (entities, identifiers, observations, error).

    Preferred parser output is CanonicalBatch; this keeps backward
    compatibility with envelope-dict parsers.
    """
    if not isinstance(item, dict):
        return [], [], [], {"reason": "parse_error:record-not-dict"}
    if "_error" in item:
        err = item["_error"]
        if isinstance(err, dict):
            return [], [], [], err
        return [], [], [], {"reason": str(err)}
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
        return entities, identifiers, observations, None
    return [], [], [item], None


def _to_batch(parsed) -> CanonicalBatch:
    if isinstance(parsed, CanonicalBatch):
        return parsed
    batch = CanonicalBatch()
    items = parsed if isinstance(parsed, list) else [parsed]
    for item in items:
        entities, identifiers, observations, error = _split_envelope(item)
        batch.entities.extend(entities)
        batch.identifiers.extend(identifiers)
        batch.observations.extend(observations)
        if error is not None:
            err = dict(error)
            err.setdefault("stage", "parse")
            err.setdefault("failure_code", err.get("reason", "parse_error"))
            batch.rejects.append(err)
    return batch


def run_ingest(source_id: str, adapter, raw_store, store,
               parser=None, normalizer=None,
               registered_sources: set = None, registry=None) -> dict:
    """Execute full ingest pipeline for a source.

    registry: optional SourceRegistry. When provided, ingestion requires a
    registered source contract and passes a preflight PolicyDecision; the
    contract hash is bound into every receipt. When omitted, the legacy
    registered_sources set (default {source_id}) is used with an empty
    contract hash.
    """
    from oracle.gates import run_gates
    from oracle.provenance import RawEvidenceReceipt
    from oracle.sources.fetch_result import FetchResult, FetchStatus

    contract_hash = ""
    if registry is not None:
        policy = registry.policy_check(source_id)
        if not policy.get("allowed"):
            run_receipt = store.begin_ingest_run(source_id)
            final = {"rows_in": 0, "rows_out": 0, "quarantined": 0,
                     "errors": [], "status": "denied",
                     "error": f"source_policy_denied:{policy.get('reasons')}"}
            return {**final, **store.commit_ingest_run(
                run_receipt["run_id"], final)}
        contract_hash = policy["contract_hash"]
        registered_sources = {source_id}
        try:
            store.put_source(registry.get(source_id)["source"].to_dict())
        except Exception as e:
            stats_boot = {"rows_in": 0, "rows_out": 0, "quarantined": 0,
                          "errors": [f"source_store_error: {e}"],
                          "inserted": 0, "already_present": 0}
            _run = store.begin_ingest_run(source_id)
            final = {**stats_boot, "status": "error",
                     "error": f"source_store_error: {e}"}
            return {**final, **store.commit_ingest_run(_run["run_id"], final)}
    if registered_sources is None:
        registered_sources = {source_id}

    # Begin run
    run_receipt = store.begin_ingest_run(source_id)
    run_id = run_receipt["run_id"]
    stats = {"rows_in": 0, "rows_out": 0, "quarantined": 0, "errors": [],
             "inserted": 0, "already_present": 0}

    def _quarantine(record, reason, *, stage, failure_code,
                    receipt_id="", record_locator=""):
        stats["quarantined"] += 1
        try:
            store.quarantine(
                record if isinstance(record, dict) else {"value": str(record)},
                str(reason),
                {"stage": stage, "failure_code": failure_code,
                 "run_id": run_id, "receipt_id": receipt_id,
                 "record_locator": record_locator},
            )
        except Exception as e:
            stats["errors"].append(f"quarantine_error: {e}")

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
                     "error": str(fetch_result.error) if fetch_result.error
                     else "fetch_failed"}
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
                source_contract_hash=contract_hash,
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
            try:
                store.put_raw_object({
                    "raw_sha256": raw_sha,
                    "source_id": source_id,
                    "raw_uri": "",
                    "byte_length": put["byte_length"],
                    "media_type": "application/json",
                    "parser_version": parser_version,
                    "ingested_at": fetched_at,
                })
            except Exception as e:
                stats["errors"].append(f"raw_object_store_error: {e}")
            staged.append((artifact, receipt, receipt.to_dict()))
            raw_hashes.append(raw_sha)
            receipt_ids.append(receipt.receipt_id)

        # 3. Parse (per artifact, with receipt context) → CanonicalBatch
        batch = CanonicalBatch()
        artifact_name = getattr(adapter, "artifact_name", "artifact")
        for artifact, receipt, rdict in staged:
            if parser is None:
                continue
            try:
                parsed = _call_parser(parser, artifact, fetch_result, receipt,
                                      artifact_name)
            except Exception as e:
                _quarantine(
                    {"artifact_sha": rdict["raw_sha256"],
                     "source_id": source_id},
                    f"parse_error: {e}", stage="parse",
                    failure_code="parse_error:exception",
                    receipt_id=rdict["receipt_id"])
                stats["errors"].append(f"parse_error: {e}")
                continue
            if parsed:
                sub = _to_batch(parsed)
                batch.entities.extend(sub.entities)
                batch.identifiers.extend(sub.identifiers)
                batch.observations.extend(sub.observations)
                batch.relations.extend(sub.relations)
                batch.events.extend(sub.events)
                batch.rejects.extend(sub.rejects)

        stats["rows_in"] = (len(batch.observations) + len(batch.rejects)
                            + len(batch.relations) + len(batch.events))

        receipts_by_id = {r["receipt_id"]: r for _, _, r in staged}

        # 3b. Parser-level rejects → quarantine (stage=parse)
        for reject in batch.rejects:
            _quarantine(
                reject, reject.get("reason", "parse_error"),
                stage="parse",
                failure_code=reject.get("failure_code", "parse_error"),
                receipt_id="",
                record_locator=reject.get("record_locator", ""))

        # 4. Commit entities + identifiers (mutable projections, REPLACE ok)
        for entity in batch.entities:
            try:
                store.put_entity(entity)
            except Exception as e:
                stats["errors"].append(f"entity_store_error: {e}")
        for ident in batch.identifiers:
            try:
                store.put_identifier(ident)
            except Exception as e:
                stats["errors"].append(f"identifier_store_error: {e}")

        # 5. Gate + commit observations (append-only facts)
        derived_ids = list(batch.record_ids())
        for record in batch.observations:
            if normalizer:
                try:
                    record = normalizer.normalize(record)
                except Exception as e:
                    _quarantine(record, f"normalize_error: {e}",
                                stage="normalize",
                                failure_code="normalize_error:exception",
                                receipt_id=record.get("raw_receipt_id", ""),
                                record_locator=record.get("record_locator", ""))
                    continue
            all_passed, gate_results = run_gates(
                record, registered_sources, receipts=receipts_by_id)
            if all_passed:
                res = store.put_observation(record)
                if res.get("inserted"):
                    stats["inserted"] += 1
                else:
                    stats["already_present"] += 1
            else:
                failed_gates = [r.gate_name for r in gate_results if not r.passed]
                _quarantine(record, f"gates_failed: {failed_gates}",
                            stage="gate",
                            failure_code=f"gates_failed:{','.join(failed_gates)}",
                            receipt_id=record.get("raw_receipt_id", ""),
                            record_locator=record.get("record_locator", ""))

        # 6. Relations + events (append-only; no gates in E1)
        for relation in batch.relations:
            try:
                store.put_relation(relation)
            except Exception as e:
                stats["errors"].append(f"relation_store_error: {e}")
        for event in batch.events:
            try:
                store.put_event(event)
            except Exception as e:
                stats["errors"].append(f"event_store_error: {e}")

        stats["rows_out"] = stats["inserted"] + stats["already_present"]
        semantic_root = ids.semantic_root(derived_ids) if derived_ids else ""

        # 7. Commit run (merge stats into the returned receipt)
        final_stats = {
            **stats,
            "status": "completed" if not stats["errors"] else "completed_with_errors",
            "artifacts": len(raw_hashes),
            "raw_hashes": raw_hashes,
            "receipt_ids": receipt_ids,
            "semantic_root": semantic_root,
            "fetch_status": fetch_result.status.value,
            "cursor": fetch_result.cursor,
            "watermark": fetch_result.watermark,
        }
        committed = store.commit_ingest_run(run_id, final_stats)
        return {**final_stats, **committed}

    except Exception as e:
        stats["errors"].append(f"ingest_error: {e}")
        final = {**stats, "status": "error", "error": str(e),
                 "semantic_root": ""}
        try:
            return {**final, **store.commit_ingest_run(run_id, final)}
        except Exception:
            return final


def run_bulk_ingest(source_id: str, adapter, raw_store, store,
                    parser=None, registry=None,
                    chunk_rows: int = 5000,
                    sample_observations: int = 2000,
                    quarantine_cap: int = 1000) -> dict:
    """Stream a bulk snapshot (multi-GB ZIP parts) with bounded memory.

    Per file: hash-while-copy → receipt → stream chunks → gate every
    observation → store ALL entities + the first `sample_observations`
    companies' observations (bounded queryable proof) → chunk roots →
    run root (streaming Merkle-style: sha over ordered chunk roots).

    Storage budget is explicit: full observation history for millions of
    companies belongs in BigQuery (bq adapter), not local SQLite.
    """
    import hashlib

    from oracle.gates import run_gates
    from oracle.provenance import RawEvidenceReceipt
    from oracle.sources.fetch_result import FetchResult, FetchStatus

    contract_hash = ""
    if registry is not None:
        policy = registry.policy_check(source_id)
        if not policy.get("allowed"):
            run_receipt = store.begin_ingest_run(source_id)
            final = {"rows_in": 0, "rows_out": 0, "quarantined": 0,
                     "errors": [], "status": "denied",
                     "error": f"source_policy_denied:{policy.get('reasons')}"}
            return {**final, **store.commit_ingest_run(
                run_receipt["run_id"], final)}
        contract_hash = policy["contract_hash"]
        try:
            store.put_source(registry.get(source_id)["source"].to_dict())
        except Exception as e:
            _run = store.begin_ingest_run(source_id)
            final = {"rows_in": 0, "rows_out": 0, "quarantined": 0,
                     "errors": [f"source_store_error: {e}"],
                     "inserted": 0, "already_present": 0,
                     "status": "error", "error": f"source_store_error: {e}"}
            return {**final, **store.commit_ingest_run(_run["run_id"], final)}
    registered_sources = {source_id}

    run_receipt = store.begin_ingest_run(source_id)
    run_id = run_receipt["run_id"]
    stats = {"rows_in": 0, "rows_out": 0, "quarantined": 0, "errors": [],
             "inserted": 0, "already_present": 0,
             "entities_stored": 0, "observations_derived": 0,
             "observations_stored": 0, "observations_sampled_out": 0,
             "quarantine_capped": 0, "chunks": 0}
    chunk_roots = []
    sampled_companies = 0

    def _quarantine(record, reason, *, stage, failure_code,
                    receipt_id="", record_locator=""):
        if stats["quarantined"] < quarantine_cap:
            try:
                store.quarantine(
                    record if isinstance(record, dict) else {"value": str(record)},
                    str(reason),
                    {"stage": stage, "failure_code": failure_code,
                     "run_id": run_id, "receipt_id": receipt_id,
                     "record_locator": record_locator},
                )
            except Exception as e:
                stats["errors"].append(f"quarantine_error: {e}")
        else:
            stats["quarantine_capped"] += 1
        stats["quarantined"] += 1

    try:
        fetch_result = adapter.fetch()
        if not isinstance(fetch_result, FetchResult):
            final = {**stats, "status": "error", "error": "bad_fetch_return"}
            return {**final, **store.commit_ingest_run(run_id, final)}
        ok, reasons = fetch_result.validate()
        if not ok:
            final = {**stats, "status": "error",
                     "error": f"bad_fetch_result:{reasons}"}
            return {**final, **store.commit_ingest_run(run_id, final)}
        if fetch_result.status == FetchStatus.FAILED:
            final = {**stats, "status": "failed",
                     "error": str(fetch_result.error) if fetch_result.error
                     else "fetch_failed"}
            return {**final, **store.commit_ingest_run(run_id, final)}

        fetched_at = fetch_result.watermark or _utcnow()
        parser_version = getattr(parser, "PARSER_VERSION", None) or "v1"
        raw_hashes, receipt_ids = [], []

        for artifact in fetch_result.artifacts:
            src_path = getattr(artifact, "path", None)
            if not src_path:
                stats["errors"].append("bulk_artifact_not_a_file:skipped")
                continue
            from pathlib import Path as _P

            artifact_name = _P(src_path).name
            date = (fetched_at[:10] if len(fetched_at) >= 10
                    else _utcnow()[:10])
            # Parse from the STORED copy: replay reads RawStore, not the
            # download location.
            put = raw_store.put_file(source_id, date, src_path)
            raw_sha = put["raw_sha256"]
            receipt = RawEvidenceReceipt(
                source_id=source_id,
                source_contract_hash=contract_hash,
                raw_sha256=raw_sha,
                byte_length=put["byte_length"],
                media_type=getattr(artifact, "media_type", "application/zip"),
                fetched_at=fetched_at,
                snapshot_semantics=fetch_result.snapshot_semantics.value,
                complete=fetch_result.complete,
                cursor=fetch_result.cursor,
                watermark=fetch_result.watermark,
                adapter_version=getattr(adapter, "ADAPTER_VERSION", ""),
                parser_version=parser_version,
                ingest_run_id=run_id,
            )
            store.put_receipt(receipt.to_dict())
            store.put_raw_object({
                "raw_sha256": raw_sha, "source_id": source_id,
                "raw_uri": "", "byte_length": put["byte_length"],
                "media_type": getattr(artifact, "media_type",
                                      "application/zip"),
                "parser_version": parser_version, "ingested_at": fetched_at,
            })
            raw_hashes.append(raw_sha)
            receipt_ids.append(receipt.receipt_id)
            receipts_by_id = {receipt.receipt_id: receipt.to_dict()}

            for batch in parser.iter_batches(
                    put["path"], receipt_id=receipt.receipt_id,
                    raw_sha256=raw_sha, observed_at=fetched_at,
                    artifact_name=artifact_name, chunk_rows=chunk_rows):
                stats["chunks"] += 1
                store_ctx = (store.batch() if hasattr(store, "batch")
                             else _nullcontext())
                with store_ctx:
                    chunk_ids = _commit_chunk(
                        store, batch, receipts_by_id, receipt, stats,
                        _quarantine, registered_sources,
                        sample_observations, sampled_companies)
                sampled_companies += len(batch.entities)
                stats["rows_in"] += (len(batch.observations)
                                     + len(batch.rejects))
                if chunk_ids:
                    chunk_roots.append(ids.semantic_root(chunk_ids))

        run_root = ("ROOT:" + hashlib.sha256(
            "\n".join(chunk_roots).encode("utf-8")).hexdigest()
            if chunk_roots else "")
        stats["rows_out"] = stats["inserted"] + stats["already_present"]
        final_stats = {
            **stats,
            "status": "completed" if not stats["errors"] else "completed_with_errors",
            "artifacts": len(raw_hashes),
            "raw_hashes": raw_hashes,
            "receipt_ids": receipt_ids,
            "semantic_root": run_root,
            "fetch_status": fetch_result.status.value,
            "cursor": fetch_result.cursor,
            "watermark": fetch_result.watermark,
        }
        committed = store.commit_ingest_run(run_id, final_stats)
        return {**final_stats, **committed}
    except Exception as e:
        stats["errors"].append(f"ingest_error: {e}")
        final = {**stats, "status": "error", "error": str(e),
                 "semantic_root": ""}
        try:
            return {**final, **store.commit_ingest_run(run_id, final)}
        except Exception:
            return final
