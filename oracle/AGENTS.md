# AGENTS.md — ographuk oracle runtime

You implement the Oracle UK runtime. Your job is to turn raw external evidence
into stable entities, temporal observations, deterministic signals, and
candidate opportunities — with full provenance back to original bytes.

## Architecture

```text
EXTERNAL WORLD → RAW EVIDENCE → ENTITIES → OBSERVATIONS → SIGNALS
    → OPPORTUNITIES → SEESAW → AGENTCOM → OUTCOMES → ORACLE
```

**Boundary:** ographuk owns runtime (contracts, ingestion, normalization,
entity resolution, events, signals, opportunities, query). cgraphuk owns
semantics (verticals, pains, fixes, laws, campaigns). bq owns storage.
agentcomfinal owns actions.

## Module Map

| Module | Function | Status |
|--------|----------|--------|
| `ids.py` | Stable entity IDs + semantic record IDs (frozen fields) + semantic_root | LIVE (E1) |
| `contracts.py` | Schemas-as-code: all Oracle record types (+IngestRun, +Quarantine) | LIVE (E1) — real three-way parity enforced |
| `provenance.py` | Raw hashing + persisted RawEvidenceReceipts | LIVE (E1) |
| `normalize/companies_house.py` | CH parser: JSON + streaming ZIP/CSV → CanonicalBatch | LIVE (E1) — both fixtures → 5 entities + 44 obs |
| `sources/companies_house.py` | CH adapter (fixture/empty/failed/partial, deterministic watermark) + canonical source contract | LIVE (E1) |
| `sources/registry.py` | SourceRegistry v2 + preflight PolicyDecision + contract hash | LIVE (E1) — enforcement on |
| `batch.py` | CanonicalBatch: typed parser → runner boundary | LIVE (E1) |
| `exports/seesaw.py` | CandidateOpportunity → feature vector | LIVE — needs provenance-backed signal export |
| `cli.py` | Operator interface: ingest / replay / evidence / check | LIVE (E1) |
| `normalize/` | Taxonomy mapping, source → canonical | LIVE (E1) — CH parser; generic taxonomy pending |
| `resolve/` | Entity resolution, SAME_AS_CANDIDATE promotion | STUB (E4) |
| `signals/` | Versioned deterministic formula transforms | STUB (E7) |
| `opportunities/` | Opportunity detectors (supply gap, fragmentation, etc) | STUB (E9) |
| `probes/` | Probe requests for information acquisition | STUB (E8) |
| `mcp/` | MCP query interface (oracle.entity, .slice, .changes) | STUB (E6+) |
| `store/` | Append-only SQLite backend (+receipts/sources/raw_objects/opportunities) | LIVE (E1) — BQ adapter pending |
| `raw/` | Raw evidence store (hash-addressed filesystem) | LIVE (E1) — put/get/verify + tamper detection |
| `gates.py` | Quarantine gate runner | LIVE (E1) — receipt-aware RAW_HASH/RECEIPT wiring |
| `ingest/` | Ingest pipeline runner | LIVE (E1) — policy preflight, receipts, CanonicalBatch, semantic_root |

## Build Order (decdev.md §49)

Current track — E1 golden path proven on two formats (2026-09-15, 80 tests
green): `ORACLE_GOLDEN_PATH_V1` works locally for the JSON unit fixture AND
the real-format ZIP/CSV fixture (real CH headers, streaming rows, same 44
observations, same stable entities). Append-only store, semantic IDs with
frozen field sets, deterministic watermarks (re-ingest → 0 inserted,
identical semantic_root), receipt-aware gates, CanonicalBatch boundary,
registered source contracts bound into receipts, structured quarantine,
real three-way schema parity, CI workflow. Next: E2 live Companies House
adapter (bulk snapshot + streaming) against the seven official parts.

1. ~~Fix repository ownership wording~~ (done: README, DEVINSTRUCT)
2. Stable entity IDs vs immutable record IDs ← YOU ARE HERE
3. Harden canonical serializer (reject NaN/Inf)
4. Schema manifest (Python ↔ SQL parity enforcement)
5. Fix Relation semantics (evidence_refs, lineage_root, rename fields)
6. FetchResult (SUCCESS/SUCCESS_EMPTY/PARTIAL/FAILED)
7. Expand source rights contract
8. RawStore (local filesystem)
9. RawEvidenceReceipt v2
10. Record locators
11. OracleStore + SQLite backend
12. Ingest runner
13. Quarantine gates
14. Golden Companies House fixture
15. Remove arbitrary Seesaw feature injection
16. Signal registry skeleton

## Running Tests

```bash
cd /root/ographuk
python3 -m pytest tests/ -q
```

Tests must stay green. New code needs new tests.

## Extending

- **New source:** register Source (license + rights required) → adapter
  (implements FetchResult) → normalize map entry → heartbeat row.
- **New signal:** formula_id + version + inputs + test with frozen fixture.
- **New phase:** meet the DEVINSTRUCT DONE criteria verbatim, then tick
  README status.

## Inherited Laws

- Stdlib only (core). External adapters: pinned official deps only.
- Unknown = null. Never 0, never False, never "".
- Quarantine-first. Gates fire before promotion.
- No fuzzy joins in canonical truth.
- Raw evidence retained hash-addressed.
- No observation without provenance.
- No empty source ambiguity (FetchResult).
- Idempotent ingestion.
- Temporal is canonical. History never overwritten.
- Nothing becomes more true because an agent found it persuasive.
