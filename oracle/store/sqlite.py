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
    from_entity_id TEXT NOT NULL,
    to_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence_refs TEXT DEFAULT '[]',
    confidence REAL,
    lineage_root TEXT DEFAULT '',
    valid_from TEXT DEFAULT '',
    valid_to TEXT DEFAULT '',
    PRIMARY KEY (from_entity_id, to_entity_id, relation_type)
);
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
    error TEXT
);
CREATE TABLE IF NOT EXISTS oracle_quarantine (
    quarantine_id TEXT PRIMARY KEY,
    record_type TEXT NOT NULL,
    record_data TEXT NOT NULL,
    gate_failures TEXT DEFAULT '[]',
    quarantined_at TEXT NOT NULL,
    source_id TEXT DEFAULT '',
    run_id TEXT DEFAULT ''
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
        if isinstance(obj, str):
            return obj
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
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_relations
               (from_entity_id, to_entity_id, relation_type,
                evidence_refs, confidence, lineage_root,
                valid_from, valid_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (relation["from_entity_id"], relation["to_entity_id"],
             relation["relation_type"],
             self._json(relation.get("evidence_refs", [])),
             relation.get("confidence"),
             relation.get("lineage_root", ""),
             relation.get("valid_from", ""),
             relation.get("valid_to", ""))
        )
        self.conn.commit()
        return {"stored": f"{relation['from_entity_id']}→{relation['to_entity_id']}"}

    def put_observation(self, observation: dict) -> dict:
        oid = observation.get("observation_id") or ids.record_id("OBS", observation)
        observation["observation_id"] = oid
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_observations
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
        return {"observation_id": oid, "stored": True}

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

    def put_event(self, event: dict) -> dict:
        eid = event.get("event_id") or ids.record_id("EVT", event)
        event["event_id"] = eid
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_events
               (event_id, event_type, subject, observed_at,
                payload, triggering_observation_ids)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (eid, event["event_type"], event.get("subject", ""),
             event.get("observed_at", ""),
             self._json(event.get("payload", {})),
             self._json(event.get("triggering_observation_ids", [])))
        )
        self.conn.commit()
        return {"event_id": eid, "stored": True}

    def put_signal(self, signal: dict) -> dict:
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_signals
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
        return {"stored": signal["signal_id"]}

    def put_hypothesis(self, hypothesis: dict) -> dict:
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_hypotheses
               (hypothesis_id, thesis, supporting, contradicting, falsifiers)
               VALUES (?, ?, ?, ?, ?)""",
            (hypothesis["hypothesis_id"], hypothesis.get("thesis", ""),
             self._json(hypothesis.get("supporting", [])),
             self._json(hypothesis.get("contradicting", [])),
             self._json(hypothesis.get("falsifiers", [])))
        )
        self.conn.commit()
        return {"stored": hypothesis["hypothesis_id"]}

    def put_outcome(self, outcome: dict) -> dict:
        self.conn.execute(
            """INSERT OR REPLACE INTO oracle_outcomes
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
        return {"stored": outcome["outcome_id"]}

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
                   rows_out = ?, quarantined = ?, error = ?
               WHERE run_id = ?""",
            (now, stats.get("status", "completed"),
             stats.get("rows_in", 0), stats.get("rows_out", 0),
             stats.get("quarantined", 0), stats.get("error"),
             run_id)
        )
        self.conn.commit()
        return {"run_id": run_id, "finished_at": now}

    def quarantine(self, record: dict, reason: str) -> dict:
        qid = ids.record_id("Q", {"record": record, "reason": reason})
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.conn.execute(
            """INSERT INTO oracle_quarantine
               (quarantine_id, record_type, record_data,
                gate_failures, quarantined_at, source_id, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (qid, type(record).__name__, self._json(record),
             self._json([reason]), now,
             record.get("source_id", ""),
             record.get("run_id", ""))
        )
        self.conn.commit()
        return {"quarantine_id": qid, "quarantined_at": now}

    def close(self):
        self.conn.close()
