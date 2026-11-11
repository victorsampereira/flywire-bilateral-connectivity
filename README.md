# FlyWire bilateral comparison audit

[![Tests](https://github.com/victorsampereira/flywire-bilateral-connectivity/actions/workflows/tests.yml/badge.svg)](https://github.com/victorsampereira/flywire-bilateral-connectivity/actions/workflows/tests.yml)

An offline analysis of how **annotation coverage, neuronal laterality and
normalization affect bilateral cell-type connectivity comparisons** in FlyWire.
Use it to check which observations enter a comparison and whether its conclusion
depends on the denominator, before investigating a circuit anatomically.

The reference run covers the complete v783 proofread connectivity export:
**16,847,997 connection rows and 54,492,922 synapses**. Independent SQL verifies
all **48,986** default report rows, and two published circuit examples reproduce
exactly. See the [findings](docs/FINDINGS.md) for the evidence and limitations.

The tool verifies input checksums, audits excluded records, applies the published
`cell_type` → `hemibrain_type` fallback, and compares both same-side and
opposite-side relations. It reports raw counts, counts per source and target,
and shares of observed target inputs. No credentials are needed.

This is an independent reproducibility study. Bilateral comparison, cell matching
and connectivity similarity are established methods implemented by
[cocoa](https://github.com/flyconnectome/cocoa),
[fafbseg](https://github.com/navis-org/fafbseg-py), and
[navis](https://github.com/navis-org/navis).
[Related work](docs/RELATED_WORK.md) explains the scope of this analysis.

## Install and reproduce

Python 3.10+. CSV analysis has no runtime dependencies. PyArrow reads the official
Feather data; DuckDB and NumPy are used only for independent real-data verification.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test,data,validation]'
python scripts/download_data.py
python -m flywire_bilateral \
  --annotations data/annotations_v2.1.0.tsv \
  --connections data/proofread_connections_783.feather \
  --manifest docs/data_manifest.json \
  --snapshot 'FAFB v783 / annotations v2.1.0' \
  --output results/v783.csv
python scripts/validate_real_data.py
```

Download size is approximately 880 MB. Large data and generated reports are
ignored by Git. The downloader verifies existing files instead of replacing
them, and verifies downloaded bytes before promoting `.part` files. It does
not need a CAVE token or Codex login. Outputs must not already exist: use a fresh
path for each run. See [validation](docs/VALIDATION.md) for repeat/sensitivity
commands and [findings](docs/FINDINGS.md) for measured results and limits.

A quick synthetic demonstration needs no data download:

```sh
python -m flywire_bilateral \
  --annotations examples/synthetic_annotations.tsv \
  --connections examples/synthetic_connections.csv \
  --snapshot SYNTHETIC --min-synapses 1 --output results/example.csv
```

## Reading the output

Each row compares a directed type pair in either `same` (L→L versus R→R) or
`opposite` (L→R versus R→L) relation. Left/right refers to the **source** side,
not the synapse location. Target counts and budgets follow the destination side.
Both types must exist on both sides; population counts include zero-edge neurons.

The CSV includes raw counts, population sizes, counts per source/target,
observed input fractions, and their signed contrasts. `signed_asymmetry` is
(xL − xR)/(xL + xR) using counts per source. Ranking uses its absolute value;
this is descriptive, **not statistical significance**. Missing fractions are
empty fields. The default 100 combined-synapse threshold is a reporting heuristic.

`results/v783.csv.audit.json` records hashes, release verification, settings,
annotation coverage, row/synapse exclusion partitions, missing roots, software
version and runtime. Unknown roots fail by default. `--manifest` checks known
input identities; `--snapshot` alone cannot establish release compatibility.

`--type-policy cell_type` and `--include-seg-types` expose the annotation controls.
The default excludes entire types containing a segmentation outlier, while
retaining biological outliers. Input budgets include untyped and nonlateral
sources, but only connections present in the supplied proofread export.

## Verification and documentation

```sh
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

CI runs synthetic and realistic-schema tests on Python 3.10 and 3.13. It does
not download the scientific dataset. The manually triggered
[Reference dataset validation](https://github.com/victorsampereira/flywire-bilateral-connectivity/actions/workflows/validate-data.yml)
workflow downloads the pinned inputs, recomputes the full report, verifies it
independently and checks the reference CSV hash. Results and audit records are
available as workflow artifacts. The same checks can be run locally.

- [Scientific context and related work](docs/RELATED_WORK.md)
- [Methods, denominator definitions and limitations](docs/METHODOLOGY.md)
- [Dataset provenance and checksums](docs/data_manifest.json)
- [Validation and exact commands](docs/VALIDATION.md)
- [Observed findings](docs/FINDINGS.md)

Core modules separate numerical analysis, data reading, provenance and CLI.
The `compare_hemispheres` API returns same-side comparisons only; use
`analyze` for both relations and exclusion accounting.

One brain, annotation labels and observed counts cannot establish biological
asymmetry. Reconstruction and detection biases remain, and target-input fractions
are based on proofread partners rather than complete anatomical inputs.
The work has not undergone external scientific review and does not estimate
biological asymmetry probabilities.

## Attribution and licensing

Software is MIT-licensed; see [LICENSE](LICENSE). Scientific inputs are not relicensed
by this repository: the Zenodo record specifies CC BY 4.0; the annotation GitHub
repository has no standalone license file in the inspected tree. Fetch those
inputs from their authors and follow their citation/usage instructions. This
repository does not redistribute the annotation table or connectivity export.
Cite [Schlegel et al.](https://doi.org/10.1038/s41586-024-07686-5) and
[Dorkenwald et al.](https://doi.org/10.1038/s41586-024-07558-y), together with the
[dataset DOI](https://doi.org/10.5281/zenodo.10676866), when using this reference run.
