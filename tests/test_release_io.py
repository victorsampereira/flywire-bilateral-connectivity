"""Real export schemas without shipping or downloading scientific data in CI."""

import json
import subprocess
import sys

import pytest

from flywire_bilateral.io import iter_edges
from flywire_bilateral.provenance import sha256, verify_inputs


def test_feather_batches_match_csv_and_preserve_large_ids(tmp_path):
    pa = pytest.importorskip("pyarrow")
    ipc = pytest.importorskip("pyarrow.ipc")
    feather = tmp_path / "official.feather"
    csv = tmp_path / "official.csv"
    pre, post = 720575940600000001, 720575940600000003
    schema = pa.schema(
        [
            ("pre_pt_root_id", pa.uint64()),
            ("post_pt_root_id", pa.uint64()),
            ("syn_count", pa.int64()),
            ("neuropil", pa.string()),
        ]
    )
    with ipc.new_file(str(feather), schema) as writer:
        for n in (2, 3):
            writer.write_batch(pa.record_batch([[pre], [post], [n], ["AL_L"]], schema=schema))
    csv.write_text(
        f"pre_pt_root_id,post_pt_root_id,syn_count,neuropil\n{pre},{post},2,AL_L\n{pre},{post},3,AL_L\n"
    )
    assert list(iter_edges(csv)) == list(iter_edges(feather))
    assert list(iter_edges(feather))[0].pre_root_id == pre


@pytest.mark.parametrize("value", ["1.0", "1e18", "NaN", "-1", "0"])
def test_csv_rejects_noninteger_identifiers(tmp_path, value):
    path = tmp_path / "bad.csv"
    path.write_text(f"pre_root_id,post_root_id,syn_count\n{value},2,3\n")
    with pytest.raises(ValueError, match="invalid connection"):
        list(iter_edges(path))


def test_manifest_rejects_tampering_and_mixed_materializations(tmp_path):
    a, c, m = [tmp_path / x for x in ("a", "c", "manifest.json")]
    a.write_text("annotation data")
    c.write_text("connection data")
    records = {
        "files": {
            key: {"sha256": sha256(path), "materialization": 783}
            for key, path in (("annotations", a), ("connections", c))
        }
    }
    m.write_text(json.dumps(records))
    assert verify_inputs(a, c, m)["status"] == "matched_curated_manifest"
    records["files"]["connections"]["materialization"] = 630
    m.write_text(json.dumps(records))
    with pytest.raises(ValueError, match="materializations"):
        verify_inputs(a, c, m)
    records["files"]["connections"]["materialization"] = 783
    m.write_text(json.dumps(records))
    c.write_text("changed")
    with pytest.raises(ValueError, match="checksum"):
        verify_inputs(a, c, m)


def test_cli_missing_roots_fail_with_persisted_audit_and_no_report(tmp_path):
    a, c, out = [tmp_path / x for x in ("a.csv", "c.csv", "report.csv")]
    a.write_text("root_id,cell_type,side\n1,A,left\n2,A,right\n")
    c.write_text("pre_root_id,post_root_id,syn_count\n999,1,10\n")
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "flywire_bilateral",
            "--annotations",
            str(a),
            "--connections",
            str(c),
            "--output",
            str(out),
            "--snapshot",
            "test",
        ],
        capture_output=True,
        text=True,
    )
    assert run.returncode != 0 and "unmatched root IDs" in run.stderr
    assert not out.exists()
    audit = json.loads(out.with_suffix(".csv.audit.json").read_text())
    assert audit["missing_root_count"] == 1 and audit["report_written"] is False


def test_feather_rejects_floating_point_identifiers(tmp_path):
    pa = pytest.importorskip("pyarrow")
    feather = pytest.importorskip("pyarrow.feather")
    path = tmp_path / "bad.feather"
    feather.write_feather(
        pa.table({"pre_pt_root_id": [1.0], "post_pt_root_id": [2], "syn_count": [3]}), path
    )
    with pytest.raises(ValueError, match="integer storage"):
        list(iter_edges(path))
