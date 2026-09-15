"""OracleStore: abstract persistence interface.

DEVINSTRUCT §18. All canonical operations use OracleStore, not direct BQ calls.
SQLite for development, BQ for production.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class OracleStore(ABC):
    """Abstract Oracle persistence layer."""

    @abstractmethod
    def put_entity(self, entity: dict) -> dict:
        """Insert or update entity. Returns receipt."""

    @abstractmethod
    def get_entity(self, entity_id: str) -> dict | None:
        """Retrieve entity by ID."""

    @abstractmethod
    def put_identifier(self, identifier: dict) -> dict:
        """Insert identifier mapping."""

    @abstractmethod
    def put_relation(self, relation: dict) -> dict:
        """Insert or update relation."""

    @abstractmethod
    def put_observation(self, observation: dict) -> dict:
        """Insert observation."""

    @abstractmethod
    def get_observations(self, subject_entity_id: str,
                         predicate: str = None) -> list[dict]:
        """Get observations for an entity, optionally filtered by predicate."""

    @abstractmethod
    def get_observation(self, observation_id: str) -> dict | None:
        """Retrieve a single observation by ID."""

    @abstractmethod
    def count_observations(self) -> int:
        """Total observation rows (idempotence / replay checks)."""

    @abstractmethod
    def put_receipt(self, receipt: dict) -> dict:
        """Persist a RawEvidenceReceipt (idempotent on receipt_id)."""

    @abstractmethod
    def get_receipt(self, receipt_id: str) -> dict | None:
        """Retrieve a receipt by ID (lineage: observation → receipt)."""

    @abstractmethod
    def put_event(self, event: dict) -> dict:
        """Insert event."""

    @abstractmethod
    def put_signal(self, signal: dict) -> dict:
        """Insert signal."""

    @abstractmethod
    def put_hypothesis(self, hypothesis: dict) -> dict:
        """Insert hypothesis."""

    @abstractmethod
    def put_outcome(self, outcome: dict) -> dict:
        """Insert outcome."""

    @abstractmethod
    def begin_ingest_run(self, source_id: str) -> dict:
        """Start an ingest run. Returns run receipt."""

    @abstractmethod
    def commit_ingest_run(self, run_id: str, stats: dict) -> dict:
        """Finalize an ingest run with statistics."""

    @abstractmethod
    def quarantine(self, record: dict, reason: str) -> dict:
        """Quarantine a record that failed gates."""
