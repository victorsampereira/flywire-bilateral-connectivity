# Validation and reproduction record

## What was executed

- Full official v783 proofread connectivity, publication-era annotations v2.1.0,
  and official proofread root-ID array; publisher MD5 and local SHA-256 verified.
- Default analysis, identical repeat, combined-type/all-status control, and
  cell-type-only/all-status control, each scanning the entire dataset.
- Independent DuckDB recomputation of every default output row, both published
  circuit examples and published KC counts. Zero mismatches.
- 34 local tests, Ruff lint, Ruff formatting check and strict mypy on the package.
- Editable installation reports version 0.2.0; a wheel builds successfully and
  includes the CLI, package source, `py.typed` marker and license.
- CI runs the tests, Ruff and strict mypy on Python 3.10 and 3.13, including
  optional Feather tests.
- The full reference validation was also run on a GitHub-hosted Ubuntu runner
  ([run 42939139229](https://github.com/victorsampereira/flywire-bilateral-connectivity/actions/runs/42939139229),
  11 November 2026 UTC): the official inputs were downloaded and verified,
  16,847,997 rows / 54,492,922 synapses were processed, all 48,986 report rows
  were checked independently, and the report SHA-256 matched the reference hash
  below, the same hash produced locally on macOS arm64.

Full results are in [FINDINGS.md](FINDINGS.md); the small tracked
[reference_results.json](reference_results.json) is a deliberate review/regression
artifact. Large source data and output CSVs remain ignored. Installed validation
dependencies are recorded in [validation_environment.txt](validation_environment.txt)
from Python 3.15.2 on macOS 26.5.2 arm64. That file records this environment; older
Python versions may require older compatible dependency releases.

## Remote reproduction

The `Reference dataset validation` workflow can be run manually from GitHub
Actions. It downloads and verifies the official inputs, recomputes the full
report, runs the independent SQL checks and checks the reference CSV hash.
Its artifact contains the CSV, audit, validation summary and retrieval record.
The standard push/PR workflow runs the tests and static checks without large
data downloads.

## Exact commands

From the repository root, create an environment and install as in README. The
following function is POSIX-shell compatible and avoids ambiguous snapshot labels:

```sh
python scripts/download_data.py
run_audit() {
  python -m flywire_bilateral \
    --annotations data/annotations_v2.1.0.tsv \
    --connections data/proofread_connections_783.feather \
    --manifest docs/data_manifest.json \
    --snapshot 'FAFB v783 / annotations v2.1.0' "$@"
}
run_audit --output results/v783.csv
run_audit --output results/v783_repeat.csv
cmp results/v783.csv results/v783_repeat.csv
run_audit --include-seg-types --output results/v783_combined_all.csv
run_audit --include-seg-types --type-policy cell_type \
  --output results/v783_cell_type_only.csv
python scripts/validate_real_data.py
python scripts/summarize_results.py
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m mypy
```

Use a clean output directory or fresh output names; the CLI deliberately refuses
to overwrite an existing CSV or audit. The controls retain both relations;
select `relation=same` from `v783_cell_type_only.csv` to inspect the
cell-type-only, same-side selection. The 500/1,000 threshold results are filtered
from the default report because all denominators are computed before filtering.

The CSV is deterministic for identical bytes/settings. JSON audit records include
runtime and invocation paths and are not expected to be byte-identical. Reference
CSV SHA-256:

```text
b2e6ad579194ee6710c6ad7cd7add7777c63952386931ed318073bc9c67d512b
```

For performance measurement on macOS, prefix `run_audit`'s Python invocation
with `/usr/bin/time -l` (on Linux use `/usr/bin/time -v`). Raw local timings are
under `results/*.performance.txt`. Peak memory includes mapped input pages;
streaming avoids retaining neuron-level edges, but type aggregates and reports
still consume memory proportional to the number of distinct type/side pairs.

## Test coverage and interpretation

Tests protect mirror-sign symmetry, source/target normalization, destination-side
budgets, whole-type exclusion, fallback precedence, zero-budget missingness,
annotation-independent input denominators, row/synapse conservation, region-split
summation, thresholds, deterministic ordering, large integer IDs, strict schemas,
gzip and multiple Arrow record batches. They also test wrong-release manifests,
tampered downloads, duplicate IDs in excluded rows and failure on missing roots.
They use small invented data in real export schemas, not redistributed FlyWire
observations.

The independent SQL checker uses different grouping/join machinery and does not
import our analysis or annotation parser. It still implements the same documented
scientific definition, so agreement is a software check, not independent evidence
that the definition answers a biological question. Published numerical anchors
provide additional external checks but are only two circuits and a population count.

## Remaining scientific work

A researcher should assess whether a pooled target-input share and the whole-type
segmentation exclusion suit their question. Current ontology versions, anatomical
review, per-neuropil completion, matched individuals where available, and additional
brains would be needed for stronger interpretation. We have neither reproduced
Figure 4's noise model nor visually reviewed candidate arbors. The analysis
has not undergone external scientific review.
