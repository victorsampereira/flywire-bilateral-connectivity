import csv
import subprocess
import sys
from pathlib import Path


def test_cli_produces_ranked_report(tmp_path: Path):
    annotations = tmp_path / "a.tsv"
    connections = tmp_path / "c.csv"
    report = tmp_path / "output.csv"
    annotations.write_text(
        "root_id\tside\tcell_type\n1\tleft\tA\n2\tright\tA\n3\tleft\tB\n4\tright\tB\n"
    )
    connections.write_text("pre_root_id,post_root_id,syn_count\n1,3,50\n2,4,10\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flywire_bilateral",
            "--annotations",
            str(annotations),
            "--connections",
            str(connections),
            "--output",
            str(report),
            "--snapshot",
            "SYNTHETIC",
            "--min-synapses",
            "1",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert '"candidate_type_pairs": 1' in result.stdout
    with report.open(newline="") as handle:
        [row] = list(csv.DictReader(handle))
    assert row["source_type"] == "A"
    assert row["target_type"] == "B"
    assert float(row["signed_asymmetry"]) == (50 - 10) / (50 + 10)


def test_cli_handles_invalid_annotation_file(tmp_path: Path):
    missing = tmp_path / "missing.tsv"
    connections = tmp_path / "connections.csv"
    connections.write_text("pre_root_id,post_root_id,syn_count\n1,2,10\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "flywire_bilateral",
            "--annotations",
            str(missing),
            "--connections",
            str(connections),
            "--output",
            str(tmp_path / "out.csv"),
            "--snapshot",
            "SYNTHETIC",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr
