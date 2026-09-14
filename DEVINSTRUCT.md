# DEVINSTRUCT.md — Oracle UK Canonical Build Brief

*The single source of truth for what ographuk is, why it exists, and how to build it.*

---

## Mission

Build the canonical continually updating information graph for the UK.

Turn heterogeneous public, commercial and proprietary observations into a
temporally versioned, provenance-preserving graph that supports: Seesaw
investment allocation, AgentCom autonomous builds, UK business opportunity
detection, market research, lead generation, regulatory products, and future
autonomous businesses.

**Optimize for:** How much useful, attributable, queryable reality can the
system accumulate?

---

## Repository Ownership (Frozen)

```text
ographuk = Oracle runtime
            contracts, ingestion, normalization, entity resolution,
            events, signals, opportunities, query/MCP interfaces

cgraphuk = semantic/domain packs
           vertical ontologies, pain/fix/regulation mappings,
           campaigns, voice profiles, human-curated reference knowledge

bq       = persistent analytical storage
           BigQuery Graph, views, materializations, DDL

agentcomfinal = opportunity consumer
                Seesaw, Autobuild, real-world actions, real outcomes
```

**No future agent should have to decide where ingestion belongs.**
It belongs in ographuk.

---

## The Canonical Loop

```text
                    EXTERNAL WORLD
                          │
                    source adapters
                          │
                          ▼
                    RAW EVIDENCE (immutable, hash-addressed)
                          │
                          ▼
                      NORMALIZER
                          │
                          ▼
                   IDENTITY RESOLVER
                          │
                          ▼
                 ┌─────────────────┐
                 │  ORACLE FACTS   │
                 │  entities       │
                 │  observations   │
                 │  relationships  │
                 │  events         │
                 └────────┬────────┘
                          │
                          ▼
                  BIGQUERY GRAPH
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
           signals      slices       changes
              │
              ▼
           OPPORTUNITY DETECTORS
                          │
                          ▼
                  candidate hypotheses
                          │
                          ▼
                       SEESAW
                          │
            BUILD / TRADE / WATCH / DROP
                          │
                          ▼
                      AGENTCOM
                          │
                real products/actions
                          │
                          ▼
                      outcomes
                          │
                          └──────────────→ ORACLE
```

Oracle observes. Seesaw interprets economically. AgentCom acts. QP verifies.
**Do not collapse these responsibilities.**

---

## Three Epistemic Layers (Never Mix)

### Layer 1 — Observations
Things a source actually said. E.g.: `{subject: "COMP_01234567", predicate: "company.status", value: "active", source: "companies-house"}`

### Layer 2 — Derived Signals
Mechanical transformations. E.g.: `local_company_density = count(companies matching SIC within 5km)`. Every signal stores: formula_id, formula_version, input observation IDs.

### Layer 3 — Hypotheses / Opportunities
Interpretations. E.g.: "Manchester electricians may have unusually high demand relative to supply." Never facts. Stored separately with supporting + contradicting evidence.

---

## Oracle Data Model

Small generic spine. Domain SQL in views. **No more empty tables.**

```text
oracle_sources          source registry entries
oracle_ingest_runs      ingestion run receipts
oracle_raw_objects      hash-addressed raw evidence
oracle_entities         stable entity identities
oracle_identifiers      cross-system ID mappings
oracle_relations        entity-to-entity relationships
oracle_observations     temporal fact records
oracle_events           deterministic change records
oracle_signals          versioned formula outputs
oracle_hypotheses       candidate opportunities
oracle_outcomes         verified action results
```

---

## Entity Identity Rules

### Stable Entity Identity (survives attribute changes)
```python
entity_id(entity_type, namespace, external_key)
# e.g. company + companies-house + 01234567 → stable ID
```

### Immutable Record Identity (content-derived)
```text
ObservationID = H(entity, predicate, value, source, source-record, effective-time)
SignalID      = H(formula-id, formula-version, ordered input IDs)
EventID       = H(event-type, subject, triggering observation IDs)
```

---

## Source Interface Rules

### FetchResult (mandatory for all adapters)
```text
status:          SUCCESS | SUCCESS_EMPTY | PARTIAL | FAILED
snapshot_semantics: FULL | DELTA | STREAM | PARTIAL
complete:        bool
artifacts:       list
cursor:          str | None
watermark:       str | None
error:           dict | None
```

**FAILED ≠ SUCCESS_EMPTY.** Source outage is UNKNOWN. Empty data is factual.

### Source Rights (fail closed)
Every source requires: license, commercial_use, raw_storage, redistribution,
attribution_required, personal_data_class. If raw_storage=UNKNOWN and
raw_retention=true → source cannot run.

---

## Raw Evidence

```text
raw/<source>/<YYYY-MM-DD>/<sha256>.<format>
```

Every raw artifact gets a `RawEvidenceReceipt` with:
receipt_id, source_id, source_contract_hash, raw_sha256, raw_uri,
byte_length, media_type, fetched_at, response_status, snapshot_semantics,
complete, adapter_version, parser_version, ingest_run_id.

No normalized observation can exist without a receipt reference.

---

## Provenance Chain

```text
Observation
    ↓
RawEvidenceReceipt
    ↓
RawObject (hash-addressed bytes)
    ↓
record_locator (exact origin within the raw artifact)
```

---

## Temporal Semantics

- `observed_at` — when source measurement was observed
- `valid_from` — when source claims value became effective
- `valid_to` — when source claims it stopped being effective
- `ingested_at` — when Oracle received it

**Never overwrite.** Current state is a VIEW. History is canonical.

---

## Quarantine Gates

Every observation passes gates before promotion:

```text
SOURCE_REGISTERED          RIGHTS_ALLOW_INGEST         RIGHTS_ALLOW_STORAGE
RAW_HASH_VALID             RAW_RECEIPT_VALID            PARSER_COMPLETED
PARSER_SCHEMA_RECOGNIZED   NORMALIZED_RECORD_VALID      PROVENANCE_COMPLETE
IDENTITY_VALID             TEMPORAL_FIELDS_VALID
```

Failure → quarantine. Never silently discard.

---

## Persistence

```text
oracle/store/base.py       abstract OracleStore interface
oracle/store/sqlite.py     local stdlib backend (development)
oracle/store/bigquery.py   BQ adapter (when billing enabled)
```

SQLite for development. BigQuery for production. Same semantic tests against both.

---

## Phase Roadmap

### E0 — Oracle Contracts (IN PROGRESS)

**DONE when:**
- All record types have schemas + content-derived IDs
- Entity IDs survive attribute changes
- NaN/Inf rejected from canonical serialization
- Python ↔ SQL schema parity enforced
- FetchResult distinguishes SUCCESS_EMPTY / FAILED / PARTIAL
- Source rights fail closed
- RawStore implements hash-addressed local storage
- RawEvidenceReceipt v2 complete
- Record locators on all observations
- OracleStore + SQLite backend working
- Ingest runner produces IngestRunReceipt
- Quarantine gates fire on every observation
- Golden Companies House fixture passes replay/idempotence test
- Seesaw export uses Oracle-backed signals only
- Signal registry skeleton exists

### E1 — Raw/Provenance Pipeline

**DONE when:**
- Same payload → same raw hash
- Parser can replay from raw snapshot
- No observation lacks provenance
- Idempotent: re-ingest same fixture → zero new records

### E2 — Companies House Backbone

**DONE when:**
- Monthly bulk snapshot downloaded, hashed, stored
- Millions of companies parsed incrementally (memory bounded)
- Streaming changes attached
- Sample 100 companies: number resolves, name/status/SIC/postcode match
- Re-run same snapshot → zero semantic change

### E3 — Geography Spine

**DONE when:**
- company → registered_location → postcode → local_authority works

### E4 — Independent Cross-Source Proof

**DONE when:**
- FSA + CQC + procurement joined to Companies House entities
- At least one entity with ≥2 independent source namespaces
- False-match fixtures stored permanently

### E5 — Physical-Property Graph

**DONE when:**
- Land Registry + EPC + Planning joined
- location → transaction → energy → planning → nearby providers queryable

### E6 — Change Engine + MCP

**DONE when:**
- `oracle changes --since 24h` returns real events with provenance
- MCP tools: oracle.entity, .search, .slice, .changes, .evidence

### E7 — Market/Demand Graph

**DONE when:**
- Pinterest, Meta, TikTok, eBay daily snapshots running
- Proprietary history accumulating

### E8 — Signal Library

**DONE when:**
- 10+ deterministic signals versioned and auditable
- Signal → formula → observations → raw evidence traceable

### E9 — Opportunity Detectors

**DONE when:**
- 100 CandidateOpportunities generated
- Each has: ≥1 supporting signal, contradicting signals, ≥1 falsifier, ≥1 probe
- All Seesaw-exportable with full evidence lineage

### E10 — First Downstream Proof

**DONE when:**
- One Oracle opportunity → Seesaw decision → AgentCom build → real outcome → feedback into Oracle
- `oracle.evidence(outcome)` traces full chain

---

## Priority Sources (Implementation Order)

1. **Companies House** — bulk monthly snapshot + streaming API (free, 469MB/month)
2. **ONS / Nomis** — business populations, births/deaths, employment, vacancies
3. **FSA FHRS** — free keyless API, geocoded food businesses
4. **CQC** — daily-updated care provider API
5. **Contracts Finder + Find a Tender** — OCDS procurement data
6. **Planning Data** — 100+ England planning datasets via one API
7. **Land Registry** — Price Paid Data, monthly, OGL
8. **EPC** — energy performance certificates
9. **Gazette / Insolvency** — official notices, insolvency data
10. **Pinterest Trends** — daily snapshots create proprietary history
11. **Meta Ad Library** — ad intelligence
12. **TikTok Creative Centre** — trend intelligence

---

## What NOT to Build Now

- Graph visualization UI
- Neo4j / Spanner migration
- LLM embeddings over everything
- 50 source adapters at once
- Predictive ML
- Opaque opportunity scores
- Large agent swarms
- Full UPRN national ingestion
- All Companies House financial filings
- Perfect entity resolution
- Dashboards

**The binding constraint:** Can we turn bytes from reality into replayable,
trustworthy, temporal graph facts and use them to make one better decision?

---

## Doctrine

> **Nothing becomes more true merely because an agent found it persuasive.**

SOURCE reports something.
ORACLE OBSERVATION records exactly what was reported.
SIGNAL mechanically transforms observations.
HYPOTHESIS interprets signals.
SEESAW decides whether interpretation matters economically.
AGENTCOM acts.
QP verifies consequential transitions.
OUTCOME records what reality did afterward.
