"""Content-derived IDs and stable entity identity.

Two identity classes (DEVINSTRUCT §4):

A. Stable entity identity — survives attribute changes.
   entity_id(entity_type, namespace, external_key) → stable content hash
   of the tuple (entity_type, namespace, external_key), NOT of the entity's
   current attributes.

B. Immutable record identity — content-derived for observations, signals,
   events, relations, raw artifacts, hypotheses.
   record_id(prefix, **fields) → full 64-hex content hash.
"""
import hashlib
import json
import math


def _assert_finite(obj):
    """Reject NaN, Infinity, -Infinity in any nested structure."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"non-finite float rejected: {obj}")
    elif isinstance(obj, dict):
        for v in obj.values():
            _assert_finite(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _assert_finite(v)


def canonical(obj) -> bytes:
    """Deterministic JSON serialization. Rejects non-finite floats.
    Normalizes: sets → sorted arrays, None preserved, UTF-8."""
    _assert_finite(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- A. Stable entity identity ---

def entity_id(entity_type: str, namespace: str, external_key: str) -> str:
    """Stable entity ID. Survives name/status/address changes.
    Hash is over the tuple (type, namespace, key) only."""
    _assert_finite(entity_type)
    _assert_finite(namespace)
    _assert_finite(external_key)
    tuple_bytes = canonical({"t": entity_type, "n": namespace, "k": external_key})
    return entity_type.upper() + ":" + sha256_hex(tuple_bytes)


def entity_short(entity_type: str, namespace: str, external_key: str,
                 n: int = 8) -> str:
    """Display form for entity ID (e.g. COMP-XXXXXXXX). Never identity."""
    tuple_bytes = canonical({"t": entity_type, "n": namespace, "k": external_key})
    return entity_type.upper() + "-" + sha256_hex(tuple_bytes)[:n].upper()


# --- B. Immutable record identity ---

def record_id(prefix: str, obj) -> str:
    """Full 64-hex content ID for records. Display may truncate; identity never does."""
    _assert_finite(obj)
    return prefix + ":" + sha256_hex(canonical(obj))


def record_short(prefix: str, obj, n: int = 8) -> str:
    """Display form only (e.g. OBS-XXXXXXXX). Never identity."""
    _assert_finite(obj)
    return prefix + "-" + sha256_hex(canonical(obj))[:n].upper()


# --- Legacy aliases (remove after migration) ---

def obj_id(prefix: str, obj) -> str:
    """DEPRECATED: use record_id instead."""
    return record_id(prefix, obj)


def short(prefix: str, obj, n: int = 8) -> str:
    """DEPRECATED: use record_short instead."""
    return record_short(prefix, obj, n)
