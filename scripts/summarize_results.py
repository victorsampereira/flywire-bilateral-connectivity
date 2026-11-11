"""Regenerate the small review artifact from full local analysis outputs."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    directory = Path("results")
    summaries = {}
    for variant in ("v783", "v783_combined_all", "v783_cell_type_only"):
        audit = json.loads((directory / f"{variant}.csv.audit.json").read_text())
        summaries[variant] = {
            key: audit[key]
            for key in (
                "annotation_counts",
                "edge_rows",
                "edge_synapses",
                "total_rows",
                "total_synapses",
                "candidate_type_pairs",
                "missing_root_count",
                "type_policy",
                "exclude_seg_types",
            )
        }
    report = directory / "v783.csv"
    digest = file_hash(report)
    repeated = file_hash(directory / "v783_repeat.csv") == digest
    if not repeated:
        raise ValueError("Repeated report differs")
    with report.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    sensitivity = []
    for threshold in (100, 500, 1000):
        selected = [
            r for r in rows if int(r["left_synapses"]) + int(r["right_synapses"]) >= threshold
        ]
        comparable = [r for r in selected if r["input_fraction_asymmetry"] != ""]
        flipped = [
            r
            for r in comparable
            if float(r["signed_asymmetry"]) * float(r["input_fraction_asymmetry"]) < 0
        ]
        substantial = [
            r
            for r in flipped
            if min(abs(float(r["signed_asymmetry"])), abs(float(r["input_fraction_asymmetry"])))
            >= 0.2
        ]
        sensitivity.append(
            {
                "min_total_synapses": threshold,
                "rows": len(selected),
                "both_measures_defined": len(comparable),
                "opposite_sign": len(flipped),
                "opposite_sign_both_abs_at_least_0.2": len(substantial),
            }
        )
    examples = [("PS137", "CB2825", "same"), ("Tm9", "CT1", "opposite"), ("CB0980", "JO-E", "same")]
    selected_examples = [
        r for r in rows if (r["source_type"], r["target_type"], r["relation"]) in examples
    ]
    final = {
        "dataset": "FAFB 783 / annotations v2.1.0",
        "policies": summaries,
        "report_sha256": digest,
        "repeat_byte_identical": repeated,
        "report_relations": dict(Counter(r["relation"] for r in rows)),
        "normalization_sensitivity": sensitivity,
        "exploratory_examples": selected_examples,
        "independent_validation": json.loads((directory / "validation.json").read_text()),
    }
    path = Path("docs/reference_results.json")
    path.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n")
    print(path)


if __name__ == "__main__":
    main()
