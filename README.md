# ographuk — Oracle UK Runtime

The canonical Oracle runtime for the UK. Turns raw external evidence into
stable entities, temporal observations, deterministic signals, and candidate
opportunities that Seesaw evaluates economically.

## What Oracle Does

```text
EXTERNAL WORLD
      ↓ source adapters
RAW EVIDENCE (immutable, hash-addressed)
      ↓ parser + normalizer
ENTITIES + IDENTIFIERS (stable identity)
      ↓
OBSERVATIONS + RELATIONS (temporal, provenance-linked)
      ↓ deterministic transforms
SIGNALS (versioned formulas)
      ↓ detectors
CANDIDATE OPPORTUNITIES (with falsifiers + evidence)
      ↓
SEESAW (economic evaluation)
      ↓
AGENTCOM (real products / campaigns / trades)
      ↓
VERIFIED OUTCOMES → back into Oracle
```

**The asset is not graph software.** It is years of normalized UK reality +
historical snapshots + cross-source identity + our own action/outcome data.

## Repo Relationships

| Repo | Role | Owns |
|------|------|------|
| **ographuk** (this repo) | Oracle runtime | contracts, ingestion, normalization, entity resolution, events, signals, opportunities, query/MCP interfaces |
| **cgraphuk** | Semantic/domain packs | vertical ontologies, pain/fix/regulation mappings, campaigns, voice profiles, human-curated reference knowledge |
| **bq** | Persistent analytical storage | BigQuery Graph, views, materializations, DDL |
| **agentcomfinal** | Opportunity consumer | Seesaw allocation, Autobuild, real-world actions, real outcomes |

**Boundary:** Ingestion belongs in ographuk. Semantic knowledge belongs in
cgraphuk. Storage adapters belong in bq. Actions belong in agentcomfinal.

## Layout

```
ographuk/
  README.md              this file
  DEVINSTRUCT.md         canonical build brief (E0–E10 full spec)
  decdev.md              working brief for autonomous execution
  oracle/
    ids.py               content-hash IDs (stable entity + immutable record)
    contracts.py         schemas-as-code: all Oracle record types
    provenance.py        raw hashing + ingest receipt helpers
    sources/
      registry.py        SourceRegistry v2: licensing + adapter interface
      companies_house.py fixture-backed CH adapter (fixture/empty/failed/partial)
      fetch_result.py    FetchResult: SUCCESS/SUCCESS_EMPTY/PARTIAL/FAILED
    exports/
      seesaw.py          CandidateOpportunity → feature vector
    cli.py               operator interface: ingest / replay / evidence / check
    normalize/
      companies_house.py CH JSON parser → Entity + Observation bundles (E1 live)
    resolve/             entity resolution (E4 — stub)
    signals/             versioned formula transforms (E7 — stub)
    opportunities/       opportunity detectors (E9 — stub)
    probes/              probe request logic (E8 — stub)
    mcp/                 MCP query interface (E6+ — stub)
    store/
      base.py            OracleStore interface (+ receipts)
      sqlite.py          SQLite backend incl. oracle_receipts (E1 live)
    raw/
      store.py           hash-addressed RawStore (E1 live)
    gates.py             quarantine gate runner (receipt-aware, E1 live)
    ingest/
      runner.py          ingest pipeline runner (receipts + entities, E1 live)
  schemas/
    001_oracle_core.sql  BigQuery DDL (12 tables incl. oracle_receipts)
  fixtures/
    companies_house/   golden CH fixture (5 rows)
  tests/
    conftest.py          test path setup
    test_contracts.py    E0 contract + validation tests (57)
    test_golden_path.py  E1 golden-path tests (19: json + zip + quarantine + FetchResult)
    test_schema_parity.py real parity: dataclasses ↔ manifest ↔ SQLite/BQ (4)
```

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| **E0** | Oracle contracts + IDs + hardening | **IN PROGRESS** — core contracts exist, hardening in progress |
| **E1** | Raw/provenance pipeline | **IN PROGRESS** — golden path proven locally on two formats: JSON fixture + real-format ZIP/CSV (`ch_basic_fixture.zip`, real CH headers, streaming rows) → RawStore → receipt (contract-bound) → parse → CanonicalBatch → 5 entities + 44 obs → gates → append-only SQLite; re-ingest → 0 inserted / identical `semantic_root`; replay + evidence via `python -m oracle.cli`; 80 tests green (2026-09-15). Remaining: live source adapter heartbeat |
| E2 | Companies House backbone | TODO — parser architecture is ZIP/CSV-streaming ready; needs live 7-part bulk snapshot |
| E3 | Geography spine | TODO |
| E4 | Cross-source entity resolution | TODO |
| E5 | Physical-property graph | TODO |
| E6 | Change engine + MCP interface | TODO |
| E7 | Market/demand graph | TODO |
| E8 | Seesaw feed (full) | TODO — basic export exists |
| E9 | Opportunity detectors | TODO |
| E10 | First downstream proof | TODO |

## Laws

1. **Stdlib only** for core. External adapters may use pinned official deps.
2. **Unknown = null**, never 0 or False.
3. **Quarantine-first.** Every observation passes gates before promotion.
4. **No fuzzy joins in canonical truth.** Candidate resolution edges carry
   confidence/method but are excluded from default graph traversal.
5. **Raw evidence retained.** Hash-addressed. Parser replay possible.
6. **No observation without provenance.** receipt + record_locator required.
7. **No empty source ambiguity.** FetchResult distinguishes SUCCESS_EMPTY
   from FAILED from PARTIAL.
8. **Idempotent.** Same input + same parser + same normalizer = same output.
9. **Temporal is canonical.** History is never overwritten. Current state is
   a view over the full observation stream.
10. **Nothing becomes more true because an agent found it persuasive.**

## Quickstart

```bash
cd /root/ographuk
python3 -m pytest tests/ -q          # run contract tests
python3 -c "from oracle.contracts import *; print('contracts OK')"
```

## What "E0 Complete" Looks Like

All of these pass:

```bash
pytest -q                              # all tests green
python -m oracle.cli check             # schema parity + rights + canonicalization
python -m oracle.cli ingest fixtures/companies_house/ch_basic_fixture.zip
python -m oracle.cli replay <raw_sha>
python -m oracle.cli evidence <observation_id>
```

With: entity IDs surviving name changes, NaN rejected, SQL/Python parity
enforced, FetchResult semantics, RawStore round-trip, quarantine gates
firing, Seesaw rejecting unbacked features, full provenance replay.
