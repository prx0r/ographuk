"""Signal registry. Versioned deterministic formula transforms.

DEVINSTRUCT §25. Signals are pure transforms: formula_id + version + inputs → value.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field

from oracle import ids


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
        """Hash of the compute method source for versioning."""
        try:
            source = self.compute.__code__.co_consts
            return hashlib.sha256(str(source).encode()).hexdigest()[:16]
        except AttributeError:
            return ""


class SignalRegistry:
    """Registry of versioned signal formulas."""

    def __init__(self):
        self._formulas: dict[str, SignalFormula] = {}

    def register(self, formula: SignalFormula) -> dict:
        key = f"{formula.formula_id}:{formula.version}"
        if key in self._formulas:
            return {"error": f"already registered: {key}"}
        self._formulas[key] = formula
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

        # Check required inputs
        missing = [k for k in formula.required_inputs if k not in inputs]
        if missing:
            return {"error": f"missing inputs: {missing}"}

        value = formula.compute(inputs)
        now = ids.canonical({"ts": "now"}).decode()[:19]  # placeholder

        return {
            "signal_id": ids.record_id("SIG", {
                "formula_id": formula_id,
                "formula_version": version,
                "input_ids": sorted(input_ids),
            }),
            "formula_id": formula_id,
            "formula_version": version,
            "input_ids": input_ids,
            "value": value,
            "computed_at": now,
            "code_hash": formula.code_hash(),
        }
