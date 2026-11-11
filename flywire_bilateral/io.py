"""Strict annotation readers and bounded-memory CSV/Feather connection readers."""

from __future__ import annotations

import csv
import gzip
import re
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TextIO, cast

from .analysis import Neuron, Side, SynapticEdge

TypePolicy = Literal["combined", "cell_type"]


@contextmanager
def open_text(path: Path) -> Iterator[TextIO]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        yield handle


def require_columns(fieldnames: Sequence[str] | None, columns: set[str], path: Path) -> None:
    missing = columns - set(fieldnames or [])
    if missing:
        raise ValueError(f"{path}: missing required columns: {', '.join(sorted(missing))}")
    if fieldnames and len(fieldnames) != len(set(fieldnames)):
        raise ValueError(f"{path}: duplicate column names")


def positive_integer(value: object) -> int:
    """Never round 64-bit root IDs through floating point or accept decimal counts."""
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise ValueError(f"Expected positive integer, got {value!r}")
    result = int(str(value))
    if result <= 0:
        raise ValueError("Connection values and root IDs must be positive")
    return result


@dataclass
class Annotations:
    neurons: dict[int, Neuron]
    root_ids: set[int]
    counts: Counter[str]
    excluded_seg_types: list[str]
    columns: list[str]


def read_annotations(
    path: Path,
    *,
    type_policy: TypePolicy = "combined",
    exclude_seg_types: bool = True,
) -> Annotations:
    """Use the authors' cell_type→hemibrain_type fallback, with an audit.

    Exclude an entire type if ANY member has status outlier_seg, avoiding
    asymmetric removal of individual members. Keep biological outliers.
    Validate IDs before filtering, including untyped/nonlateral records.
    """
    if type_policy not in ("combined", "cell_type"):
        raise ValueError("Unknown type policy")
    ids: set[int] = set()
    neurons: dict[int, Neuron] = {}
    counts: Counter[str] = Counter()
    seg_types: set[str] = set()
    with open_text(path) as handle:
        reader = csv.DictReader(handle, delimiter="\t" if ".tsv" in path.suffixes else ",")
        require_columns(reader.fieldnames, {"root_id", "cell_type", "side"}, path)
        columns = list(reader.fieldnames or [])
        for line_no, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}:{line_no}: malformed annotation row")
            try:
                root_id = positive_integer(row["root_id"])
            except ValueError as exc:
                raise ValueError(f"{path}:{line_no}: invalid root_id") from exc
            if root_id in ids:
                raise ValueError(f"{path}:{line_no}: duplicate root_id {root_id}")
            ids.add(root_id)
            counts["total"] += 1
            cell_type = row["cell_type"].strip()
            if not cell_type and type_policy == "combined":
                cell_type = row.get("hemibrain_type", "").strip()
                if cell_type:
                    counts["fallback_typed"] += 1
            if cell_type and row.get("status", "").strip() == "outlier_seg":
                seg_types.add(cell_type)
            side = row["side"].strip().lower()
            if not cell_type:
                counts["untyped"] += 1
            elif side not in ("left", "right"):
                counts["nonlateral"] += 1
            else:
                neurons[root_id] = Neuron(root_id, cell_type, cast(Side, side))
        if exclude_seg_types:
            neurons = {i: n for i, n in neurons.items() if n.cell_type not in seg_types}
        counts["excluded_seg_type"] = (
            len(ids) - counts["untyped"] - counts["nonlateral"] - len(neurons)
        )
        counts["eligible"] = len(neurons)
    return Annotations(
        neurons, ids, counts, sorted(seg_types) if exclude_seg_types else [], columns
    )


def read_neurons(path: Path) -> dict[int, Neuron]:
    """Return eligible neurons under the default annotated-release policy."""
    return read_annotations(path).neurons


def edge_columns(names: list[str], path: Path) -> tuple[str, str, str]:
    schemas = [
        ("pre_root_id", "post_root_id", "syn_count"),
        ("pre_pt_root_id", "post_pt_root_id", "syn_count"),
    ]
    matches = [schema for schema in schemas if set(schema) <= set(names)]
    if len(matches) != 1:
        raise ValueError(f"{path}: require exactly one pre/post schema and syn_count")
    require_columns(names, set(matches[0]), path)
    return matches[0]


def iter_edges(path: Path) -> Iterator[SynapticEdge]:
    """Stream CSV/gzip or Feather v2 record batches (optional PyArrow).

    Both official Zenodo and Codex column names are recognized. Rows split
    across neuropils are intentionally summed by the analysis, not deduplicated.
    """
    if path.suffix == ".feather":
        yield from _iter_feather(path)
        return
    with open_text(path) as handle:
        reader = csv.DictReader(handle)
        columns = edge_columns(list(reader.fieldnames or []), path)
        for line_no, row in enumerate(reader, 2):
            try:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError("Malformed row")
                yield SynapticEdge(*(positive_integer(row[c]) for c in columns))
            except ValueError as exc:
                raise ValueError(f"{path}:{line_no}: invalid connection row: {exc}") from exc


def _iter_feather(path: Path) -> Iterator[SynapticEdge]:
    try:
        import pyarrow as pa
        import pyarrow.ipc as ipc
    except ImportError as exc:
        raise ValueError("Feather input requires pip install '.[data]'") from exc
    with pa.memory_map(str(path), "r") as source:
        reader = ipc.open_file(source)
        columns = edge_columns(reader.schema.names, path)
        for col in columns:
            if not pa.types.is_integer(reader.schema.field(col).type):
                raise ValueError(f"{path}: {col} must have integer storage")
        offset = 0
        for batch_index in range(reader.num_record_batches):
            batch = reader.get_batch(batch_index).select(list(columns))
            arrays = [batch.column(i).to_pylist() for i in range(3)]
            for row_index, (pre, post, count) in enumerate(zip(*arrays), 1):
                if pre is None or post is None or count is None or min(pre, post, count) <= 0:
                    raise ValueError(f"{path}:row {offset + row_index}: invalid connection values")
                yield SynapticEdge(pre, post, count)
            offset += batch.num_rows
