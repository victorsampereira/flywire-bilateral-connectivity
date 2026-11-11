"""Download only the checksum-pinned official files needed for this analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    result = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/data_manifest.json"))
    parser.add_argument("--directory", type=Path, default=Path("data"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.directory.mkdir(parents=True, exist_ok=True)
    retrieved = {}
    for name, record in manifest["files"].items():
        path = args.directory / record["filename"]
        if not path.exists():
            partial = path.with_suffix(path.suffix + ".part")
            print(f"Downloading {record['url']}", flush=True)
            with (
                urllib.request.urlopen(record["url"], timeout=120) as response,
                partial.open("wb") as handle,
            ):
                while block := response.read(1024 * 1024):
                    handle.write(block)
            if digest(partial, "sha256") != record["sha256"]:
                raise ValueError(f"Checksum mismatch: {partial}; retained for inspection")
            partial.replace(path)
        if digest(path, "sha256") != record["sha256"]:
            raise ValueError(f"Checksum mismatch: {path}; refusing to overwrite")
        if "publisher_md5" in record and digest(path, "md5") != record["publisher_md5"]:
            raise ValueError(f"Publisher checksum mismatch: {path}")
        retrieved[name] = {
            "path": str(path),
            "sha256": record["sha256"],
            "verified_utc": datetime.now(timezone.utc).isoformat(),
        }
        print(f"Verified {path}", flush=True)
    (args.directory / "retrieval.json").write_text(json.dumps(retrieved, indent=2) + "\n")


if __name__ == "__main__":
    main()
