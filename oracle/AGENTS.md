# AGENTS.md — ographuk oracle runtime

You implement DEVINSTRUCT.md phases E0–E10. cgraphuk owns semantics; bq owns
state; agentcomfinal consumes opportunities and produces outcomes.

## Module functions

| Module | Function | Status |
|---|---|---|
| `ids.py`, `provenance.py` | content-hash IDs, raw hashing, ingest receipts | LIVE + tested |
| `contracts.py` | E0 schemas-as-code, binary validate() | LIVE + tested |
| `sources/registry.py` | SourceRegistry v2 (licensing enforced) + adapter interface | LIVE + tested |
| `exports/seesaw.py` | candidate → feature vector (no Seesaw scoring here) | LIVE + tested |
| `sources/companies_house.py` + rest | per-source adapters (E2+) | TODO (E2) |
| `normalize/`, `resolve/` | taxonomy map, SAME_AS_CANDIDATE → SAME_AS promotion | TODO (E1/E4) |
| `signals/`, `opportunities/`, `probes/` | versioned transforms, detectors, ProbeRequests | TODO (E7–E9) |
| `mcp/` | oracle.entity/.search/.slice/.changes/.evidence/.opportunities/.signal | TODO (E6+) |

## Laws (DEVINSTRUCT + doctrine)

Stdlib only. Unknown=null. Quarantine-first (killfeed2 G1–G11 on write path).
No placeholders. No LLM verdicts — deterministic gates only. Raw retained
hash-addressed (`raw/<source>/<date>/<sha>`). No observation without provenance.
No fuzzy joins in truth (SAME_AS_CANDIDATE edges carry confidence/method).
No new empty tables — every schema justified by live data (the 45-empty-table
mistake). BQ DDL queued until billing enabled.

## Commands

```bash
python3 -m pytest tests/ -q     # must stay green
```

## Extending

New source: register Source (license required) → adapter (fail-soft fetch) →
normalize map entry → heartbeat row. New signal: formula_id + version + inputs
+ test with frozen fixture. New phase: meet the DEVINSTRUCT DONE criteria
verbatim, then tick README.
