"""Signal registry. Versioned deterministic formula transforms.

DEVINSTRUCT §25. Signals are pure transforms: formula_id + version + inputs → value.

Identity vs metadata, kept strict:
- signal_id covers (formula_id, formula_version, sorted input_ids) ONLY.
  computed_at / code_hash are audit metadata and never enter identity.
- code_hash fingerprints the normalized compute() source plus declared
  config. If the implementation changes without a version bump, compute
  fails closed instead of silently rewriting history.
"""

from __future__ import annotations

import hashlib
import inspect
import time
from dataclasses import dataclass, field

from oracle import ids


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class SignalFormula:
    """A registered signal formula."""
    formula_id: str
    version: str = "v1"
    description: str = ""
    required_inputs: list = field(default_factory=list)
    output_type: str = "float"     # float / int / bool

    def compute(self, inputs: dict) -> float | int | bool | None:
        """Override in subclasses. Return computed value or None."""
        raise NotImplementedError

    def code_hash(self) -> str:
        """Fingerprint of normalized compute() source + declared config.

        Whitespace-normalized so formatting churn does not rotate the hash;
        any semantic edit does.
        """
        try:
            source = inspect.getsource(self.compute)
        except (OSError, TypeError):
            return ""
        normalized = "\n".join(
            line.strip() for line in source.strip().splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        blob = "\n".join([
            normalized,
            f"required_inputs={sorted(self.required_inputs)}",
            f"output_type={self.output_type}",
        ])
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class SignalRegistry:
    """Registry of versioned signal formulas."""

    def __init__(self):
        self._formulas: dict[str, SignalFormula] = {}
        self._hashes: dict[str, str] = {}

    def register(self, formula: SignalFormula) -> dict:
        key = f"{formula.formula_id}:{formula.version}"
        if key in self._formulas:
            return {"error": f"already registered: {key}"}
        self._formulas[key] = formula
        self._hashes[key] = formula.code_hash()
        return {"registered": key}

    def get(self, formula_id: str, version: str = "v1") -> SignalFormula | None:
        return self._formulas.get(f"{formula_id}:{version}")

    def list(self) -> list[str]:
        return sorted(self._formulas.keys())

    def compute_signal(self, formula_id: str, version: str,
                       input_ids: list[str], inputs: dict) -> dict:
        """Compute a signal and return the Signal record."""
        formula = self.get(formula_id, version)
        if formula is None:
            return {"error": f"unknown formula: {formula_id}:{version}"}

        # Fail closed on implementation drift without a version bump.
        key = f"{formula_id}:{version}"
        current_hash = formula.code_hash()
        if current_hash and self._hashes.get(key) != current_hash:
            return {"error": f"formula_impl_changed_without_version_bump:{key}"}

        # Check required inputs
        missing = [k for k in formula.required_inputs if k not in inputs]
        if missing:
            return {"error": f"missing inputs: {missing}"}

        value = formula.compute(inputs)

        return {
            "signal_id": ids.signal_id(formula_id, version, input_ids),
            "formula_id": formula_id,
            "formula_version": version,
            "input_ids": input_ids,
            "value": value,
            "computed_at": _utcnow(),
            "code_hash": current_hash,
        }
