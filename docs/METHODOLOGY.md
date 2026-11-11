# Methodology and interpretation

## Inputs and scope

The reference dataset is FAFB materialization **783**, annotation release **v2.1.0**
(commit `ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0`), and Zenodo connectivity
version **783.0**, DOI [10.5281/zenodo.10676866](https://zenodo.org/records/10676866).
The tracked [manifest](data_manifest.json) records immutable annotation URL,
SHA-256, publisher MD5 where available, byte counts, rows and schemas. It is the
reference identity of this analysis, not an assertion that these are the newest
annotations. The supporting proofread-ID file is a NumPy uint64 array of shape
(139255,); the independent checker compares its complete set with the TSV IDs.
Root IDs are read as integers, never floating point.

`proofread_connections_783.feather` is already aggregated by directed
presynaptic ID, postsynaptic ID and neuropil. Every positive count is retained
before aggregation; there is no per-neuron-edge threshold. CSV/gzip readers
support both Zenodo `pre_pt_root_id/post_pt_root_id` and Codex
`pre_root_id/post_root_id`. They reject ambiguous schemas and malformed records.
Feather v2 uses memory-mapped Arrow record batches, not a full pandas dataframe.

## Annotation and population policy

1. Validate every annotation ID, including rows later excluded. Duplicate IDs
   are errors. Keep the full ID set for join auditing.
2. Choose nonempty `cell_type`, falling back to `hemibrain_type` exactly as the
   authors' [annotation notebook](https://github.com/flyconnectome/flywire_annotations/blob/ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0/code/annotation_counts.ipynb)
   does. `--type-policy cell_type` disables fallback as a sensitivity control.
   Type names containing commas are kept as a single population label; they are
   not expanded into multiple neurons or treated as individual homologues.
3. Retain typed left/right neurons. Other side labels and untyped neurons are
   separately counted. `side` denotes soma side for intrinsic neurons and nerve
   entry side for sensory/ascending neurons. Use the published corrected side
   labels; do not infer laterality from raw x coordinates in the mirrored FAFB
   image stack. A type label is a population correspondence, not a neuron pairing.
4. By default exclude **whole types** with any `status=outlier_seg` member. Removing
   just the affected neuron could manufacture a population imbalance. This
   conservative rule follows the spirit of the paper's stereotypy selection,
   but does not recreate that selection. `--include-seg-types` is the control.
   Keep `outlier_bio`; these are observations, not known reconstruction failures.
5. Population counts include neurons with zero retained connections. Both types
   must have at least `--min-neurons` eligible members on each side (default 1).

The annotation audit partitions rows into untyped, typed nonlateral,
segmentation-type-excluded and eligible, in that order. `fallback_typed` is an
additional diagnostic and must not be added to this partition.

## Directed comparisons and denominators

For source type A and target type B, define two independent relations:

| Relation | Left weight | Right weight |
| --- | --- | --- |
| same | A-left → B-left | A-right → B-right |
| opposite | A-left → B-right | A-right → B-left |

Here “left/right” always indexes the **source** side. It does not locate the
synapse or imply that either neuron's arbor is confined to that hemisphere.
All neuropils are summed, including midline neuropils. We do not use a neuropil
suffix to decide the relation. Anatomically regional analyses require a different
selection and independently appropriate denominators.

For each relation, with weights W_L and W_R:

- Raw: W_L, W_R.
- Per source: W_L / N(A-left), W_R / N(A-right).
- Per target: W_L / N(destination-left-comparison), W_R / N(destination-right-comparison).
- Observed input fraction: W_L / I(destination-left-comparison), W_R / I(destination-right-comparison).

I(B-side) sums **all non-autaptic rows in the supplied connectivity file** onto
eligible B-side neurons, regardless of whether the source is typed, lateral or
segmentation-flagged. Opposite-side comparisons use B-right's budget on the
left and B-left's on the right. Denominators are calculated before output
thresholding. A zero budget gives a missing fraction (empty CSV field), not zero.
These are ratios of pooled synapse counts, not averages of per-neuron fractions;
neurons with larger input counts contribute more to the pooled fraction.

For each measure x, the signed contrast is (x_L − x_R)/(x_L + x_R). An undefined
input fraction produces an undefined contrast. `signed_asymmetry` retains the
original per-source definition; `asymmetry_score` is its absolute value. The
other columns expose sensitivity to the measurement choice. These measures
answer different questions. None is universally the correct normalization.

Rows require W_L + W_R ≥ `--min-synapses` (default 100), a reporting convenience,
not a significance cutoff. Unobserved pairs on both sides are not enumerated.
An observed zero on one side is relative to this export and selection. All
reports sort by absolute source contrast, total weight, source type, target
type and relation. Sorting does not imply biological importance.

## Exclusion accounting and release checks

Every connection row belongs to exactly one audit category, in this priority:
missing endpoint in the full annotation ID set; autapse; ineligible annotation
endpoint; eligible same-side; eligible opposite-side. Synapse-weight partitions
are recorded too. An edge involving two missing IDs counts once. Missing-ID
samples and unique counts are diagnostics, not additional row categories.

Missing roots cause a failed CLI run and an audit JSON without a candidate CSV.
`--allow-missing-roots` explicitly relaxes this; missing-source counts still
contribute to a known eligible target's observed budget. This override cannot
make incompatible releases comparable. Root overlap alone cannot prove release
identity either. `--manifest` verifies the actual bytes and a shared declared
materialization; without it, the audit says `unverified_release`. The manifest
is a curated assertion tied to authoritative sources, not automatic detection
of biological semantics. The `--snapshot` string is only a human label.

## What cannot be inferred

This is one female brain, not a population sample. Synapses and neurons are
not independent biological replicates. No confidence intervals, hypothesis
tests or biological-asymmetry probabilities are estimated. Simple Poisson
or synapse bootstrap errors would omit the dominant reconstruction uncertainties.
Input fractions can reduce some scaling effects but are compositional: changes
in other inputs can change the fraction of an unchanged connection.

The proofread-only export lacks inputs from unproofread partners. Its budgets
are therefore not total anatomical input, and annotation coverage is not a
synaptic completion rate. Segmentation, missing fine dendrites, synapse detection,
region-dependent completion, population composition, and typing errors can all
explain differences. Regional completion-rate modelling from the source paper
is not implemented. No anatomical review in Codex/Neuroglancer was performed.
Do not interpret high scores as proofreading mistakes or new biological findings.

The independent checks reproduce selected published counts, not the complete
Figure 4 population, hemibrain cropping, or its noise model. Published examples
were chosen before inspecting connectivity and should remain regression anchors.
An annotation-only count check and agreement with independent SQL establish
computational correctness within this scope; neither validates causal inference.
