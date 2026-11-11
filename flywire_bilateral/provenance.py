"""Content identities and explicit release assertions, separate from scientific logic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_inputs(
    annotations: Path,
    connections: Path,
    manifest: Path | None,
) -> dict[str, Any]:
    """Verify file identity against a curated manifest when supplied.

    The manifest asserts release semantics; hashes alone cannot prove that the
    publisher's labels or the manifest's scientific assertions are correct.
    """
    inputs = {
        name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for name, path in (("annotations", annotations), ("connections", connections))
    }
    if manifest is None:
        return {"status": "unverified_release", "inputs": inputs}
    data = json.loads(manifest.read_text())
    entries = data["files"]
    versions = {entries[name]["materialization"] for name in inputs}
    if len(versions) != 1:
        raise ValueError("Manifest materializations differ")
    for name, identity in inputs.items():
        if identity["sha256"] != entries[name]["sha256"]:
            raise ValueError(f"Manifest checksum mismatch for {name}")
    return {
        "status": "matched_curated_manifest",
        "manifest_sha256": sha256(manifest),
        "materialization": versions.pop(),
        "inputs": inputs,
    }
