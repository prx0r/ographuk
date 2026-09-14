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
    exports/
      seesaw.py          CandidateOpportunity → feature vector
    normalize/           taxonomy mapping (E1 — stub)
    resolve/             entity resolution (E4 — stub)
    signals/             versioned formula transforms (E7 — stub)
    opportunities/       opportunity detectors (E9 — stub)
    probes/              probe request logic (E8 — stub)
    mcp/                 MCP query interface (E6+ — stub)
    store/               persistence layer (E0 — stub)
    raw/                 raw evidence store (E0 — stub)
    gates.py             quarantine gate runner (E0 — stub)
    ingest/              ingest pipeline runner (E0 — stub)
  schemas/
    001_oracle_core.sql  BigQuery DDL (11 tables, queued until billing on)
  fixtures/              golden test fixtures
  tests/
    conftest.py          test path setup
    test_contracts.py    E0 contract + validation tests
```

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| **E0** | Oracle contracts + IDs + hardening | **IN PROGRESS** — core contracts exist, hardening in progress |
| E1 | Raw/provenance pipeline | TODO — requires RawStore + FetchResult + receipts |
| E2 | Companies House backbone | TODO — requires E1 + live source adapter |
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
python -m oracle.cli ingest fixtures/companies_house_small.zip
python -m oracle.cli replay <raw_sha>
python -m oracle.cli evidence <observation_id>
```

With: entity IDs surviving name changes, NaN rejected, SQL/Python parity
enforced, FetchResult semantics, RawStore round-trip, quarantine gates
firing, Seesaw rejecting unbacked features, full provenance replay.
