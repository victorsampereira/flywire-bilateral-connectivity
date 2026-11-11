"""Exercise gzip reading, data provenance constraints and row validation."""

import csv
import gzip
from pathlib import Path

import pytest

from flywire_bilateral.io import iter_edges, read_neurons


def test_read_neurons_filters_unknown_side_and_untyped(tmp_path: Path):
    path = tmp_path / "annotations.tsv"
    path.write_text("root_id\tside\tcell_type\n1\tleft\tA\n2\tright\tA\n3\tcenter\tB\n4\tleft\t\n")
    assert set(read_neurons(path)) == {1, 2}


def test_duplicate_ids_fail_instead_of_overwriting(tmp_path: Path):
    path = tmp_path / "a.tsv"
    path.write_text("root_id\tside\tcell_type\n1\tleft\tA\n1\tright\tB\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_neurons(path)


def test_connection_gzip_streaming_and_extra_columns(tmp_path: Path):
    path = tmp_path / "connections.csv.gz"
    with gzip.open(path, "wt", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows(
            [
                ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"],
                [1, 2, "AL", 13, "ACH"],
            ]
        )
    [(edge)] = list(iter_edges(path))
    assert (edge.pre_root_id, edge.post_root_id, edge.syn_count) == (1, 2, 13)


def test_invalid_count_is_rejected_with_line_number(tmp_path: Path):
    path = tmp_path / "c.csv"
    path.write_text("pre_root_id,post_root_id,syn_count\n1,2,0\n")
    with pytest.raises(ValueError, match=":2:"):
        list(iter_edges(path))


def test_missing_columns_fail_early(tmp_path: Path):
    path = tmp_path / "c.csv"
    path.write_text("pre_root_id,post_root_id\n1,2\n")
    with pytest.raises(ValueError, match="syn_count"):
        list(iter_edges(path))
