# ographuk — Oracle UK runtime (oraclegraph)

First-class layer: world data → verified observations → entities/relationships →
signals → candidate opportunities → **Seesaw** → products/trades/campaigns →
real outcomes → better Oracle.

- **Build brief:** `DEVINSTRUCT.md` (full E0–E10 spec, source priority, schemas).
- **Semantics/ontology:** `prx0r/cgraphuk` (24 verticals, pains, fixes, laws,
  campaigns, namespaces, index.json feed).
- **BQ state/catalog:** `prx0r/bq` (schemas live in `schemas/` here; state in BigQuery).
- **Consumer/outcomes:** `prx0r/agentcomfinal` (Seesaw allocation, builds).

Loop discipline: Oracle observes. Seesaw interprets economically. AgentCom acts.
QP verifies consequential outcomes. Never collapse these.

## Layout (per DEVINSTRUCT §32)

```
ographuk/
  DEVINSTRUCT.md       the brief (E0–E10, sources, schemas)
  README.md            this file
  oracle/
    AGENTS.md          module functions + gates (operator manual)
    ids.py             content-hash IDs (tested)
    contracts.py       schemas-as-code: all 10 E0 objects (tested)
    provenance.py      raw hashing + receipt helpers (tested)
    sources/registry.py  SourceRegistry v2: licensing + adapter interface
    exports/seesaw.py  CandidateOpportunity → feature vector (tested)
    normalize/ resolve/ signals/ opportunities/ probes/ mcp/  (stubs per phase)
  schemas/
    001_oracle_core.sql  oracle_* spine (11 tables)
  fixtures/ tests/
```

## Phase status (DEVINSTRUCT §34)

- [ ] E0 contract (schemas + content IDs — `contracts.py`+`ids.py` now exist, unreviewed)
- [ ] E1 raw/provenance pipeline · E2 company spine · E3 geography … E10 proof

## Rules (inherited)

Stdlib only. Unknown=null. Quarantine-first (killfeed2 gates). No placeholders.
No BQ writes unreceipted. Billing-gated BQ DDL runs only after owner enables
billing (sandbox 403 as of 2026-09-14) — local-first meanwhile.
