-- 001_oracle_core.sql — generic Oracle spine (DEVINSTRUCT §5).
-- Small generic tables; domain SQL lives in views. Queued until BQ billing on.
CREATE TABLE IF NOT EXISTS `drop.oracle_sources` (
  source_id STRING NOT NULL, jurisdiction STRING, access STRING,
  auth_class STRING, cost FLOAT64, license STRING,
  allowed_uses ARRAY<STRING>, prohibited_uses ARRAY<STRING>, cadence STRING,
  entity_keys ARRAY<STRING>, raw_retention BOOL, adapter STRING,
  parser_version STRING, last_success TIMESTAMP, cursor STRING, schema_hash STRING
);
CREATE TABLE IF NOT EXISTS `drop.oracle_ingest_runs` (
  run_id STRING NOT NULL, source_id STRING NOT NULL, started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP, status STRING, rows_in INT64, rows_out INT64, error STRING
);
CREATE TABLE IF NOT EXISTS `drop.oracle_raw_objects` (
  raw_sha256 STRING NOT NULL, source_id STRING NOT NULL, raw_uri STRING,
  parser_version STRING, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS `drop.oracle_entities` (
  entity_id STRING NOT NULL, entity_type STRING NOT NULL, country STRING,
  canonical_name STRING, status STRING, created_at TIMESTAMP,
  verification STRING DEFAULT 'HYPOTHESIS', basis STRING
);
CREATE TABLE IF NOT EXISTS `drop.oracle_identifiers` (
  entity_id STRING NOT NULL, id_type STRING NOT NULL, id_value STRING NOT NULL
);
CREATE TABLE IF NOT EXISTS `drop.oracle_relations` (
  source_id STRING NOT NULL, target_id STRING NOT NULL, rel_type STRING NOT NULL,
  valid_from TIMESTAMP, valid_to TIMESTAMP, grade STRING, confidence FLOAT64,
  source_refs ARRAY<STRING>, lineage_root STRING
);
CREATE TABLE IF NOT EXISTS `drop.oracle_observations` (
  subject STRING NOT NULL, predicate STRING NOT NULL, value STRING,
  source STRING NOT NULL, source_class STRING, observed_at TIMESTAMP,
  valid_from TIMESTAMP, valid_to TIMESTAMP, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  raw_sha256 STRING NOT NULL, status STRING DEFAULT 'OBSERVED',
  confidence FLOAT64, basis STRING
)
PARTITION BY DATE(ingested_at)
CLUSTER BY subject, predicate;
CREATE TABLE IF NOT EXISTS `drop.oracle_events` (
  event_type STRING NOT NULL, subject STRING, observed_at TIMESTAMP,
  payload STRING, ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
PARTITION BY DATE(ingested_at)
CLUSTER BY event_type;
CREATE TABLE IF NOT EXISTS `drop.oracle_signals` (
  signal_id STRING NOT NULL, formula_id STRING NOT NULL, formula_version STRING,
  input_ids ARRAY<STRING>, value FLOAT64, computed_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS `drop.oracle_hypotheses` (
  hypothesis_id STRING NOT NULL, thesis STRING, supporting ARRAY<STRING>,
  contradicting ARRAY<STRING>, falsifiers ARRAY<STRING>, grade STRING
);
CREATE TABLE IF NOT EXISTS `drop.oracle_outcomes` (
  subject STRING NOT NULL, action STRING, metrics STRING, observed_at TIMESTAMP
);
