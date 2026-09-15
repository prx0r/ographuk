"""Real schema parity: dataclasses ↔ manifest ↔ actual SQL (review item 8).

Not a hand-written sample: dataclass fields are introspected, and both the
SQLite DDL and the BigQuery DDL file are parsed. Every field-name mismatch
in EITHER direction fails. One schema source of truth, enforced three ways.
"""
import dataclasses
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle import contracts
from oracle.provenance import RawEvidenceReceipt
from oracle.schema_manifest import SCHEMAS
from oracle.sources.fetch_result import FetchResult

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# manifest name → dataclass
DATACLASSES = {
    "Source": contracts.Source,
    "RawObject": contracts.RawObject,
    "Entity": contracts.Entity,
    "Identifier": contracts.Identifier,
    "Relation": contracts.Relation,
    "Observation": contracts.Observation,
    "Event": contracts.Event,
    "Signal": contracts.Signal,
    "Hypothesis": contracts.Hypothesis,
    "Outcome": contracts.Outcome,
    "CandidateOpportunity": contracts.CandidateOpportunity,
    "IngestRun": contracts.IngestRun,
    "Quarantine": contracts.Quarantine,
    "RawEvidenceReceipt": RawEvidenceReceipt,
    "FetchResult": FetchResult,
}

# manifest name → physical table (None = no persisted table by design)
TABLES = {
    "Source": "oracle_sources",
    "RawObject": "oracle_raw_objects",
    "Entity": "oracle_entities",
    "Identifier": "oracle_identifiers",
    "Relation": "oracle_relations",
    "Observation": "oracle_observations",
    "Event": "oracle_events",
    "Signal": "oracle_signals",
    "Hypothesis": "oracle_hypotheses",
    "Outcome": "oracle_outcomes",
    "CandidateOpportunity": "oracle_opportunities",
    "IngestRun": "oracle_ingest_runs",
    "Quarantine": "oracle_quarantine",
    "RawEvidenceReceipt": "oracle_receipts",
    "FetchResult": None,
}

_CONSTRAINT_FIRST = {"primary", "foreign", "check", "unique", "constraint",
                     "key", "index"}


def _parse_tables(ddl: str) -> dict:
    """CREATE TABLE blocks → {table: {columns}}. Both `drop.x` and bare names."""
    tables = {}
    for m in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?"
            r"(?:drop\.)?(\w+)[`\"]?\s*\((.*?)\)\s*"
            r"(?:PARTITION\s+BY\s+[^;]*)?(?:CLUSTER\s+BY\s+[^;]*)?;",
            ddl, re.IGNORECASE | re.DOTALL):
        table, body = m.group(1).lower(), m.group(2)
        cols = set()
        for line in body.splitlines():
            line = line.strip().rstrip(",")
            if not line:
                continue
            first = line.strip("`\"'").split()[0].lower()
            if first in _CONSTRAINT_FIRST:
                continue
            col = re.match(r"^[`\"']?(\w+)[`\"']?\s+(\w+)", line)
            if col:
                cols.add(col.group(1).lower())
        tables[table] = cols
    return tables


def _load_sql() -> dict:
    from oracle.store.sqlite import DDL as SQLITE_DDL

    with open(os.path.join(REPO, "schemas", "001_oracle_core.sql")) as f:
        bq = _parse_tables(f.read())
    lite = _parse_tables(SQLITE_DDL)
    merged = {}
    for table in set(bq) | set(lite):
        merged[table] = (bq.get(table, set()), lite.get(table, set()))
    return merged


class TestRealParity:
    def test_every_manifest_has_a_dataclass(self):
        missing = [k for k in SCHEMAS if k not in DATACLASSES]
        assert not missing, f"manifest without dataclass: {missing}"

    def test_dataclass_fields_match_manifest(self):
        problems = []
        for name, cls in DATACLASSES.items():
            dc_fields = {f.name for f in dataclasses.fields(cls)}
            manifest_fields = set(SCHEMAS[name].keys())
            for f in sorted(manifest_fields - dc_fields):
                problems.append(f"in_manifest_not_dataclass:{name}.{f}")
            for f in sorted(dc_fields - manifest_fields):
                problems.append(f"in_dataclass_not_manifest:{name}.{f}")
        assert not problems, problems

    def test_manifest_matches_both_sql_backends(self):
        sql = _load_sql()
        problems = []
        for name, table in TABLES.items():
            if table is None:
                continue
            bq_cols, lite_cols = sql.get(table, (set(), set()))
            if not bq_cols and not lite_cols:
                problems.append(f"missing_table:{table}")
                continue
            manifest_cols = {c.lower() for c in SCHEMAS[name]}
            for cols, backend in ((bq_cols, "bq"), (lite_cols, "sqlite")):
                for c in sorted(manifest_cols - cols):
                    problems.append(f"in_manifest_not_{backend}:{table}.{c}")
                for c in sorted(cols - manifest_cols):
                    problems.append(f"in_{backend}_not_manifest:{table}.{c}")
        assert not problems, problems

    def test_backends_agree_with_each_other(self):
        sql = _load_sql()
        problems = []
        for table, (bq_cols, lite_cols) in sorted(sql.items()):
            if table.startswith("sqlite_"):
                continue
            for c in sorted(bq_cols - lite_cols):
                problems.append(f"in_bq_not_sqlite:{table}.{c}")
            for c in sorted(lite_cols - bq_cols):
                problems.append(f"in_sqlite_not_bq:{table}.{c}")
        assert not problems, problems
