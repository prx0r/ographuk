# ographuk — Canonical Oracle Build Instruction

*Saved 2026-09-14. Working brief for autonomous execution.*

## 0. Mission

Build `prx0r/ographuk` into the canonical **Oracle runtime**.

Oracle's sole purpose is:

```text
external reality
    ↓
raw attributable evidence
    ↓
stable entities
    ↓
observations + relationships + events
    ↓
deterministic signals
    ↓
candidate hypotheses/opportunities
    ↓
Seesaw
    ↓
AgentCom / products / trades / campaigns
    ↓
verified outcomes
    ↓
Oracle
```

The long-term asset is not graph software.

It is:

```text
historical UK observations
+
stable cross-source identities
+
change history
+
structured causal/economic signals
+
proprietary outcomes from things we actually build
```

---

# 1. Freeze repository ownership immediately

```text
ographuk
=
Oracle runtime
contracts
ingestion
normalization
entity resolution
events
signals
opportunities
query/MCP interfaces

cgraphuk
=
semantic/domain packs
vertical ontologies
pain/fix/regulation mappings
human-curated reference knowledge

bq
=
persistent analytical storage
BigQuery Graph
views
materializations

agentcomfinal
=
opportunity consumer
Seesaw
Autobuild
real-world actions
real outcomes
```

No future agent should have to decide whether ingestion belongs in `cgraphuk` or `ographuk`.

It belongs in `ographuk`.

---

# 2. Terminal acceptance condition

The first real Oracle proof is:

```text
one external raw record
        ↓
immutable raw evidence
        ↓
source receipt
        ↓
stable entity identity
        ↓
normalized observation
        ↓
second observation at later time
        ↓
deterministic change event
        ↓
deterministic signal
        ↓
candidate opportunity
        ↓
Seesaw export
        ↓
full evidence lineage back to the original bytes
```

That entire chain must work locally before BigQuery is necessary.

Call it:

```text
ORACLE_GOLDEN_PATH_V1
```

---

# 3. E0 is not complete yet

Do not tick E0 until all P0 gates below pass.

The current E0 implementation is scaffolding.

Preserve good existing ideas:

```text
full SHA-256 IDs
binary contract validation
three epistemic layers
raw retention
no fuzzy identity in canonical truth
deterministic Seesaw boundary
small generic BQ spine
```

But harden their semantics.

---

# 4. Split identity from content hashes

Not every object should use the same notion of identity.

## A. Stable entity identity

An entity represents the same thing through time.

Its ID must survive changes in name, status, address, rating, financials.

```python
entity_id(entity_type, namespace, external_key)
```

For example:
```text
entity_type = company
namespace   = companies-house
external_key = 01234567
→ stable EntityID
```

Hashing the canonical tuple internally is fine.
But `Acme Ltd active` must NOT determine company identity.

## B. Immutable record identity

Observations, signals, relation assertions, events, raw artifacts and hypotheses use content-derived IDs.

```text
ObservationID = H(entity, predicate, value, source, source-record, effective-time)
SignalID = H(formula-id, formula-version, ordered input IDs)
EventID = H(event-type, subject, triggering observation IDs)
RelationAssertionID = H(from, type, to, validity, evidence)
```

---

# 5. Harden canonical serialization

Current canonical JSON should not accept non-finite values.

Add tests that reject NaN, Infinity, -Infinity.

Canonical serialization must be deterministic across all supported inputs.

Use `allow_nan=False` and explicitly normalize:
- timestamps → UTC ISO-8601
- sets → sorted arrays before hashing
- decimals → canonical representation

No object's canonical identity can depend on dictionary insertion order.

---

# 6. Stop maintaining Python and SQL schemas independently

Create one canonical schema manifest:

```text
oracle/schema_manifest.py
```

containing logical fields/types for every record.

At minimum add `test_contract_sql_schema_parity` that fails when a canonical persisted field exists in one representation but not the other.

---

# 7. Fix Relation semantics

Rename `source_id`/`target_id` to `from_entity_id`/`to_entity_id`.

Canonical relation:

```json
{
  "relation_id": "...",
  "from_entity_id": "...",
  "to_entity_id": "...",
  "relation_type": "OPERATES_AT",
  "valid_from": null,
  "valid_to": null,
  "evidence_refs": [],
  "confidence": null,
  "lineage_root": "..."
}
```

A canonical relation with no evidence should fail.

---

# 8. Candidate identity resolution must be isolated

Never let fuzzy matching enter canonical graph truth accidentally.

Create `oracle_resolution_candidates` with states: CANDIDATE → PROMOTED / REJECTED.

Canonical graph traversal must ignore CANDIDATE matches by default.

---

# 9. Fix SourceAdapter before implementing any source

Current `fetch failure → []` is prohibited.

Implement `FetchResult` with:
- status: SUCCESS / SUCCESS_EMPTY / PARTIAL / FAILED
- artifacts, cursor, watermark
- snapshot_semantics: FULL / DELTA / STREAM / PARTIAL
- complete: true/false
- error: null/structured

---

# 10. Source Registry becomes an enforceable rights contract

Current gating only checks `license != ""`.

A source requires at minimum:
- commercial_use: ALLOWED / FORBIDDEN / UNKNOWN
- raw_storage: ALLOWED / FORBIDDEN / LIMITED / UNKNOWN
- redistribution: ALLOWED / FORBIDDEN / LIMITED / UNKNOWN
- attribution_required: bool
- personal_data_class: NONE / PUBLIC_PERSONAL / SENSITIVE_RESTRICTED

Fail closed.

---

# 11. Raw evidence store

Interface:
```text
RawStore.put(...) / get(hash) / exists(hash) / verify(hash)
```

First backend: `oracle/raw/local.py`
Path: `data/raw/<source>/<YYYY-MM-DD>/<sha256>`

---

# 12. Replace the current ingest receipt

Create `RawEvidenceReceipt` with full metadata including receipt_id = content hash of receipt semantic fields.

No normalized observation can exist without a receipt reference.

---

# 13. Record locator

An observation must identify the exact origin of a value.

```text
companies.csv#row=581922
file.json#/companies/13/status
stream:event:003829
```

Provenance: Observation → RawEvidenceReceipt → RawObject → record_locator

---

# 14. Observation v2

Canonical observation includes: observation_id, subject_entity_id, predicate, typed value, source_id, source_class, raw_receipt_id, record_locator, temporal fields, parser_version, normalizer_version, status, confidence, lineage_root.

Requirements: source required, raw receipt required, record locator required, time required.

---

# 15. Typed values

Use `value_json JSON` + `value_type STRING` for BQ.

Events: `payload JSON`. Outcomes: `metrics JSON`.

Do not serialize structured truth to opaque strings.

---

# 16. Temporal semantics

Frozen definitions:
- `observed_at` = when source measurement was observed
- `valid_from` = when source claims value became effective
- `valid_to` = when source claims it stopped being effective
- `ingested_at` = when Oracle received it

History is canonical. Never overwrite.

---

# 17. Full snapshots require completeness semantics

Any detector like `ENTITY_DISAPPEARED` must require a complete source boundary.

A partial snapshot missing company → NO disappearance event.

---

# 18. Persistence interface

Create `oracle/store/base.py`, `oracle/store/sqlite.py`, `oracle/store/bigquery.py`.

SQLite gives a fast stdlib-only local backend. BigQuery becomes a storage adapter.

---

# 19. Clarify "stdlib only"

Oracle core and local development path are stdlib-only.

External adapters MAY use pinned official dependencies (google-cloud-bigquery, MCP SDK).

---

# 20. Quarantine must become executable

Create `oracle/gates.py` with minimum local ingest gates:
- SOURCE_REGISTERED, RIGHTS_ALLOW_INGEST, RIGHTS_ALLOW_STORAGE
- RAW_HASH_VALID, RAW_RECEIPT_VALID
- PARSER_COMPLETED, PARSER_SCHEMA_RECOGNIZED
- NORMALIZED_RECORD_VALID, PROVENANCE_COMPLETE
- IDENTITY_VALID, TEMPORAL_FIELDS_VALID

Failure → quarantine. Never silently discard.

---

# 21. Ingest runner

Create `oracle/ingest/runner.py` with full pipeline and `IngestRunReceipt`.

Runs must be replayable.

---

# 22. Idempotence is a constitutional gate

Same raw object + parser version + normalizer version → same semantic output root.

---

# 23. E0 hardening test suite

Required tests before E1:
- test_canonical_rejects_nan
- test_entity_id_survives_name_change
- test_sql_contract_parity
- test_relation_requires_evidence
- test_observation_requires_raw_receipt
- test_observation_requires_record_locator
- test_confidence_range
- test_fetch_failure_not_empty
- test_partial_not_complete
- test_source_rights_fail_closed
- test_raw_storage_unknown_refused
- test_raw_store_roundtrip
- test_raw_hash_tamper_detected
- test_ingest_replay_idempotent
- test_partial_snapshot_cannot_emit_deletion
- test_unknown_is_null_not_false
- test_seesaw_rejects_unbacked_features

---

# 24-56. Implementation phases (see full brief)

See original DEVINSTRUCT.md and this file for complete E1-E10 spec.

---

# Build order (immediate)

1. Fix repository ownership wording in DEVINSTRUCT.md
2. Introduce stable entity IDs vs immutable record IDs
3. Harden canonical serializer against NaN/Inf
4. Create one canonical schema manifest
5. Fix Relation code/SQL drift
6. Implement FetchResult
7. Remove fetch failure → []
8. Expand source rights contract
9. Implement RawStore
10. Implement complete raw evidence receipts
11. Add record locators
12. Implement OracleStore + SQLite backend
13. Implement ingest runner
14. Implement quarantine gates
15. Add golden Companies House fixture
16. Prove replay/idempotence
17. Remove arbitrary Seesaw feature injection
18. Implement signal registry skeleton
19. Add CI
20. Only now tick E0/E1

---

# Doctrine

> **Nothing becomes more true merely because an agent found it persuasive.**

SOURCE reports something.
ORACLE OBSERVATION records exactly what was reported.
SIGNAL mechanically transforms observations.
HYPOTHESIS interprets signals.
SEESAW decides whether interpretation matters economically.
AGENTCOM acts.
QP verifies consequential transitions.
OUTCOME records what reality did afterward.
