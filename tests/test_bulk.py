"""Bulk path tests: FileArtifact, put_file, chunked ingest, sampling.

Uses a synthetic 300-row ZIP (same real-format headers). The live part-1
proof runs outside pytest (see experiments log); these tests pin the
mechanics deterministically.
"""
import csv
import io
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle.ingest.runner import run_bulk_ingest
from oracle.normalize import companies_house as ch
from oracle.raw.store import RawStore
from oracle.sources.companies_house import (
    CompaniesHouseBulkAdapter, FileArtifact, source_contract)
from oracle.sources.registry import SourceRegistry
from oracle.store.sqlite import SqliteStore

SOURCE = "companies-house"

HEADERS = ["CompanyName", " CompanyNumber", "CompanyStatus",
           "CompanyCategory", "IncorporationDate",
           "RegAddress.PostCode", "SICCode.SicText_1",
           "ConfStmtNextDueDate"]


def _make_zip(path, n, start=1, bad_at=None):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADERS)
    for i in range(start, start + n):
        if bad_at is not None and i == bad_at:
            w.writerow([f"NO NUMBER {i}", "", "Active", "ltd",
                        "01/01/2020", "", "", ""])
            continue
        w.writerow([f"TEST CO {i:06d}", f"{i:08d}", "Active",
                    "Private Limited Company", "01/02/2021", "E1 6AN",
                    "62012 - Business and domestic software development",
                    "01/02/2026"])
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("BasicCompanyData-2026-09-01-part9_9.csv", buf.getvalue())
    return path


def _harness():
    tmp = tempfile.mkdtemp()
    raw = RawStore(os.path.join(tmp, "raw"))
    store = SqliteStore(os.path.join(tmp, "oracle.db"))
    reg = SourceRegistry()
    assert reg.register(source_contract())["registered"] == SOURCE
    return tmp, raw, store, reg


class TestBulkMechanics:
    def test_put_file_roundtrip(self):
        tmp, raw, store, reg = _harness()
        zp = _make_zip(os.path.join(tmp, "t.zip"), 10)
        put = raw.put_file(SOURCE, "2026-09-01", zp)
        assert put["byte_length"] == os.path.getsize(zp)
        assert raw.verify(put["raw_sha256"])
        assert raw.get(put["raw_sha256"]) == open(zp, "rb").read()
        store.close()

    def test_bulk_adapter_lists_parts(self):
        tmp, raw, store, reg = _harness()
        zp = _make_zip(os.path.join(tmp, "t.zip"), 10)
        fr = CompaniesHouseBulkAdapter([zp]).fetch()
        assert fr.status.value == "SUCCESS"
        assert isinstance(fr.artifacts[0], FileArtifact)
        assert fr.watermark == "2026-09-01T00:00:00Z" or "2026" in fr.watermark
        store.close()

    def test_bulk_adapter_missing_part_fails(self):
        tmp, raw, store, reg = _harness()
        fr = CompaniesHouseBulkAdapter(
            [os.path.join(tmp, "nope.zip")]).fetch()
        assert fr.status.value == "FAILED"
        assert not fr.complete
        store.close()

    def test_chunked_ingest_counts_and_root(self):
        tmp, raw, store, reg = _harness()
        zp = _make_zip(os.path.join(tmp, "t.zip"), 300)
        r1 = run_bulk_ingest(
            SOURCE, CompaniesHouseBulkAdapter([zp]), raw, store,
            parser=ch.CompaniesHouseParser(), registry=reg,
            chunk_rows=50, sample_observations=1000)
        assert r1["status"] == "completed", r1
        assert r1["chunks"] == 6, r1
        assert r1["entities_stored"] == 300, r1
        assert r1["observations_derived"] == 300 * 7, r1
        assert r1["observations_stored"] == 300 * 7, r1
        assert r1["semantic_root"].startswith("ROOT:")
        r2 = run_bulk_ingest(
            SOURCE, CompaniesHouseBulkAdapter([zp]), raw, store,
            parser=ch.CompaniesHouseParser(), registry=reg,
            chunk_rows=50, sample_observations=1000)
        assert r2["semantic_root"] == r1["semantic_root"]
        assert r2["inserted"] == 0
        assert r2["already_present"] == 300 * 7
        store.close()

    def test_sampling_bounds_storage(self):
        tmp, raw, store, reg = _harness()
        zp = _make_zip(os.path.join(tmp, "t.zip"), 300)
        r = run_bulk_ingest(
            SOURCE, CompaniesHouseBulkAdapter([zp]), raw, store,
            parser=ch.CompaniesHouseParser(), registry=reg,
            chunk_rows=50, sample_observations=100)
        assert r["entities_stored"] == 300
        assert r["observations_derived"] == 300 * 7
        assert r["observations_stored"] < r["observations_derived"]
        assert (r["observations_stored"]
                + r["observations_sampled_out"] == r["observations_derived"])
        store.close()

    def test_bulk_rejects_quarantined(self):
        tmp, raw, store, reg = _harness()
        zp = _make_zip(os.path.join(tmp, "t.zip"), 100, bad_at=50)
        r = run_bulk_ingest(
            SOURCE, CompaniesHouseBulkAdapter([zp]), raw, store,
            parser=ch.CompaniesHouseParser(), registry=reg,
            chunk_rows=50, sample_observations=1000)
        assert r["quarantined"] == 1, r
        assert r["entities_stored"] == 99, r
        store.close()
