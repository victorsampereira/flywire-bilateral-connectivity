"""Dataset integrity must be checked before a download becomes an input."""

import hashlib
import io
import json
import runpy
import sys
from pathlib import Path

import pytest

main = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/download_data.py"))["main"]


def test_download_checksum_failure_leaves_only_partial_file(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": {
                    "annotations": {
                        "filename": "a.tsv",
                        "url": "https://example.invalid/a.tsv",
                        "sha256": hashlib.sha256(b"expected").hexdigest(),
                    }
                }
            }
        )
    )
    monkeypatch.setattr(
        sys, "argv", ["download_data.py", "--manifest", str(manifest), "--directory", str(tmp_path)]
    )
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **kw: io.BytesIO(b"corrupted"))
    with pytest.raises(ValueError, match="Checksum mismatch"):
        main()
    assert not (tmp_path / "a.tsv").exists()
    assert (tmp_path / "a.tsv.part").read_bytes() == b"corrupted"


def test_verified_cached_download_does_not_use_network(tmp_path, monkeypatch):
    content = b"root_id,cell_type,side\n1,A,left\n"
    path = tmp_path / "a.csv"
    path.write_bytes(content)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "files": {
                    "annotations": {
                        "filename": "a.csv",
                        "url": "https://example.invalid/a.csv",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                }
            }
        )
    )
    monkeypatch.setattr(
        sys, "argv", ["download_data.py", "--manifest", str(manifest), "--directory", str(tmp_path)]
    )

    def no_network(*args, **kwargs):
        pytest.fail("Valid cached inputs must not be downloaded again")

    monkeypatch.setattr("urllib.request.urlopen", no_network)
    main()
    assert path.read_bytes() == content
    assert (
        json.loads((tmp_path / "retrieval.json").read_text())["annotations"]["sha256"]
        == hashlib.sha256(content).hexdigest()
    )
