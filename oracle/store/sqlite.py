"""SQLite backend for OracleStore. Stdlib only.

DEVINSTRUCT §18. Fast local backend. Same semantic tests as BQ adapter.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from oracle import ids
from oracle.store.base import OracleStore


DDL = """
CREATE TABLE IF NOT EXISTS oracle_entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    country TEXT DEFAULT 'GB',
    canonical_name TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_identifiers (
    entity_id TEXT NOT NULL,
    id_type TEXT NOT NULL,
    id_value TEXT NOT NULL,
    PRIMARY KEY (entity_id, id_type, id_value)
);
CREATE TABLE IF NOT EXISTS oracle_relations (
    relation_id TEXT PRIMARY KEY,
    from_entity_id TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence_refs TEXT DEFAULT '[]',
    confidence REAL,
    lineage_root TEXT DEFAULT '',
    valid_from TEXT DEFAULT '',
    valid_to TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_relations_edge ON oracle_relations
    (from_entity_id, to_entity_id, relation_type);
CREATE TABLE IF NOT EXISTS oracle_observations (
    observation_id TEXT PRIMARY KEY,
    subject_entity_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    value TEXT,
    value_type TEXT DEFAULT 'string',
    source_id TEXT NOT NULL,
    source_class TEXT DEFAULT '',
    raw_receipt_id TEXT NOT NULL,
    record_locator TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    valid_from TEXT DEFAULT '',
    valid_to TEXT DEFAULT '',
    ingested_at TEXT DEFAULT '',
    parser_version TEXT DEFAULT '',
    normalizer_version TEXT DEFAULT '',
    status TEXT DEFAULT 'OBSERVED',
    confidence REAL,
    lineage_root TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    subject TEXT DEFAULT '',
    observed_at TEXT NOT NULL,
    ingested_at TEXT DEFAULT '',
    payload TEXT DEFAULT '{}',
    triggering_observation_ids TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS oracle_signals (
    signal_id TEXT PRIMARY KEY,
    formula_id TEXT NOT NULL,
    formula_version TEXT DEFAULT 'v1',
    input_ids TEXT DEFAULT '[]',
    value REAL,
    computed_at TEXT NOT NULL,
    code_hash TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    thesis TEXT DEFAULT '',
    supporting TEXT DEFAULT '[]',
    contradicting TEXT DEFAULT '[]',
    falsifiers TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS oracle_outcomes (
    outcome_id TEXT PRIMARY KEY,
    opportunity_id TEXT DEFAULT '',
    campaign_id TEXT DEFAULT '',
    action TEXT NOT NULL,
    metrics TEXT DEFAULT '{}',
    evidence_refs TEXT DEFAULT '[]',
    qp_receipt_ids TEXT DEFAULT '[]',
    observed_at TEXT NOT NULL,
    verification_status TEXT DEFAULT 'UNVERIFIED'
);
CREATE TABLE IF NOT EXISTS oracle_ingest_runs (
    run_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT DEFAULT 'running',
    rows_in INTEGER DEFAULT 0,
    rows_out INTEGER DEFAULT 0,
    quarantined INTEGER DEFAULT 0,
    error TEXT,
    semantic_root TEXT DEFAULT '',
    rows_inserted INTEGER DEFAULT 0,
    rows_existing INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS oracle_quarantine (
    quarantine_id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    record_data TEXT NOT NULL,
    gate_failures TEXT DEFAULT '[]',
    quarantined_at TEXT NOT NULL,
    source_id TEXT DEFAULT '',
    run_id TEXT DEFAULT '',
    stage TEXT DEFAULT '',
    failure_code TEXT DEFAULT '',
    receipt_id TEXT DEFAULT '',
    record_locator TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_opportunities (
    opportunity_id TEXT PRIMARY KEY,
    detector_id TEXT DEFAULT '',
    detector_version TEXT DEFAULT 'v1',
    subject TEXT DEFAULT '',
    type TEXT DEFAULT '',
    thesis TEXT DEFAULT '',
    supporting_signal_ids TEXT DEFAULT '[]',
    contradicting_signal_ids TEXT DEFAULT '[]',
    unknowns TEXT DEFAULT '[]',
    affected_entity_ids TEXT DEFAULT '[]',
    possible_moat TEXT DEFAULT '[]',
    falsifiers TEXT DEFAULT '[]',
    probe_request_ids TEXT DEFAULT '[]',
    input_root TEXT DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_receipts (
    receipt_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_contract_hash TEXT DEFAULT '',
    raw_sha256 TEXT NOT NULL,
    raw_uri TEXT DEFAULT '',
    byte_length INTEGER DEFAULT 0,
    media_type TEXT DEFAULT '',
    compression TEXT DEFAULT '',
    fetched_at TEXT NOT NULL,
    request_fingerprint TEXT DEFAULT '',
    response_status INTEGER DEFAULT 0,
    snapshot_semantics TEXT DEFAULT 'FULL',
    complete INTEGER DEFAULT 1,
    cursor TEXT DEFAULT '',
    watermark TEXT DEFAULT '',
    adapter_version TEXT DEFAULT '',
    parser_version TEXT DEFAULT 'v1',
    ingest_run_id TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_sources (
    source_id TEXT PRIMARY KEY,
    jurisdiction TEXT DEFAULT 'GB',
    access TEXT DEFAULT '',
    auth_class TEXT DEFAULT '',
    cost REAL DEFAULT 0,
    license TEXT DEFAULT '',
    terms_url TEXT DEFAULT '',
    terms_hash TEXT DEFAULT '',
    commercial_use TEXT DEFAULT 'UNKNOWN',
    raw_storage TEXT DEFAULT 'UNKNOWN',
    redistribution TEXT DEFAULT 'UNKNOWN',
    attribution_required INTEGER DEFAULT 0,
    personal_data_class TEXT DEFAULT 'NONE',
    allowed_uses TEXT DEFAULT '[]',
    prohibited_uses TEXT DEFAULT '[]',
    cadence TEXT DEFAULT '',
    entity_keys TEXT DEFAULT '[]',
    raw_retention INTEGER DEFAULT 1,
    adapter TEXT DEFAULT '',
    parser_version TEXT DEFAULT 'v1',
    last_success TEXT DEFAULT '',
    cursor TEXT DEFAULT '',
    schema_hash TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS oracle_raw_objects (
    raw_sha256 TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    raw_uri TEXT DEFAULT '',
    byte_length INTEGER DEFAULT 0,
    media_type TEXT DEFAULT '',
    parser_version TEXT DEFAULT 'v1',
    ingested_at TEXT DEFAULT ''
);
"""


class SqliteStore(OracleStore):
    """SQLite-backed OracleStore. Stdlib only."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(DDL)
        self.conn.commit()

    def _json(self, obj) -> str:
        # Always valid JSON: strings are quoted ("active", not active) so the
        # value column round-trips through _unjson and matches BQ JSON type.
        if obj is None:
            return "null"
        return json.dumps(obj, default=str)

    def _unjson(self, s):
        if s is None:
            return None
        try:
            return json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return s

    def put_entity(self, entity: dict) -> dict:
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_entities
               (entity_id, entity_type, country, canonical_name, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entity["entity_id"], entity.get("entity_type", ""),
             entity.get("country", "GB"), entity.get("canonical_name", ""),
             entity.get("status", "active"), entity.get("created_at", ""))
        )
        self.conn.commit()
        return {"stored": entity["entity_id"]}

    def get_entity(self, entity_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_entities WHERE entity_id = ?", (entity_id,))
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def put_identifier(self, identifier: dict) -> dict:
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_identifiers
               (entity_id, id_type, id_value) VALUES (?, ?, ?)""",
            (identifier["entity_id"], identifier["id_type"],
             identifier["id_value"])
        )
        self.conn.commit()
        return {"stored": f"{identifier['id_type']}:{identifier['id_value']}"}

    def put_relation(self, relation: dict) -> dict:
        from oracle import ids as _ids

        rid = relation.get("relation_id") or _ids.relation_assertion_id(
            relation["from_entity_id"], relation["to_entity_id"],
            relation["relation_type"], relation.get("valid_from", ""),
            relation.get("valid_to", ""), relation.get("evidence_refs", []))
        relation["relation_id"] = rid
        # Append-only: same assertion re-ingested is a no-op, never a
        # destructive REPLACE of earlier history.
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_relations
               (relation_id, from_entity_id, to_entity_id, relation_type,
                evidence_refs, confidence, lineage_root,
                valid_from, valid_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rid, relation["from_entity_id"], relation["to_entity_id"],
             relation["relation_type"],
             self._json(relation.get("evidence_refs", [])),
             relation.get("confidence"),
             relation.get("lineage_root", ""),
             relation.get("valid_from", ""),
             relation.get("valid_to", ""))
        )
        self.conn.commit()
        return {"stored": rid, "inserted": cur.rowcount == 1}

    def put_observation(self, observation: dict) -> dict:
        # Append-only immutable fact: content ID assigned upstream by the
        # parser (ids.observation_id over frozen semantic fields). Re-ingest
        # is INSERT OR IGNORE — 0 new rows, identical semantic root.
        oid = observation.get("observation_id") or ids.record_id("OBS", observation)
        observation["observation_id"] = oid
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_observations
               (observation_id, subject_entity_id, predicate, value, value_type,
                source_id, source_class, raw_receipt_id, record_locator,
                observed_at, valid_from, valid_to, ingested_at,
                parser_version, normalizer_version, status, confidence, lineage_root)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (oid, observation["subject_entity_id"], observation["predicate"],
             self._json(observation.get("value")),
             observation.get("value_type", "string"),
             observation["source_id"],
             observation.get("source_class", ""),
             observation.get("raw_receipt_id", ""),
             observation.get("record_locator", ""),
             observation.get("observed_at", ""),
             observation.get("valid_from", ""),
             observation.get("valid_to", ""),
             observation.get("ingested_at", ""),
             observation.get("parser_version", ""),
             observation.get("normalizer_version", ""),
             observation.get("status", "OBSERVED"),
              observation.get("confidence"),
              observation.get("lineage_root", ""))
        )
        self.conn.commit()
        return {"observation_id": oid, "stored": True,
                "inserted": cur.rowcount == 1}

    def get_observations(self, subject_entity_id: str,
                         predicate: str = None) -> list[dict]:
        if predicate:
            cur = self.conn.execute(
                "SELECT * FROM oracle_observations WHERE subject_entity_id = ? AND predicate = ?",
                (subject_entity_id, predicate))
        else:
            cur = self.conn.execute(
                "SELECT * FROM oracle_observations WHERE subject_entity_id = ?",
                (subject_entity_id,))
        return [dict(row) for row in cur.fetchall()]

    def get_observation(self, observation_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_observations WHERE observation_id = ?",
            (observation_id,))
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def count_observations(self) -> int:
        cur = self.conn.execute("SELECT COUNT(*) AS n FROM oracle_observations")
        return int(cur.fetchone()["n"])

    def put_receipt(self, receipt: dict) -> dict:
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_receipts
               (receipt_id, source_id, source_contract_hash, raw_sha256,
                raw_uri, byte_length, media_type, compression, fetched_at,
                request_fingerprint, response_status, snapshot_semantics,
                complete, cursor, watermark, adapter_version, parser_version,
                ingest_run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (receipt["receipt_id"], receipt.get("source_id", ""),
             receipt.get("source_contract_hash", ""),
             receipt.get("raw_sha256", ""), receipt.get("raw_uri", ""),
             receipt.get("byte_length", 0), receipt.get("media_type", ""),
             receipt.get("compression", ""), receipt.get("fetched_at", ""),
             receipt.get("request_fingerprint", ""),
             receipt.get("response_status", 0),
             receipt.get("snapshot_semantics", "FULL"),
             1 if receipt.get("complete", True) else 0,
             receipt.get("cursor", ""), receipt.get("watermark", ""),
             receipt.get("adapter_version", ""),
             receipt.get("parser_version", "v1"),
             receipt.get("ingest_run_id", ""))
        )
        self.conn.commit()
        return {"stored": receipt["receipt_id"]}

    def get_receipt(self, receipt_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_receipts WHERE receipt_id = ?",
            (receipt_id,))
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["complete"] = bool(d.get("complete", 1))
        return d

    def put_event(self, event: dict) -> dict:
        eid = event.get("event_id") or ids.event_id(
            event.get("event_type", ""), event.get("subject", ""),
            event.get("triggering_observation_ids", []))
        event["event_id"] = eid
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_events
               (event_id, event_type, subject, observed_at, ingested_at,
                payload, triggering_observation_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (eid, event["event_type"], event.get("subject", ""),
             event.get("observed_at", ""),
             event.get("ingested_at", "") or time.strftime(
                 "%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             self._json(event.get("payload", {})),
             self._json(event.get("triggering_observation_ids", [])))
        )
        self.conn.commit()
        return {"event_id": eid, "stored": True, "inserted": cur.rowcount == 1}

    def put_signal(self, signal: dict) -> dict:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_signals
               (signal_id, formula_id, formula_version, input_ids,
                value, computed_at, code_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (signal["signal_id"], signal["formula_id"],
             signal.get("formula_version", "v1"),
             self._json(signal.get("input_ids", [])),
             signal.get("value"),
              signal.get("computed_at", ""),
              signal.get("code_hash", ""))
        )
        self.conn.commit()
        return {"stored": signal["signal_id"], "inserted": cur.rowcount == 1}

    def put_hypothesis(self, hypothesis: dict) -> dict:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_hypotheses
               (hypothesis_id, thesis, supporting, contradicting, falsifiers)
               VALUES (?, ?, ?, ?, ?)""",
            (hypothesis["hypothesis_id"], hypothesis.get("thesis", ""),
             self._json(hypothesis.get("supporting", [])),
              self._json(hypothesis.get("contradicting", [])),
              self._json(hypothesis.get("falsifiers", [])))
        )
        self.conn.commit()
        return {"stored": hypothesis["hypothesis_id"],
                "inserted": cur.rowcount == 1}

    def put_outcome(self, outcome: dict) -> dict:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_outcomes
               (outcome_id, opportunity_id, campaign_id, action,
                metrics, evidence_refs, qp_receipt_ids,
                observed_at, verification_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (outcome["outcome_id"], outcome.get("opportunity_id", ""),
             outcome.get("campaign_id", ""),
             outcome["action"],
             self._json(outcome.get("metrics", {})),
             self._json(outcome.get("evidence_refs", [])),
             self._json(outcome.get("qp_receipt_ids", [])),
              outcome.get("observed_at", ""),
              outcome.get("verification_status", "UNVERIFIED"))
        )
        self.conn.commit()
        return {"stored": outcome["outcome_id"], "inserted": cur.rowcount == 1}

    def put_opportunity(self, opportunity: dict) -> dict:
        """Append-only decision-facing artifact (E9 primitive)."""
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_opportunities
               (opportunity_id, detector_id, detector_version, subject, type,
                thesis, supporting_signal_ids, contradicting_signal_ids,
                unknowns, affected_entity_ids, possible_moat, falsifiers,
                probe_request_ids, input_root, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (opportunity["opportunity_id"],
             opportunity.get("detector_id", ""),
             opportunity.get("detector_version", "v1"),
             opportunity.get("subject", ""), opportunity.get("type", ""),
             opportunity.get("thesis", ""),
             self._json(opportunity.get("supporting_signal_ids", [])),
             self._json(opportunity.get("contradicting_signal_ids", [])),
             self._json(opportunity.get("unknowns", [])),
             self._json(opportunity.get("affected_entity_ids", [])),
             self._json(opportunity.get("possible_moat", [])),
             self._json(opportunity.get("falsifiers", [])),
             self._json(opportunity.get("probe_request_ids", [])),
             opportunity.get("input_root", ""),
             opportunity.get("created_at", ""))
        )
        self.conn.commit()
        return {"stored": opportunity["opportunity_id"],
                "inserted": cur.rowcount == 1}

    def get_opportunity(self, opportunity_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_opportunities WHERE opportunity_id = ?",
            (opportunity_id,))
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def begin_ingest_run(self, source_id: str) -> dict:
        run_id = ids.record_id("RUN", {"source": source_id, "ts": time.time()})
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            """INSERT INTO oracle_ingest_runs
               (run_id, source_id, started_at, status)
               VALUES (?, ?, ?, 'running')""",
            (run_id, source_id, now)
        )
        self.conn.commit()
        return {"run_id": run_id, "source_id": source_id, "started_at": now}

    def commit_ingest_run(self, run_id: str, stats: dict) -> dict:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            """UPDATE oracle_ingest_runs
               SET finished_at = ?, status = ?, rows_in = ?,
                   rows_out = ?, quarantined = ?, error = ?,
                   semantic_root = ?, rows_inserted = ?, rows_existing = ?
               WHERE run_id = ?""",
            (now, stats.get("status", "completed"),
             stats.get("rows_in", 0), stats.get("rows_out", 0),
             stats.get("quarantined", 0), stats.get("error"),
             stats.get("semantic_root", ""),
             stats.get("inserted", 0), stats.get("already_present", 0),
             run_id)
        )
        self.conn.commit()
        return {"run_id": run_id, "finished_at": now}

    def quarantine(self, record: dict, reason: str,
                   context: dict | None = None) -> dict:
        """Structured quarantine entry. Idempotent: same failure re-ingested
        is a no-op (INSERT OR IGNORE on the deterministic quarantine_id)."""
        ctx = context or {}
        stage = ctx.get("stage", "")
        failure_code = ctx.get("failure_code", reason)
        qid = ids.record_id("Q", {
            "record": record,
            "reason": reason,
            "stage": stage,
            "failure_code": failure_code,
        })
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_quarantine
               (quarantine_id, record_type, record_data,
                gate_failures, quarantined_at, source_id, run_id,
                stage, failure_code, receipt_id, record_locator)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (qid, type(record).__name__, self._json(record),
             self._json([reason]), now,
             record.get("source_id", "") if isinstance(record, dict) else "",
             ctx.get("run_id", "") or (record.get("run_id", "")
                                       if isinstance(record, dict) else ""),
             stage, failure_code,
             ctx.get("receipt_id", ""),
             ctx.get("record_locator", "") or (
                 record.get("record_locator", "")
                 if isinstance(record, dict) else ""))
        )
        self.conn.commit()
        return {"quarantine_id": qid, "quarantined_at": now,
                "inserted": cur.rowcount == 1}

    def get_ingest_run(self, run_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_ingest_runs WHERE run_id = ?", (run_id,))
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def put_source(self, source: dict) -> dict:
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO oracle_sources
               (source_id, jurisdiction, access, auth_class, cost, license,
                terms_url, terms_hash, commercial_use, raw_storage,
                redistribution, attribution_required, personal_data_class,
                allowed_uses, prohibited_uses, cadence, entity_keys,
                raw_retention, adapter, parser_version, last_success,
                cursor, schema_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source["source_id"], source.get("jurisdiction", "GB"),
             source.get("access", ""), source.get("auth_class", ""),
             source.get("cost", 0.0), source.get("license", ""),
             source.get("terms_url", ""), source.get("terms_hash", ""),
             source.get("commercial_use", "UNKNOWN"),
             source.get("raw_storage", "UNKNOWN"),
             source.get("redistribution", "UNKNOWN"),
             1 if source.get("attribution_required", False) else 0,
             source.get("personal_data_class", "NONE"),
             self._json(source.get("allowed_uses", [])),
             self._json(source.get("prohibited_uses", [])),
             source.get("cadence", ""),
             self._json(source.get("entity_keys", [])),
             1 if source.get("raw_retention", True) else 0,
             source.get("adapter", ""), source.get("parser_version", "v1"),
             source.get("last_success", ""), source.get("cursor", ""),
             source.get("schema_hash", ""))
        )
        self.conn.commit()
        return {"stored": source["source_id"],
                "inserted": cur.rowcount == 1}

    def get_source(self, source_id: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_sources WHERE source_id = ?", (source_id,))
        row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        d["attribution_required"] = bool(d.get("attribution_required", 0))
        d["raw_retention"] = bool(d.get("raw_retention", 1))
        return d

    def put_raw_object(self, raw_object: dict) -> dict:
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO oracle_raw_objects
               (raw_sha256, source_id, raw_uri, byte_length, media_type,
                parser_version, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (raw_object["raw_sha256"], raw_object.get("source_id", ""),
             raw_object.get("raw_uri", ""),
             raw_object.get("byte_length", 0),
             raw_object.get("media_type", ""),
             raw_object.get("parser_version", "v1"),
             raw_object.get("ingested_at", "") or time.strftime(
                 "%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        )
        self.conn.commit()
        return {"stored": raw_object["raw_sha256"],
                "inserted": cur.rowcount == 1}

    def get_raw_object(self, raw_sha256: str) -> dict | None:
        cur = self.conn.execute(
            "SELECT * FROM oracle_raw_objects WHERE raw_sha256 = ?",
            (raw_sha256,))
        row = cur.fetchone()
        return dict(row) if row is not None else None

    def close(self):
        self.conn.close()
