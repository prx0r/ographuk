from oracle import ids, provenance
from oracle.contracts import (
    CandidateOpportunity, Entity, Event, Hypothesis, Identifier, Observation,
    Outcome, RawObject, Relation, Signal, Source)
from oracle.exports import seesaw
from oracle.sources.registry import SourceAdapter, SourceRegistry


def test_ids_stable_and_prefixed():
    a = ids.obj_id("COMP", {"n": "Acme Ltd", "c": "GB"})
    assert ids.obj_id("COMP", {"n": "Acme Ltd", "c": "GB"}) == a
    assert a.startswith("COMP:") and len(a) == 5 + 64
    assert ids.short("COMP", {"n": "Acme Ltd", "c": "GB"}).startswith("COMP-")
    assert provenance.raw_hash(b"x") == ids.sha256_hex(b"x")


def test_provenance_receipt():
    r = provenance.ingest_receipt("companies-house", "abc", "v3")
    assert r == {"source_id": "companies-house", "raw_sha256": "abc",
                 "parser_version": "v3"}


def test_source_requires_license():
    ok, reasons = Source(source_id="x").validate()
    assert not ok and reasons == ["missing:license"]
    ok, _ = Source(source_id="companies-house", license="OGL-3.0").validate()
    assert ok


def test_observation_binary_gates():
    ok, reasons = Observation(subject="COMP_1", predicate="company.status",
                              source="ch", raw_sha256="h").validate()
    assert ok, reasons
    bad, r2 = Observation(subject="", predicate="p", source="s",
                          raw_sha256="h", confidence="high").validate()
    assert not bad and "bad:confidence" in r2


def test_hypothesis_requires_falsifiers():
    ok, _ = Hypothesis(hypothesis_id="H1", thesis="t",
                       falsifiers=["f"]).validate()
    assert ok
    bad, r = Hypothesis(hypothesis_id="H1", thesis="t").validate()
    assert not bad and r == ["missing:falsifiers"]


def test_relation_upper_snake():
    ok, _ = Relation(source_id="a", target_id="b",
                     rel_type="OPERATES_AT").validate()
    assert ok
    bad, r = Relation(source_id="a", target_id="b",
                      rel_type="operates at").validate()
    assert not bad and "rel_type:not-upper-snake" in r


def test_registry_rejects_unlicensed():
    reg = SourceRegistry()
    assert "error" in reg.register(Source(source_id="x"))
    assert reg.register(Source(source_id="ch", license="OGL")) == {
        "registered": "ch"}
    assert reg.list() == ["ch"]


def test_seesaw_export_passthrough():
    cand = {"opportunity_id": "opp-1", "thesis": "t",
            "falsifiers": ["f"], "type": "PLUGIN",
            "features": {"demand_change": 0.82, "note": " prose dropped "},
            "unknowns": ["u1"]}
    v = seesaw.export_candidate(cand)
    assert v["demand_change"] == 0.82 and "note" not in v
    assert v["unknowns"] == ["u1"]
    bad = seesaw.export_candidate({"opportunity_id": "x"})
    assert "error" in bad
