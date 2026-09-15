-- 001_oracle_core.sql — generic Oracle spine (DEVINSTRUCT §5).
-- Small generic tables; domain SQL lives in views.
-- Updated to match Python schema_manifest.py (devdev.md §6).
-- Queued until BQ billing on.

CREATE TABLE IF NOT EXISTS `drop.oracle_sources` (
  source_id STRING NOT NULL,
  jurisdiction STRING,
  access STRING,
  auth_class STRING,
  cost FLOAT64,
  license STRING,
  terms_url STRING,
  terms_hash STRING,
  commercial_use STRING DEFAULT 'UNKNOWN',
  raw_storage STRING DEFAULT 'UNKNOWN',
  redistribution STRING DEFAULT 'UNKNOWN',
  attribution_required BOOL DEFAULT FALSE,
  personal_data_class STRING DEFAULT 'NONE',
  allowed_uses ARRAY<STRING>,
  prohibited_uses ARRAY<STRING>,
  cadence STRING,
  entity_keys ARRAY<STRING>,
  raw_retention BOOL DEFAULT TRUE,
  adapter STRING,
  parser_version STRING DEFAULT 'v1',
  last_success TIMESTAMP,
  cursor STRING,
  schema_hash STRING
);

CREATE TABLE IF NOT EXISTS `drop.oracle_ingest_runs` (
  run_id STRING NOT NULL,
  source_id STRING NOT NULL,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP,
  status STRING DEFAULT 'running',
  rows_in INT64 DEFAULT 0,
  rows_out INT64 DEFAULT 0,
  quarantined INT64 DEFAULT 0,
  error STRING,
  semantic_root STRING DEFAULT '',
  rows_inserted INT64 DEFAULT 0,
  rows_existing INT64 DEFAULT 0
);

CREATE TABLE IF NOT EXISTS `drop.oracle_raw_objects` (
  raw_sha256 STRING NOT NULL,
  source_id STRING NOT NULL,
  raw_uri STRING,
  byte_length INT64 DEFAULT 0,
  media_type STRING DEFAULT '',
  parser_version STRING DEFAULT 'v1',
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `drop.oracle_entities` (
  entity_id STRING NOT NULL,
  entity_type STRING NOT NULL,
  country STRING DEFAULT 'GB',
  canonical_name STRING DEFAULT '',
  status STRING DEFAULT 'active',
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `drop.oracle_identifiers` (
  entity_id STRING NOT NULL,
  id_type STRING NOT NULL,
  id_value STRING NOT NULL
);

CREATE TABLE IF NOT EXISTS `drop.oracle_relations` (
  relation_id STRING NOT NULL,
  from_entity_id STRING NOT NULL,
  to_entity_id STRING NOT NULL,
  relation_type STRING NOT NULL,
  evidence_refs ARRAY<STRING>,
  confidence FLOAT64,
  lineage_root STRING DEFAULT '',
  valid_from TIMESTAMP,
  valid_to TIMESTAMP
);
CREATE TABLE IF NOT EXISTS `drop.oracle_observations` (
  observation_id STRING NOT NULL,
  subject_entity_id STRING NOT NULL,
  predicate STRING NOT NULL,
  value JSON,
  value_type STRING DEFAULT 'string',
  source_id STRING NOT NULL,
  source_class STRING DEFAULT '',
  raw_receipt_id STRING NOT NULL,
  record_locator STRING NOT NULL,
  observed_at TIMESTAMP NOT NULL,
  valid_from TIMESTAMP,
  valid_to TIMESTAMP,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  parser_version STRING DEFAULT '',
  normalizer_version STRING DEFAULT '',
  status STRING DEFAULT 'OBSERVED',
  confidence FLOAT64,
  lineage_root STRING DEFAULT ''
)
PARTITION BY DATE(ingested_at)
CLUSTER BY subject_entity_id, predicate;

CREATE TABLE IF NOT EXISTS `drop.oracle_events` (
  event_id STRING NOT NULL,
  event_type STRING NOT NULL,
  subject STRING DEFAULT '',
  observed_at TIMESTAMP NOT NULL,
  payload JSON,
  triggering_observation_ids ARRAY<STRING>,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
PARTITION BY DATE(ingested_at)
CLUSTER BY event_type;

CREATE TABLE IF NOT EXISTS `drop.oracle_signals` (
  signal_id STRING NOT NULL,
  formula_id STRING NOT NULL,
  formula_version STRING DEFAULT 'v1',
  input_ids ARRAY<STRING>,
  value FLOAT64,
  computed_at TIMESTAMP NOT NULL,
  code_hash STRING DEFAULT ''
);

CREATE TABLE IF NOT EXISTS `drop.oracle_hypotheses` (
  hypothesis_id STRING NOT NULL,
  thesis STRING DEFAULT '',
  supporting ARRAY<STRING>,
  contradicting ARRAY<STRING>,
  falsifiers ARRAY<STRING>
);

CREATE TABLE IF NOT EXISTS `drop.oracle_outcomes` (
  outcome_id STRING NOT NULL,
  opportunity_id STRING DEFAULT '',
  campaign_id STRING DEFAULT '',
  action STRING NOT NULL,
  metrics JSON,
  evidence_refs ARRAY<STRING>,
  qp_receipt_ids ARRAY<STRING>,
  observed_at TIMESTAMP NOT NULL,
  verification_status STRING DEFAULT 'UNVERIFIED'
);

CREATE TABLE IF NOT EXISTS `drop.oracle_quarantine` (
  quarantine_id STRING NOT NULL,
  record_type STRING NOT NULL,
  record_data JSON,
  gate_failures ARRAY<STRING>,
  quarantined_at TIMESTAMP NOT NULL,
  source_id STRING DEFAULT '',
  run_id STRING DEFAULT '',
  stage STRING DEFAULT '',
  failure_code STRING DEFAULT '',
  receipt_id STRING DEFAULT '',
  record_locator STRING DEFAULT ''
);

CREATE TABLE IF NOT EXISTS `drop.oracle_opportunities` (
  opportunity_id STRING NOT NULL,
  detector_id STRING DEFAULT '',
  detector_version STRING DEFAULT 'v1',
  subject STRING DEFAULT '',
  type STRING DEFAULT '',
  thesis STRING DEFAULT '',
  supporting_signal_ids ARRAY<STRING>,
  contradicting_signal_ids ARRAY<STRING>,
  unknowns ARRAY<STRING>,
  affected_entity_ids ARRAY<STRING>,
  possible_moat ARRAY<STRING>,
  falsifiers ARRAY<STRING>,
  probe_request_ids ARRAY<STRING>,
  input_root STRING DEFAULT '',
  created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS `drop.oracle_receipts` (
  receipt_id STRING NOT NULL,
  source_id STRING NOT NULL,
  source_contract_hash STRING DEFAULT '',
  raw_sha256 STRING NOT NULL,
  raw_uri STRING DEFAULT '',
  byte_length INT64 DEFAULT 0,
  media_type STRING DEFAULT '',
  compression STRING DEFAULT '',
  fetched_at TIMESTAMP NOT NULL,
  request_fingerprint STRING DEFAULT '',
  response_status INT64 DEFAULT 0,
  snapshot_semantics STRING DEFAULT 'FULL',
  complete BOOL DEFAULT TRUE,
  cursor STRING DEFAULT '',
  watermark STRING DEFAULT '',
  adapter_version STRING DEFAULT '',
  parser_version STRING DEFAULT 'v1',
  ingest_run_id STRING DEFAULT ''
);
