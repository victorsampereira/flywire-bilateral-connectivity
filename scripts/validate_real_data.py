"""Independent SQL verification of every default-report row and published examples.

Requires .[data,validation]. Does not import the analysis or annotation reader.
A mismatch fails the command and is written into validation.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--report", type=Path, default=Path("results/v783.csv"))
    parser.add_argument("--output", type=Path, default=Path("results/validation.json"))
    args = parser.parse_args()
    audit = json.loads(args.report.with_suffix(".csv.audit.json").read_text())
    if audit["type_policy"] != "combined" or not audit["exclude_seg_types"]:
        raise ValueError("This independent check targets the default selection policy")
    connection = duckdb.connect()
    connection.execute("SET memory_limit='2GB'")
    connection.execute("SET threads=2")
    connection.execute(
        """CREATE TABLE annotations AS
        SELECT CAST(root_id AS UBIGINT) AS id,
               COALESCE(NULLIF(trim(cell_type), ''), NULLIF(trim(hemibrain_type), '')) AS type,
               side, status, cell_class, hemibrain_type
        FROM read_csv(?, delim='\t', header=true, all_varchar=true)""",
        [str(args.data / "annotations_v2.1.0.tsv")],
    )
    connection.execute("""CREATE TABLE eligible AS SELECT * FROM annotations n
        WHERE type IS NOT NULL AND side IN ('left','right')
        AND NOT EXISTS (SELECT 1 FROM annotations s
                        WHERE s.type=n.type AND s.status='outlier_seg')""")
    with pa.memory_map(str(args.data / "proofread_connections_783.feather"), "r") as source:
        reader = ipc.open_file(source)
        schema = (
            reader.get_batch(0).select(["pre_pt_root_id", "post_pt_root_id", "syn_count"]).schema
        )
        batches = pa.RecordBatchReader.from_batches(
            schema,
            (reader.get_batch(i).select(schema.names) for i in range(reader.num_record_batches)),
        )
        connection.register("batches", batches)
        connection.execute(
            "CREATE TABLE edges AS SELECT pre_pt_root_id AS pre, post_pt_root_id AS post, syn_count AS n FROM batches"
        )
    connection.execute("""CREATE TABLE grouped AS
        SELECT p.type AS source_type, q.type AS target_type,
               CASE WHEN p.side=q.side THEN 'same' ELSE 'opposite' END AS relation,
               SUM(CASE WHEN p.side='left' THEN e.n ELSE 0 END) AS l,
               SUM(CASE WHEN p.side='right' THEN e.n ELSE 0 END) AS r
        FROM edges e JOIN eligible p ON e.pre=p.id JOIN eligible q ON e.post=q.id
        WHERE e.pre<>e.post GROUP BY 1,2,3""")
    connection.execute("""CREATE TABLE populations AS SELECT type,
        COUNT(*) FILTER (WHERE side='left') AS l, COUNT(*) FILTER (WHERE side='right') AS r
        FROM eligible GROUP BY type""")
    connection.execute("""CREATE TABLE budgets AS SELECT q.type,
        SUM(CASE WHEN q.side='left' THEN e.n ELSE 0 END) AS l,
        SUM(CASE WHEN q.side='right' THEN e.n ELSE 0 END) AS r
        FROM edges e JOIN eligible q ON e.post=q.id WHERE e.pre<>e.post GROUP BY q.type""")
    expected = connection.execute(
        """SELECT g.*, p.l, p.r,
        CASE WHEN relation='same' THEN q.l ELSE q.r END,
        CASE WHEN relation='same' THEN q.r ELSE q.l END,
        b.l, b.r FROM grouped g JOIN populations p ON source_type=p.type
        JOIN populations q ON target_type=q.type JOIN budgets b ON target_type=b.type
        WHERE g.l+g.r>=? AND least(p.l,p.r,q.l,q.r)>=?
        ORDER BY source_type,target_type,relation""",
        [audit["min_total_synapses"], audit["min_neurons_per_side"]],
    ).fetchall()
    with args.report.open(newline="") as handle:
        actual_rows = list(csv.DictReader(handle))
    actual = {
        (right["source_type"], right["target_type"], right["relation"]): right
        for right in actual_rows
    }
    errors = []
    if len(actual) != len(expected) or len(actual_rows) != len(actual):
        errors.append("Row count or uniqueness mismatch")
    for (
        src,
        dst,
        relation,
        left,
        right,
        source_left,
        source_right,
        target_left,
        target_right,
        budget_left,
        budget_right,
    ) in expected:
        if relation == "opposite":
            budget_left, budget_right = budget_right, budget_left
        row = actual.get((src, dst, relation))
        if row is None:
            errors.append(f"Missing row: {(src, dst, relation)}")
            continue
        counts = dict(
            left_synapses=left,
            right_synapses=right,
            left_source_neurons=source_left,
            right_source_neurons=source_right,
            left_target_neurons=target_left,
            right_target_neurons=target_right,
            left_target_input_budget=budget_left,
            right_target_input_budget=budget_right,
        )
        fractions = dict(
            left_per_source=left / source_left,
            right_per_source=right / source_right,
            left_per_target=left / target_left,
            right_per_target=right / target_right,
            left_input_fraction=left / budget_left if budget_left else None,
            right_input_fraction=right / budget_right if budget_right else None,
        )
        fractions["raw_asymmetry"] = (left - right) / (left + right)
        fractions["signed_asymmetry"] = (left / source_left - right / source_right) / (
            left / source_left + right / source_right
        )
        fractions["target_asymmetry"] = (left / target_left - right / target_right) / (
            left / target_left + right / target_right
        )
        fractions["asymmetry_score"] = abs(fractions["signed_asymmetry"])
        fractions["input_fraction_asymmetry"] = (
            (
                (left / budget_left - right / budget_right)
                / (left / budget_left + right / budget_right)
            )
            if budget_left and budget_right
            else None
        )
        for key, value in counts.items():
            if int(row[key]) != value:
                errors.append(f"{src}/{dst}/{relation}: {key}")
        for key, value in fractions.items():
            if (value is None and row[key] != "") or (
                value is not None
                and (
                    row[key] == ""
                    or not math.isclose(float(row[key]), value, rel_tol=1e-12, abs_tol=1e-12)
                )
            ):
                errors.append(f"{src}/{dst}/{relation}: {key}")
    references = []
    for src, dst, expected_counts in [
        ("LTe56", "DNp42", [0, 34]),
        ("LHCENT3", "LHAV3g2", [30, 23]),
    ]:
        observed = connection.execute(
            """SELECT
            COALESCE(SUM(e.n) FILTER (WHERE p.side='left'),0),
            COALESCE(SUM(e.n) FILTER (WHERE p.side='right'),0)
            FROM edges e JOIN annotations p ON e.pre=p.id JOIN annotations q ON e.post=q.id
            WHERE p.type=? AND q.type=? AND p.side=q.side AND e.pre<>e.post""",
            [src, dst],
        ).fetchone()
        references.append(
            {
                "source": src,
                "target": dst,
                "published": expected_counts,
                "observed": list(observed),
                "match": list(observed) == expected_counts,
            }
        )
    kc = dict(
        connection.execute(
            "SELECT side,COUNT(*) FROM annotations WHERE cell_class='Kenyon_Cell' GROUP BY side"
        ).fetchall()
    )
    root_ids = {right[0] for right in connection.execute("SELECT id FROM annotations").fetchall()}
    proofread = set(np.load(args.data / "proofread_root_ids_783.npy", allow_pickle=False).tolist())
    totals = connection.execute("SELECT COUNT(*), SUM(n) FROM edges").fetchone()
    summary = {
        "report_rows_checked": len(actual),
        "mismatch_count": len(errors),
        "first_mismatches": errors[:10],
        "published_examples": references,
        "kenyon_counts": kc,
        "kenyon_published_match": kc == {"left": 2580, "right": 2597},
        "annotation_proofread_id_sets_equal": root_ids == proofread,
        "proofread_neurons": len(proofread),
        "connection_rows": totals[0],
        "synapses": totals[1],
        "edge_totals_match_audit": list(totals) == [audit["total_rows"], audit["total_synapses"]],
        "duckdb_version": duckdb.__version__,
        "note": "PLP146 is the hemibrain alias of combined type LTe56 in v2.1.0.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if (
        errors
        or not all(right["match"] for right in references)
        or not summary["kenyon_published_match"]
        or not summary["annotation_proofread_id_sets_equal"]
        or not summary["edge_totals_match_audit"]
    ):
        raise SystemExit("Validation failed: inspect the saved summary")


if __name__ == "__main__":
    main()
