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
| `ids.py` | Content-hash IDs (entity identity + record identity) | LIVE — needs entity ID split |
| `contracts.py` | Schemas-as-code: all Oracle record types | LIVE — needs schema parity with SQL |
| `provenance.py` | Raw hashing + ingest receipts | LIVE — needs RawEvidenceReceipt v2 |
| `sources/registry.py` | SourceRegistry v2: licensing + adapter interface | LIVE — needs FetchResult + rights expansion |
| `exports/seesaw.py` | CandidateOpportunity → feature vector | LIVE — needs provenance-backed signal export |
| `normalize/` | Taxonomy mapping, source → canonical | STUB (E1) |
| `resolve/` | Entity resolution, SAME_AS_CANDIDATE promotion | STUB (E4) |
| `signals/` | Versioned deterministic formula transforms | STUB (E7) |
| `opportunities/` | Opportunity detectors (supply gap, fragmentation, etc) | STUB (E9) |
| `probes/` | Probe requests for information acquisition | STUB (E8) |
| `mcp/` | MCP query interface (oracle.entity, .slice, .changes) | STUB (E6+) |
| `store/` | Persistence layer (SQLite local, BQ adapter) | STUB (E0) |
| `raw/` | Raw evidence store (hash-addressed filesystem) | STUB (E0) |
| `gates.py` | Quarantine gate runner | STUB (E0) |
| `ingest/` | Ingest pipeline runner | STUB (E0) |

## Build Order (decdev.md §49)

Current track — E0 hardening before E1:

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
