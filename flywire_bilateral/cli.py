"""Run an offline comparison and persist provenance and exclusion accounting."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from dataclasses import asdict, fields
from pathlib import Path

from . import __version__
from .analysis import Comparison, analyze
from .io import iter_edges, read_annotations
from .provenance import verify_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit bilateral connectivity comparison choices.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--connections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="CSV, plus <output>.audit.json")
    parser.add_argument("--snapshot", required=True, help="Human label; not a release check")
    parser.add_argument("--manifest", type=Path, help="Curated input hashes and materializations")
    parser.add_argument("--min-synapses", type=int, default=100)
    parser.add_argument("--min-neurons", type=int, default=1)
    parser.add_argument("--type-policy", choices=("combined", "cell_type"), default="combined")
    parser.add_argument(
        "--include-seg-types",
        action="store_true",
        help="Keep types containing outlier_seg neurons (sensitivity control)",
    )
    parser.add_argument(
        "--allow-missing-roots",
        action="store_true",
        help="Explicitly permit unmatched roots; release remains suspect",
    )
    args = parser.parse_args()
    audit_path = args.output.with_suffix(args.output.suffix + ".audit.json")
    protected = {args.annotations.resolve(), args.connections.resolve()}
    if args.manifest:
        protected.add(args.manifest.resolve())
    if args.output.resolve() in protected or audit_path.resolve() in protected:
        parser.error("Output would overwrite an input")
    # Prevent stale successful reports being mistaken for a new failed run.
    if args.output.exists() or audit_path.exists():
        parser.error("Output already exists; choose a new path or remove the old run explicitly")
    started = time.perf_counter()
    try:
        identity = verify_inputs(args.annotations, args.connections, args.manifest)
        annotations = read_annotations(
            args.annotations,
            type_policy=args.type_policy,
            exclude_seg_types=not args.include_seg_types,
        )
        if not annotations.neurons:
            raise ValueError("No typed left/right neurons found")
        result = analyze(
            annotations.neurons,
            iter_edges(args.connections),
            known_root_ids=annotations.root_ids,
            min_total_synapses=args.min_synapses,
            min_neurons_per_side=args.min_neurons,
        )
        missing = result.audit.missing_root_ids
        blocked = bool(missing) and not args.allow_missing_roots
        audit = {
            "software_version": __version__,
            "python": platform.python_version(),
            "argv": sys.argv[1:],
            "snapshot_label": args.snapshot,
            "provenance": identity,
            "type_policy": args.type_policy,
            "exclude_seg_types": not args.include_seg_types,
            "annotation_columns": annotations.columns,
            "annotation_counts": dict(sorted(annotations.counts.items())),
            "excluded_seg_types": annotations.excluded_seg_types,
            "edge_rows": dict(sorted(result.audit.rows.items())),
            "edge_synapses": dict(sorted(result.audit.synapses.items())),
            "total_rows": sum(result.audit.rows.values()),
            "total_synapses": sum(result.audit.synapses.values()),
            "missing_root_count": len(missing),
            "missing_root_sample": sorted(missing)[:20],
            "candidate_type_pairs": len(result.comparisons),
            "min_total_synapses": args.min_synapses,
            "min_neurons_per_side": args.min_neurons,
            "report_written": not blocked,
            "elapsed_seconds": time.perf_counter() - started,
            "warning": "Descriptive sensitivity analysis; not evidence of biological asymmetry.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if blocked:
            audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
            parser.error(
                f"{len(missing)} unmatched root IDs; see {audit_path}. "
                "Check releases or explicitly use --allow-missing-roots"
            )
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=[f.name for f in fields(Comparison)] + ["asymmetry_score"]
            )
            writer.writeheader()
            for row in result.comparisons:
                writer.writerow(asdict(row) | {"asymmetry_score": row.asymmetry_score})
        audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
        print(json.dumps(audit, indent=2, sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
