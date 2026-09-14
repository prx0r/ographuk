"""Content-derived IDs. Full SHA-256, always (cgraphuk rule + agentcomfinal core/ids.py pattern)."""
import hashlib
import json


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def obj_id(prefix: str, obj) -> str:
    """Full 64-hex content id. Display may truncate; identity never does."""
    return prefix + ":" + sha256_hex(canonical(obj))


def short(prefix: str, obj, n: int = 8) -> str:
    """Display form only (e.g. COMP-XXXXXXXX). Never identity."""
    return prefix + "-" + sha256_hex(canonical(obj))[:n].upper()
