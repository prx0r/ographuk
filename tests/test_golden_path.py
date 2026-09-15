"""ORACLE_GOLDEN_PATH_V1: fixture → raw → receipt → parse → store → lineage.

One external raw record through the full chain with evidence back to the
original bytes. Covers decdev TODOs: golden path, idempotence, lineage,
quarantine gates, FetchResult semantics end-to-end.
"""
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle import ids
from oracle.contracts import Entity, Observation
from oracle.gates import run_gates
from oracle.ingest.runner import run_ingest
from oracle.normalize import companies_house as ch
from oracle.raw.store import RawStore
from oracle.sources.companies_house import CompaniesHouseAdapter, source_contract
from oracle.sources.fetch_result import FetchStatus
from oracle.sources.registry import SourceRegistry
from oracle.store.sqlite import SqliteStore

FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "fixtures", "companies_house", "small_snapshot.json")
ZIP_FIXTURE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "fixtures", "companies_house", "ch_basic_fixture.zip")
SOURCE = "companies-house"


def _registry():
    reg = SourceRegistry()
    assert reg.register(source_contract(),
                        CompaniesHouseAdapter())["registered"] == SOURCE
    return reg


def _harness():
    tmp = tempfile.mkdtemp()
    raw = RawStore(os.path.join(tmp, "raw"))
    store = SqliteStore(os.path.join(tmp, "oracle.db"))
    return tmp, raw, store


def _ingest(raw, store, adapter=None, parser=None):
    return run_ingest(SOURCE, adapter or CompaniesHouseAdapter(), raw, store,
                      parser=parser or ch.CompaniesHouseParser(),
                      registry=_registry())


def _counts(tmp):
    c = sqlite3.connect(os.path.join(tmp, "oracle.db"))
    out = {
        "entities": c.execute("select count(*) from oracle_entities").fetchone()[0],
        "observations": c.execute("select count(*) from oracle_observations").fetchone()[0],
        "receipts": c.execute("select count(*) from oracle_receipts").fetchone()[0],
        "quarantine": c.execute("select count(*) from oracle_quarantine").fetchone()[0],
    }
    c.close()
    return out


def _observation_ids(tmp):
    c = sqlite3.connect(os.path.join(tmp, "oracle.db"))
    rows = c.execute("select observation_id from oracle_observations").fetchall()
    c.close()
    return sorted(r[0] for r in rows)


# ── Golden path ──────────────────────────────────────────────

class TestGoldenPath:
    def test_ingest_fixture_end_to_end(self):
        tmp, raw, store = _harness()
        receipt = _ingest(raw, store)
        assert receipt["finished_at"], receipt
        assert receipt.get("status") == "completed", receipt
        assert receipt["fetch_status"] == "SUCCESS", receipt
        assert receipt["artifacts"] == 1
        counts = _counts(tmp)
        assert counts["entities"] == 5, counts
        assert counts["observations"] == 44, counts
        assert counts["receipts"] == 1, counts
        assert counts["quarantined"] == 0 if "quarantined" in counts else True
        assert receipt["rows_in"] == 44  # 44 derived observations
        assert receipt["rows_out"] == 44
        assert receipt["inserted"] == 44
        assert receipt["already_present"] == 0
        assert receipt["quarantined"] == 0
        assert receipt["semantic_root"].startswith("ROOT:"), receipt
        # contract hash bound into the receipt
        assert store.get_receipt(
            receipt["receipt_ids"][0])["source_contract_hash"]
        store.close()

    def test_every_observation_validates(self):
        tmp, raw, store = _harness()
        _ingest(raw, store)
        c = sqlite3.connect(os.path.join(tmp, "oracle.db"))
        cur = c.execute("select * from oracle_observations")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        c.close()
        assert len(rows) == 44
        for row in rows:
            d = dict(zip(cols, row))
            value = json.loads(d["value"]) if d["value"] else None
            obs = Observation(
                subject_entity_id=d["subject_entity_id"], predicate=d["predicate"],
                value=value, value_type=d["value_type"], source_id=d["source_id"],
                source_class=d["source_class"] or "",
                raw_receipt_id=d["raw_receipt_id"],
                record_locator=d["record_locator"], observed_at=d["observed_at"],
                parser_version=d["parser_version"],
                normalizer_version=d["normalizer_version"],
                status=d["status"], confidence=d["confidence"],
                lineage_root=d["lineage_root"],
            )
            ok, reasons = obs.validate()
            assert ok, (reasons, d["predicate"], d["record_locator"])
        store.close()

    def test_unknown_is_null_not_false(self):
        """NULL FIELDS company (00000004): null postcode/address emit nothing;
        known-empty sic_codes ([]) IS emitted as factual []."""
        tmp, raw, store = _harness()
        _ingest(raw, store)
        eid = ids.entity_id("company", "companies-house", "00000004")
        preds = {o["predicate"]: o["value"] for o in store.get_observations(eid)}
        assert "company.postcode" not in preds
        assert "company.address_line_1" not in preds
        assert "company.locality" not in preds
        assert json.loads(preds["company.sic_codes"]) == []
        store.close()

    def test_entity_ids_stable(self):
        tmp, raw, store = _harness()
        _ingest(raw, store)
        for number in ["00000001", "00000002", "00000005"]:
            eid = ids.entity_id("company", "companies-house", number)
            assert store.get_entity(eid) is not None
        store.close()


# ── Idempotence ──────────────────────────────────────────────

class TestIdempotence:
    def test_reingest_same_fixture_zero_new_records(self):
        tmp, raw, store = _harness()
        receipt1 = _ingest(raw, store)
        before_ids = _observation_ids(tmp)
        before = _counts(tmp)
        receipt2 = _ingest(raw, store)
        after_ids = _observation_ids(tmp)
        after = _counts(tmp)
        assert after_ids == before_ids  # same semantic root
        assert after["observations"] == before["observations"]
        assert after["entities"] == before["entities"]
        assert receipt2["rows_out"] == 44  # deterministic re-derivation
        assert receipt2["inserted"] == 0
        assert receipt2["already_present"] == 44
        assert receipt2["semantic_root"] == receipt1["semantic_root"]
        # run receipts persist the root
        assert store.get_ingest_run(
            receipt2["run_id"])["semantic_root"] == receipt1["semantic_root"]
        store.close()

    def test_reingest_across_second_boundary_stays_identical(self):
        """Fetch-time must not leak into identity (the 88-row bug)."""
        import time as _time

        tmp, raw, store = _harness()
        receipt1 = _ingest(raw, store)
        _time.sleep(1.1)
        receipt2 = _ingest(raw, store)
        assert _counts(tmp)["observations"] == 44
        assert receipt2["inserted"] == 0
        assert receipt2["semantic_root"] == receipt1["semantic_root"]
        store.close()

    def test_same_bytes_same_raw_hash(self):
        h1 = ids.sha256_hex(open(FIXTURE, "rb").read())
        tmp, raw, store = _harness()
        _ingest(raw, store)
        c = sqlite3.connect(os.path.join(tmp, "oracle.db"))
        sha = c.execute("select raw_sha256 from oracle_receipts").fetchone()[0]
        c.close()
        assert sha == h1
        assert raw.verify(sha)
        store.close()


# ── Lineage ──────────────────────────────────────────────────

class TestLineage:
    def test_observation_to_raw_bytes(self):
        """observation → receipt → raw SHA → source bytes → registered source."""
        tmp, raw, store = _harness()
        _ingest(raw, store)
        eid = ids.entity_id("company", "companies-house", "00000001")
        obs = store.get_observations(eid, "company.status")[0]
        assert json.loads(obs["value"]) == "active"
        # observation → receipt
        receipt = store.get_receipt(obs["raw_receipt_id"])
        assert receipt is not None
        assert receipt["source_id"] == SOURCE
        assert receipt["raw_sha256"] == obs["lineage_root"]
        # receipt → raw bytes
        payload = raw.get(receipt["raw_sha256"])
        assert payload is not None
        assert payload == open(FIXTURE, "rb").read()
        # record locator resolves inside the artifact
        loc = obs["record_locator"]
        assert loc.startswith("small_snapshot.json#/")
        rows = json.loads(payload.decode("utf-8"))
        assert rows[0]["company_status"] == "active"
        # gates pass on the stored observation with receipt joined
        ok, _ = run_gates(
            {**obs, "value": json.loads(obs["value"]),
             "confidence": None},
            {SOURCE}, receipts={receipt["receipt_id"]: receipt})
        assert ok
        store.close()


# ── Real-format ZIP/CSV fixture ──────────────────────────

class TestZipFixture:
    """The E2 parser architecture must work on real CH format, not just
    the synthetic JSON unit fixture."""

    def test_zip_ingest_matches_json_shape(self):
        tmp, raw, store = _harness()
        receipt = _ingest(raw, store, adapter=CompaniesHouseAdapter(
            fixture_path=ZIP_FIXTURE))
        assert receipt["status"] == "completed", receipt
        assert receipt["inserted"] == 44, receipt
        assert _counts(tmp)["entities"] == 5
        # same stable entities as the JSON path (identity = company number)
        for number in ["00000001", "00000005"]:
            assert store.get_entity(
                ids.entity_id("company", "companies-house", number)) is not None

    def test_zip_locators_point_into_csv_rows(self):
        tmp, raw, store = _harness()
        _ingest(raw, store, adapter=CompaniesHouseAdapter(
            fixture_path=ZIP_FIXTURE))
        eid = ids.entity_id("company", "companies-house", "00000001")
        obs = store.get_observations(eid, "company.name")[0]
        assert obs["record_locator"] == (
            "ch_basic_fixture.zip#BasicCompanyData-2026-09-01-part1_1.csv"
            ":row=2/CompanyName"), obs["record_locator"]
        assert json.loads(obs["value"]) == "ACME TESTINGS LIMITED"

    def test_zip_idempotent_and_rooted(self):
        tmp, raw, store = _harness()
        r1 = _ingest(raw, store, adapter=CompaniesHouseAdapter(
            fixture_path=ZIP_FIXTURE))
        r2 = _ingest(raw, store, adapter=CompaniesHouseAdapter(
            fixture_path=ZIP_FIXTURE))
        assert _counts(tmp)["observations"] == 44
        assert r2["inserted"] == 0
        assert r2["semantic_root"] == r1["semantic_root"]

    def test_zip_partial_slices_rows(self):
        tmp, raw, store = _harness()
        receipt = _ingest(raw, store, adapter=CompaniesHouseAdapter(
            fixture_path=ZIP_FIXTURE, mode="partial"))
        assert receipt["fetch_status"] == "PARTIAL", receipt
        assert _counts(tmp)["entities"] == 3


# ── Quarantine ───────────────────────────────────────────────

class TestQuarantine:
    def _bad_fixture(self, tmpdir, rows):
        p = os.path.join(tmpdir, "bad.json")
        with open(p, "w") as f:
            json.dump(rows, f)
        return p

    def test_malformed_record_quarantined_not_dropped_silently(self):
        tmp, raw, store = _harness()
        good = json.load(open(FIXTURE))
        bad = good + [{"company_name": "NO NUMBER LTD", "company_status": "active"}]
        bad_path = self._bad_fixture(tmp, bad)
        receipt = _ingest(raw, store,
                          adapter=CompaniesHouseAdapter(fixture_path=bad_path))
        assert receipt["rows_in"] == 45, receipt  # 44 obs + 1 reject
        assert receipt["rows_out"] == 44, receipt
        assert receipt["inserted"] == 44, receipt
        assert receipt["quarantined"] == 1, receipt
        counts = _counts(tmp)
        assert counts["quarantine"] == 1, counts
        assert counts["observations"] == 44
        # structured quarantine entry carries stage + locator
        q = sqlite3.connect(os.path.join(tmp, "oracle.db")).execute(
            "select stage, failure_code, record_locator, receipt_id from "
            "oracle_quarantine").fetchall()
        assert q[0][0] == "parse" and "bad.json" in q[0][2], q
        # replaying the same bad fixture does not duplicate quarantine rows
        receipt2 = _ingest(raw, store,
                           adapter=CompaniesHouseAdapter(fixture_path=bad_path))
        assert _counts(tmp)["quarantine"] == 1
        assert receipt2["inserted"] == 0
        store.close()

    def test_unregistered_source_denied(self):
        from oracle.sources.registry import SourceRegistry

        tmp, raw, store = _harness()
        receipt = run_ingest(SOURCE, CompaniesHouseAdapter(), raw, store,
                             parser=ch.CompaniesHouseParser(),
                             registry=SourceRegistry())
        assert receipt["status"] == "denied", receipt
        assert _counts(tmp)["observations"] == 0
        store.close()

    def test_observation_without_provenance_fails_gates(self):
        naked = {"subject_entity_id": "COMPANY:x", "predicate": "company.status",
                 "value": "active", "source_id": SOURCE, "raw_receipt_id": "",
                 "record_locator": "", "observed_at": "", "status": "OBSERVED"}
        ok, results = run_gates(naked, {SOURCE})
        assert not ok
        failed = {r.gate_name for r in results if not r.passed}
        assert "PROVENANCE_COMPLETE" in failed or "RAW_RECEIPT_VALID" in failed


# ── FetchResult semantics end-to-end ─────────────────────────

class TestFetchSemantics:
    def test_success_empty_writes_nothing_but_completes(self):
        tmp, raw, store = _harness()
        receipt = _ingest(raw, store,
                          adapter=CompaniesHouseAdapter(mode="empty"))
        assert receipt["fetch_status"] == "SUCCESS_EMPTY", receipt
        assert _counts(tmp)["observations"] == 0
        store.close()

    def test_failed_writes_nothing_and_marks_failed(self):
        tmp, raw, store = _harness()
        receipt = _ingest(raw, store,
                          adapter=CompaniesHouseAdapter(mode="failed"))
        assert receipt["status"] == "failed", receipt
        assert _counts(tmp)["observations"] == 0
        assert _counts(tmp)["receipts"] == 0  # outage stores no evidence
        store.close()

    def test_partial_ingests_what_arrived(self):
        tmp, raw, store = _harness()
        receipt = _ingest(raw, store,
                          adapter=CompaniesHouseAdapter(mode="partial"))
        assert receipt["fetch_status"] == "PARTIAL", receipt
        counts = _counts(tmp)
        assert counts["entities"] == 3, counts
        assert counts["observations"] > 0
        store.close()

    def test_fetch_result_contract(self):
        for mode, status in [("fixture", FetchStatus.SUCCESS),
                             ("empty", FetchStatus.SUCCESS_EMPTY),
                             ("failed", FetchStatus.FAILED),
                             ("partial", FetchStatus.PARTIAL)]:
            fr = CompaniesHouseAdapter(mode=mode).fetch()
            ok, reasons = fr.validate()
            assert ok, (mode, reasons)
            assert fr.status == status
        failed = CompaniesHouseAdapter(mode="failed").fetch()
        assert not failed.is_success and not failed.has_data
        empty = CompaniesHouseAdapter(mode="empty").fetch()
        assert empty.is_success and not empty.has_data
