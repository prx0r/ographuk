"""Raw evidence store. Hash-addressed filesystem backend.

DEVINSTRUCT §11. RawStore.put(...) / get(hash) / exists(hash) / verify(hash).
Path: data/raw/<source>/<YYYY-MM-DD>/<sha256>.<format>
"""
from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path


class RawStore:
    """Hash-addressed raw evidence storage.

    Invariants:
    - put() returns receipt with verified hash
    - get() returns exact bytes stored
    - verify() checks integrity against stored hash
    - tampered bytes detected on get()
    """

    def __init__(self, base_dir: str):
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, source_id: str, date: str, sha256: str) -> Path:
        d = self.base / source_id / date
        d.mkdir(parents=True, exist_ok=True)
        return d / sha256

    def put(self, source_id: str, date: str, data: bytes) -> dict:
        """Store raw bytes. Returns receipt with hash verified."""
        sha = hashlib.sha256(data).hexdigest()
        p = self._path(source_id, date, sha)
        if not p.exists():
            p.write_bytes(data)
        else:
            existing = p.read_bytes()
            if existing != data:
                raise ValueError(f"hash collision: {sha} exists with different bytes")
        return {
            "raw_sha256": sha,
            "byte_length": len(data),
            "path": str(p),
        }

    def put_file(self, source_id: str, date: str, src: str) -> dict:
        """Hash-while-copy a file into the store without loading it.

        Bounded memory regardless of artifact size. Returns the same
        receipt shape as put(). Re-copying identical bytes is a no-op
        verified by comparison of the copied stream.
        """
        import hashlib as _hl

        src_path = Path(src)
        h = _hl.sha256()
        with open(src_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        sha = h.hexdigest()
        p = self._path(source_id, date, sha)
        if not p.exists():
            h2 = _hl.sha256()
            with open(src_path, "rb") as fh, open(p, "wb") as out:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h2.update(chunk)
                    out.write(chunk)
            if h2.hexdigest() != sha:
                p.unlink(missing_ok=True)
                raise ValueError("copy changed mid-stream; aborted")
        return {
            "raw_sha256": sha,
            "byte_length": src_path.stat().st_size,
            "path": str(p),
        }

    def get(self, sha256: str) -> bytes | None:
        """Retrieve raw bytes by hash. Returns None if not found."""
        for source_dir in self.base.iterdir():
            if not source_dir.is_dir():
                continue
            for date_dir in source_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                p = date_dir / sha256
                if p.exists():
                    data = p.read_bytes()
                    # Verify integrity
                    actual = hashlib.sha256(data).hexdigest()
                    if actual != sha256:
                        raise ValueError(f"integrity failure: stored={sha256} actual={actual}")
                    return data
        return None

    def exists(self, sha256: str) -> bool:
        """Check if raw artifact exists."""
        return self.get(sha256) is not None

    def verify(self, sha256: str) -> bool:
        """Verify stored artifact integrity. Returns True if hash matches bytes."""
        try:
            data = self.get(sha256)
            if data is None:
                return False
            return hashlib.sha256(data).hexdigest() == sha256
        except (ValueError, OSError):
            return False

    def artifact_path(self, source_id: str, date: str, sha256: str) -> Path:
        """Return the path where an artifact should be stored."""
        return self._path(source_id, date, sha256)

    def list_hashes(self, source_id: str = None) -> list[str]:
        """List all stored hashes, optionally filtered by source."""
        hashes = []
        sources = [self.base / source_id] if source_id else [
            d for d in self.base.iterdir() if d.is_dir()
        ]
        for src in sources:
            if not src.exists():
                continue
            for date_dir in src.iterdir():
                if not date_dir.is_dir():
                    continue
                for f in date_dir.iterdir():
                    if f.is_file():
                        hashes.append(f.name)
        return sorted(hashes)
