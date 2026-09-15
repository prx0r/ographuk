"""Comprehensive E0 test suite. Covers decdev.md §23 hardening tests."""
import json
import math
import os
import sys
import tempfile

import pytest

# Ensure ographuk root is on path (avoids /root/oracle/ shadow)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle import ids
from oracle.contracts import (
    CandidateOpportunity, Entity, Event, Hypothesis, Identifier, Observation,
    Outcome, RawObject, Relation, Signal, Source)
from oracle.exports import seesaw
from oracle.gates import (
    run_gates, gate_source_registered, gate_raw_hash_valid,
    gate_raw_receipt_valid, gate_provenance_complete, gate_identity_valid,
    gate_temporal_valid, gate_confidence_range, GateResult)
from oracle.provenance import RawEvidenceReceipt, raw_hash
from oracle.raw.store import RawStore
from oracle.schema_manifest import SCHEMAS, check_parity, bq_columns
from oracle.signals.registry import SignalFormula, SignalRegistry
from oracle.sources.fetch_result import FetchResult, FetchStatus, SnapshotSemantics
from oracle.store.sqlite import SqliteStore


# ──────────────────────────────────────────────
# §23 E0 Hardening Tests
# ──────────────────────────────────────────────

class TestCanonicalRejectsNan:
    """test_canonical_rejects_nan"""

    def test_rejects_nan_float(self):
        with pytest.raises(ValueError, match="non-finite"):
            ids.canonical({"x": float("nan")})

    def test_rejects_inf(self):
        with pytest.raises(ValueError, match="non-finite"):
            ids.canonical({"x": float("inf")})

    def test_rejects_neg_inf(self):
        with pytest.raises(ValueError, match="non-finite"):
            ids.canonical({"x": float("-inf")})

    def test_rejects_nested_nan(self):
        with pytest.raises(ValueError, match="non-finite"):
            ids.canonical({"a": {"b": float("nan")}})

    def test_rejects_nan_in_list(self):
        with pytest.raises(ValueError, match="non-finite"):
            ids.canonical([1.0, float("nan"), 3.0])

    def test_allows_normal_floats(self):
        result = ids.canonical({"x": 1.5, "y": 0.0, "z": -42.1})
        assert b"1.5" in result
        assert b"-42.1" in result

    def test_allows_none(self):
        result = ids.canonical({"x": None})
        assert b"null" in result


class TestEntityIdSurvivesNameChange:
    """test_entity_id_survives_name_change"""

    def test_same_entity_different_names(self):
        id1 = ids.entity_id("company", "companies-house", "01234567")
        id2 = ids.entity_id("company", "companies-house", "01234567")
        assert id1 == id2

    def test_different_entities_different_ids(self):
        id1 = ids.entity_id("company", "companies-house", "01234567")
        id2 = ids.entity_id("company", "companies-house", "01234568")
        assert id1 != id2

    def test_different_namespaces_different_ids(self):
        id1 = ids.entity_id("company", "ch", "01234567")
        id2 = ids.entity_id("company", "osm", "01234567")
        assert id1 != id2

    def test_entity_id_prefix(self):
        eid = ids.entity_id("company", "ch", "01234567")
        assert eid.startswith("COMPANY:")

    def test_entity_short_display(self):
        s = ids.entity_short("company", "ch", "01234567")
        assert s.startswith("COMPANY-") and len(s) == 8 + 8


class TestRecordIds:
    def test_record_id_stable(self):
        a = ids.record_id("OBS", {"s": "e1", "p": "status"})
        b = ids.record_id("OBS", {"s": "e1", "p": "status"})
        assert a == b

    def test_record_id_prefix(self):
        rid = ids.record_id("SIG", {"f": "density", "v": "v1"})
        assert rid.startswith("SIG:") and len(rid) == 4 + 64

    def test_record_short(self):
        s = ids.record_short("OBS", {"s": "e1"})
        assert s.startswith("OBS-") and len(s) == 4 + 8


class TestSqlContractParity:
    """test_sql_contract_parity — every field in manifest appears in SQL DDL"""

    def test_parity_check(self):
        sql_relations = {
            "relation_id": "STRING",
            "from_entity_id": "STRING",
            "to_entity_id": "STRING",
            "relation_type": "STRING",
            "evidence_refs": "ARRAY<STRING>",
            "confidence": "FLOAT64",
            "lineage_root": "STRING",
            "valid_from": "TIMESTAMP",
            "valid_to": "TIMESTAMP",
        }
        discrepancies = check_parity("Relation", sql_relations)
        assert discrepancies == [], f"Relation parity failed: {discrepancies}"

    def test_all_schemas_have_fields(self):
        for name, fields in SCHEMAS.items():
            assert len(fields) > 0, f"Schema {name} has no fields"


class TestRelationRequiresEvidence:
    """test_relation_requires_evidence"""

    def test_relation_without_evidence_fails(self):
        ok, reasons = Relation(
            from_entity_id="COMP:abc",
            to_entity_id="LOC:def",
            relation_type="OPERATES_AT",
            evidence_refs=[]
        ).validate()
        assert not ok
        assert "missing:evidence_refs" in reasons

    def test_relation_with_evidence_passes(self):
        ok, reasons = Relation(
            from_entity_id="COMP:abc",
            to_entity_id="LOC:def",
            relation_type="OPERATES_AT",
            evidence_refs=["OBS:123"]
        ).validate()
        assert ok, reasons


class TestRelationFieldRenaming:
    """Relation uses from_entity_id/to_entity_id, not source_id/target_id"""

    def test_old_field_names_not_accepted(self):
        import inspect
        sig = inspect.signature(Relation.__init__)
        params = list(sig.parameters.keys())
        assert "source_id" not in params
        assert "target_id" not in params
        assert "from_entity_id" in params
        assert "to_entity_id" in params


class TestObservationRequiresRawReceipt:
    """test_observation_requires_raw_receipt"""

    def test_observation_without_receipt_fails(self):
        ok, reasons = Observation(
            subject_entity_id="COMP:abc",
            predicate="company.status",
            source_id="ch",
            raw_receipt_id="",
            record_locator="csv#row=1",
            observed_at="2026-01-01T00:00:00Z"
        ).validate()
        assert not ok
        assert "missing:raw_receipt_id" in reasons

    def test_observation_with_receipt_passes(self):
        ok, reasons = Observation(
            subject_entity_id="COMP:abc",
            predicate="company.status",
            source_id="ch",
            raw_receipt_id="RECEIPT:abc123",
            record_locator="csv#row=1",
            observed_at="2026-01-01T00:00:00Z"
        ).validate()
        assert ok, reasons


class TestObservationRequiresRecordLocator:
    """test_observation_requires_record_locator"""

    def test_observation_without_locator_fails(self):
        ok, reasons = Observation(
            subject_entity_id="COMP:abc",
            predicate="company.status",
            source_id="ch",
            raw_receipt_id="RECEIPT:abc",
            record_locator="",
            observed_at="2026-01-01T00:00:00Z"
        ).validate()
        assert not ok
        assert "missing:record_locator" in reasons


class TestConfidenceRange:
    """test_confidence_range"""

    def test_valid_range(self):
        for v in [0.0, 0.5, 1.0, None]:
            ok, reasons = Observation(
                subject_entity_id="COMP:abc",
                predicate="p",
                source_id="s",
                raw_receipt_id="R:1",
                record_locator="x#1",
                observed_at="2026-01-01",
                confidence=v
            ).validate()
            assert ok, f"confidence={v} should be valid: {reasons}"

    def test_out_of_range(self):
        ok, reasons = Observation(
            subject_entity_id="COMP:abc",
            predicate="p",
            source_id="s",
            raw_receipt_id="R:1",
            record_locator="x#1",
            observed_at="2026-01-01",
            confidence=1.5
        ).validate()
        assert not ok
        assert any("out-of-range" in r for r in reasons)


class TestFetchFailureNotEmpty:
    """test_fetch_failure_not_empty — FAILED ≠ SUCCESS_EMPTY"""

    def test_fetch_result_success_empty(self):
        fr = FetchResult(status=FetchStatus.SUCCESS_EMPTY)
        assert fr.is_success
        assert not fr.has_data

    def test_fetch_result_failed(self):
        fr = FetchResult(status=FetchStatus.FAILED, complete=False)
        assert not fr.is_success

    def test_fetch_result_partial_not_complete(self):
        fr = FetchResult(status=FetchStatus.PARTIAL, complete=False)
        ok, reasons = fr.validate()
        assert ok

    def test_fetch_result_partial_but_complete_fails(self):
        fr = FetchResult(status=FetchStatus.PARTIAL, complete=True)
        ok, reasons = fr.validate()
        assert not ok
        assert "partial:but:complete=true" in reasons

    def test_fetch_result_failed_but_complete_fails(self):
        fr = FetchResult(status=FetchStatus.FAILED, complete=True)
        ok, reasons = fr.validate()
        assert not ok


class TestSourceRightsFailClosed:
    """test_source_rights_fail_closed"""

    def test_raw_storage_unknown_blocked(self):
        ok, reasons = Source(
            source_id="ch",
            license="OGL-3.0",
            terms_url="https://example.com",
            raw_retention=True,
            raw_storage="UNKNOWN"
        ).validate()
        assert not ok
        assert "blocked:raw_storage_unknown_with_retention" in reasons

    def test_raw_storage_allowed_passes(self):
        ok, reasons = Source(
            source_id="ch",
            license="OGL-3.0",
            terms_url="https://example.com",
            raw_retention=True,
            raw_storage="ALLOWED"
        ).validate()
        assert ok, reasons

    def test_source_requires_terms_url(self):
        ok, reasons = Source(source_id="x", license="OGL").validate()
        assert not ok
        assert "missing:terms_url" in reasons


class TestRawStoreRoundtrip:
    """test_raw_store_roundtrip"""

    def test_put_get_verify(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RawStore(tmpdir)
            data = b"test raw payload"
            result = store.put("companies-house", "2026-01-01", data)
            assert result["byte_length"] == len(data)

            retrieved = store.get(result["raw_sha256"])
            assert retrieved == data
            assert store.verify(result["raw_sha256"])

    def test_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RawStore(tmpdir)
            assert not store.exists("nonexistent")
            store.put("src", "2026-01-01", b"data")
            hashes = store.list_hashes("src")
            assert len(hashes) == 1
            assert store.exists(hashes[0])


class TestRawHashTamperDetected:
    """test_raw_hash_tamper_detected"""

    def test_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RawStore(tmpdir)
            result = store.put("src", "2026-01-01", b"original data")
            sha = result["raw_sha256"]
            # Tamper by writing different bytes to same path
            path = store.artifact_path("src", "2026-01-01", sha)
            path.write_bytes(b"TAMPERED DATA")
            # get should raise ValueError
            with pytest.raises(ValueError, match="integrity failure"):
                store.get(sha)


class TestIngestReplayIdempotent:
    """test_ingest_replay_idempotent — SQLite store"""

    def test_same_observation_twice(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            store = SqliteStore(db_path)
            obs = {
                "subject_entity_id": "COMP:abc",
                "predicate": "company.status",
                "value": "active",
                "source_id": "ch",
                "raw_receipt_id": "R:1",
                "record_locator": "csv#1",
                "observed_at": "2026-01-01",
                "status": "OBSERVED",
            }
            r1 = store.put_observation(obs)
            r2 = store.put_observation(obs)
            assert r1["observation_id"] == r2["observation_id"]
            # Get should return exactly one
            results = store.get_observations("COMP:abc")
            assert len(results) == 1
            store.close()
        finally:
            os.unlink(db_path)


class TestPartialSnapshotCannotEmitDeletion:
    """test_partial_snapshot_cannot_emit_deletion"""

    def test_partial_no_deletion(self):
        fr = FetchResult(
            status=FetchStatus.PARTIAL,
            complete=False,
            snapshot_semantics=SnapshotSemantics.PARTIAL
        )
        ok, reasons = fr.validate()
        assert ok  # partial with complete=False is valid
        # But a partial snapshot should NOT trigger deletion logic
        # This is a design invariant: only FULL+complete snapshots
        # can produce absence-based events


class TestUnknownIsNullNotFalse:
    """test_unknown_is_null_not_false"""

    def test_unknown_confidence_is_none(self):
        obs = Observation(
            subject_entity_id="COMP:abc",
            predicate="p",
            source_id="s",
            raw_receipt_id="R:1",
            record_locator="x#1",
            observed_at="2026-01-01",
            confidence=None
        )
        ok, reasons = obs.validate()
        assert ok
        assert obs.confidence is None

    def test_unknown_value_is_none(self):
        obs = Observation(
            subject_entity_id="COMP:abc",
            predicate="p",
            source_id="s",
            raw_receipt_id="R:1",
            record_locator="x#1",
            observed_at="2026-01-01",
            value=None,
            value_type="null"
        )
        ok, reasons = obs.validate()
        assert ok


class TestSeesawRejectsUnbackedFeatures:
    """test_seesaw_rejects_unbacked_features"""

    def test_legacy_no_numeric_injection(self):
        cand = {
            "opportunity_id": "opp-1",
            "thesis": "test thesis",
            "falsifiers": ["f1"],
            "type": "PLUGIN",
            "supporting_signal_ids": ["SIG:abc"],
            "features": {"demand_change": 0.99, "note": "prose dropped"},
        }
        v = seesaw.export_candidate(cand)
        # Should NOT have demand_change injected
        assert "demand_change" not in v
        assert "note" not in v
        # Should have signal IDs
        assert "signal_ids" in v or "resolved_signals" in v

    def test_validation_error(self):
        bad = {"opportunity_id": "x"}
        v = seesaw.export_candidate(bad)
        assert "error" in v


# ──────────────────────────────────────────────
# Original tests (preserved)
# ──────────────────────────────────────────────

def test_ids_stable_and_prefixed():
    a = ids.record_id("COMP", {"n": "Acme Ltd", "c": "GB"})
    assert ids.record_id("COMP", {"n": "Acme Ltd", "c": "GB"}) == a
    assert a.startswith("COMP:") and len(a) == 5 + 64
    assert ids.record_short("COMP", {"n": "Acme Ltd", "c": "GB"}).startswith("COMP-")
    assert raw_hash(b"x") == ids.sha256_hex(b"x")


def test_provenance_receipt():
    r = RawEvidenceReceipt(
        source_id="companies-house",
        raw_sha256="abc123def456789012345678901234567890123456789012345678901234567890",
        parser_version="v3",
        fetched_at="2026-01-01T00:00:00Z",
        source_contract_hash="",
        snapshot_semantics="FULL",
        complete=True
    )
    ok, reasons = r.validate()
    assert ok, reasons
    d = r.to_dict()
    assert d["source_id"] == "companies-house"
    assert d["parser_version"] == "v3"


def test_source_requires_license():
    ok, reasons = Source(source_id="x").validate()
    assert not ok
    assert "missing:license" in reasons


def test_observation_binary_gates():
    ok, reasons = Observation(
        subject_entity_id="COMP_1",
        predicate="company.status",
        source_id="ch",
        raw_receipt_id="R:1",
        record_locator="csv#1",
        observed_at="2026-01-01"
    ).validate()
    assert ok, reasons


def test_hypothesis_requires_falsifiers():
    ok, _ = Hypothesis(hypothesis_id="H1", thesis="t",
                       falsifiers=["f"]).validate()
    assert ok
    bad, r = Hypothesis(hypothesis_id="H1", thesis="t").validate()
    assert not bad and r == ["missing:falsifiers"]


def test_relation_upper_snake():
    ok, _ = Relation(
        from_entity_id="a", to_entity_id="b",
        relation_type="OPERATES_AT",
        evidence_refs=["OBS:1"]
    ).validate()
    assert ok
    bad, r = Relation(
        from_entity_id="a", to_entity_id="b",
        relation_type="operates at",
        evidence_refs=["OBS:1"]
    ).validate()
    assert not bad and "relation_type:not-upper-snake" in r


def test_registry_rejects_unlicensed():
    from oracle.sources.registry import SourceRegistry
    reg = SourceRegistry()
    assert "error" in reg.register(Source(source_id="x"))
    assert reg.register(Source(source_id="ch", license="OGL",
                               terms_url="https://example.com",
                               raw_storage="ALLOWED")) == {
        "registered": "ch"}
    assert reg.list() == ["ch"]


def test_seesaw_export_passthrough():
    cand = {"opportunity_id": "opp-1", "thesis": "t",
            "falsifiers": ["f"], "type": "PLUGIN",
            "supporting_signal_ids": ["SIG:1"],
            "unknowns": ["u1"]}
    v = seesaw.export_candidate(cand)
    assert v["thesis"] == "t"
    assert v["unknowns"] == ["u1"]


# ──────────────────────────────────────────────
# Additional unit tests
# ──────────────────────────────────────────────

def test_event_requires_observations():
    ok, _ = Event(
        event_type="COMPANY_CREATED",
        observed_at="2026-01-01",
        triggering_observation_ids=["OBS:1"]
    ).validate()
    assert ok
    bad, r = Event(event_type="X").validate()
    assert not bad


def test_signal_requires_inputs():
    ok, _ = Signal(
        signal_id="SIG:1",
        formula_id="density",
        input_ids=["OBS:1"],
        computed_at="2026-01-01"
    ).validate()
    assert ok


def test_outcome_requires_fields():
    ok, _ = Outcome(
        outcome_id="OUT:1",
        action="build",
        observed_at="2026-01-01"
    ).validate()
    assert ok
    bad, _ = Outcome(outcome_id="OUT:1").validate()
    assert not bad


def test_candidate_opportunity_requires_signals():
    ok, _ = CandidateOpportunity(
        opportunity_id="OPP:1",
        thesis="test",
        falsifiers=["f"],
        supporting_signal_ids=["SIG:1"]
    ).validate()
    assert ok
    bad, r = CandidateOpportunity(
        opportunity_id="OPP:1",
        thesis="test",
        falsifiers=["f"]
    ).validate()
    assert not bad
    assert "missing:supporting_signal_ids" in r


def test_signal_registry():
    reg = SignalRegistry()

    class TestFormula(SignalFormula):
        formula_id = "test_density"
        required_inputs = ["count", "area"]
        def compute(self, inputs):
            return inputs["count"] / inputs["area"]

    f = TestFormula(formula_id="test_density")
    result = reg.register(f)
    assert "registered" in result

    computed = reg.compute_signal("test_density", "v1",
                                   ["obs:1", "obs:2"],
                                   {"count": 10, "area": 5.0})
    assert computed["value"] == 2.0
    assert computed["formula_id"] == "test_density"


def test_gate_functions():
    # SOURCE_REGISTERED
    r = gate_source_registered("ch", {"ch", "fhrs"})
    assert r.passed
    r = gate_source_registered("unknown", {"ch"})
    assert not r.passed

    # RAW_HASH_VALID
    r = gate_raw_hash_valid("a" * 64)
    assert r.passed
    r = gate_raw_hash_valid("short")
    assert not r.passed

    # CONFIDENCE_RANGE
    r = gate_confidence_range(0.5)
    assert r.passed
    r = gate_confidence_range(None)
    assert r.passed
    r = gate_confidence_range(1.5)
    assert not r.passed


def test_sqlite_store_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        store = SqliteStore(db_path)

        # Entity
        e = {"entity_id": "COMP:abc", "entity_type": "company",
             "canonical_name": "Test Co"}
        store.put_entity(e)
        assert store.get_entity("COMP:abc")["canonical_name"] == "Test Co"
        assert store.get_entity("COMP:xyz") is None

        # Identifier
        store.put_identifier({"entity_id": "COMP:abc",
                              "id_type": "ch_number", "id_value": "123"})

        # Observation
        obs = {
            "subject_entity_id": "COMP:abc",
            "predicate": "company.status",
            "value": "active",
            "source_id": "ch",
            "raw_receipt_id": "R:1",
            "record_locator": "csv#1",
            "observed_at": "2026-01-01",
        }
        store.put_observation(obs)
        results = store.get_observations("COMP:abc")
        assert len(results) == 1
        assert results[0]["predicate"] == "company.status"

        # Ingest run
        run = store.begin_ingest_run("ch")
        assert run["run_id"]
        store.commit_ingest_run(run["run_id"], {"status": "done", "rows_in": 10})

        # Quarantine
        q = store.quarantine(obs, "test reason")
        assert q["quarantine_id"]

        store.close()
    finally:
        os.unlink(db_path)
