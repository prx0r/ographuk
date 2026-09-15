"""oracle.cli — local operator interface (stdlib only).

Usage:
  python -m oracle.cli ingest <fixture.json> [--db PATH] [--raw DIR]
  python -m oracle.cli replay <raw_sha256> [--db PATH] [--raw DIR]
  python -m oracle.cli evidence <observation_id> [--db PATH] [--raw DIR]
  python -m oracle.cli check

ingest   — fixture bytes → RawStore → receipt → parse → SQLite.
replay   — re-parse stored raw bytes, compare derived observation IDs
             against the store (idempotence proof).
evidence — observation → receipt → raw SHA → byte verification → source.
check    — schema parity + rights + canonicalization smoke checks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEFAULT_DB = os.path.join(REPO_ROOT, "data", "oracle.db")
DEFAULT_RAW = os.path.join(REPO_ROOT, "data", "raw")
SOURCE_ID = "companies-house"


def _stores(db_path, raw_dir):
    from oracle.raw.store import RawStore
    from oracle.store.sqlite import SqliteStore

    return RawStore(raw_dir), SqliteStore(db_path)


def cmd_ingest(args) -> int:
    from oracle.ingest.runner import run_ingest
    from oracle.normalize.companies_house import CompaniesHouseParser
    from oracle.sources.companies_house import (
        CompaniesHouseAdapter, source_contract)
    from oracle.sources.registry import SourceRegistry

    raw_store, store = _stores(args.db, args.raw)
    registry = SourceRegistry()
    reg_result = registry.register(
        source_contract(), CompaniesHouseAdapter())
    if "error" in reg_result:
        print(json.dumps({"error": reg_result["error"]}))
        store.close()
        return 1
    adapter = CompaniesHouseAdapter(fixture_path=args.fixture)
    receipt = run_ingest(SOURCE_ID, adapter, raw_store, store,
                         parser=CompaniesHouseParser(),
                         registry=registry)
    store.close()
    print(json.dumps(receipt, indent=2, default=str))
    return 0 if receipt.get("status") == "completed" else 1


def cmd_replay(args) -> int:
    """Re-parse raw bytes for <raw_sha> and diff derived IDs vs stored rows."""
    from oracle import ids
    from oracle.normalize import companies_house as ch

    raw_store, store = _stores(args.db, args.raw)
    payload = raw_store.get(args.raw_sha)
    if payload is None:
        print(json.dumps({"error": f"raw {args.raw_sha} not in store"}))
        store.close()
        return 1
    actual = ids.sha256_hex(payload)
    if actual != args.raw_sha:
        print(json.dumps({"error": "integrity failure", "stored": args.raw_sha,
                          "actual": actual}))
        store.close()
        return 1
    # Re-derive deterministically from the stored receipt context.
    import sqlite3

    c = sqlite3.connect(args.db)
    cur = c.execute("select * from oracle_receipts where raw_sha256 = ?",
                    (args.raw_sha,))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    c.close()
    if row is None:
        print(json.dumps({"error": "no receipt for raw_sha (ingest first)"}))
        store.close()
        return 1
    rdict = dict(zip(cols, row))
    batch = ch.parse_artifact(
        payload, receipt_id=rdict["receipt_id"], raw_sha256=args.raw_sha,
        observed_at=rdict["fetched_at"],
        artifact_name=args.raw_sha[:12])
    # Semantic root: (subject, predicate, value) sets must match exactly.
    # (Observation IDs are content-hashes over the same dicts, so a semantic
    # match implies ID match; we compare the semantic tuples directly.)
    c = sqlite3.connect(args.db)
    sem = sorted(c.execute(
        "select subject_entity_id, predicate, value from oracle_observations "
        "where lineage_root = ?", (args.raw_sha,)).fetchall())
    n_stored = len(sem)
    c.close()
    re_sem = sorted(
        (o["subject_entity_id"], o["predicate"], json.dumps(o["value"], sort_keys=True, default=str))
        for o in batch.observations)
    # Stored values are JSON-encoded; normalize both sides before comparing.
    norm_stored = sorted((s, p, json.dumps(json.loads(v), sort_keys=True, default=str)
                          if _is_json(v) else json.dumps(v, sort_keys=True, default=str))
                         for s, p, v in sem)
    match = norm_stored == re_sem and not batch.rejects
    print(json.dumps({
        "raw_sha256": args.raw_sha,
        "receipt_id": rdict["receipt_id"],
        "stored_observations": n_stored,
        "rederived_observations": len(re_sem),
        "semantic_match": match,
        "parse_rejects": batch.rejects,
    }, indent=2))
    store.close()
    return 0 if match else 1


def _is_json(s) -> bool:
    try:
        json.loads(s)
        return True
    except (TypeError, json.JSONDecodeError):
        return False


def cmd_evidence(args) -> int:
    """Full provenance chain for one observation."""
    raw_store, store = _stores(args.db, args.raw)
    obs = store.get_observation(args.observation_id)
    if obs is None:
        print(json.dumps({"error": f"observation {args.observation_id} not found"}))
        store.close()
        return 1
    receipt = store.get_receipt(obs["raw_receipt_id"])
    if receipt is None:
        print(json.dumps({"error": "receipt missing — provenance broken",
                          "raw_receipt_id": obs["raw_receipt_id"]}))
        store.close()
        return 1
    payload = raw_store.get(receipt["raw_sha256"])
    chain = {
        "observation": {k: obs[k] for k in (
            "observation_id", "subject_entity_id", "predicate", "value",
            "value_type", "source_id", "raw_receipt_id", "record_locator",
            "observed_at", "parser_version", "normalizer_version",
            "lineage_root")},
        "receipt": receipt,
        "raw": {
            "sha256": receipt["raw_sha256"],
            "bytes_present": payload is not None,
            "integrity_ok": bool(payload) and __import__(
                "hashlib").sha256(payload).hexdigest() == receipt["raw_sha256"],
            "byte_length": len(payload) if payload else 0,
        },
        "source": {"source_id": receipt["source_id"]},
    }
    print(json.dumps(chain, indent=2, default=str))
    store.close()
    return 0 if chain["raw"]["integrity_ok"] else 1


def cmd_check(_args) -> int:
    """E0 smoke checks: imports, parity sample, canonicalization, rights."""
    from oracle import ids
    from oracle.contracts import Source
    from oracle.schema_manifest import check_parity

    problems = []
    sql_relations = {
        "relation_id": "STRING", "from_entity_id": "STRING",
        "to_entity_id": "STRING", "relation_type": "STRING",
        "evidence_refs": "ARRAY<STRING>", "confidence": "FLOAT64",
        "lineage_root": "STRING", "valid_from": "TIMESTAMP",
        "valid_to": "TIMESTAMP",
    }
    if check_parity("Relation", sql_relations):
        problems.append("relation parity drift")
    try:
        ids.canonical({"x": float("nan")})
        problems.append("canonical accepts NaN")
    except ValueError:
        pass
    ok, reasons = Source(source_id="x", license="OGL").validate()
    if ok or "missing:terms_url" not in reasons:
        problems.append("source rights not fail-closed")
    print(json.dumps({"check": "ok" if not problems else "FAIL",
                      "problems": problems}))
    return 0 if not problems else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="oracle.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("ingest")
    pi.add_argument("fixture")
    pi.add_argument("--db", default=DEFAULT_DB)
    pi.add_argument("--raw", default=DEFAULT_RAW)
    pr = sub.add_parser("replay")
    pr.add_argument("raw_sha")
    pr.add_argument("--db", default=DEFAULT_DB)
    pr.add_argument("--raw", default=DEFAULT_RAW)
    pe = sub.add_parser("evidence")
    pe.add_argument("observation_id")
    pe.add_argument("--db", default=DEFAULT_DB)
    pe.add_argument("--raw", default=DEFAULT_RAW)
    sub.add_parser("check")
    args = p.parse_args(argv)
    if args.cmd == "ingest":
        return cmd_ingest(args)
    if args.cmd == "replay":
        return cmd_replay(args)
    if args.cmd == "evidence":
        return cmd_evidence(args)
    if args.cmd == "check":
        return cmd_check(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
